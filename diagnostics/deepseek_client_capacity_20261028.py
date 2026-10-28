"""One Vercel free-tier bootstrap and one official, tool-disabled OpenCode run."""
from __future__ import annotations
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
import hashlib
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import requests
sys.path.insert(0, str(Path('loyalty').resolve()))
import merchant_extract as m
OUT = Path('capacity-check').resolve()
KEYS = [os.environ.get(k, '') for k in ('OPENCODE_API_KEY', 'AI_GATEWAY_API_KEY') if os.environ.get(k)]


def write(path, data):
    raw = json.dumps(data, ensure_ascii=False, indent=2)
    for key in KEYS: raw = raw.replace(key, '[REDACTED]')
    path.parent.mkdir(parents=True, exist_ok=True); path.write_text(raw)


def credit_read(session, key):
    r = session.get('https://ai-gateway.vercel.sh/v1/credits', headers={'Authorization': 'Bearer '+key}, timeout=(10, 30), allow_redirects=False)
    r.raise_for_status(); data = r.json()
    return {k: data[k] for k in ('balance', 'total_used', 'free_credits', 'purchased_credits') if k in data}


def vercel(doc, schema, system):
    row = {'provider': 'vercel', 'generation_requests': 0, 'publication_allowed': False}
    key = os.environ['AI_GATEWAY_API_KEY']
    with requests.Session() as s:
        s.trust_env = False
        try:
            before = credit_read(s, key); row['credits_before'] = before
            # A new zero-balance account receives its free allowance on first use.
            # This is one bounded bootstrap, never an ongoing paid fallback.
            if Decimal(before['balance']) != 0 or Decimal(before['total_used']) != 0:
                raise ValueError('bootstrap_requires_unused_zero_balance_account')
            purchased = before.get('purchased_credits', {})
            if any(Decimal(str(v)) != 0 for k, v in purchased.items() if k in ('balance', 'total_purchased', 'total_used')):
                raise ValueError('purchased_credits_not_authorized')
            payload = m.build_request(doc['target'], doc['text'], doc['images'], schema, system)
            payload.update(model='deepseek/deepseek-v4.1-flash-1017', max_tokens=16384)
            payload.pop('reasoning')
            raw = json.dumps(payload, ensure_ascii=False).encode()
            row.update(requested_model=payload['model'], request_sha256=hashlib.sha256(raw).hexdigest())
            started = time.monotonic(); row['generation_requests'] = 1
            r = s.post('https://ai-gateway.vercel.sh/v1/chat/completions', headers={'Authorization': 'Bearer '+key, 'Content-Type': 'application/json'}, data=raw, timeout=(15, 240), allow_redirects=False)
            row.update(http_status=r.status_code, seconds=round(time.monotonic()-started, 3))
            try: data = m.strict_json(r.text)
            except ValueError: data = {'non_json_excerpt': r.text[:2000]}
            write(OUT/'vercel-bootstrap-response.json', data)
            row['returned_model'] = data.get('model'); row['usage'] = data.get('usage')
            if r.status_code == 200:
                row['extracted'] = m.parse_final(data, schema, provider='vercel')
                row['status'] = 'completed'
            else:
                row.update(status='failed', error=data.get('error', data))
            row['credits_after'] = credit_read(s, key)
        except (requests.RequestException, ValueError, KeyError) as exc:
            row.update(status='failed', error_type=type(exc).__name__)
            if isinstance(exc, ValueError): row['error'] = str(exc)[:300]
    write(OUT/'vercel-bootstrap.json', row)
    return row


def opencode(doc, schema, system):
    row = {'provider': 'opencode-official-cli', 'publication_allowed': False, 'tools_allowed': False}
    with tempfile.TemporaryDirectory(prefix='oc-free-extract-') as tmp:
        root = Path(tmp); home = root/'home'; home.mkdir(); cwd = root/'input'; cwd.mkdir()
        model = 'opencode/deepseek-v4.1-flash-free'
        config = {'$schema': 'https://opencode.ai/config.json', 'model': model, 'small_model': model,
            'share': 'disabled', 'autoupdate': False, 'permission': {'*': 'deny'}, 'tools': {'*': False},
            'provider': {'opencode': {'options': {'apiKey': '{env:OPENCODE_API_KEY}', 'baseURL': 'https://opencode.ai/inference/openai/v1'}}},
            'agent': {'extract': {'description': 'Single response from supplied public documents.', 'mode': 'primary',
                'prompt': system, 'steps': 1, 'permission': {'*': 'deny'}, 'tools': {'*': False}},
                'title': {'disable': True}, 'summary': {'disable': True}, 'compaction': {'disable': True}}}
        write(cwd/'opencode.json', config)
        env = {k: v for k, v in os.environ.items() if not k.endswith(('_API_KEY', '_TOKEN')) and k not in ('GH_TOKEN', 'GITHUB_TOKEN')}
        env.update(HOME=str(home), XDG_CONFIG_HOME=str(home/'config'), XDG_DATA_HOME=str(home/'data'),
            XDG_CACHE_HOME=str(home/'cache'), OPENCODE_API_KEY=os.environ['OPENCODE_API_KEY'],
            OPENCODE_CONFIG_CONTENT=json.dumps(config), OPENCODE_DISABLE_AUTOUPDATE='true',
            OPENCODE_DISABLE_DEFAULT_PLUGINS='true', OPENCODE_DISABLE_CLAUDE_CODE='true')
        binary = os.environ['OC_BINARY']
        row['version'] = subprocess.check_output([binary, '--version'], env=env, text=True, timeout=30).strip()
        args = [binary, 'run', '--model', model, '--agent', 'extract', '--format', 'json', '--title', 'Free DeepSeek extraction verification']
        for i, raw in enumerate(doc['images']):
            path = cwd/f'page-{i+1}.png'; path.write_bytes(raw); args.extend(['--file', str(path)])
        prompt = 'TARGET: '+json.dumps(doc['target'], ensure_ascii=False)+'\nSCHEMA: '+json.dumps(schema, ensure_ascii=False)+'\nПолный текст:\n'+doc['text']
        args.extend(['--', prompt])
        started = time.monotonic()
        process = subprocess.Popen(args, cwd=cwd, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, start_new_session=True)
        try:
            stdout, stderr = process.communicate(timeout=240)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGKILL)
            stdout, stderr = process.communicate(); row['timeout'] = True
        for key in KEYS:
            stdout = stdout.replace(key, '[REDACTED]'); stderr = stderr.replace(key, '[REDACTED]')
        (OUT/'opencode-events.jsonl').write_text(stdout); (OUT/'opencode-stderr.txt').write_text(stderr)
        row.update(exit_code=process.returncode, seconds=round(time.monotonic()-started, 3), stdout=stdout, stderr=stderr[-10000:])
    write(OUT/'opencode-client.json', row)
    return row


def main():
    OUT.mkdir(exist_ok=True)
    manifest = next(Path('archived').rglob('captures/manifest.json'))
    specs = m.strict_json(manifest.read_text())['documents']
    spec = next(s for s in specs if s['id'] == '3e850b3d90a3a65a5b95f8340b48bc8b')
    selected = manifest.parent/'bootstrap-manifest.json'; write(selected, {'documents': [spec]})
    doc = m.load_manifest(selected)[0]
    schema = m.strict_json(Path('loyalty/merchant_offer.schema.json').read_text())
    system = Path('loyalty/merchant_prompt.txt').read_text()
    write(OUT/'source.json', {'source': doc['source'], 'target': doc['target'], 'text': doc['text']})
    for i, raw in enumerate(doc['images']): (OUT/f'page-{i+1}.png').write_bytes(raw)
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(fn, doc, schema, system) for fn in (vercel, opencode)]
        result = [future.result() for future in futures]
    write(OUT/'client-summary.json', result)
    print((OUT/'client-summary.json').read_text())


if __name__ == '__main__': main()
