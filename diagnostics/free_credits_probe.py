"""Bounded live checks after account activation; never publishes or purchases."""
from __future__ import annotations

import argparse
import base64
from decimal import Decimal
import hashlib
import io
import json
import os
from pathlib import Path
import time

from PIL import Image, ImageDraw, ImageFont
import jsonschema
import requests
import deepseek_capacity_probe as common

ROUTES = {
    'vercel': ('https://ai-gateway.vercel.sh/v1/chat/completions',
               ['deepseek/deepseek-v4.1-flash-1017', 'deepseek/deepseek-v4.1-flash']),
    'experiential': ('https://api.experientiallabs.ai/v1/chat/completions',
                    ['deepseek-v4.1-flash:free']),
    'openrouter': ('https://openrouter.ai/api/v1/chat/completions',
                   ['nvidia/nemotron-3.5-super-vl:free', 'google/gemma-4-31b-it:free']),
    'gemini': ('https://generativelanguage.googleapis.com/v1beta/openai/chat/completions',
               ['gemini-3.8-flash']),
}
CREDITS = 'https://ai-gateway.vercel.sh/v1/credits'
INPUT_HASH = '890f6e09b759b8d8367fe00f39b0023124eb32ff96fa7e3a1172d5b9f7670d72'


def free_credit_budget(data: dict, *, initial: bool = False) -> bool:
    values = common.credit_numbers(data)
    if values is None:
        return False
    balance, spent = values
    if initial and values == (Decimal(0), Decimal(0)):
        return True  # Activation itself requires the first small request.
    return (Decimal('4.75') <= balance <= Decimal(5)
            and Decimal('4.99') <= balance + spent <= Decimal('5.01'))


def payload(doc: dict, provider: str, model: str) -> dict:
    result = common.build_payload(doc, model)
    result['max_tokens'] = 4096 if doc['id'] == 'vision' else 16384
    if provider == 'openrouter':
        result['reasoning'] = {'enabled': True}
    elif provider in ('gemini', 'experiential'):
        result['reasoning_effort'] = 'high'
    return result


def prepare(source: Path, out: Path) -> None:
    raw = source.read_bytes()
    if hashlib.sha256(raw).hexdigest() != INPUT_HASH:
        raise ValueError('frozen_input_hash_mismatch')
    documents = common.existing.strict_json(raw.decode())
    if len(documents) != 4 or sum(len(d['images']) for d in documents) != 13:
        raise ValueError('frozen_input_shape')
    out.mkdir(parents=True, exist_ok=True)
    im = Image.new('RGB', (340, 110), 'white')
    ImageDraw.Draw(im).text((20, 15), '5837', fill='black',
        font=ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', 64))
    buffer = io.BytesIO(); im.save(buffer, format='PNG')
    smoke = {'id': 'vision', 'system': 'Read the supplied image and return only JSON.',
             'text': 'Return the four digits visible in the image. SCHEMA: ' + json.dumps(common.SMOKE_SCHEMA),
             'images': [base64.b64encode(buffer.getvalue()).decode()], 'schema': common.SMOKE_SCHEMA}
    common.save(out/'inputs.json', {'smoke': smoke, 'documents': documents})
    (out/'vision.png').write_bytes(buffer.getvalue())
    summary = []
    for doc in documents:
        folder = out/'evidence'/doc['id']; folder.mkdir(parents=True)
        (folder/'input-text.txt').write_text(doc['text'])
        image_hashes = []
        for n, encoded in enumerate(doc['images'], 1):
            image = base64.b64decode(encoded, validate=True)
            (folder/f'page-{n}.png').write_bytes(image)
            image_hashes.append(hashlib.sha256(image).hexdigest())
        summary.append({'id': doc['id'], 'images': image_hashes,
                        'text_sha256': hashlib.sha256(doc['text'].encode()).hexdigest()})
    common.save(out/'input-provenance.json', {'source_run': 40077128489,
        'artifact_id': 12554050020, 'inputs_sha256': INPUT_HASH, 'recaptured': False,
        'documents': summary, 'publication_allowed': False})


class ObservedSession(requests.Session):
    def __init__(self):
        super().__init__()
        self.trust_env = False
        self.observed_headers = {}

    def request(self, *args, **kwargs):
        self.observed_headers = {}
        response = super().request(*args, **kwargs)
        self.observed_headers = {k: v for k, v in response.headers.items()
            if k.lower().startswith(('x-gateway-', 'x-experiential-', 'x-ratelimit-'))
            or k.lower() in ('retry-after', 'x-request-id')}
        return response


def call(session, method, endpoint, folder, key, body=None):
    row, data = common.http(session, method, endpoint, folder, key, body)
    row['response_headers'] = session.observed_headers
    common.save(folder/'measurement.json', row, key)
    return row, data


def unexpected_cost(data: dict, headers: dict) -> str | None:
    warning = common.existing.reported_cost_warning(data)
    if warning:
        return warning
    usage = data.get('usage') if isinstance(data.get('usage'), dict) else {}
    values = [obj[name] for obj in (data, usage) for name in ('cost_nano_usd', 'billed_cost_nano_usd')
              if name in obj and obj[name] is not None]
    values += [v for k, v in headers.items() if k.lower() in ('x-gateway-cost-nano-usd', 'x-gateway-cost-usd')]
    for value in values:
        try:
            cost = Decimal(str(value))
            if not cost.is_finite() or cost != 0:
                return 'unexpected_reported_cost'
        except Exception:
            return 'invalid_reported_cost'
    return None


def probe(provider: str, inputs: dict, out: Path) -> dict:
    key = os.environ.get('LLM_PROBE_KEY', '').strip()
    report = {'provider': provider, 'credential_present': bool(key), 'models': [],
              'http_generation_attempts': 0, 'completed_documents': 0,
              'publication_allowed': False, 'production_state_changed': False,
              'semantic_review': 'pending'}
    out.mkdir(parents=True, exist_ok=True)
    def persist():
        common.save(out/'summary.json', report, key)
    if not key:
        report['status'] = 'missing_credential'; persist(); return report
    endpoint, models = ROUTES[provider]
    session = ObservedSession()
    try:
        if provider == 'vercel':
            row, credits = call(session, 'GET', CREDITS, out/'credits-before', key)
            report['credits_before'] = credits
            if row.get('http_status') != 200 or not free_credit_budget(credits, initial=True):
                report['status'] = 'free_credit_provenance_requires_review'; return report
        if provider == 'experiential':
            # Optional accounting evidence, never a capability/availability gate.
            row, usage = call(session, 'GET', 'https://api.experientiallabs.ai/api/gateway/usage/daily',
                              out/'usage-before', key)
            report['accounting_before_http'] = row.get('http_status')
        for index, model in enumerate(models):
            route = {'requested_model': model, 'cases': [], 'completed_documents': 0}
            report['models'].append(route)
            folder = out/f'model-{index}'
            for doc in [inputs['smoke'], *inputs['documents']]:
                if route['cases']:
                    time.sleep(7)
                row, data = call(session, 'POST', endpoint, folder/doc['id'], key,
                                 payload(doc, provider, model))
                report['http_generation_attempts'] += 1
                row['case'] = doc['id']
                try:
                    if row.get('http_status') != 200 or row.get('error'):
                        raise ValueError('no_successful_response')
                    value = common.validate_response(data, doc['schema'])
                    common.save(folder/doc['id']/'extracted.json', value)
                    row.update(status='completed', schema_valid=True)
                    if doc['id'] == 'vision':
                        row['vision_correct'] = value == {'code': '5837'}
                        if not row['vision_correct']:
                            row['status'] = 'vision_mismatch'
                    else:
                        route['completed_documents'] += 1
                        report['completed_documents'] += 1
                except (ValueError, TypeError, KeyError, jsonschema.ValidationError) as exc:
                    row.update(status='failed', validation_error=str(exc)[:160])
                route['cases'].append(row)
                common.save(folder/doc['id']/'measurement.json', row, key)
                persist()
                if provider == 'vercel':
                    cr, credits = call(session, 'GET', CREDITS, folder/doc['id']/'credits-after', key)
                    report['credits_after'] = credits
                    if cr.get('http_status') != 200:
                        report['status'] = 'credit_read_failed'; return report
                    if row.get('http_status') == 200 and not free_credit_budget(credits):
                        report['status'] = 'free_credit_budget_stop'; return report
                    if row.get('http_status') != 200 and not free_credit_budget(credits, initial=True):
                        report['status'] = 'free_credit_budget_stop'; return report
                else:
                    cost_warning = unexpected_cost(data, row.get('response_headers', {}))
                    if cost_warning:
                        report['status'] = cost_warning; return report
                if row.get('unknown_execution_outcome'):
                    break  # No retries of a possibly executed request.
                if row.get('http_status') in (401, 402):
                    report['status'] = 'account_access_error'; return report
                if row.get('http_status') == 429:
                    # All models share the provider allowance. Do not rotate around it.
                    report['status'] = 'rate_limited'; return report
                error = data.get('error', {}) if isinstance(data, dict) else {}
                if isinstance(error, dict) and error.get('type') == 'customer_verification_required':
                    report['status'] = 'account_verification_required'; return report
                if doc['id'] == 'vision' and row['status'] != 'completed':
                    break
                if row.get('http_status') == 403:
                    break
            route['complete_json_for_all_documents'] = route['completed_documents'] == len(inputs['documents'])
            persist()
            if provider == 'vercel' and route['complete_json_for_all_documents']:
                break  # One working DeepSeek route is enough; do not burn credits on its alias.
        report['status'] = 'tested'
    finally:
        if provider == 'experiential':
            row, usage = call(session, 'GET', 'https://api.experientiallabs.ai/api/gateway/usage/daily',
                              out/'usage-after', key)
            report['accounting_after_http'] = row.get('http_status')
        session.close()
        persist()
        print(common.scrub(json.dumps(report, ensure_ascii=False), key), flush=True)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['prepare', *ROUTES])
    parser.add_argument('--inputs', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    if args.command == 'prepare':
        prepare(args.inputs, args.out)
    else:
        probe(args.command, common.existing.strict_json(args.inputs.read_text()), args.out)


if __name__ == '__main__':
    main()
