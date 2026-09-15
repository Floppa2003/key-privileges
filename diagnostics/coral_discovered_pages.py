"""One bounded anonymous discovery pass; no publication or saved-answer fallback."""
from __future__ import annotations
import hashlib
import json
import os
import re
import sys
import time
from pathlib import Path
from urllib.parse import urlsplit
from bs4 import BeautifulSoup
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'loyalty'))
from free_access_probe import FreeReader, ProbeError, configured_roots, read_policy, sanitized_page, now

OUT = Path('coral-discovery-output')


def candidates(raw, prefix, depth, selector='a[href]'):
    result = {}
    for a in BeautifulSoup(raw, 'html.parser').select(selector):
        u = urlsplit(a.get('href', ''))
        if (u.scheme == 'https' and u.netloc == 'coralbonus.ru' and not u.query and not u.fragment
            and u.path.startswith(prefix) and len(u.path.strip('/').split('/')) == depth
            and re.fullmatch(r'/[a-z0-9_/-]+/', u.path)):
            result.setdefault(a['href'], a.get_text(' ', strip=True))
    return list(result)


def selfcheck():
    html = '<a href="https://coralbonus.ru/klub-privilegii/new/">New</a>'
    assert candidates(html, '/klub-privilegii/', 2) == ['https://coralbonus.ru/klub-privilegii/new/']
    assert not candidates(html.replace('coralbonus.ru', 'foreign.example'), '/klub-privilegii/', 2)
    assert not candidates(html.replace('/new/', '/new/?token=x'), '/klub-privilegii/', 2)
    assert not candidates(html.replace('/new/', '/new/child/'), '/klub-privilegii/', 2)
    assert len(candidates(html + html, '/klub-privilegii/', 2)) == 1
    print('5 discovery assertions passed')


def main():
    from public_transport import robots_document, check_response
    from protego import Protego
    OUT.mkdir(exist_ok=True)
    report = {'run_id': os.getenv('GITHUB_RUN_ID'), 'commit': os.getenv('GITHUB_SHA'),
              'started_at': now(), 'publication': False, 'account_sessions': False, 'pages': []}
    def save():
        (OUT / 'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2))
    reader = None
    try:
        reader = FreeReader(os.environ.get('SCRAPINGANT_API_KEY', ''), configured_roots(Path('loyalty/sources_normalized.json')))
        reader.preflight(); report['free_plan_confirmed'] = True
        info = {}; status, raw, _ = read_policy(reader, 'https://coralbonus.ru/robots.txt', info)
        rules, state = robots_document(status, raw); policy = Protego.parse(rules)
        rate = policy.request_rate('LoyaltyCatalogResearchBot')
        interval = max(1, policy.crawl_delay('LoyaltyCatalogResearchBot') or 0, rate.seconds / rate.requests if rate else 0)
        if interval > 30: raise ProbeError('crawl_delay_exceeds_budget')
        report['policy'] = {**info, 'state': state, 'origin_status': status}
        def read(url, label, browser=True):
            if not policy.can_fetch(url, 'LoyaltyCatalogResearchBot'): raise ProbeError('robots_disallow')
            item = {'url': url, 'browser': browser, 'started_at': now()}; report['pages'].append(item); save()
            try:
                time.sleep(interval)
                status, raw, cost = reader.read(url, browser=browser)
                item.update(origin_status=status, credits=cost)
                check_response(status, raw)
                if not browser:
                    # Sanitize only; this explicit diagnostic does NOT certify final HTTP location.
                    soup = BeautifulSoup(raw, 'html.parser')
                    if soup.html is None: raise ProbeError('missing_html')
                    item['location_verified'] = False
                    item['canonical_urls'] = [a.get('href') for a in soup.select('link[rel="canonical"]')]
                    soup.html['data-loyalty-probe-location'] = url
                    raw = str(soup)
                clean, meta = sanitized_page(raw, url)
                item.update(meta); item['location_verified'] = browser
                item['file'] = label + '.html'; item['sha256'] = hashlib.sha256(clean.encode()).hexdigest()
                item['title'] = BeautifulSoup(clean, 'html.parser').h1.get_text(' ', strip=True) if BeautifulSoup(clean, 'html.parser').h1 else ''
                (OUT / item['file']).write_text(clean)
                return clean
            except Exception as exc:
                item['error'] = str(exc) if isinstance(exc, ProbeError) else type(exc).__name__
                return None
            finally:
                item['finished_at'] = now(); save()
        root = read('https://coralbonus.ru/klub-privilegii/', 'club-root')
        if root:
            cats = candidates(root, '/klub-privilegii/', 2, '.category-box-menu h5 a[href]')
            report['category_urls'] = cats
            for index, url in enumerate(cats[-2:]):
                reader.allowed.add(url)
                read(url, f'category-{index}-plain', browser=False)
                page = read(url, f'category-{index}')
                if page:
                    links = candidates(page, urlsplit(url).path, 3)
                    report.setdefault('discovered_details', {})[url] = links
                    if links:
                        reader.allowed.add(links[0]); read(links[0], f'club-detail-{index}')
        root = read('https://coralbonus.ru/promo/', 'promo-root')
        if root:
            links = candidates(root, '/promo/', 2, '.sale-item-description h5 a[href]')
            report['promotion_urls'] = links
            for index, url in enumerate(links[:1] + links[-1:]):
                reader.allowed.add(url); read(url, f'promo-detail-{index}')
    except Exception as exc:
        report['error'] = str(exc) if isinstance(exc, ProbeError) else type(exc).__name__
    finally:
        if reader:
            report.update(source_requests=reader.calls, reserved_credits=reader.reserved,
                          known_cost_headers=reader.known_charged_credits)
        report['finished_at'] = now(); save()
        (OUT / 'executed.py').write_bytes(Path(__file__).read_bytes())


if __name__ == '__main__':
    selfcheck()
    if '--selfcheck' not in sys.argv: main()
