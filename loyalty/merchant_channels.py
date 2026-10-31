"""Provider-specific wire formats and credit policy for the existing extractor.

No search/tools, account mutations, paid fallbacks or source-text transformations.
"""
from __future__ import annotations

from decimal import Decimal, InvalidOperation
import json
import requests

PROVIDERS = {
    'experiential': {'model': 'deepseek-v4.1-flash:free',
        'endpoint': 'https://api.experientiallabs.ai/v1/chat/completions',
        'secret': 'EXPERIENTAL_API_KEY', 'max_tokens': 16384},
    'kilo': {'model': 'nvidia/nemotron-3.5-super-vl:free',
        'endpoint': 'https://ai-gateway.kilo.ai/api/v1/chat/completions',
        'secret': 'KILO_API_KEY', 'max_tokens': 16384, 'reasoning_high': True},
    'openrouter': {'model': 'nvidia/nemotron-3.5-super-vl:free',
        'endpoint': 'https://openrouter.ai/api/v1/chat/completions',
        'secret': 'OPENROUTER_API_KEY', 'max_tokens': 16384, 'reasoning_high': True},
    'vercel': {'model': 'nvidia/nemotron-3.5-super-vl',
        'endpoint': 'https://ai-gateway.vercel.sh/v1/chat/completions',
        'secret': 'AI_GATEWAY_API_KEY', 'max_tokens': 16384},
    'gemini': {'model': 'gemini-3.8-flash',
        'endpoint': 'https://generativelanguage.googleapis.com/v1beta/models/gemini-3.8-flash:generateContent',
        'secret': 'GEMINI_API_KEY', 'max_tokens': 16384},
}
DEFAULT_PROVIDERS = ('orcarouter', 'tokenharbor', 'experiential', 'kilo', 'openrouter', 'vercel', 'gemini')
# Local workload ceilings, NOT promises of provider-granted quota.
DAILY_LIMITS = {'orcarouter': 50, 'tokenharbor': 200, 'experiential': 100,
                'kilo': 200, 'openrouter': 50, 'vercel': 200, 'gemini': 20}
INTERVALS = {'orcarouter': 7, 'tokenharbor': 2, 'experiential': 7,
             'kilo': 20, 'openrouter': 4, 'vercel': 2, 'gemini': 7}
VERCEL_RESERVATION = Decimal('0.25')
VERCEL_MONTHLY_BUDGET = Decimal('4.50')
VERCEL_BALANCE_FLOOR = Decimal('0.50')


def wire_request(payload: dict, provider: str) -> dict:
    if provider != 'gemini':
        return payload
    system, user = payload['messages']
    parts = []
    for part in user['content']:
        if part['type'] == 'text':
            parts.append({'text': part['text']})
        elif part['type'] == 'image_url':
            prefix, encoded = part['image_url']['url'].split(',', 1)
            if prefix != 'data:image/png;base64':
                raise ValueError('native_image_format')
            parts.append({'inlineData': {'mimeType': 'image/png', 'data': encoded}})
        else:
            raise ValueError('unexpected_native_part')
    return {'systemInstruction': {'parts': [{'text': system['content']}]},
            'contents': [{'role': 'user', 'parts': parts}],
            'generationConfig': {'maxOutputTokens': payload['max_tokens'],
                                 'responseMimeType': 'application/json'}}


def response_envelope(data: dict, provider: str) -> dict:
    """Only normalize the transport envelope, never repair/rewrite the answer."""
    if provider != 'gemini':
        return data
    if not isinstance(data, dict):
        raise ValueError('response_shape')
    candidates = data.get('candidates')
    if not isinstance(candidates, list) or len(candidates) != 1:
        raise ValueError('incomplete_or_blocked_generation')
    candidate = candidates[0]
    if candidate.get('finishReason') != 'STOP':
        raise ValueError('incomplete_or_blocked_generation')
    parts = candidate.get('content', {}).get('parts', [])
    if not parts or any(not isinstance(p, dict) or 'functionCall' in p or 'executableCode' in p
                        or 'codeExecutionResult' in p for p in parts):
        raise ValueError('unexpected_tool_call_or_refusal')
    text = ''.join(p.get('text', '') for p in parts if not p.get('thought'))
    raw_usage = data.get('usageMetadata', {})
    usage = {}
    if raw_usage:
        prompt = int(raw_usage.get('promptTokenCount', 0))
        final = int(raw_usage.get('candidatesTokenCount', 0))
        thinking = int(raw_usage.get('thoughtsTokenCount', 0))
        total = int(raw_usage.get('totalTokenCount', prompt + final + thinking))
        if min(prompt, final, thinking, total) < 0:
            raise ValueError('invalid_usage')
        usage = {'prompt_tokens': prompt, 'completion_tokens': final + thinking,
                 'total_tokens': total, 'completion_tokens_details': {'reasoning_tokens': thinking},
                 'native_usage': raw_usage}
    return {'model': data.get('modelVersion'), 'usage': usage,
            'choices': [{'finish_reason': 'stop', 'message': {'role': 'assistant', 'content': text}}]}


def decimal_nonnegative(value) -> Decimal:
    if isinstance(value, bool):
        raise ValueError('invalid_credit_number')
    try:
        number = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        raise ValueError('invalid_credit_number') from None
    if not number.is_finite() or number < 0:
        raise ValueError('invalid_credit_number')
    return number


def vercel_credit_guard(session, key: str, payload: dict) -> dict:
    """Financial admission only. Zero-price routes never depend on catalogue reads.

    Check the current priced model's full context + maximum output against the
    durable reservation. This bounds a single request even for image-heavy input.
    Keep a balance floor and never invoke billing/top-up APIs.
    """
    headers = {'Authorization': 'Bearer ' + key, 'Accept': 'application/json'}
    def read(path):
        response = session.get('https://ai-gateway.vercel.sh/v1/' + path, headers=headers,
                               timeout=(10, 30), allow_redirects=False)
        if response.status_code != 200 or key.encode() in response.content:
            raise ValueError('credit_read_unavailable')
        data = response.json()
        if not isinstance(data, dict):
            raise ValueError('credit_read_shape')
        return data
    try:
        credits = read('credits')
        balance = decimal_nonnegative(credits.get('balance'))
        used = decimal_nonnegative(credits.get('total_used'))
        if not VERCEL_BALANCE_FLOOR + VERCEL_RESERVATION <= balance <= Decimal('5.000001'):
            raise ValueError('insufficient_or_unverified_free_balance')
        models = read('models').get('data', [])
        model = next((row for row in models if isinstance(row, dict) and row.get('id') == payload['model']), None)
        if model is None:
            raise ValueError('credit_price_unavailable')
        context = int(model.get('context_window', 0))
        pricing = model.get('pricing', {})
        input_rate = decimal_nonnegative(pricing.get('input'))
        output_rate = decimal_nonnegative(pricing.get('output'))
        if context <= 0 or context > 10_000_000:
            raise ValueError('credit_context_unavailable')
        upper = context * input_rate + int(payload['max_tokens']) * output_rate
        if upper > VERCEL_RESERVATION:
            raise ValueError('request_exceeds_credit_reservation')
        return {'allowed': True, 'balance_before': str(balance), 'total_used_before': str(used),
                'request_upper_bound_usd': str(upper), 'reservation_usd': str(VERCEL_RESERVATION)}
    except (requests.RequestException, ValueError, KeyError, TypeError, AttributeError, OverflowError):
        return {'allowed': False, 'reason': 'free_credit_budget_unavailable'}


def credit_cost(data: dict) -> Decimal | None:
    try:
        usage = data.get('usage', {})
        value = usage.get('cost', usage.get('cost_usd'))
        return decimal_nonnegative(value) if value is not None else None
    except (ValueError, AttributeError):
        return None


def credit_cost_warning(data: dict) -> str | None:
    cost = credit_cost(data)
    if cost is None:
        return 'invalid_reported_cost'
    if cost > VERCEL_RESERVATION:
        return 'nonzero_reported_cost'
    return None
