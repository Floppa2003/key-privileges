"""Bounded public-browser collection for the existing daily loyalty pipeline.

The project owner explicitly disabled robots.txt preflight for this source on
2026-09-19. This does not alter PublicSource or authorize account/API access.
"""
from __future__ import annotations
import asyncio
import hashlib
import os
import re
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import parse_qs, urlsplit
from bs4 import BeautifulSoup
from playwright.async_api import TimeoutError as BrowserTimeout
from konsierge_catalog import (ROOT, SOURCE, ITEM_KEYS, parse_capture, item_fields,
                               category_id, require, ROBOTS_POLICY, RECURRING_MODE)

HOST = 'konsierge.com'
API_HOST = 'benefits.konsierge.com'
API_PATHS = {'/api/client/v1/benefits', '/api/client/v1/rubrics'}
BLOCKED_PATH = re.compile(r'/(?:auth|login|register|activate|account|personal|session)(?:/|$)', re.I)


def allowed_read(method, url):
    """Only the reviewed public page, its assets and browser-owned catalogue GETs."""
    try:
        u = urlsplit(url)
        if method not in ('GET', 'HEAD', 'OPTIONS') or u.username or u.password:
            return False
        if u.scheme != 'https' or u.path.lower() == '/robots.txt' or BLOCKED_PATH.search(u.path):
            return False
        if u.netloc == HOST:
            if u.path == '/benefits':
                category_id(url)
                return True
            return bool(re.search(r'\.(?:js|css|ico|png|jpe?g|webp|svg|woff2?|ttf)$', u.path, re.I))
        if u.netloc == API_HOST:
            return u.path in API_PATHS
        return u.netloc == 'files-kons.s3.amazonaws.com' and method in ('GET', 'HEAD')
    except (ValueError, TypeError):
        return False


def public_item(item):
    result = {k: item[k] for k in ITEM_KEYS - {'rubrics'} if k in item}
    result['rubrics'] = [{'id': r['id']} for r in item.get('rubrics', [])]
    item_fields(result)
    return result


def dom_capture(raw):
    """Retain only display labels, not full page scripts, headers or cookies."""
    soup = BeautifulSoup(raw, 'html.parser')
    node = soup.select_one('qy-benefits-page')
    require(node is not None, 'catalogue_dom_missing')
    output = BeautifulSoup('<qy-benefits-page></qy-benefits-page>', 'html.parser')
    cards = []
    for original in node.select('qy-benefit-teaser'):
        card = {}; dest = output.new_tag('qy-benefit-teaser')
        for key, cls in (('name', 'BenefitTeaser-Title'), ('offer', 'BenefitTeaser-OfferText')):
            el = original.select_one('.' + cls)
            require(el is not None, 'card_label_missing')
            card[key] = re.sub(r'\s+', ' ', el.get_text(' ', strip=True)).strip()
            copy = output.new_tag('div', attrs={'class': cls})
            copy.string = card[key]; dest.append(copy)
        cards.append(card); output.find('qy-benefits-page').append(dest)
    return str(output), cards


async def capture(browser, directory, observed_at, limit):
    report = {'observed_at': observed_at, 'collection_mode': RECURRING_MODE,
              'robots_policy': ROBOTS_POLICY, 'robots_requests': 0,
              'one_off_public_ui_inspection': False, 'source_account_login': False,
              'direct_api_requests': 0, 'credential_values_read_or_replayed': False,
              'published': False, 'rubrics': [], 'network_pages': [], 'catalogues': [], 'errors': []}
    context = await browser.new_context(locale='ru-RU', viewport={'width': 1440, 'height': 1000}, service_workers='block')
    pending = set(); lock = asyncio.Lock(); last_read = 0.0
    try:
        async def route(r):
            nonlocal last_read
            req = r.request
            if report['errors'] or not allowed_read(req.method, req.url):
                return await r.abort()
            u = urlsplit(req.url)
            if u.netloc == API_HOST:
                async with lock:
                    await asyncio.sleep(max(0, 1.0 - (time.monotonic() - last_read)))
                    last_read = time.monotonic()
            if report['errors']:
                return await r.abort()
            await r.continue_()
        await context.route('**/*', route)
        page = await context.new_page()

        async def response(res):
            u = urlsplit(res.url)
            if u.netloc != API_HOST or u.path not in API_PATHS:
                return
            try:
                require(res.status == 200, 'native_http_' + str(res.status))
                q = parse_qs(u.query)
                query = {k: v[0] for k, v in q.items() if k in ('rubric_id', 'per', 'page')
                         and len(v) == 1 and re.fullmatch(r'\d+', v[0])}
                data = await res.json()
                require(isinstance(data.get('result'), list), 'native_result_not_list')
                if u.path.endswith('/rubrics'):
                    rubrics = sorted([{'id': x['id'], 'name': x['name']} for x in data['result']], key=lambda r: r['id'])
                    require(0 < len(rubrics) <= 32, 'rubric_budget')
                    require(not report['rubrics'] or report['rubrics'] == rubrics, 'rubric_inventory_changed')
                    report['rubrics'] = rubrics
                else:
                    require(len(report['network_pages']) < 160, 'network_page_budget')
                    require(len(data['result']) <= 12 and data['page']['total_count'] <= limit, 'item_limit')
                    meta = {k: data['page'][k] for k in ('total_pages', 'count', 'total_count', 'current_page', 'next_page')}
                    report['network_pages'].append({'path': u.path, 'query': query, 'status': res.status,
                        'received_at': datetime.now(timezone.utc).isoformat(), 'page': meta,
                        'items': [public_item(x) for x in data['result']]})
            except Exception as exc:
                reason = str(exc) if isinstance(exc, ValueError) and str(exc).startswith('konsierge_') else type(exc).__name__
                report['errors'].append({'phase': 'native_response', 'path': u.path, 'reason': reason})

        def enqueue(res):
            # Subscribe only to reviewed JSON replies; never inspect request headers.
            if urlsplit(res.url).netloc == API_HOST and urlsplit(res.url).path in API_PATHS:
                task = asyncio.create_task(response(res)); pending.add(task)
                task.add_done_callback(pending.discard)
        page.on('response', enqueue)

        async def settle():
            await page.wait_for_timeout(600)
            if pending: await asyncio.gather(*list(pending))
            require(not report['errors'], 'native_read_failed')

        async def visit(url, name):
            start = len(report['network_pages'])
            res = await page.goto(url, wait_until='domcontentloaded', timeout=30000)
            require(res is not None and res.status == 200 and page.url == url, 'public_page_not_ready')
            await settle()
            await page.wait_for_selector('qy-benefit-teaser', timeout=15000)
            complete = False; stalls = 0
            for _ in range(50):
                await settle()
                pages = report['network_pages'][start:]
                count = await page.locator('qy-benefit-teaser').count()
                require(count <= limit, 'item_limit')
                if pages and count == pages[-1]['page']['total_count'] and pages[-1]['page']['next_page'] is None:
                    complete = True; break
                await page.evaluate('window.scrollTo(0,0)')
                await page.wait_for_timeout(300)
                await page.evaluate('window.scrollTo(0,document.body.scrollHeight)')
                try:
                    await page.wait_for_function('(n)=>document.querySelectorAll("qy-benefit-teaser").length>n', arg=count, timeout=12000)
                    stalls = 0
                except BrowserTimeout:
                    stalls += 1
                    if stalls >= 2: break
            await settle()
            require(complete, 'catalogue_not_complete')
            raw, cards = dom_capture(await page.content())
            Path(directory, name + '.html').write_text(raw, encoding='utf-8')
            pages = report['network_pages'][start:]
            report['catalogues'].append({'url': url, 'file': name + '.html', 'sha256': hashlib.sha256(raw.encode()).hexdigest(),
                'cards': cards, 'native_pages': len(pages), 'native_item_count': sum(len(x['items']) for x in pages),
                'scroll_stop': 'native_last_page_and_count'})

        await visit(ROOT, 'all')
        for rubric in report['rubrics']:
            ident = rubric['id']
            require(type(ident) is int and 0 < ident < 10000000, 'invalid_native_rubric')
            await visit(ROOT + '?rubric_id=' + str(ident), 'rubric-' + str(ident))
        return report
    finally:
        # No pending tasks may outlive a cancelled/failed source or its browser.
        for task in pending: task.cancel()
        if pending: await asyncio.gather(*list(pending), return_exceptions=True)
        await context.close()


async def collect(browser, cfg, report, observed_at, limit):
    require(cfg.get('id') == SOURCE and cfg.get('url') == ROOT and cfg.get('mode') == 'konsierge'
            and cfg.get('robots_policy') == ROBOTS_POLICY, 'recurring_config')
    require(type(limit) is int and 1 <= limit <= 500, 'item_limit')
    report['robots'] = {'state': 'not_requested', 'reason': ROBOTS_POLICY, 'http_status': None}
    run = os.environ.get('GITHUB_RUN_ID', str(time.time_ns())) + ':' + os.environ.get('GITHUB_RUN_ATTEMPT', '1')
    with tempfile.TemporaryDirectory(prefix='konsierge-public-') as directory:
        captured = await capture(browser, directory, observed_at, limit)
        bundle = parse_capture(captured, directory, run)
    report.update(bundle['sources'][0])
    report['capture_sha256'] = bundle['records'][0]['details']['capture_sha256']
    report['source_run'] = run
    report['robots_requests'] = captured['robots_requests']
    return bundle['records']
