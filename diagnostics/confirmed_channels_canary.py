"""Bounded integration canary: one real document per new channel, scratch state only."""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
from pathlib import Path
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'loyalty'))
import merchant_channels as channels
import merchant_extract as extractor
import merchant_queue as queue


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--inputs', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=False)
    raw = args.inputs.read_bytes()
    data = extractor.strict_json(raw)
    docs = data if isinstance(data, list) else data['documents']
    source = next(d for d in docs if d['id'] == 'muzcomedy')
    text = source['text']
    target, _ = json.JSONDecoder().raw_decode(text.split('TARGET: ', 1)[1])
    full_text = text.split('Полный текст:\n', 1)[1]
    document = {'id': 'muzcomedy', 'target': {k: target[k] for k in ('partner', 'program', 'as_of')},
        'text': full_text, 'images': [base64.b64decode(im, validate=True) for im in source['images']],
        'source': {'source_run': 40077128489, 'source_artifact': 12554050020,
                   'inputs_sha256': hashlib.sha256(raw).hexdigest()}}
    schema = extractor.strict_json((extractor.HERE / 'merchant_offer.schema.json').read_text())
    system = (extractor.HERE / 'merchant_prompt.txt').read_text()
    report = {'execution_sha': os.environ.get('GITHUB_SHA'), 'providers': {},
              'production_state_changed': False, 'publication_allowed': False,
              'input_images': len(document['images']), 'input_text_chars': len(full_text)}
    secrets = []
    try:
        for provider in ('experiential', 'kilo', 'openrouter', 'vercel'):
            key = os.environ.get(channels.NEW_PROVIDERS[provider]['secret'], '')
            if not key:
                report['providers'][provider] = {'status': 'missing_secret', 'http_attempts': 0}
                continue
            secrets.append(key)
            state = queue.new_state()
            result = queue.process_documents([document], state, args.out / (provider + '-state.json'),
                args.out / provider, key, schema, system, max_requests=1, time_budget=300, provider=provider)
            item = state['items'].get('muzcomedy', {})
            summary = {k: result.get(k) for k in ('status', 'completed', 'http_attempts', 'stop_reason', 'allowance_check')}
            summary['result'] = {k: item.get('last_result', {}).get(k) for k in
                ('status', 'requested_model', 'returned_model', 'usage', 'error', 'stop_batch_reason')}
            if item.get('extracted'):
                summary['extracted'] = item['extracted']
                quotes = [q for offer in item['extracted'].get('offers', []) for q in offer.get('evidence', [])]
                normalized = ' '.join(full_text.split())
                summary['quotes_found'] = sum(' '.join(q.split()) in normalized for q in quotes)
                summary['quotes_total'] = len(quotes)
            if provider == 'vercel':
                import requests
                with requests.Session() as session:
                    session.trust_env = False
                    value = channels._get(session, 'https://ai-gateway.vercel.sh/v1/models', key)
                    summary['live_model'] = next((m for m in value.get('data', []) if m.get('id') == channels.SUPER_VL), None)
                    # Repeat read after other validation work; retain observed balance,
                    # never infer settled spend from the workflow badge.
                    time.sleep(5)
                    value = channels._get(session, 'https://ai-gateway.vercel.sh/v1/credits', key)
                    summary['credits_after'] = {k: value.get(k) for k in ('balance', 'total_used')}
            report['providers'][provider] = summary
            extractor.save(args.out / 'canary-report.json', report)
        key = os.environ.get('GEMINI_API_KEY', '')
        if key:
            secrets.append(key)
        report['gemini_admission'] = channels.admission('gemini', {}, key, {}, time.time())
        report['all_four_completed'] = all(v.get('completed') == 1 for v in report['providers'].values()) and len(report['providers']) == 4
    finally:
        rendered = json.dumps(report, ensure_ascii=False, indent=2)
        for key in secrets:
            rendered = rendered.replace(key, '[REDACTED]')
        (args.out / 'canary-report.json').write_text(rendered)
        for path in args.out.rglob('*'):
            if path.is_file():
                raw = path.read_bytes()
                for key in secrets:
                    raw = raw.replace(key.encode(), b'[REDACTED]')
                path.write_bytes(raw)
        (args.out / 'SHA256SUMS.json').write_text(json.dumps({str(p.relative_to(args.out)):
            hashlib.sha256(p.read_bytes()).hexdigest() for p in args.out.rglob('*') if p.is_file()}, indent=2))
        print(rendered, flush=True)
    return 0 if report.get('all_four_completed') else 2


if __name__ == '__main__':
    raise SystemExit(main())
