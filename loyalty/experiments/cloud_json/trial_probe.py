"""Bounded Cohere/Scaleway comparison on frozen public evidence; never publishes.

Reuse the selected runner's input validation, prompt builder and JSON decoder.
Only provider request/response mapping differs. Qwen runtime stays unchanged.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
from pathlib import Path
import sys
import time

import jsonschema
import requests

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent.parent))
import merchant_extract as common

MODELS = {'cohere': 'command-a-plus-05-2026', 'scaleway': 'mistral-medium-3.5-128b'}
ENDPOINTS = {'cohere': 'https://api.cohere.com/v2/chat',
             'scaleway': 'https://api.scaleway.ai/v1/chat/completions'}
METADATA = {'cohere': 'https://api.cohere.com/v1/models/' + MODELS['cohere'],
            'scaleway': 'https://api.scaleway.ai/v1/models'}
CASES = ('muzcomedy', 'nevsky', 'rzd_museum', 'lavka')
MAX_ATTEMPTS = 2


def cohere_schema(schema: dict) -> dict:
    """Equivalent nonempty-string constraint; retain the original for validation.

Cohere documents minLength as unsupported, but supports unanchored patterns.
[\\s\\S]+ matches every nonempty string, including strings made of newlines.
"""
    result = copy.deepcopy(schema)
    if 'minLength' in result:
        if result['minLength'] != 1 or result.get('type') != 'string' or 'pattern' in result:
            raise ValueError('unsupported_schema_translation')
        result.pop('minLength')
        result['pattern'] = r'[\s\S]+'
    if isinstance(result.get('properties'), dict):
        result['properties'] = {k: cohere_schema(v) for k, v in result['properties'].items()}
    if isinstance(result.get('items'), dict):
        result['items'] = cohere_schema(result['items'])
    return result


def build_payload(provider: str, baseline: dict) -> dict:
    if provider not in MODELS: raise ValueError('unknown_provider')
    result = copy.deepcopy(baseline)
    result['model'] = MODELS[provider]
    result.pop('reasoning')
    if provider == 'cohere':
        result['thinking'] = {'type': 'enabled', 'token_budget': 7168}
        result['response_format'] = {'type': 'json_object', 'schema': cohere_schema(
            baseline['response_format']['json_schema']['schema'])}
    else:
        result['reasoning_effort'] = 'high'
    return result


def select_model(provider: str, data: dict) -> dict:
    if provider == 'cohere':
        if data.get('name') != MODELS[provider] or data.get('is_deprecated') is True or 'chat' not in data.get('endpoints', []):
            raise ValueError('requested_model_unavailable')
        return data
    if provider != 'scaleway': raise ValueError('unknown_provider')
    matches = [m for m in data.get('data', []) if m.get('id') == MODELS[provider]]
    if len(matches) != 1: raise ValueError('requested_model_unavailable')
    return matches[0]


def parse_final(provider: str, data: dict, schema: dict) -> dict:
    if not isinstance(data, dict): raise ValueError('response_shape')
    if provider == 'cohere':
        # Native v2 does not guarantee a model field; metadata and request record identity.
        if data.get('model') not in (None, MODELS[provider]): raise ValueError('returned_model_mismatch')
        if data.get('finish_reason') not in ('COMPLETE', 'complete'): raise ValueError('incomplete_generation')
        message = data.get('message', {})
        parts = message.get('content', [])
        if not isinstance(parts, list) or any(not isinstance(p, dict) or p.get('type') not in ('thinking', 'text') for p in parts):
            raise ValueError('unexpected_content_block')
        content = ''.join(p['text'] for p in parts if p.get('type') == 'text')
    elif provider == 'scaleway':
        if data.get('model') not in (MODELS[provider], 'mistral/mistral-medium-3.5-128b:fp8'):
            raise ValueError('returned_model_mismatch')
        choices = data.get('choices', [])
        if len(choices) != 1 or choices[0].get('finish_reason') != 'stop': raise ValueError('incomplete_generation')
        message = choices[0].get('message', {})
        content = message.get('content')
    else:
        raise ValueError('unknown_provider')
    if message.get('tool_calls') or message.get('refusal'): raise ValueError('tool_call_or_refusal')
    if not isinstance(content, str) or not content.strip(): raise ValueError('empty_final_answer')
    obj = common.strict_json(content)
    jsonschema.validate(obj, schema)
    if obj['has_offer'] != bool(obj['offers']): raise ValueError('offer_state_mismatch')
    return obj


def infer(provider: str, payload: dict, schema: dict, out: Path, key: str, session,
          sleep=time.sleep) -> dict:
    if provider not in MODELS or payload.get('model') != MODELS[provider]:
        raise ValueError('unapproved_model')
    if not key or any(ord(c) < 33 for c in key): raise ValueError('missing_or_invalid_actions_secret')
    body = json.dumps(payload, ensure_ascii=False, allow_nan=False).encode('utf-8')
    if key.encode() in body: raise ValueError('credential_in_input')
    if len(body) > 5_000_000: raise ValueError('request_size_budget_no_truncation')
    out.mkdir(parents=True, exist_ok=True)
    result = {'provider': provider, 'requested_model': MODELS[provider], 'status': 'failed',
              'schema_valid': False, 'publication_allowed': False, 'semantic_review': 'pending',
              'request_body_sha256': hashlib.sha256(body).hexdigest(), 'attempts': []}
    start = time.monotonic()
    for number in range(1, MAX_ATTEMPTS + 1):
        folder = out / f'attempt-{number}'; folder.mkdir()
        row = {'attempt': number, 'request_body_sha256': result['request_body_sha256']}
        result['attempts'].append(row)
        t = time.monotonic()
        try:
            response = session.post(ENDPOINTS[provider], data=body,
                headers={'Authorization': 'Bearer ' + key, 'Content-Type': 'application/json'},
                timeout=(10, 180), allow_redirects=False)
            row.update(seconds=time.monotonic() - t, http_status=response.status_code)
            raw = response.content
            (folder / 'response.json').write_bytes(raw.replace(key.encode(), b'[REDACTED]'))
            if key.encode() in raw: raise ValueError('credential_echo_redacted')
            try: data = common.strict_json(raw)
            except ValueError: data = {}
            if response.status_code == 200:
                result.update(returned_model=data.get('model'), usage=data.get('usage'))
                obj = parse_final(provider, data, schema)
                common.save(out / 'extracted.json', obj)
                result.update(status='completed', schema_valid=True)
                common.save(folder / 'measurement.json', row)
                break
            row['error_body'] = data
            result['error'] = 'http_error'
            if response.status_code in common.TRANSIENT and number < MAX_ATTEMPTS:
                delay = max(15, common.retry_delay(response.headers, data))
                if delay <= 60:
                    row['wait_seconds'] = delay
                    common.save(folder / 'measurement.json', row)
                    sleep(delay)
                    continue
                row['retry_not_admitted'] = True
        except requests.RequestException as exc:
            row.update(seconds=time.monotonic() - t, error_type=type(exc).__name__)
            result['error'] = 'transport_error_not_retried'
        except (ValueError, KeyError, TypeError, AttributeError, jsonschema.ValidationError) as exc:
            # Do not log arbitrary exception text, which may contain input/credential echoes.
            row['error_type'] = type(exc).__name__
            result['error'] = 'final_validation_or_response_error'
        common.save(folder / 'measurement.json', row)
        break
    result.update(seconds=time.monotonic() - start, http_attempts=len(result['attempts']))
    common.save(out / 'summary.json', result)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--provider', choices=tuple(MODELS), required=True)
    parser.add_argument('--manifest', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--execute', action='store_true')
    args = parser.parse_args()
    if args.out.exists(): parser.error('output_exists')
    args.out.mkdir(parents=True)
    key = os.environ.get(args.provider.upper() + '_API_KEY', '') if args.execute else ''
    summary = {'provider': args.provider, 'requested_model': MODELS[args.provider],
        'publication_allowed': False, 'status': 'blocked', 'results': [],
        'http_attempts': 0, 'metadata_gets': 0, 'completed': 0, 'not_attempted': list(CASES),
        'billing_balance_verified': False}
    try:
        documents = {d['id']:d for d in common.load_manifest(args.manifest)}
        if set(documents) != set(CASES): raise ValueError('four_frozen_cases_required')
        schema = common.strict_json((common.HERE / 'merchant_offer.schema.json').read_text())
        system = (common.HERE / 'merchant_prompt.txt').read_text()
        common.save(args.out / 'schema.json', schema)
        (args.out / 'system.txt').write_text(system)
        payloads = {}
        for case in CASES:
            doc = documents[case]
            # This experiment is not a generic unbounded batch interface.
            if len(doc['text']) > 15000 or len(doc['images']) > 3: raise ValueError('frozen_input_budget')
            folder = args.out / case
            baseline = common.prepare_document(doc, folder, schema, system)
            payload = build_payload(args.provider, baseline)
            payloads[case] = payload
            log = common.strict_json((folder / 'request.json').read_text())
            common.save(folder / 'baseline-request.json', log)
            for part in log['payload_without_image_bytes']['messages'][1]['content']:
                if part.get('type') == 'image_url': part['image_url']['url'] = '[see ordered image manifest]'
            log['payload_without_image_bytes'] = build_payload(args.provider, log['payload_without_image_bytes'])
            common.save(folder / 'request.json', log)
        if not args.execute:
            summary['status'] = 'prepared_not_inferred'
        else:
            if not key or any(ord(c) < 33 for c in key): raise ValueError('missing_or_invalid_actions_secret')
            with requests.Session() as session:
                session.trust_env = False
                summary['metadata_gets'] = 1
                pre = session.get(METADATA[args.provider], headers={'Authorization':'Bearer ' + key},
                                  timeout=(10, 30), allow_redirects=False)
                summary['preflight_http_status'] = pre.status_code
                (args.out / 'preflight-response.json').write_bytes(pre.content.replace(key.encode(), b'[REDACTED]'))
                if key.encode() in pre.content: raise ValueError('credential_echo_redacted')
                if pre.status_code != 200: raise ValueError('preflight_http_error')
                common.save(args.out / 'selected-model.json', select_model(args.provider, common.strict_json(pre.content)))
                for case in CASES:
                    result = infer(args.provider, payloads[case], schema, args.out / case / 'direct', key, session)
                    result['id'] = case
                    summary['not_attempted'].remove(case)
                    summary['results'].append(result)
                    summary['http_attempts'] += result['http_attempts']
                    summary['completed'] += result['status'] == 'completed'
                    common.save(args.out / 'summary.json', summary)
                    print(json.dumps({'id':case, 'status':result['status'], 'http_attempts':result['http_attempts']}), flush=True)
                    if result['status'] != 'completed': break
                    if summary['not_attempted']: time.sleep(15)
            summary['status'] = 'completed' if summary['completed'] == 4 else 'incomplete'
    except (ValueError, KeyError, TypeError, OSError, requests.RequestException) as exc:
        summary['error_type'] = type(exc).__name__
        summary['error'] = str(exc) if isinstance(exc, ValueError) else 'input_or_transport_error'
    finally:
        if key:
            for p in args.out.rglob('*'):
                if p.is_file() and key.encode() in p.read_bytes():
                    p.write_bytes(p.read_bytes().replace(key.encode(), b'[REDACTED]'))
                    summary['status'] = 'credential_echo'
        common.save(args.out / 'summary.json', summary)
    return 0 if summary['status'] in ('completed','prepared_not_inferred') else 2


if __name__ == '__main__': raise SystemExit(main())
