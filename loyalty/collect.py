"""Public browser diagnostic. Output is page evidence, NOT verified live discounts."""
from __future__ import annotations
import argparse
import json
import os
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin, urlsplit
from urllib.robotparser import RobotFileParser

import requests
from playwright.sync_api import sync_playwright
from model import clean_url, is_offer, make_record, BLOCKED

AGENT = 'LoyaltyCatalogResearchBot/0.1'
MORE = re.compile(r'^(?:показать|загрузить)\s+(?:ещё|еще|больше)(?:\s+\d+)?$|^(?:ещё|еще|load more)$', re.I)


def robots(cfg: dict) -> RobotFileParser:
    url = f"https://{cfg['host']}/robots.txt"
    r = requests.get(url, headers={'User-Agent': AGENT}, timeout=20, allow_redirects=False)
    p = RobotFileParser(url)
    if r.status_code == 404:
        p.parse([])
    elif r.status_code == 200:
        p.parse(r.text.splitlines())
    else:
        raise RuntimeError(f'robots_unavailable_http_{r.status_code}')
    return p


def relevant_links(page, cfg: dict) -> tuple[set[str], set[str]]:
    offers, catalogs = set(), set()
    for link in page.locator('a[href]').evaluate_all('(els) => els.map(e => e.href)'):
        try:
            u = clean_url(urljoin(page.url, link))
        except (ValueError, TypeError):
            continue
        parts = urlsplit(u)
        if parts.hostname != cfg['host']:
            continue
        if is_offer(u, cfg):
            offers.add(u)
        elif re.fullmatch(cfg['catalog_pattern'], parts.path):
            catalogs.add(u)
    return offers, catalogs


def read_page(page, url: str, cfg: dict, policy: RobotFileParser) -> None:
    if not policy.can_fetch(AGENT, url):
        raise RuntimeError('robots_disallow')
    time.sleep(1)
    response = page.goto(url, wait_until='domcontentloaded', timeout=30000)
    page.wait_for_timeout(1800)
    if not response or response.status >= 400:
        raise RuntimeError(f'page_http_{response.status if response else "none"}')
    if urlsplit(page.url).hostname != cfg['host']:
        raise RuntimeError('unexpected_cross_origin_redirect')
    if BLOCKED.search(page.title()) or BLOCKED.search(page.locator('body').inner_text()[:160]):
        raise RuntimeError('access_challenge')


def probe(browser, cfg: dict, out: Path, limit: int, started: str) -> tuple[dict, list[dict]]:
    report = {'source': cfg['id'], 'name': cfg['name'], 'root': cfg['roots'][0],
              'status': 'failed', 'coverage': 'diagnostic_sample_not_full_catalog',
              'catalog_pages': 0, 'candidate_count': 0, 'record_count': 0,
              'errors': [], 'network': []}
    records, candidates, seen = [], set(), set()
    context = browser.new_context(locale='ru-RU', user_agent=AGENT)
    page = context.new_page()
    # Network metadata only: never persist cookies, headers, tokens or JSON bodies.
    network_seen = set()
    def observe(resp):
        parts = urlsplit(resp.url)
        if parts.hostname != cfg['host'] or resp.request.resource_type not in ('xhr', 'fetch'):
            return
        key = (parts.path, resp.status)
        if key not in network_seen and len(network_seen) < 60:
            network_seen.add(key)
            report['network'].append({'path': parts.path, 'status': resp.status})
    page.on('response', observe)
    try:
        policy = robots(cfg)
        queue = list(cfg['roots'])
        while queue and len(seen) < 4:
            url = queue.pop(0)
            if url in seen:
                continue
            seen.add(url)
            try:
                read_page(page, url, cfg, policy)
                for _ in range(6):
                    offers, categories = relevant_links(page, cfg)
                    candidates.update(offers)
                    queue.extend(sorted(categories - seen - set(queue)))
                    button = page.get_by_role('button', name=MORE).first
                    if button.count() == 0 or not button.is_visible() or not button.is_enabled():
                        break
                    button.click(timeout=4000)
                    page.wait_for_timeout(1500)
                offers, categories = relevant_links(page, cfg)
                candidates.update(offers)
                report['catalog_pages'] += 1
                # Public visible text only; do not save HTML/session state.
                (out / f"{cfg['id']}-catalog-{len(seen)}.txt").write_text(page.locator('body').inner_text(), encoding='utf-8')
            except Exception as exc:
                report['errors'].append({'phase': 'catalog', 'path': urlsplit(url).path, 'error_type': type(exc).__name__, 'reason': str(exc) if isinstance(exc, RuntimeError) else 'page_read_failed'})
        report['candidate_count'] = len(candidates)
        report['candidate_urls'] = sorted(candidates)
        for url in sorted(candidates)[:limit]:
            try:
                read_page(page, url, cfg, policy)
                if not is_offer(page.url, cfg):
                    raise RuntimeError('redirect_not_an_offer')
                title = page.locator('h1').first.inner_text() if page.locator('h1').count() else page.title()
                main = page.locator('main').first
                terms = main.inner_text() if main.count() else page.locator('body').inner_text()
                record = make_record(cfg['id'], page.url, title, terms, started)
                if not record:
                    raise RuntimeError('not_a_usable_offer_page')
                records.append(record)
                (out / (record['id'] + '.txt')).write_text(terms, encoding='utf-8')
            except Exception as exc:
                report['errors'].append({'phase': 'offer', 'path': urlsplit(url).path, 'error_type': type(exc).__name__, 'reason': str(exc) if isinstance(exc, RuntimeError) else 'page_read_failed'})
        report['record_count'] = len(records)
        report['status'] = 'sample_collected' if records else 'no_usable_records'
    except Exception as exc:
        report['errors'].append({'phase': 'source', 'error_type': type(exc).__name__, 'reason': str(exc) if isinstance(exc, RuntimeError) else 'source_read_failed'})
    finally:
        context.close()
    return report, records


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--limit', type=int, default=12)
    parser.add_argument('--out', default='loyalty-output')
    args = parser.parse_args()
    if not 1 <= args.limit <= 100:
        parser.error('--limit must be between 1 and 100')
    cfgs = json.loads(Path(__file__).with_name('sources.json').read_text())
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    started = datetime.now(timezone.utc).isoformat()
    run_id = os.getenv('GITHUB_RUN_ID', started) + ':' + os.getenv('GITHUB_RUN_ATTEMPT', '1')
    bundle = {'schema_version': 1, 'run_id': run_id, 'observed_at': started, 'sources': [], 'records': []}
    with sync_playwright() as p:
        browser = p.chromium.launch()
        try:
            for cfg in cfgs:
                report, records = probe(browser, cfg, out, args.limit, started)
                bundle['sources'].append(report)
                bundle['records'].extend(records)
                print(json.dumps({k: report[k] for k in ('source','status','catalog_pages','candidate_count','record_count')}, ensure_ascii=False))
        finally:
            browser.close()
    (out / 'bundle.json').write_text(json.dumps(bundle, ensure_ascii=False, indent=2), encoding='utf-8')
    summary = '\n'.join(f"- {x['source']}: {x['record_count']} page records, {x['candidate_count']} candidate URLs; {x['status']}. Coverage: diagnostic sample, NOT a complete catalog." for x in bundle['sources'])
    (out / 'summary.md').write_text(summary + '\n', encoding='utf-8')
    if os.getenv('GITHUB_STEP_SUMMARY'):
        with open(os.environ['GITHUB_STEP_SUMMARY'], 'a') as f:
            f.write(summary + '\n')
    return 0 if bundle['records'] else 2

if __name__ == '__main__':
    raise SystemExit(main())
