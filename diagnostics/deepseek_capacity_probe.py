"""Isolated free-capacity probe. No queue writes, publication, purchases or paid fallback."""
from __future__ import annotations

import argparse
import base64
import copy
from decimal import Decimal, InvalidOperation
import hashlib
import io
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import sys
import tempfile
import time

import jsonschema
import requests
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'loyalty'))
import merchant_extract as existing

ROUTES = {
    'vercel': ('AI_GATEWAY_API_KEY', 'https://ai-gateway.vercel.sh/v1/chat/completions',
               ('deepseek/deepseek-v4.1-flash', 'deepseek/deepseek-v4.1-flash-1017')),
    'openrouter': ('OPENROUTER_API_KEY', 'https://openrouter.ai/api/v1/chat/completions',
                   ('deepseek/deepseek-v4.1-flash:free',)),
    'opencode': ('OPENCODE_API_KEY', 'https://opencode.ai/inference/openai/v1/chat/completions',
                 ('deepseek-v4.1-flash-free',)),
}
SMOKE_SCHEMA = {'type': 'object', 'additionalProperties': False,
                'properties': {'code': {'type': 'string'}}, 'required': ['code']}


def scrub(text: str, key: str) -> str:
    if not key:
        return text
    for token in (key, json.dumps(key)[1:-1], base64.b64encode(key.encode()).decode()):
        text = text.replace(token, '[REDACTED]')
    return text


def save(path: Path, value, key: str = '') -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(scrub(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False), key), encoding='utf-8')


def validate_content(content: str, schema: dict):
    content = content.strip()
    fence = re.fullmatch(r'```(?:json)?[ \t]*\r?\n(.*?)\r?\n```', content, re.DOTALL | re.IGNORECASE)
    if fence:
        content = fence.group(1)
    value = existing.strict_json(content)
    jsonschema.validate(value, schema)
    if 'has_offer' in value and value['has_offer'] != bool(value['offers']):
        raise ValueError('offer_state_mismatch')
    return value


def validate_response(data: dict, schema: dict):
    if not isinstance(data, dict):
        raise ValueError('response_shape')
    choices = data.get('choices')
    if not isinstance(choices, list) or len(choices) != 1:
        raise ValueError('response_shape')
    choice = choices[0]
    if choice.get('finish_reason') != 'stop':
        raise ValueError('incomplete_generation')
    message = choice.get('message', {})
    if message.get('tool_calls') or message.get('refusal'):
        raise ValueError('unexpected_tools_or_refusal')
    if not isinstance(message.get('content'), str):
        raise ValueError('empty_final')
    return validate_content(message['content'], schema)


def build_payload(doc: dict, model: str) -> dict:
    # Keep the current one-stage evidence contract, with native default reasoning.
    return {'model': model, 'stream': False, 'temperature': 1, 'max_tokens': 16384,
            'messages': [{'role': 'system', 'content': doc['system']},
                         {'role': 'user', 'content': [
                             {'type': 'text', 'text': doc['text']}, *[
                                 {'type': 'image_url', 'image_url': {'url': 'data:image/png;base64,' + image}}
                                 for image in doc['images']]]}]}


def prepare(manifest: Path, out: Path) -> None:
    manifest_data = existing.strict_json(manifest.read_text())
    specs = sorted(manifest_data['documents'], key=lambda item: item['id'])[:3]
    selected_path = manifest.parent / 'capacity-probe-manifest.json'
    save(selected_path, {'documents': specs})
    documents = existing.load_manifest(selected_path)
    schema = existing.strict_json((ROOT / 'loyalty/merchant_offer.schema.json').read_text())
    system = (ROOT / 'loyalty/merchant_prompt.txt').read_text()
    inputs = []
    for document in documents:
        folder = out / 'evidence' / document['id']
        folder.mkdir(parents=True, exist_ok=True)
        (folder / 'text.txt').write_text(document['text'])
        for i, image in enumerate(document['images'], 1):
            (folder / f'page-{i}.png').write_bytes(image)
        inputs.append({'id': document['id'], 'system': system, 'schema': schema,
                       'text': 'TARGET: ' + json.dumps(document['target'], ensure_ascii=False)
                       + '\nSCHEMA: ' + json.dumps(schema, ensure_ascii=False)
                       + '\nВсе изображения идут по порядку страниц. Полный текст:\n' + document['text'],
                       'images': [base64.b64encode(image).decode() for image in document['images']],
                       'source': document['source']})
    image = Image.new('RGB', (340, 110), 'white')
    draw = ImageDraw.Draw(image)
    font = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', 64)
    draw.text((20, 15), '5837', font=font, fill='black')
    buffer = io.BytesIO()
    image.save(buffer, format='PNG')
    raw = buffer.getvalue()
    (out / 'vision.png').write_bytes(raw)
    smoke = {'id': 'vision', 'system': 'Read the supplied image and return only JSON.',
             'text': 'Return the four digits visible in the image. SCHEMA: ' + json.dumps(SMOKE_SCHEMA),
             'images': [base64.b64encode(raw).decode()], 'schema': SMOKE_SCHEMA}
    save(out / 'inputs.json', {'smoke': smoke, 'documents': inputs})
    save(out / 'inputs-summary.json', {'documents': [
        {'id': doc['id'], 'source': doc['source'], 'images': len(doc['images']),
         'text_sha256': hashlib.sha256(doc['text'].encode()).hexdigest(),
         'image_sha256': [hashlib.sha256(base64.b64decode(b)).hexdigest() for b in doc['images']]}
        for doc in inputs], 'publication_allowed': False})


def http(session, method: str, url: str, folder: Path, key: str, payload=None):
    folder.mkdir(parents=True, exist_ok=False)
    body = None if payload is None else json.dumps(payload, ensure_ascii=False).encode()
    row = {'method': method, 'endpoint': url, 'publication_allowed': False}
    if payload is not None:
        assert key not in body.decode()
        brief = copy.deepcopy(payload)
        for part in brief['messages'][1]['content']:
            if part['type'] == 'image_url':
                part['image_url']['url'] = '[ordered PNG supplied as base64]'
        save(folder / 'request.json', brief)
        row.update(requested_model=payload['model'], request_bytes=len(body),
                   request_sha256=hashlib.sha256(body).hexdigest())
    start = time.monotonic()
    try:
        response = session.request(method, url, headers={'Authorization': 'Bearer ' + key,
            'Content-Type': 'application/json'}, data=body, timeout=(15, 180), allow_redirects=False)
        row.update(http_status=response.status_code, seconds=round(time.monotonic() - start, 3),
                   retry_after=response.headers.get('Retry-After'))
        text = response.content.decode(errors='replace')
        (folder / 'response.json').write_text(scrub(text, key))
        if key in text:
            row['error'] = 'credential_echo'
            data = {}
        else:
            try:
                data = existing.strict_json(text)
            except (ValueError, UnicodeError):
                data = {}
        if isinstance(data, dict):
            row.update(returned_model=data.get('model'), usage=data.get('usage'))
            if response.status_code != 200:
                row['api_error'] = data.get('error', data)
    except requests.RequestException as exc:
        data = {}
        row.update(error=type(exc).__name__, seconds=round(time.monotonic() - start, 3),
                   unknown_execution_outcome=True)
    save(folder / 'measurement.json', row, key)
    return row, data


def credit_numbers(data: dict):
    try:
        balance, used = Decimal(str(data['balance'])), Decimal(str(data['total_used']))
        if not balance.is_finite() or not used.is_finite() or min(balance, used) < 0:
            return None
        return balance, used
    except (KeyError, TypeError, InvalidOperation):
        return None


def direct(provider: str, inputs: dict, out: Path):
    secret, endpoint, models = ROUTES[provider]
    key = os.environ.get(secret, '')
    report = {'provider': provider, 'credential_present': bool(key.strip()), 'attempts': [],
              'generation_requests': 0, 'publication_allowed': False, 'ready_for_integration': False}
    out.mkdir(parents=True, exist_ok=True)
    if not key.strip():
        save(out / 'summary.json', report)
        return
    session = requests.Session()
    session.trust_env = False
    try:
        if provider == 'vercel':
            row, data = http(session, 'GET', 'https://ai-gateway.vercel.sh/v1/credits', out / 'credits-before', key)
            before = credit_numbers(data)
            report['credits_before'] = data
            # No paid credit is touched: only bootstrap an unused zero-balance account.
            if row.get('http_status') != 200 or before != (Decimal(0), Decimal(0)):
                report['status'] = 'free_credit_provenance_requires_review'
                return
        elif provider == 'openrouter':
            row, catalog = http(session, 'GET', 'https://openrouter.ai/api/v1/models', out / 'catalog', key)
            report['deepseek_catalog'] = [m for m in catalog.get('data', [])
                                          if 'deepseek-v4.1-flash' in m.get('id', '')]
        for index, model in enumerate(models):
            folder = out / f'route-{index}'
            payload = build_payload(inputs['smoke'], model)
            payload['max_tokens'] = 4096
            row, data = http(session, 'POST', endpoint, folder / 'vision', key, payload)
            report['generation_requests'] += 1
            row['case'] = 'vision'
            try:
                if row.get('http_status') != 200 or row.get('error'):
                    raise ValueError('no_successful_response')
                answer = validate_response(data, SMOKE_SCHEMA)
                row['vision_correct'] = answer == {'code': '5837'}
                row['status'] = 'completed' if row['vision_correct'] else 'vision_mismatch'
                save(folder / 'vision/extracted.json', answer)
            except (ValueError, TypeError, KeyError, jsonschema.ValidationError) as exc:
                row['status'] = 'failed'
                row['validation_error'] = str(exc)[:160]
            report['attempts'].append(row)
            if provider == 'vercel':
                cr, credits = http(session, 'GET', 'https://ai-gateway.vercel.sh/v1/credits', folder / 'credits-after-vision', key)
                report['credits_after'] = credits
                numbers = credit_numbers(credits)
                free_verified = (cr.get('http_status') == 200 and numbers is not None
                                 and Decimal('4.75') <= sum(numbers) <= Decimal('5.01')
                                 and Decimal('4.75') <= numbers[0] <= Decimal(5))
                report['free_activation_verified'] = free_verified
            else:
                free_verified = existing.reported_cost_warning(data) is None
            save(out / 'summary.json', report, key)
            if row.get('http_status') == 429 or row.get('unknown_execution_outcome'):
                break
            if row.get('status') != 'completed':
                continue
            if not free_verified:
                report['status'] = 'generation_worked_but_free_budget_not_verified'
                break
            completed = 0
            for doc in inputs['documents']:
                time.sleep(7)
                result, raw = http(session, 'POST', endpoint, folder / doc['id'], key, build_payload(doc, model))
                report['generation_requests'] += 1
                result['case'] = doc['id']
                try:
                    if result.get('http_status') != 200 or result.get('error'):
                        raise ValueError('no_successful_response')
                    value = validate_response(raw, doc['schema'])
                    save(folder / doc['id'] / 'extracted.json', value)
                    result.update(status='completed', schema_valid=True)
                    completed += 1
                except (ValueError, TypeError, KeyError, jsonschema.ValidationError) as exc:
                    result.update(status='failed', validation_error=str(exc)[:160])
                report['attempts'].append(result)
                save(out / 'summary.json', report, key)
                if result.get('http_status') in (401, 402, 403, 429) or result.get('unknown_execution_outcome'):
                    break
                if provider == 'vercel':
                    cr, credits = http(session, 'GET', 'https://ai-gateway.vercel.sh/v1/credits', folder / doc['id'] / 'credits-after', key)
                    report['credits_after'] = credits
                    numbers = credit_numbers(credits)
                    if cr.get('http_status') != 200 or numbers is None or not (Decimal('4.75') <= numbers[0] <= 5 and sum(numbers) <= Decimal('5.01')):
                        report['status'] = 'free_budget_stop'
                        break
                elif existing.reported_cost_warning(raw):
                    report['status'] = 'reported_cost_stop'
                    break
            report['selected_model'] = model
            report['documents_completed'] = completed
            report['ready_for_integration'] = completed == len(inputs['documents']) and 'status' not in report
            break
    finally:
        session.close()
        save(out / 'summary.json', report, key)
        print(scrub(json.dumps(report, ensure_ascii=False), key), flush=True)


def cli_config(system: str):
    model = 'opencode/deepseek-v4.1-flash-free'
    return {'$schema': 'https://opencode.ai/config.json', 'model': model, 'small_model': model,
            'enabled_providers': ['opencode'], 'share': 'disabled', 'autoupdate': False,
            'permission': {'*': 'deny'}, 'compaction': {'auto': False},
            'provider': {'opencode': {'options': {'apiKey': '{env:OPENCODE_API_KEY}'}}},
            'agent': {'extract': {'description': 'Read supplied evidence only', 'mode': 'primary',
                      'model': model, 'prompt': system, 'steps': 1, 'temperature': 1,
                      'permission': {'*': 'deny'}}, 'title': {'disable': True}, 'summary': {'disable': True}}}


def cli(inputs: dict, out: Path):
    key = os.environ.get('OPENCODE_API_KEY', '')
    report = {'provider': 'opencode_cli', 'credential_present': bool(key.strip()), 'cases': [],
              'publication_allowed': False, 'ready_for_integration': False}
    out.mkdir(parents=True, exist_ok=True)
    if not key.strip():
        save(out / 'summary.json', report)
        return
    binary = os.environ['OPENCODE_BINARY']
    for doc in [inputs['smoke'], *inputs['documents']]:
        folder = out / doc['id']
        folder.mkdir()
        config = cli_config(doc['system'])
        save(folder / 'config.json', config)
        row = {'case': doc['id'], 'status': 'failed'}
        with tempfile.TemporaryDirectory(prefix='deepseek-cli-') as temporary:
            root = Path(temporary)
            home = root / 'home'
            work = root / 'work'
            home.mkdir()
            work.mkdir()
            env = {'PATH': os.environ['PATH'], 'HOME': str(home), 'LANG': 'C.UTF-8', 'CI': 'true',
                   'OPENCODE_API_KEY': key, 'OPENCODE_CONFIG_CONTENT': json.dumps(config),
                   'XDG_CONFIG_HOME': str(home / '.config'), 'XDG_DATA_HOME': str(home / '.local/share'),
                   'XDG_CACHE_HOME': str(home / '.cache'), 'OPENCODE_DISABLE_AUTOUPDATE': 'true',
                   'OPENCODE_DISABLE_PROJECT_CONFIG': 'true', 'OPENCODE_DISABLE_EXTERNAL_SKILLS': 'true'}
            command = [binary, 'run', doc['text'], '--model', config['model'], '--agent', 'extract',
                       '--title', 'Public source capacity test', '--format', 'json']
            for i, image in enumerate(doc['images']):
                path = work / f'page-{i}.png'
                path.write_bytes(base64.b64decode(image, validate=True))
                command.extend(['--file', str(path)])
            started = time.monotonic()
            process = subprocess.Popen(command, cwd=work, env=env, stdout=subprocess.PIPE,
                                       stderr=subprocess.PIPE, start_new_session=True)
            try:
                stdout, stderr = process.communicate(timeout=240)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGTERM)
                try:
                    stdout, stderr = process.communicate(timeout=10)
                except subprocess.TimeoutExpired:
                    os.killpg(process.pid, signal.SIGKILL)
                    stdout, stderr = process.communicate()
                row['error'] = 'cli_timeout'
            output = scrub(stdout.decode(errors='replace'), key)
            (folder / 'events.jsonl').write_text(output)
            (folder / 'stderr.txt').write_text(scrub(stderr.decode(errors='replace'), key))
            row.update(returncode=process.returncode, seconds=round(time.monotonic() - started, 3))
            events = []
            for line in output.splitlines():
                try:
                    events.append(json.loads(line))
                except ValueError:
                    continue
            row['errors'] = [e for e in events if e.get('type') in ('error', 'tool_use')]
            endings = [e for e in events if e.get('type') == 'step_finish']
            try:
                if process.returncode != 0 or row['errors'] or len(endings) != 1 or endings[0].get('part', {}).get('reason') != 'stop':
                    raise ValueError('cli_not_one_completed_step')
                text = ''.join(e.get('part', {}).get('text', '') for e in events if e.get('type') == 'text')
                value = validate_content(text, doc['schema'])
                if doc['id'] == 'vision' and value != {'code': '5837'}:
                    raise ValueError('vision_mismatch')
                save(folder / 'extracted.json', value)
                row.update(status='completed', schema_valid=True)
            except (ValueError, TypeError, KeyError, jsonschema.ValidationError) as exc:
                row['validation_error'] = str(exc)[:160]
        report['cases'].append(row)
        save(out / 'summary.json', report, key)
        if row['status'] != 'completed':
            break
    report['ready_for_integration'] = len(report['cases']) == 4 and all(r['status'] == 'completed' for r in report['cases'])
    save(out / 'summary.json', report, key)
    print(scrub(json.dumps(report, ensure_ascii=False), key), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['prepare', *ROUTES, 'cli'])
    parser.add_argument('--manifest', type=Path)
    parser.add_argument('--inputs', type=Path)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    if args.command == 'prepare':
        args.out.mkdir(parents=True, exist_ok=True)
        prepare(args.manifest, args.out)
    elif args.command == 'cli':
        cli(json.loads(args.inputs.read_text()), args.out)
    else:
        direct(args.command, json.loads(args.inputs.read_text()), args.out)


if __name__ == '__main__':
    main()
