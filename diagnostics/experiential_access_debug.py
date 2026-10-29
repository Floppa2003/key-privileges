"""Bounded Experiential diagnosis: own-account GETs and exact :free probes only.

No paid-model request, account mutation, policy relaxation, purchase or publication.
Credentials remain on the runner; account IDs and identity fields are not exported.
"""
from __future__ import annotations
import base64
import hashlib
import json
import os
from pathlib import Path
import re
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid

BASE = 'https://api.experientiallabs.ai'
MODELS = ('deepseek-v4.1-flash', 'deepseek-v4.1-flash-1017', 'clef-flash')
SAFE_ACCOUNT = re.compile(r'(plan|tier|credit|balance|payment|purchase|verif|free|promo|grant|quota|limit|allow|blocked|quarant|review|country|region|policy|scope|strength|role|status|type|zdr|training|capture|reason|enabled|active)', re.I)
PRIVATE_FIELD = re.compile(r'(email|name|address|phone|secret|password|token|api_key|customer_id|org_id|organization_id|user_id|key_id)', re.I)

class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


def minimal_payload(model: str) -> dict:
    if model not in MODELS:
        raise ValueError('unapproved_diagnostic_model')
    return {'model': model + ':free', 'messages': [{'role': 'user', 'content': 'Reply OK.'}], 'max_tokens': 64}


def classify(status: int | None, data: dict) -> str:
    error = data.get('error', {}) if isinstance(data, dict) else {}
    code = error.get('code') if isinstance(error, dict) else None
    if status == 200 and data.get('choices'):
        return 'generation_received'
    if code == 'model_not_granted':
        return 'free_access_denied'
    if code in ('card_required', 'email_unverified', 'free_tier_requires_payment', 'model_requires_payment', 'model_requires_purchase', 'org_under_review'):
        return str(code)
    if status == 429:
        return 'rate_or_budget_limited'
    return 'no_generation'


def signal_fields(value, path='') -> dict:
    """Export account-state signals, never IDs, credentials or personal identity."""
    result = {}
    if isinstance(value, dict):
        for k, v in value.items():
            field = str(k)
            if PRIVATE_FIELD.search(field) or field.lower() == 'id':
                continue
            child = path + '.' + field if path else field
            if isinstance(v, (dict, list)):
                result.update(signal_fields(v, child))
            elif SAFE_ACCOUNT.search(child):
                result[child] = v
    elif isinstance(value, list):
        for n, v in enumerate(value[:50]):
            if isinstance(v, (dict, list)):
                result.update(signal_fields(v, path + '[' + str(n) + ']'))
            elif SAFE_ACCOUNT.search(path):
                result[path + '[' + str(n) + ']'] = v
    return result


def own_org_id(data: dict) -> str | None:
    if not isinstance(data, dict):
        return None
    for k in ('org_id', 'organization_id'):
        if isinstance(data.get(k), str) and data[k]:
            return data[k]
    for k in ('org', 'organization'):
        obj = data.get(k)
        if isinstance(obj, dict) and isinstance(obj.get('id'), str):
            return obj['id']
    return None


def main() -> int:
    key = os.environ.pop('EXPERIENTAL_API_KEY', '').strip()
    out = Path('access-debug-output'); out.mkdir(exist_ok=True)
    private_values = [key] if key else []
    report = {'credential_present': bool(key), 'generation_attempts': 0, 'production_state_changed': False, 'account_mutations': 0, 'paid_model_requests': 0, 'calls': []}
    opener = urllib.request.build_opener(NoRedirect)
    def scrub(text):
        for value in private_values:
            for encoded in (value, json.dumps(value)[1:-1], base64.b64encode(value.encode()).decode()):
                text = text.replace(encoded, '[REDACTED]')
        text = re.sub(r'\bxpl_[A-Za-z0-9_-]+', '[REDACTED]', text)
        text = re.sub(r'[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}', '[REDACTED_EMAIL]', text)
        return text
    def save():
        text = scrub(json.dumps(report, ensure_ascii=False, indent=2))
        (out/'report.json').write_text(text, encoding='utf-8')
    def request(label, path, *, auth=True, body=None):
        if not path.startswith('/') or path.startswith('//'):
            raise ValueError('invalid_path')
        if body is not None and (path != '/v1/chat/completions' or body.get('model') not in [m+':free' for m in MODELS]):
            raise ValueError('only_exact_free_probes_allowed')
        headers = {'Content-Type': 'application/json', 'Accept': 'application/json'}
        if auth:
            headers['Authorization'] = 'Bearer ' + key
        if body is not None:
            headers['Idempotency-Key'] = 'access-debug-' + str(uuid.uuid4())
            report['generation_attempts'] += 1
        raw = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(BASE+path, data=raw, headers=headers, method='POST' if body is not None else 'GET')
        row = {'label': label, 'method': req.method, 'authenticated': auth}
        if body is not None:
            row['payload'] = body
        start = time.monotonic()
        try:
            try:
                response = opener.open(req, timeout=90)
            except urllib.error.HTTPError as exc:
                response = exc
            with response:
                row['http_status'] = response.status
                row['headers'] = {k:v for k,v in response.headers.items() if k.lower().startswith(('x-gateway-', 'x-ratelimit-')) or k.lower() in ('retry-after','x-request-id')}
                response_raw = response.read(2000000)
                row['response_sha256'] = hashlib.sha256(response_raw).hexdigest()
                try:
                    data = json.loads(response_raw)
                except (ValueError, UnicodeError):
                    data = {}
                    row['non_json_response'] = True
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            row['transport_error'] = type(exc).__name__
            data = {}
        row['seconds'] = round(time.monotonic()-start, 3)
        if isinstance(data, dict):
            row['top_level_fields'] = sorted(data)
            if 'error' in data:
                row['error'] = data['error']
            if 'detail' in data:
                row['detail'] = data['detail']
            if body is not None:
                row['verdict'] = classify(row.get('http_status'), data)
                row['returned_model'] = data.get('model')
                row['usage'] = data.get('usage')
                row['choices'] = data.get('choices')
        report['calls'].append(row)
        return row, data
    if not key:
        report['status'] = 'missing_credential'; save(); return 2
    row, who = request('identity', '/api/whoami')
    org = own_org_id(who)
    if org:
        private_values.append(org)
    report['org_id_resolved'] = bool(org)
    row['account_signals'] = signal_fields(who)
    save()
    if org:
        org_path = urllib.parse.quote(org, safe='')
        for label, path in (
            ('own_policy', '/api/orgs/'+org_path+'/provider-policy'),
            ('usage_before', '/api/gateway/usage/daily?'+urllib.parse.urlencode({'org_id':org})),
        ):
            row, data = request(label, path)
            row['account_signals'] = signal_fields(data)
            save()
    for model in MODELS:
        for auth in (False, True):
            row, data = request('catalog:'+model+(':authenticated' if auth else ':public'), '/api/models/'+model, auth=auth)
            row['model_signals'] = signal_fields(data)
            save()
    # Minimal actual repro: same key and free alias, no PNG/schema/reasoning/options.
    for model in MODELS:
        row, data = request('minimal:'+model, '/v1/chat/completions', body=minimal_payload(model))
        save()
        if row.get('http_status') in (401, 402, 429) or row.get('transport_error'):
            break
        usage = data.get('usage') if isinstance(data, dict) else None
        if isinstance(usage, dict) and usage.get('cost') not in (None, 0, '0', '0.0'):
            report['cost_anomaly'] = True
            break
        time.sleep(7)
    if org:
        row, data = request('usage_after', '/api/gateway/usage/daily?'+urllib.parse.urlencode({'org_id':org}))
        row['account_signals'] = signal_fields(data)
    report['generation_received'] = any(c.get('verdict') == 'generation_received' for c in report['calls'])
    report['status'] = 'diagnostic_complete'
    save()
    print(scrub(json.dumps(report, ensure_ascii=False, indent=2)), flush=True)
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
