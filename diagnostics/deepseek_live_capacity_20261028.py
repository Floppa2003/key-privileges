"""Bounded real requests on explicitly free DeepSeek routes; no publication or retries."""
from __future__ import annotations
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
import copy
import hashlib
import json
import os
from pathlib import Path
import sys
import time
import requests
sys.path.insert(0, str(Path('loyalty').resolve()))
import merchant_extract as m

OUT = Path('capacity-check')
ROUTES = {
    'openrouter': ('https://openrouter.ai/api/v1/chat/completions', 'deepseek/deepseek-v4.1-flash-1017:free', 'OPENROUTER_API_KEY'),
    'vercel': ('https://ai-gateway.vercel.sh/v1/chat/completions', 'deepseek/deepseek-v4.1-flash-1017', 'AI_GATEWAY_API_KEY'),
    'opencode': ('https://opencode.ai/inference/openai/v1/chat/completions', 'deepseek-v4.1-flash-free', 'OPENCODE_API_KEY'),
}
KEYS = [os.environ.get(v[2], '') for v in ROUTES.values() if os.environ.get(v[2])]


def safe_write(path, data):
    text = json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False)
    for key in KEYS:
        text = text.replace(key, '[REDACTED]')
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def credits(session, key):
    r = session.get('https://ai-gateway.vercel.sh/v1/credits', headers={'Authorization': 'Bearer '+key}, timeout=(10, 30), allow_redirects=False)
    r.raise_for_status()
    data = r.json()
    return {k: data[k] for k in ('balance', 'total_used', 'free_credits', 'purchased_credits') if k in data}


def require_free_credit(data):
    if Decimal(data['free_credits']['remaining']) < Decimal('0.4'):
        raise ValueError('insufficient_free_reserve')
    purchased = data['purchased_credits']
    if any(Decimal(purchased[k]) != 0 for k in ('balance', 'total_purchased', 'total_used')):
        raise ValueError('paid_account_not_authorized')


def probe(provider, docs, schema, system):
    endpoint, model, secret = ROUTES[provider]
    key = os.environ.get(secret, '')
    result = {'provider': provider, 'requested_model': model, 'results': [], 'generation_requests': 0, 'publication_allowed': False}
    session = requests.Session(); session.trust_env = False
    try:
        if not key:
            raise ValueError('missing_secret')
        if provider == 'vercel':
            result['credits_before'] = credits(session, key)
            require_free_credit(result['credits_before'])
        for doc in docs:
            folder = OUT / provider / doc['id']
            folder.mkdir(parents=True)
            payload = m.build_request(doc['target'], doc['text'], doc['images'], schema, system)
            payload['model'] = model
            payload['max_tokens'] = 16384
            if provider in ('vercel', 'opencode'):
                payload.pop('reasoning')  # Native reasoning defaults, no tool/agent configuration.
            if provider == 'openrouter':
                payload['provider'] = {'max_price': {'prompt': 0, 'completion': 0}}
            raw = json.dumps(payload, ensure_ascii=False).encode()
            brief = copy.deepcopy(payload)
            for part in brief['messages'][1]['content']:
                if part['type'] == 'image_url':
                    part['image_url']['url'] = '[ordered archived PNG]'
            safe_write(folder/'request.json', {'payload': brief, 'request_sha256': hashlib.sha256(raw).hexdigest(), 'bytes': len(raw), 'source': doc['source']})
            if provider == 'vercel':
                require_free_credit(credits(session, key))
            started = time.monotonic()
            row = {'id': doc['id'], 'target': doc['target'], 'status': 'failed', 'all_images_sent': len(doc['images']), 'full_text_chars': len(doc['text'])}
            result['generation_requests'] += 1
            try:
                response = session.post(endpoint, headers={'Authorization': 'Bearer '+key, 'Content-Type': 'application/json'}, data=raw, timeout=(15, 240), allow_redirects=False)
                row['http_status'] = response.status_code
                try:
                    data = m.strict_json(response.text)
                except ValueError:
                    data = {'non_json_excerpt': response.text[:2000]}
                safe_write(folder/'response.json', data)
                row['returned_model'] = data.get('model')
                row['usage'] = data.get('usage')
                if response.status_code == 200:
                    obj = m.parse_final(data, schema, provider=provider)
                    safe_write(folder/'extracted.json', obj)
                    row.update(status='completed', extracted=obj)
                    if provider != 'vercel' and m.reported_cost_warning(data):
                        row['stop_reason'] = m.reported_cost_warning(data)
                else:
                    row['error'] = data.get('error', data)
            except (requests.RequestException, ValueError, KeyError) as exc:
                row['error_type'] = type(exc).__name__
                if isinstance(exc, ValueError):
                    row['error'] = str(exc)[:300]
            row['seconds'] = round(time.monotonic()-started, 3)
            if provider == 'vercel':
                row['credits_after'] = credits(session, key)
                require_free_credit(row['credits_after'])
            result['results'].append(row)
            safe_write(folder/'summary.json', row)
            safe_write(OUT/(provider+'-live.json'), result)
            if row['status'] != 'completed' or row.get('stop_reason'):
                break
            time.sleep(4)
    except (requests.RequestException, ValueError, KeyError) as exc:
        result['error_type'] = type(exc).__name__
        if isinstance(exc, ValueError): result['error'] = str(exc)[:300]
    finally:
        session.close()
        safe_write(OUT/(provider+'-live.json'), result)
    return result


def main():
    manifests = list(Path('archived').rglob('captures/manifest.json'))
    if len(manifests) != 1:
        raise ValueError('ambiguous_archived_manifest')
    manifest = manifests[0]
    data = m.strict_json(manifest.read_text())
    chosen = []
    for spec in data['documents']:
        text = (manifest.parent/spec['text']).read_text()
        image_bytes = sum((manifest.parent/name).stat().st_size for name in spec['images'])
        if 500 <= len(text) <= 20000 and image_bytes < 2000000 and len(spec['images']) <= 6:
            chosen.append(spec)
        if len(chosen) == 3: break
    if len(chosen) != 3: raise ValueError('insufficient_bounded_inputs')
    selected = manifest.parent/'probe-manifest.json'
    safe_write(selected, {'documents': chosen})
    docs = m.load_manifest(selected)
    schema = m.strict_json(Path('loyalty/merchant_offer.schema.json').read_text())
    system = Path('loyalty/merchant_prompt.txt').read_text()
    safe_write(OUT/'input-sources.json', [{'id': d['id'], 'target': d['target'], 'text': d['text'], 'source': d['source']} for d in docs])
    with ThreadPoolExecutor(max_workers=3) as pool:
        results = list(pool.map(lambda p: probe(p, docs, schema, system), ROUTES))
    safe_write(OUT/'live-summary.json', results)
    print('LIVE_RESULTS_BEGIN')
    print((OUT/'live-summary.json').read_text())
    print('LIVE_RESULTS_END')
    print('INPUT_TEXTS_BEGIN')
    print((OUT/'input-sources.json').read_text())
    print('INPUT_TEXTS_END')


if __name__ == '__main__': main()
