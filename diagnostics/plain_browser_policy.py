"""One distinct Free-plan transport test for EKP, RZD and Aeroflot.

Browser source mode requests unrendered server bytes at two documented credits.
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


class SourceReader(FreeReader):
    def policy_source(self, url):
        if not self.ready or self.halted or url not in self.allowed or not url.endswith('/robots.txt'):
            raise ProbeError('unapproved_policy_source')
        if self.reserved + 2 > 36 or self.calls >= 6:
            raise ProbeError('diagnostic_budget')
        self.reserved += 2; self.calls += 1
        raw, meta = self._request('general', {'url': url, 'browser': 'true', 'return_page_source': 'true',
            'proxy_country': 'RU', 'proxy_type': 'datacenter', 'timeout': '60'})
        cost = str(meta.get('Ant-credits-cost', ''))
        status = str(meta.get('Ant-page-status-code', ''))
        if not cost.isdigit() or int(cost) > 2 or not re.fullmatch('[1-5][0-9]{2}', status):
            self.halted = True; raise ProbeError('unverified_provider_contract')
        self.known_charged_credits += int(cost)
        if status == '429' or meta.get('ant-original-header-retry-after'):
            self.halted = True; raise ProbeError('origin_rate_limit')
        return int(status), raw


def main():
    from public_transport import robots_document, check_response
    from protego import Protego
    roots = [x for x in configured_roots(Path('loyalty/sources_normalized.json')) if x['id'] in ('ekp','rzd','aeroflot')]
    report = {'run_id': os.getenv('GITHUB_RUN_ID'), 'commit': os.getenv('GITHUB_SHA'), 'started_at': now(),
        'method': 'browser_return_page_source_policy_then_normal_browser_root', 'publication': False,
        'account_sessions': False, 'maximum_reserved_credits': 36, 'sources': []}
    OUT.mkdir(exist_ok=True)
    reader = SourceReader(os.environ.get('SCRAPINGANT_API_KEY',''), roots)
    def save():
        report.update(reserved_credits=reader.reserved, requests=reader.calls, known_cost_headers=reader.known_charged_credits)
        (OUT/'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2))
    save()
    try:
        reader.preflight(); report['free_plan_confirmed'] = True
        for cfg in roots:
            item = {'source_id': cfg['id'], 'root': cfg['url'], 'phase': 'policy', 'started_at': now()}
            report['sources'].append(item); save()
            try:
                status, raw = reader.policy_source('https://'+urlsplit(cfg['url']).netloc+'/robots.txt')
                item['policy_status'] = status
                item['policy_response_sha256'] = hashlib.sha256(raw.encode()).hexdigest()
                rules, state = robots_document(status, raw); item['policy_state'] = state
                policy = Protego.parse(rules)
                rate = policy.request_rate('LoyaltyCatalogResearchBot')
                delay = max(1, policy.crawl_delay('LoyaltyCatalogResearchBot') or 0, rate.seconds/rate.requests if rate else 0)
                if delay > 30: raise ProbeError('policy_delay_exceeds_budget')
                if not policy.can_fetch(cfg['url'], 'LoyaltyCatalogResearchBot'): raise ProbeError('robots_disallow')
                (OUT/(cfg['id']+'-rules.txt')).write_text(rules)
                time.sleep(delay); item['phase'] = 'root'
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
