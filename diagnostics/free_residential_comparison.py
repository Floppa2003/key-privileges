"""One-shot, public-only alternate-network test; never upgrades or publishes.

For each of three roots: one plain policy (25 credits), then one rendered root
(125 credits) only under usable rules. No retries, account sessions or CAPTCHA
interaction. Production always keeps the cheaper datacenter path unchanged.
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
from free_access_probe import FreeReader, ProbeError, free_plan, configured_roots, sanitized_page, LOCATION_JS, now

OUT = Path('free-network-comparison-output')


class ComparisonReader(FreeReader):
    def read(self, url, *, browser):
        if not self.ready or self.halted or url not in self.allowed:
            raise ProbeError('unapproved_comparison_request')
        cost = 125 if browser else 25
        if self.calls >= 2 or self.reserved + cost > 150:
            raise ProbeError('comparison_budget')
        self.calls += 1; self.reserved += cost
        params = {'url': url, 'browser': str(browser).lower(), 'proxy_type': 'residential',
                  'proxy_country': 'RU', 'timeout': '60'}
        if browser:
            params['js_snippet'] = LOCATION_JS
            params['block_resource'] = ['image', 'media', 'font']
        raw, meta = self._request('general', params)
        charged = str(meta.get('Ant-credits-cost', ''))
        status = str(meta.get('Ant-page-status-code', ''))
        if not charged.isdigit() or int(charged) > cost or not re.fullmatch('[1-5][0-9]{2}', status):
            self.halted = True; raise ProbeError('comparison_cost_or_status_unverified')
        self.known_charged_credits += int(charged)
        if status == '429' or meta.get('ant-original-header-retry-after'):
            self.halted = True; raise ProbeError('origin_rate_limit')
        return int(status), raw, int(charged)


def selfcheck():
    root = {'url': 'https://example.org/catalog'}
    reader = ComparisonReader('fixture-key', [root], max_credits=150, max_requests=2)
    reader.ready = True
    calls = []
    def request(endpoint, params):
        calls.append(params)
        return '<html></html>', {'Ant-credits-cost': '125' if params['browser']=='true' else '25', 'Ant-page-status-code':'200'}
    reader._request = request
    reader.read('https://example.org/robots.txt', browser=False)
    reader.read(root['url'], browser=True)
    assert reader.reserved == reader.known_charged_credits == 150 and len(calls) == 2
    assert all(p['proxy_type']=='residential' and 'cookies' not in p for p in calls)
    try: reader.read(root['url'], browser=True)
    except ProbeError: pass
    else: raise AssertionError('budget must stop')
    for plan in ('Trial','Enthusiast','Business'):
        try: free_plan({'plan_name':plan,'plan_total_credits':10000,'remained_credits':10000})
        except ProbeError: pass
        else: raise AssertionError('paid/unknown plan must stop')
    print('6 alternate-network budget/plan assertions passed')


def main():
    from public_transport import robots_document, check_response
    from protego import Protego
    roots = [r for r in configured_roots(Path('loyalty/sources_normalized.json')) if r['id'] in ('ekp','rzd','aeroflot')]
    report = {'run_id':os.getenv('GITHUB_RUN_ID'), 'commit':os.getenv('GITHUB_SHA'), 'started_at':now(),
              'source_account_sessions':False, 'publication':False, 'maximum_reserved_credits':450,
              'requested_proxy_type':'residential', 'requested_country':'RU', 'sources':[]}
    OUT.mkdir(exist_ok=True)
    def save():
        (OUT/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
    save()
    for cfg in roots:
        item = {'source_id':cfg['id'], 'root':cfg['url'], 'phase':'free_plan', 'started_at':now()}
        report['sources'].append(item); reader = None
        try:
            reader = ComparisonReader(os.environ.get('SCRAPINGANT_API_KEY',''), [cfg], max_credits=150, max_requests=2)
            reader.preflight(); item['free_plan_confirmed'] = True
            item['phase'] = 'policy'
            policy_url = 'https://'+urlsplit(cfg['url']).netloc+'/robots.txt'
            status, raw, _ = reader.read(policy_url, browser=False)
            item['policy_status'] = status; item['policy_sha256'] = hashlib.sha256(raw.encode()).hexdigest()
            rules, state = robots_document(status,raw); item['policy_state'] = state
            policy = Protego.parse(rules)
            rate = policy.request_rate('LoyaltyCatalogResearchBot')
            delay = max(1,policy.crawl_delay('LoyaltyCatalogResearchBot') or 0,rate.seconds/rate.requests if rate else 0)
            if delay > 30: raise ProbeError('policy_delay_exceeds_budget')
            if not policy.can_fetch(cfg['url'],'LoyaltyCatalogResearchBot'): raise ProbeError('robots_disallow')
            (OUT/(cfg['id']+'-rules.txt')).write_text(rules)
            time.sleep(delay); item['phase'] = 'root'
            status,raw,cost = reader.read(cfg['url'],browser=True)
            item['origin_http_status'] = status; check_response(status,raw)
            clean,meta = sanitized_page(raw,cfg['url']); item.update(meta)
            item['status'] = 'candidate_requires_review'
            item['dom_sha256'] = hashlib.sha256(clean.encode()).hexdigest()
            (OUT/(cfg['id']+'.html')).write_text(clean)
        except Exception as exc:
            value = str(exc); item['error'] = value if re.fullmatch('[a-z_0-9]+',value) else type(exc).__name__
        finally:
            if reader:
                item.update(reserved_credits=reader.reserved, source_requests=reader.calls, known_cost_headers=reader.known_charged_credits)
            item['finished_at'] = now(); save()
        if reader is None or reader.halted or item.get('phase') == 'free_plan': break
    report['finished_at'] = now(); save()
    (OUT/'executed.py').write_bytes(Path(__file__).read_bytes())


if __name__ == '__main__':
    selfcheck()
    if '--selfcheck' not in sys.argv: main()
