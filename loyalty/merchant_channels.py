"""Audited serving routes and allowance guards for the existing merchant queue.

No discovery-based model selection, purchases, key rotation or paid fallback.
Request ceilings below are local workload limits, not advertised account grants.
"""
from __future__ import annotations

import copy
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
import hashlib
import json
import os

import requests
import merchant_credit_prices

SUPER_VL = 'nvidia/nemotron-3.5-super-vl'
NEW_PROVIDERS = {
    'experiential': {'model': 'deepseek-v4.1-flash:free',
        'endpoint': 'https://api.experientiallabs.ai/v1/chat/completions', 'secret': 'EXPERIENTAL_API_KEY'},
    'kilo': {'model': SUPER_VL + ':free',
        'endpoint': 'https://ai-gateway.kilo.ai/api/v1/chat/completions', 'secret': 'KILO_API_KEY'},
    'openrouter': {'model': SUPER_VL + ':free',
        'endpoint': 'https://openrouter.ai/api/v1/chat/completions', 'secret': 'OPENROUTER_API_KEY'},
    'vercel': {'model': SUPER_VL,
        'endpoint': 'https://ai-gateway.vercel.sh/v1/chat/completions', 'secret': 'AI_GATEWAY_API_KEY'},
    'gemini': {'model': 'gemini-3.8-flash',
        'endpoint': 'https://generativelanguage.googleapis.com/v1beta/models/gemini-3.8-flash:generateContent',
        'secret': 'GEMINI_API_KEY'},
}
DAILY_LIMITS = {'experiential': 100, 'kilo': 180, 'openrouter': 50, 'vercel': 100, 'gemini': 20}
INTERVALS = {'experiential': 7, 'kilo': 20, 'openrouter': 4, 'vercel': 2, 'gemini': 15}
# OpenRouter remains an explicit diagnostic route, but not an automatic queue route:
# run 41110786925 mixed two neighbouring programs despite valid JSON and matching quotes.
DEFAULT_PROVIDERS = ('orcarouter', 'experiential', 'kilo', 'vercel', 'gemini', 'tokenharbor')
VERCEL_DAILY_USD = Decimal('1')
VERCEL_AUDITED_GRANT = Decimal('5')
EXPERIENTIAL_DAILY_TOKENS = 1_000_000


def decimal(value):
    if isinstance(value, bool):
        raise ValueError('invalid_numeric_allowance')
    try:
        number = Decimal(str(value))
    except (InvalidOperation, TypeError):
        raise ValueError('invalid_numeric_allowance') from None
    if not number.is_finite() or number < 0:
        raise ValueError('invalid_numeric_allowance')
    return number


def adapt_request(payload, provider):
    if provider not in NEW_PROVIDERS:
        return payload
    result = copy.deepcopy(payload)
    result['max_tokens'] = 16384
    if provider in ('experiential', 'vercel', 'gemini'):
        result.pop('reasoning', None)
    if provider != 'gemini':
        return result
    system, user = result['messages']
    parts = []
    for part in user['content']:
        if part['type'] == 'text':
            parts.append({'text': part['text']})
        else:
            prefix = 'data:image/png;base64,'
            url = part['image_url']['url']
            if not url.startswith(prefix):
                raise ValueError('non_inline_image')
            parts.append({'inlineData': {'mimeType': 'image/png', 'data': url[len(prefix):]}})
    return {'systemInstruction': {'parts': [{'text': system['content']}]},
            'contents': [{'role': 'user', 'parts': parts}],
            'generationConfig': {'maxOutputTokens': 16384, 'responseMimeType': 'application/json'}}


def request_model(payload, provider):
    if provider == 'gemini':
        return NEW_PROVIDERS['gemini']['model']
    return payload.get('model')


def redact_images(payload, provider):
    result = copy.deepcopy(payload)
    if provider == 'gemini':
        for part in result['contents'][0]['parts']:
            if 'inlineData' in part:
                part['inlineData']['data'] = '[see ordered image manifest]'
    else:
        for part in result['messages'][1]['content']:
            if part.get('type') == 'image_url':
                part['image_url']['url'] = '[see ordered image manifest]'
    return result


def normalize_response(data, provider):
    if provider != 'gemini' or not isinstance(data, dict):
        return data
    candidates = data.get('candidates')
    if not isinstance(candidates, list) or len(candidates) != 1:
        raise ValueError('response_shape')
    candidate = candidates[0]
    if candidate.get('finishReason') != 'STOP':
        raise ValueError('incomplete_or_blocked_generation')
    parts = candidate.get('content', {}).get('parts', [])
    if not parts or any(set(part) - {'text', 'thought', 'thoughtSignature'} for part in parts):
        raise ValueError('unexpected_tool_call_or_refusal')
    content = ''.join(part.get('text', '') for part in parts if not part.get('thought'))
    native = data.get('usageMetadata', {})
    return {'model': data.get('modelVersion'),
            'choices': [{'finish_reason': 'stop', 'message': {'content': content}}],
            'usage': {'prompt_tokens': native.get('promptTokenCount'),
                      'completion_tokens': (native.get('candidatesTokenCount', 0) + native.get('thoughtsTokenCount', 0)),
                      'total_tokens': native.get('totalTokenCount')},
            'native_usage': native}


def accepted_model(provider, returned):
    if provider == 'experiential':
        return returned in ('deepseek-v4.1-flash', 'deepseek-v4.1-flash:free')
    if provider in ('kilo', 'openrouter', 'vercel'):
        return returned in (SUPER_VL, SUPER_VL + ':free')
    if provider == 'gemini':
        return returned == 'gemini-3.8-flash'
    return False


def cost_warning(data, provider):
    usage = data.get('usage') if isinstance(data, dict) else None
    if provider not in NEW_PROVIDERS or provider == 'gemini':
        return None
    if not isinstance(usage, dict):
        return 'missing_reported_cost'
    if usage.get('is_byok') is True:
        return 'unexpected_byok'
    costs = [usage[k] for k in ('cost', 'cost_usd') if usage.get(k) is not None]
    if not costs:
        return 'missing_reported_cost'
    try:
        values = [decimal(value) for value in costs]
    except ValueError:
        return 'invalid_reported_cost'
    if provider != 'vercel' and any(values):
        return 'nonzero_reported_cost'
    return None


def daily_budget(ledger, timestamp):
    day = datetime.fromtimestamp(timestamp, timezone.utc).date().isoformat()
    if ledger.get('budget', {}).get('date') != day:
        ledger['budget'] = {'date': day, 'tokens': 0, 'usd': '0'}
    return ledger['budget']


def _get(session, url, key):
    response = session.get(url, headers={'Authorization': 'Bearer ' + key, 'Accept': 'application/json'},
                           timeout=(10, 30), allow_redirects=False)
    if response.status_code != 200:
        raise ValueError('allowance_read_failed')
    if key.encode() in response.content:
        raise ValueError('credential_echo_in_allowance')
    value = json.loads(response.content)
    if not isinstance(value, dict):
        raise ValueError('allowance_shape')
    return value


def admission(provider, payload, key, ledger, timestamp, session=None):
    """Read-only checks. Missing billing/credit evidence blocks that provider, not the queue."""
    if provider not in NEW_PROVIDERS:
        return {'allowed': True}
    budget = daily_budget(ledger, timestamp)
    if provider == 'experiential':
        return {'allowed': budget['tokens'] < EXPERIENTIAL_DAILY_TOKENS,
                'reason': 'daily_token_safety_ceiling'}
    if provider == 'kilo':
        return {'allowed': True}
    if provider == 'gemini':
        # Set only after a real billing-status read for THIS key/project. A successful
        # inference, a public free tier, or serviceTier=standard is not that evidence.
        verified_key = os.environ.get('GEMINI_FREE_TIER_KEY_SHA256', '')
        until = os.environ.get('GEMINI_FREE_TIER_VERIFIED_UNTIL', '')
        try:
            expires = datetime.fromisoformat(until.replace('Z', '+00:00')).timestamp()
        except (ValueError, TypeError):
            expires = 0
        allowed = (verified_key == hashlib.sha256(key.encode()).hexdigest()
                   and timestamp < expires <= timestamp + 7 * 86400)
        return {'allowed': allowed, 'reason': 'billing_status_unverified'}
    owned = session is None
    if owned:
        session = requests.Session()
        session.trust_env = False
    try:
        if provider == 'openrouter':
            data = _get(session, 'https://openrouter.ai/api/v1/key', key).get('data', {})
            counters = data.get('free_model_daily_requests', {})
            remaining = counters.get('remaining')
            if type(remaining) is not int or remaining < 0:
                raise ValueError('free_request_counter_unavailable')
            return {'allowed': remaining > 0, 'reason': 'account_daily_quota',
                    'account_remaining': remaining}
        if ledger.get('spend_needs_review'):
            return {'allowed': False, 'reason': 'unreconciled_credit_spend'}
        credits = _get(session, 'https://ai-gateway.vercel.sh/v1/credits', key)
        balance, used = decimal(credits.get('balance')), decimal(credits.get('total_used'))
        # This grants only the independently audited $5. Future grants/purchases
        # are not silently treated as donated credit; an unknown grant is fail-closed.
        if abs(balance + used - VERCEL_AUDITED_GRANT) > Decimal('0.00001'):
            raise ValueError('free_credit_origin_unverified')
        models = _get(session, 'https://ai-gateway.vercel.sh/v1/models', key).get('data', [])
        model = next((row for row in models if row.get('id') == SUPER_VL), None)
        if not model:
            raise ValueError('audited_model_missing')
        endpoint_data = None
        if model.get('pricing', {}).get('varies_by_provider'):
            endpoint_data = _get(session, 'https://ai-gateway.vercel.sh/v1/models/' + SUPER_VL + '/endpoints', key).get('data')
        reserve = merchant_credit_prices.reservation(model, payload.get('max_tokens'), endpoint_data)
        virtual = min(balance, decimal(ledger.get('credit_remaining', str(balance))))
        allowed = reserve <= virtual and decimal(budget['usd']) + reserve <= VERCEL_DAILY_USD
        return {'allowed': allowed, 'reason': 'free_credit_safety_budget', 'reservation_usd': str(reserve),
                'balance': str(balance), 'total_used': str(used), 'virtual_remaining': str(virtual),
                'pricing_endpoints_checked': len(endpoint_data['endpoints']) if endpoint_data else 0}
    except (requests.RequestException, ValueError, KeyError, TypeError, AttributeError, StopIteration) as exc:
        # Never retain raw exception bodies/headers or authentication material.
        return {'allowed': False, 'reason': str(exc) if type(exc) is ValueError else type(exc).__name__}
    finally:
        if owned:
            session.close()


def reserve_budget(ledger, check, timestamp):
    if 'reservation_usd' in check:
        budget = daily_budget(ledger, timestamp)
        reserve = decimal(check['reservation_usd'])
        budget['usd'] = str(decimal(budget['usd']) + reserve)
        ledger['credit_remaining'] = str(decimal(check['virtual_remaining']) - reserve)
        ledger['spend_needs_review'] = True


def reconcile(provider, ledger, check, result, timestamp):
    if provider not in NEW_PROVIDERS:
        return
    budget = daily_budget(ledger, timestamp)
    usage = result.get('usage')
    if provider == 'experiential' and result.get('http_attempts'):
        tokens = usage.get('total_tokens') if isinstance(usage, dict) else None
        # Unknown execution usage reserves the rest of this day's local allowance.
        budget['tokens'] += tokens if type(tokens) is int and tokens >= 0 else EXPERIENTIAL_DAILY_TOKENS
    if provider != 'vercel' or 'reservation_usd' not in check:
        return
    reserve = decimal(check['reservation_usd'])
    try:
        cost = decimal(usage['cost'])
    except (ValueError, KeyError, TypeError):
        # Definitive access/quota/input errors never ran generation; a timeout/5xx
        # remains reserved and requires review, including across UTC day changes.
        statuses = [row.get('http_status') for row in result.get('attempts', [])]
        if statuses and all(s in (400, 401, 402, 403, 404, 413, 422, 429) for s in statuses):
            cost = Decimal(0)
        else:
            result['stop_batch_reason'] = 'unreconciled_credit_spend'
            return
    budget['usd'] = str(max(Decimal(0), decimal(budget['usd']) - reserve + cost))
    ledger['credit_remaining'] = str(max(Decimal(0), decimal(ledger['credit_remaining']) + reserve - cost))
    if cost > reserve:
        result['stop_batch_reason'] = 'credit_cost_bound_exceeded'
    else:
        ledger['spend_needs_review'] = False
