"""One Vercel follow-up. Preserve prior failures; do not re-run successful or quarantined routes."""
import base64
from decimal import Decimal
import hashlib
import json
import os
from pathlib import Path
import sys
import time

import requests
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'loyalty'))
import merchant_channels as channels
import merchant_extract as extractor
import merchant_queue as queue

root = Path('vercel-acceptance')
root.mkdir(exist_ok=False)
key = os.environ['AI_GATEWAY_API_KEY']
report = {'execution_sha': os.environ['GITHUB_SHA'], 'production_state_changed': False,
          'publication_allowed': False, 'generation_requests': 0}
try:
    raw = Path('inputs.json').read_bytes()
    data = extractor.strict_json(raw)
    docs = data if isinstance(data, list) else data['documents']
    source = next(row for row in docs if row['id'] == 'muzcomedy')
    target, _ = json.JSONDecoder().raw_decode(source['text'].split('TARGET: ', 1)[1])
    doc = {'id': 'muzcomedy', 'target': {k: target[k] for k in ('partner', 'program', 'as_of')},
           'text': source['text'].split('Полный текст:\n', 1)[1],
           'images': [base64.b64decode(value, validate=True) for value in source['images']],
           'source': {'run_id': 40077128489, 'artifact_id': 12554050020,
                      'inputs_sha256': hashlib.sha256(raw).hexdigest()}}
    schema = extractor.strict_json((extractor.HERE / 'merchant_offer.schema.json').read_text())
    prompt = (extractor.HERE / 'merchant_prompt.txt').read_text()
    state = queue.new_state()
    with requests.Session() as session:
        session.trust_env = False
        payload = extractor.build_request(doc['target'], doc['text'], doc['images'], schema, prompt, provider='vercel')
        report['preflight'] = channels.admission('vercel', payload, key, {}, time.time(), session)
        assert report['preflight']['allowed'], report['preflight']
        report['credits_before'] = channels._get(session, 'https://ai-gateway.vercel.sh/v1/credits', key)
        result = queue.process_documents([doc], state, root / 'state.json', root / 'queue', key, schema, prompt,
            provider='vercel', max_requests=1, time_budget=300, session=session)
        report['generation_requests'] = result['http_attempts']
        report['queue_summary'] = result
        report['item'] = state['items']['muzcomedy']
        report['credits_reads'] = []
        before = Decimal(report['credits_before']['total_used'])
        actual = Decimal(str(report['item']['last_result'].get('usage', {}).get('cost', 'NaN')))
        for attempt in range(5):
            current = channels._get(session, 'https://ai-gateway.vercel.sh/v1/credits', key)
            report['credits_reads'].append(current)
            if actual.is_finite() and abs(Decimal(current['total_used']) - before - actual) <= Decimal('0.00000001'):
                report['credits_reconciled'] = True
                break
            if attempt < 4:
                time.sleep(5)
    assert result['completed'] == 1 and result['http_attempts'] == 1, 'queue_integration_failed'
    assert not result.get('stop_reason'), result.get('stop_reason')
    assert report.get('credits_reconciled'), 'settled_credit_delta_not_confirmed'
    assert report['item']['publication_allowed'] is False
    report['status'] = 'completed'
finally:
    text = json.dumps(report, ensure_ascii=False, indent=2).replace(key, '[REDACTED]')
    (root / 'report.json').write_text(text)
    for path in root.rglob('*'):
        if path.is_file():
            path.write_bytes(path.read_bytes().replace(key.encode(), b'[REDACTED]'))
    manifest = {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
                for p in root.rglob('*') if p.is_file()}
    (root / 'SHA256SUMS.json').write_text(json.dumps(manifest, indent=2))
    print(text, flush=True)
