"""One distinct Free-plan transport test for EKP, RZD and Aeroflot.

Directly reads the three public roots with the existing datacenter browser mode.
No login, proxy purchase, CAPTCHA action, Google access or publication.
"""
from __future__ import annotations
import hashlib
import json
import os
import re
import sys
import time
from pathlib import Path
from urllib.parse import urlsplit
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'loyalty'))
from free_access_probe import FreeReader, ProbeError, configured_roots, sanitized_page, now

OUT = Path('plain-browser-policy-output')




def main():
    from public_transport import check_response
    roots = [x for x in configured_roots(Path('loyalty/sources_normalized.json')) if x['id'] in ('ekp','rzd','aeroflot')]
    report = {'run_id': os.getenv('GITHUB_RUN_ID'), 'commit': os.getenv('GITHUB_SHA'), 'started_at': now(),
        'method': 'normal_browser_root', 'publication': False,
        'account_sessions': False, 'maximum_reserved_credits': 30, 'sources': []}
    OUT.mkdir(exist_ok=True)
    reader = FreeReader(os.environ.get('SCRAPINGANT_API_KEY',''), roots, max_credits=30, max_requests=3)
    def save():
        report.update(reserved_credits=reader.reserved, requests=reader.calls, known_cost_headers=reader.known_charged_credits)
        (OUT/'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2))
    save()
    try:
        reader.preflight(); report['free_plan_confirmed'] = True
        for cfg in roots:
            item = {'source_id': cfg['id'], 'root': cfg['url'], 'phase': 'root', 'started_at': now()}
            report['sources'].append(item); save()
            try:
                time.sleep(1); item['phase'] = 'root'
                status, raw, cost = reader.read(cfg['url'], browser=True)
                item['origin_status'] = status; check_response(status, raw)
                clean, meta = sanitized_page(raw, cfg['url']); item.update(meta)
                item['status'] = 'candidate_requires_review'
                item['dom_sha256'] = hashlib.sha256(clean.encode()).hexdigest()
                (OUT/(cfg['id']+'.html')).write_text(clean)
            except Exception as exc:
                value = str(exc)
                item['error'] = value if re.fullmatch('[a-z_0-9]+', value) else type(exc).__name__
            item['finished_at'] = now(); save()
            if reader.halted: break
    except Exception as exc:
        report['error'] = str(exc) if isinstance(exc, ProbeError) else type(exc).__name__
    finally:
        report['finished_at'] = now(); save()
        (OUT/'executed.py').write_bytes(Path(__file__).read_bytes())


if __name__ == '__main__': main()
