"""Read-only discovery for additional DeepSeek capacity. Never prints credentials."""
from __future__ import annotations
import json
import os
from pathlib import Path
import time
import requests

OUT = Path('capacity-check')
SECRET_NAMES = ('OPENROUTER_API_KEY', 'OPENCODE_API_KEY', 'AI_GATEWAY_API_KEY',
                'KILO_API_KEY', 'NVIDIA_API_KEY', 'NEBIUS_API_KEY',
                'SCALEWAY_API_KEY')
SECRETS = [os.environ.get(name, '') for name in SECRET_NAMES if os.environ.get(name)]


def safe(value):
    text = json.dumps(value, ensure_ascii=False, indent=2)
    for secret in SECRETS:
        text = text.replace(secret, '[REDACTED]')
    return text


def request(url, secret_name=None):
    headers = {'Accept': 'application/json', 'Cache-Control': 'no-cache'}
    if secret_name:
        key = os.environ.get(secret_name, '')
        if not key:
            return {'status': 'missing_secret'}
        headers['Authorization'] = 'Bearer ' + key
    started = time.monotonic()
    with requests.Session() as session:
        session.trust_env = False
        try:
            response = session.get(url, headers=headers, timeout=(10, 40), allow_redirects=False)
        except requests.RequestException as exc:
            return {'url': url, 'error_type': type(exc).__name__}
    row = {'url': url, 'http_status': response.status_code, 'seconds': round(time.monotonic()-started, 3)}
    try:
        row['data'] = response.json()
    except ValueError:
        row['non_json_excerpt'] = response.text[:1000]
    return row


def main():
    OUT.mkdir(exist_ok=True)
    report = {'keys_present': {name: bool(os.environ.get(name)) for name in SECRET_NAMES},
              'generation_requests': 0, 'catalogues': {}, 'accounts': {}}
    urls = {
        'openrouter': 'https://openrouter.ai/api/v1/models',
        'opencode': 'https://opencode.ai/inference/openai/v1/models',
        'opencode_legacy': 'https://opencode.ai/zen/v1/models',
        'vercel': 'https://ai-gateway.vercel.sh/v1/models',
        'kilo': 'https://api.kilo.ai/api/gateway/models',
    }
    for name, url in urls.items():
        row = request(url)
        (OUT / (name + '-catalogue.json')).write_text(safe(row))
        data = row.pop('data', {})
        models = data.get('data', data.get('models', [])) if isinstance(data, dict) else data
        if isinstance(models, dict):
            models = list(models.values())
        selected = [m for m in models if isinstance(m, dict) and 'deepseek' in str(m.get('id', '')).lower()] if isinstance(models, list) else []
        row['deepseek_models'] = selected
        row['model_count'] = len(models) if isinstance(models, list) else None
        report['catalogues'][name] = row
    row = request('https://ai-gateway.vercel.sh/v1/credits', 'AI_GATEWAY_API_KEY')
    data = row.pop('data', {})
    row['account'] = {k: data.get(k) for k in ('balance', 'total_used', 'free_credits', 'purchased_credits', 'tier', 'plan') if k in data} if isinstance(data, dict) else {}
    if isinstance(data, dict) and 'error' in data:
        row['error'] = data['error']
    report['accounts']['vercel'] = row
    row = request('https://openrouter.ai/api/v1/key', 'OPENROUTER_API_KEY')
    data = row.pop('data', {})
    data = data.get('data', {}) if isinstance(data, dict) else {}
    row['account'] = {k: data.get(k) for k in ('is_free_tier', 'limit', 'limit_remaining', 'limit_reset', 'usage', 'usage_daily', 'usage_weekly', 'usage_monthly') if k in data}
    report['accounts']['openrouter'] = row
    (OUT / 'discovery.json').write_text(safe(report))
    print('CAPACITY_DISCOVERY_BEGIN')
    print(safe(report))
    print('CAPACITY_DISCOVERY_END')


if __name__ == '__main__':
    main()
