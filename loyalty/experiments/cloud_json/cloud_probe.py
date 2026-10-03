"""Bounded cloud control: same frozen evidence/prompt, one call per sample; no publication."""
from __future__ import annotations

import argparse
import base64
import copy
import hashlib
import json
import os
import sys
import time
from decimal import Decimal
from pathlib import Path

import jsonschema
import requests

HERE = Path(__file__).resolve().parent
MODELS = {'gemini': 'gemini-3.8-flash', 'kilo': 'minimax/minimax-m3:free'}
BASELINE_SHA256 = 'f6da311be861ca002ac7802de0224beabb3fa8d2749d53c3514961362f999da2'
BASE_URLS = {'gemini': 'https://generativelanguage.googleapis.com/v1beta',
             'kilo': 'https://api.kilo.ai/api/gateway'}
CASES = ('muzcomedy', 'nevsky', 'rzd_museum', 'lavka')


def build_payload(provider: str, baseline: dict) -> dict:
    system, user = baseline['messages']
    schema = copy.deepcopy(baseline['format'])
    if provider == 'gemini':
        return {'systemInstruction': {'parts': [{'text': system['content']}]},
                'contents': [{'role': 'user', 'parts': [{'text': user['content']}, *[
                    {'inlineData': {'mimeType': 'image/png', 'data': b}} for b in user['images']]]}],
                'generationConfig': {'temperature': 1.0, 'maxOutputTokens': 8192,
                    'thinkingConfig': {'thinkingLevel': 'HIGH', 'includeThoughts': False},
                    'responseMimeType': 'application/json', 'responseJsonSchema': schema}}
    if provider == 'kilo':
        return {'model': MODELS[provider], 'stream': False, 'temperature': 1.0, 'max_tokens': 8192,
                'reasoning': {'enabled': True, 'effort': 'high'},
                'messages': [{'role': 'system', 'content': system['content']},
                    {'role': 'user', 'content': [{'type': 'text', 'text': user['content']}, *[
                        {'type': 'image_url', 'image_url': {'url': 'data:image/png;base64,' + b}}
                        for b in user['images']]]}],
                'response_format': {'type': 'json_schema', 'json_schema': {
                    'name': 'loyalty_offer', 'strict': True, 'schema': schema}}}
    raise ValueError('unknown_provider')


def parse_final(provider: str, data: dict, schema: dict) -> dict:
    """Never repair content, harvest thoughts, or accept a different model/unfinished response."""
    if provider == 'gemini':
        version = data.get('modelVersion', '')
        if version != MODELS[provider] and not version.startswith(MODELS[provider] + '-'):
            raise ValueError('returned_model_mismatch')
        choices = data.get('candidates', [])
        if len(choices) != 1 or choices[0].get('finishReason') != 'STOP':
            raise ValueError('incomplete_or_blocked_generation')
        parts = choices[0].get('content', {}).get('parts', [])
        if any('functionCall' in p for p in parts):
            raise ValueError('unexpected_tool_call')
        content = ''.join(p.get('text', '') for p in parts if not p.get('thought'))
    elif provider == 'kilo':
        if data.get('model') not in (MODELS[provider], 'minimax/minimax-m3', 'MiniMax-M3'):
            raise ValueError('returned_model_mismatch')
        choices = data.get('choices', [])
        if len(choices) != 1 or choices[0].get('finish_reason') != 'stop':
            raise ValueError('incomplete_or_blocked_generation')
        message = choices[0].get('message', {})
        if message.get('tool_calls') or message.get('refusal'):
            raise ValueError('unexpected_tool_call_or_refusal')
        content = message.get('content')
    else:
        raise ValueError('unknown_provider')
    if not isinstance(content, str) or not content.strip():
        raise ValueError('empty_final_answer')
    try:
        obj = json.loads(content)
        jsonschema.validate(obj, schema)
    except (json.JSONDecodeError, jsonschema.ValidationError) as exc:
        raise ValueError('invalid_final_json') from exc
    if obj['has_offer'] != bool(obj['offers']):
        raise ValueError('offer_state_mismatch')
    return obj


def select_model(provider: str, data: dict) -> dict:
    if provider == 'gemini':
        if data.get('name') != 'models/' + MODELS[provider] or 'generateContent' not in data.get('supportedGenerationMethods', []):
            raise ValueError('requested_gemini_model_unavailable')
        return data
    if provider != 'kilo':
        raise ValueError('unknown_provider')
    matches = [m for m in data.get('data', []) if m.get('id') == MODELS[provider]]
    if len(matches) != 1:
        raise ValueError('requested_free_model_unavailable')
    m = matches[0]
    if m.get('isFree') is not True:
        raise ValueError('free_route_not_confirmed')
    pricing = m.get('pricing', {})
    if not {'prompt', 'completion'} <= pricing.keys() or any(Decimal(str(v)) != 0 for v in pricing.values()):
        raise ValueError('nonzero_or_missing_price')
    if not {'image', 'text'} <= set(m.get('architecture', {}).get('input_modalities', [])):
        raise ValueError('multimodal_input_not_confirmed')
    if not {'response_format', 'reasoning'} <= set(m.get('supported_parameters', [])):
        raise ValueError('requested_parameters_not_confirmed')
    return m


def scrub_bytes(raw: bytes, secrets: list[str]) -> bytes:
    for secret in secrets:
        if secret:
            raw = raw.replace(secret.encode(), b'[REDACTED]')
    return raw


def request_log(provider: str, payload: dict) -> dict:
    """Keep all text/schema, replace image bytes only in the log copy with ordered SHA256s."""
    result = copy.deepcopy(payload)
    images = []
    parts = result['contents'][0]['parts'] if provider == 'gemini' else result['messages'][1]['content']
    for part in parts:
        if provider == 'gemini' and 'inlineData' in part:
            encoded = part['inlineData']['data']
            part['inlineData']['data'] = '[see ordered image manifest]'
        elif provider == 'kilo' and part.get('type') == 'image_url':
            encoded = part['image_url']['url'].split(',', 1)[1]
            part['image_url']['url'] = '[see ordered image manifest]'
        else:
            continue
        raw = base64.b64decode(encoded, validate=True)
        images.append({'file': f'page-{len(images)+1}.png', 'bytes': len(raw),
                       'sha256': hashlib.sha256(raw).hexdigest()})
    return {'payload_without_image_bytes': result, 'images': images}


def save(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')


def prepare(source: Path, out: Path) -> dict:
    """Reuse the audited frozen-input loader and baseline prompt builder, without running Ollama."""
    old_dir = HERE.parent / 'direct_think_json'
    if hashlib.sha256((old_dir / 'direct_sampling.py').read_bytes()).hexdigest() != BASELINE_SHA256:
        raise ValueError('baseline_code_changed')
    sys.path.insert(0, str(old_dir))
    import direct_sampling as baseline
    plan = json.loads((HERE.parent / 'simple_thinking' / 'plan.json').read_text())
    legacy = json.loads((HERE.parent / 'prompt_ab' / 'practical_schema.json').read_text())
    schema = copy.deepcopy(legacy)
    offer = schema['properties']['offers']['items']
    field = offer['properties'].pop('redemption')
    field['description'] = 'Что пользователь должен или может сделать, чтобы получить эту выгоду. Не на что потом потратить баллы.'
    offer['properties']['how_to_get'] = field
    offer['required'] = ['how_to_get' if k == 'redemption' else k for k in offer['required']]
    jsonschema.Draft202012Validator.check_schema(schema)
    prepared = {}
    for spec in plan['cases']:
        case = spec['id']
        frozen = baseline.frozen_io.load_request(source, spec)
        target = json.loads(frozen['messages'][-1]['content'].split('\n', 1)[0])
        text = baseline.frozen_io.checked_bytes(source, spec['text'], spec['sha256'][spec['text']]).decode('utf-8')
        request = baseline.build_request(frozen, target, text, schema)
        folder = out / case
        folder.mkdir()
        save(folder / 'frozen-input.json', spec)
        (folder / 'visible-text.txt').write_text(text, encoding='utf-8')
        for i, image in enumerate(request['messages'][1]['images'], 1):
            (folder / f'page-{i}.png').write_bytes(base64.b64decode(image, validate=True))
        brief = copy.deepcopy(request)
        brief['messages'][1].pop('images')
        save(folder / 'baseline-request.json', brief)
        prepared[case] = request
    if set(prepared) != set(CASES):
        raise ValueError('case_set_mismatch')
    save(out / 'schema.json', schema)
    save(out / 'legacy-schema.json', legacy)
    return prepared


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--provider', choices=tuple(MODELS), required=True)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    if args.out.exists():
        parser.error('output_exists')
    args.out.mkdir(parents=True)
    rows = []
    summary = {'provider': args.provider, 'requested_model': MODELS[args.provider],
               'publication_allowed': False, 'semantic_review': 'pending',
               'planned_samples': 12, 'inference_http_attempts': 0, 'attempts': rows}
    key = os.environ.get(args.provider.upper() + '_API_KEY', '')
    # No headers, credential values, or credential-derived hashes are ever persisted.
    session = requests.Session()
    session.trust_env = False
    headers = {'x-goog-api-key': key} if args.provider == 'gemini' else {'Authorization': 'Bearer ' + key}
    headers['Content-Type'] = 'application/json'
    try:
        if not key.strip():
            raise ValueError('missing_actions_secret')
        prepared = prepare(args.source, args.out)
        base = BASE_URLS[args.provider]
        model_url = base + ('/models/' + MODELS['gemini'] if args.provider == 'gemini' else '/models')
        pre = session.get(model_url, headers=headers if args.provider == 'gemini' else {},
                          timeout=(10, 30), allow_redirects=False)
        (args.out / 'preflight-response.json').write_bytes(scrub_bytes(pre.content, [key]))
        summary['preflight_http_status'] = pre.status_code
        if pre.status_code != 200:
            raise ValueError('preflight_http_error')
        save(args.out / 'selected-model.json', select_model(args.provider, pre.json()))
        url = base + ('/models/' + MODELS['gemini'] + ':generateContent' if args.provider == 'gemini' else '/chat/completions')
        stop = False
        for repeat in range(1, 4):
            for case in CASES:
                folder = args.out / case / f'sample-{repeat}'
                folder.mkdir()
                row = {'case': case, 'repeat': repeat, 'status': 'failed', 'schema_valid': False,
                       'publication_allowed': False, 'semantic_review': 'pending'}
                request = prepared[case]
                payload = build_payload(args.provider, request)
                body = json.dumps(payload, ensure_ascii=False).encode('utf-8')
                save(folder / 'request.json', request_log(args.provider, payload))
                row['request_body_sha256'] = hashlib.sha256(body).hexdigest()
                start = time.monotonic()
                summary['inference_http_attempts'] += 1
                try:
                    # Intentionally no transport retry, model fallback, continuation or JSON repair.
                    response = session.post(url, headers=headers, data=body, timeout=(10, 180), allow_redirects=False)
                    row['seconds'] = time.monotonic() - start
                    row['http_status'] = response.status_code
                    raw = scrub_bytes(response.content, [key])
                    (folder / 'response.json').write_bytes(raw)
                    if response.status_code != 200:
                        stop = True
                        raise ValueError('inference_http_error')
                    data = json.loads(raw)
                    row['returned_model'] = data.get('modelVersion', data.get('model'))
                    row['usage'] = data.get('usageMetadata', data.get('usage'))
                    row['finish_reasons'] = [c.get('finishReason', c.get('finish_reason'))
                                            for c in data.get('candidates', data.get('choices', []))]
                    obj = parse_final(args.provider, data, request['format'])
                    save(folder / 'extracted.json', obj)
                    row.update(status='completed', schema_valid=True)
                except (requests.RequestException, ValueError, KeyError, TypeError) as exc:
                    row['seconds'] = time.monotonic() - start
                    row['error_type'] = type(exc).__name__
                    row['error'] = scrub_bytes(str(exc).encode(), [key]).decode()[:400]
                    if isinstance(exc, requests.RequestException) or str(exc) == 'returned_model_mismatch':
                        stop = True
                save(folder / 'measurement.json', row)
                rows.append(row)
                save(args.out / 'summary.json', summary)
                print(json.dumps(row, ensure_ascii=False), flush=True)
                if stop:
                    break
                if len(rows) < 12:
                    time.sleep(15)
            if stop:
                break
    except Exception as exc:
        summary['blocked'] = scrub_bytes(str(exc).encode(), [key]).decode()[:400]
        summary['error_type'] = type(exc).__name__
    finally:
        session.close()
        summary['not_attempted'] = 12 - summary['inference_http_attempts']
        summary['completed'] = sum(r['status'] == 'completed' for r in rows)
        summary['status'] = 'completed' if summary['completed'] == 12 else 'failed_or_blocked'
        save(args.out / 'summary.json', summary)
        # A final defensive check covers all emitted files, including provider error echoes.
        if key and any(key.encode() in p.read_bytes() for p in args.out.rglob('*') if p.is_file()):
            for p in args.out.rglob('*'):
                if p.is_file(): p.write_bytes(scrub_bytes(p.read_bytes(), [key]))
            raise RuntimeError('credential_echo_redacted')
    print(json.dumps({'status': summary['status'], 'completed': summary['completed'],
                      'attempted': summary['inference_http_attempts'], 'not_attempted': summary['not_attempted']}, ensure_ascii=False))
    return 0 if summary['status'] == 'completed' else 2


if __name__ == '__main__':
    raise SystemExit(main())
