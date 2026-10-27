"""Selected merchant extractor: full prepared pages -> free DeepSeek JSON, review only.

No publisher, paid/model fallback, output repair or partner-specific extraction rules.
The source collector stays separate. See MERCHANT_DEEPSEEK.md for the manifest.
"""
from __future__ import annotations

import argparse
import base64
import copy
from datetime import datetime
from decimal import Decimal, InvalidOperation
from email.utils import parsedate_to_datetime
import hashlib
import json
import math
import os
from pathlib import Path
import random
import re
import time

import jsonschema
import requests

HERE = Path(__file__).resolve().parent
MODEL = 'deepseek/deepseek-v4.1-flash-free'
BASE_URL = 'https://api.orcarouter.ai/v1'
ENDPOINT = BASE_URL + '/chat/completions'
# Explicit free routes for the same selected model; never accept arbitrary paid IDs.
PROVIDERS = {
    'orcarouter': {'model': MODEL, 'endpoint': ENDPOINT, 'secret': 'ORCAROUTER_API_KEY'},
    'tokenharbor': {'model': 'deepseek-v4.1-flash:free',
                    'endpoint': 'https://tokenharbor.ai/v1/chat/completions',
                    'secret': 'TOKENHARBOR_API_KEY'},
}


def provider_config(provider: str) -> dict:
    try:
        return PROVIDERS[provider]
    except KeyError:
        raise ValueError('unknown_free_provider') from None

TRANSIENT = {408, 429, 500, 502, 503, 504}
MAX_ATTEMPTS = 3
RETRY_BUDGET_SECONDS = 300


def save(path: Path, obj) -> None:
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2, allow_nan=False), encoding='utf-8')


def strict_json(text):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError('duplicate_json_key')
            result[key] = value
        return result
    def nonfinite(value):
        raise ValueError('nonfinite_json_number')
    def finite_float(value):
        result = float(value)
        if not math.isfinite(result): raise ValueError('nonfinite_json_number')
        return result
    return json.loads(text, object_pairs_hook=pairs, parse_constant=nonfinite, parse_float=finite_float)


def build_request(target: dict, text: str, images: list[bytes], schema: dict, system: str, *, provider='orcarouter') -> dict:
    """Same tested provider payload: one fixed model, complete evidence and visible schema."""
    user = ('TARGET: ' + json.dumps(target, ensure_ascii=False)
            + '\nSCHEMA: ' + json.dumps(schema, ensure_ascii=False)
            + '\nВсе изображения идут по порядку страниц. Полный текст:\n' + text)
    result = {
        'model': provider_config(provider)['model'], 'stream': False, 'temperature': 1.0, 'max_tokens': 8192,
        'reasoning': {'enabled': True, 'effort': 'high'},
        'messages': [{'role': 'system', 'content': system},
            {'role': 'user', 'content': [{'type': 'text', 'text': user}, *[
                {'type': 'image_url', 'image_url': {
                    'url': 'data:image/png;base64,' + base64.b64encode(b).decode('ascii')}}
                for b in images]]}]}
    if provider == 'tokenharbor':
        # Exactly the previously successful Harbor payload: native default thinking,
        # not OrcaRouter's provider-specific reasoning extension.
        result.pop('reasoning')
        result['max_tokens'] = 16384
    return result



def reported_cost_warning(data: dict) -> str | None:
    """A billing anomaly stops further spending, not preservation of a valid answer."""
    usage = data.get('usage') if isinstance(data, dict) else None
    if not isinstance(usage, dict):
        return None
    for field in ('cost', 'cost_usd'):
        if usage.get(field) is None:
            continue
        try:
            cost = Decimal(str(usage[field]))
        except InvalidOperation:
            return 'invalid_reported_cost'
        if not cost.is_finite():
            return 'invalid_reported_cost'
        if cost != 0:
            return 'nonzero_reported_cost'
    return None


def parse_final(data: dict, schema: dict, *, provider='orcarouter') -> dict:
    if not isinstance(data, dict): raise ValueError('response_shape')
    returned = data.get('model')
    if not isinstance(returned, str):
        raise ValueError('returned_model_missing')
    # Providers may report the native family and a dated snapshot, not the route ID.
    normalized = re.sub(r'[-_.]', '', returned.rsplit('/', 1)[-1].lower().removesuffix(':free'))
    # Accept only the observed OrcaRouter snapshot, not arbitrary economy variants.
    # The request stays on the free route; the actual returned model is preserved.
    orca_snapshot = (provider == 'orcarouter'
                     and returned == 'deepseek-v4-1-flash-economy-261017')
    if not orca_snapshot and not re.fullmatch(r'deepseekv41flash(?:free|[0-9]{4,8})?', normalized):
        raise ValueError('returned_model_mismatch')
    choices = data.get('choices')
    if not isinstance(choices, list) or len(choices) != 1 or not isinstance(choices[0], dict) or choices[0].get('finish_reason') != 'stop':
        raise ValueError('incomplete_or_blocked_generation')
    message = choices[0].get('message')
    if not isinstance(message, dict): raise ValueError('response_shape')
    if message.get('tool_calls') or message.get('refusal'):
        raise ValueError('unexpected_tool_call_or_refusal')
    content = message.get('content')
    if not isinstance(content, str) or not content.strip(): raise ValueError('empty_final_answer')
    content = content.strip()
    envelope = re.fullmatch(r'```(?:json)?[ \t]*\r?\n(.*?)\r?\n```', content,
                            flags=re.DOTALL | re.IGNORECASE)
    if envelope:
        content = envelope.group(1)
    try:
        obj = strict_json(content)
        jsonschema.validate(obj, schema)
    except (ValueError, jsonschema.ValidationError) as exc:
        raise ValueError('invalid_final_json') from exc
    if obj['has_offer'] != bool(obj['offers']): raise ValueError('offer_state_mismatch')
    return obj


def retry_delay(headers: dict, data: dict, *, now: float | None = None) -> float:
    """Server delays are lower bounds, never shortened to squeeze into our budget."""
    values = []
    hint = headers.get('Retry-After')
    if hint is not None:
        try:
            values.append(float(hint))
        except (ValueError, TypeError):
            try:
                values.append(parsedate_to_datetime(hint).timestamp() - (time.time() if now is None else now))
            except (ValueError, TypeError, OverflowError):
                pass
    if isinstance(data, dict) and isinstance(data.get('error'), dict):
        metadata = data['error'].get('metadata', {})
        if isinstance(metadata, dict):
            try: values.append(float(metadata.get('retry_after_seconds')))
            except (ValueError, TypeError): pass
        details = data['error'].get('details', [])
        for detail in details if isinstance(details, list) else []:
            if isinstance(detail, dict) and detail.get('@type') == 'type.googleapis.com/google.rpc.RetryInfo':
                try:
                    value = detail['retryDelay']
                    if isinstance(value, str) and value.endswith('s'):
                        values.append(float(value[:-1]))
                except (KeyError, ValueError):
                    pass
    return max((v for v in values if math.isfinite(v) and v >= 0), default=0)


def infer(payload: dict, schema: dict, out: Path, key: str, *, session=None,
          sleep=time.sleep, monotonic=time.monotonic, jitter=None, max_attempts=MAX_ATTEMPTS, provider='orcarouter') -> dict:
    """At most 3 HTTP attempts on explicit transient responses; no model-answer retries.

Network timeouts have an unknown execution outcome and are not retried here.
The retry budget bounds admission of new attempts/waits; socket timeouts bound IO.
"""
    if not 1 <= max_attempts <= MAX_ATTEMPTS:
        raise ValueError('invalid_attempt_budget')
    if not key.strip() or any(ord(c) < 33 for c in key):
        raise ValueError('missing_or_invalid_actions_secret')
    route = provider_config(provider)
    if payload.get('model') != route['model']: raise ValueError('unapproved_request_model')
    allowed = {'model', 'stream', 'temperature', 'max_tokens', 'reasoning', 'messages'}
    if set(payload) - allowed:
        raise ValueError('unexpected_request_options')
    body = json.dumps(payload, ensure_ascii=False, allow_nan=False).encode('utf-8')
    if key.encode() in body:
        raise ValueError('credential_in_input')
    if len(body) > 20_000_000:
        raise ValueError('request_size_budget_no_truncation')
    out.mkdir(parents=True, exist_ok=False)
    owned = session is None
    if owned:
        session = requests.Session()
        session.trust_env = False
    jitter = jitter or (lambda: random.uniform(0, 3))
    started = monotonic()
    result = {'provider': provider, 'requested_model': route['model'], 'endpoint': route['endpoint'],
              'request_body_sha256': hashlib.sha256(body).hexdigest(), 'status': 'failed',
              'schema_valid': False, 'publication_allowed': False, 'semantic_review': 'pending',
              'attempts': []}
    try:
        for number in range(1, max_attempts + 1):
            remaining = RETRY_BUDGET_SECONDS - (monotonic() - started)
            if remaining <= 10:
                result.update(status='deferred', error='retry_budget_exhausted')
                break
            folder = out / f'attempt-{number}'; folder.mkdir()
            row = {'attempt': number, 'request_body_sha256': result['request_body_sha256']}
            call_start = monotonic()
            try:
                response = session.post(route['endpoint'], headers={'Content-Type': 'application/json', 'Authorization': 'Bearer ' + key},
                    data=body, timeout=(min(10, remaining / 2), min(180 if provider == 'tokenharbor' else 90, remaining / 2)), allow_redirects=False)
            except requests.RequestException as exc:
                row.update(seconds=monotonic() - call_start, error_type=type(exc).__name__)
                result.update(status='transport_error', error='unknown_execution_outcome_not_retried')
                result['attempts'].append(row); save(folder / 'measurement.json', row)
                break
            row.update(seconds=monotonic() - call_start, http_status=response.status_code)
            raw = response.content
            secret_echo = key.encode() in raw
            (folder / 'response.json').write_bytes(raw.replace(key.encode(), b'[REDACTED]'))
            result['attempts'].append(row)
            if secret_echo:
                result.update(status='credential_echo', error='credential_echo_redacted_not_accepted')
                save(folder / 'measurement.json', row)
                break
            try:
                data = strict_json(raw)
            except (ValueError, UnicodeError):
                data = {}
            if response.status_code == 200:
                if isinstance(data, dict):
                    row.update(returned_model=data.get('model'), usage=data.get('usage'))
                try:
                    obj = parse_final(data, schema, provider=provider)
                    save(out / 'extracted.json', obj)
                    result.pop('error', None)
                    result.update(status='completed', schema_valid=True, returned_model=data['model'],
                                  usage=data.get('usage'))
                except (ValueError, KeyError, TypeError, AttributeError) as exc:
                    result.update(status='failed_validation', error=str(exc) if isinstance(exc, ValueError) else type(exc).__name__)
                warning = reported_cost_warning(data)
                if warning:
                    result['stop_batch_reason'] = warning
                    result['warnings'] = [warning]
                save(folder / 'measurement.json', row)
                break
            error = data.get('error', {}) if isinstance(data, dict) else {}
            error = error if isinstance(error, dict) else {}
            code = error.get('code')
            if isinstance(code, (str, int)):
                result['api_error_code'] = str(code)[:160]
            metadata = error.get('metadata', {})
            metadata = metadata if isinstance(metadata, dict) else {}
            nonretryable = error.get('retryable') is False or metadata.get('retryable') is False
            if nonretryable and metadata.get('reason') != 'err_free_prompt_cap':
                result['stop_batch_reason'] = 'provider_nonretryable_error'
            if response.status_code in (401, 402, 403):
                result['stop_batch_reason'] = 'provider_access_error'
            if response.status_code not in TRANSIENT or nonretryable:
                result.update(status='failed', error='nonretryable_http_status')
                save(folder / 'measurement.json', row)
                break
            result.update(status='deferred', error='transient_http_exhausted')
            server_delay = retry_delay(response.headers, data)
            row['retry_after_seconds'] = server_delay
            result['retry_after_seconds'] = server_delay
            delay = max(15 * 2 ** (number - 1) + jitter(), server_delay)
            remaining = RETRY_BUDGET_SECONDS - (monotonic() - started)
            if number == max_attempts or delay > 60 or delay + 10 >= remaining:
                row['retry_not_admitted'] = True
                if response.status_code == 429:
                    result['stop_batch_reason'] = 'provider_rate_limited'
                save(folder / 'measurement.json', row)
                break
            row['wait_seconds'] = delay
            save(folder / 'measurement.json', row)
            save(out / 'summary.json', result)
            sleep(delay)
    finally:
        if owned: session.close()
        result['seconds'] = monotonic() - started
        result['http_attempts'] = len(result['attempts'])
        save(out / 'summary.json', result)
    return result





def load_manifest(path: Path, *, max_documents: int = 30) -> list[dict]:
    """Validate the entire batch before any network call; all source files need hashes."""
    from PIL import Image
    import io
    root = path.resolve().parent
    manifest = strict_json(path.read_text(encoding='utf-8'))
    specs = manifest.get('documents')
    if not isinstance(specs, list) or not 1 <= len(specs) <= max_documents:
        raise ValueError('document_count_budget')
    documents = []; seen = set()
    for spec in specs:
        case = spec.get('id', '')
        if not isinstance(case, str) or not re.fullmatch(r'[a-z0-9_-]{1,60}', case) or case in seen:
            raise ValueError('invalid_or_duplicate_document_id')
        seen.add(case)
        target = spec.get('target', {})
        if not isinstance(target, dict) or set(target) != {'partner', 'program', 'as_of'}:
            raise ValueError('target_schema')
        if any(not isinstance(v, str) or not v.strip() or len(v) > 300 for v in target.values()):
            raise ValueError('invalid_target')
        try: datetime.strptime(target['as_of'], '%Y-%m-%d')
        except ValueError: raise ValueError('invalid_as_of') from None
        names = spec.get('images', [])
        if not isinstance(names, list) or not 1 <= len(names) <= 40 or len(set(names)) != len(names):
            raise ValueError('image_count_budget_no_truncation')
        text_name = spec.get('text')
        hashes = spec.get('sha256', {})
        def read(name):
            if not isinstance(name, str) or Path(name).is_absolute() or '..' in Path(name).parts:
                raise ValueError('source_path_escape')
            p = (root / name).resolve()
            if not p.is_relative_to(root) or not p.is_file():
                raise ValueError('source_missing_or_outside_root')
            if p.stat().st_size > 15_000_000:
                raise ValueError('source_file_size_budget')
            raw = p.read_bytes()
            if hashes.get(name) != hashlib.sha256(raw).hexdigest():
                raise ValueError('source_hash_mismatch')
            return raw
        text = read(text_name).decode('utf-8')
        if not text.strip() or len(text) > 500000:
            raise ValueError('source_text_budget_no_truncation')
        images = []; total_bytes = len(text.encode('utf-8'))
        for name in names:
            raw = read(name); total_bytes += len(raw)
            if total_bytes > 14_000_000: raise ValueError('source_size_budget_no_truncation')
            images.append(raw)
        for raw in images:
            with Image.open(io.BytesIO(raw)) as im:
                if im.format != 'PNG': raise ValueError('source_not_png')
                im.verify()
        documents.append({'id': case, 'target': copy.deepcopy(target), 'text': text,
                          'images': images, 'source': copy.deepcopy(spec)})
    return documents


def prepare_document(document: dict, out: Path, schema: dict, system: str, *, provider='orcarouter') -> dict:
    out.mkdir()
    (out / 'visible-text.txt').write_text(document['text'], encoding='utf-8')
    image_manifest = []
    for n, raw in enumerate(document['images'], 1):
        name = f'page-{n}.png'; (out / name).write_bytes(raw)
        image_manifest.append({'file': name, 'sha256': hashlib.sha256(raw).hexdigest(), 'bytes': len(raw)})
    payload = build_request(document['target'], document['text'], document['images'], schema, system, provider=provider)
    brief = copy.deepcopy(payload)
    for part in brief['messages'][1]['content']:
        if part.get('type') == 'image_url':
            part['image_url']['url'] = '[see ordered image manifest]'
    save(out / 'request.json', {'payload_without_image_bytes': brief, 'images': image_manifest})
    save(out / 'input.json', {'source': document['source'], 'images': image_manifest,
                            'all_images_sent': True, 'full_text_sent': True, 'publication_allowed': False})
    return payload


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--execute', action='store_true', help='Otherwise prepare without any network request.')
    args = parser.parse_args(argv)
    if args.out.exists(): parser.error('output_exists_use_new_path')
    args.out.mkdir(parents=True)
    summary = {'requested_model': MODEL, 'provider': 'orcarouter', 'publication_allowed': False,
               'status': 'blocked', 'completed': 0, 'http_attempts': 0, 'results': [], 'not_attempted': []}
    key = os.environ.get('ORCAROUTER_API_KEY', '') if args.execute else ''
    session = None
    try:
        documents = load_manifest(args.manifest)
        summary['not_attempted'] = [d['id'] for d in documents]
        schema = strict_json((HERE / 'merchant_offer.schema.json').read_text(encoding='utf-8'))
        system = (HERE / 'merchant_prompt.txt').read_text(encoding='utf-8')
        jsonschema.Draft202012Validator.check_schema(schema)
        save(args.out / 'schema.json', schema)
        if args.execute:
            if not key.strip() or any(ord(c) < 33 for c in key): raise ValueError('missing_or_invalid_actions_secret')
            session = requests.Session(); session.trust_env = False
            # Call the chosen free route directly. Catalog metadata is not an extraction gate.
        for document in documents:
            folder = args.out / document['id']
            payload = prepare_document(document, folder, schema, system)
            if not args.execute:
                result = {'status': 'prepared_not_inferred', 'http_attempts': 0}
            else:
                result = infer(payload, schema, folder / 'direct', key, session=session)
                summary['not_attempted'].remove(document['id'])
            result['id'] = document['id']
            summary['results'].append(result)
            summary['http_attempts'] += result['http_attempts']
            summary['completed'] += result['status'] == 'completed'
            save(args.out / 'summary.json', summary)
            print(json.dumps({'id': document['id'], 'status': result['status'],
                              'http_attempts': result['http_attempts']}, ensure_ascii=False), flush=True)
            if args.execute and (result.get('stop_batch_reason') or result['status'] == 'credential_echo'):
                summary['stop_reason'] = result.get('stop_batch_reason', 'credential_echo')
                break
            if args.execute and summary['not_attempted']: time.sleep(15)
        summary['status'] = ('prepared_not_inferred' if not args.execute else
                             'completed' if summary['completed'] == len(documents) and not summary.get('stop_reason') else 'incomplete')
    except (ValueError, KeyError, TypeError, OSError, jsonschema.SchemaError) as exc:
        summary.update(status='blocked', error_type=type(exc).__name__)
        if isinstance(exc, ValueError): summary['error'] = str(exc)[:160]
    finally:
        if session is not None: session.close()
        # Secrets never enter prompts/URLs; redact a defensive match in all saved outputs.
        if key:
            for p in args.out.rglob('*'):
                if p.is_file() and key.encode() in p.read_bytes():
                    p.write_bytes(p.read_bytes().replace(key.encode(), b'[REDACTED]'))
                    summary['status'] = 'credential_echo'
        save(args.out / 'summary.json', summary)
    return 0 if summary['status'] in ('completed', 'prepared_not_inferred') else 2


if __name__ == '__main__': raise SystemExit(main())