"""One-off owner-requested public UI capture; no direct API or credential access."""
from __future__ import annotations
import asyncio, hashlib, json, re
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit, parse_qs
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright, TimeoutError as BrowserTimeout

OUT = Path('category-check')
HOST = 'konsierge.com'
ROOT = 'https://konsierge.com/benefits'


def compact(value):
    return re.sub(r'\s+', ' ', value).strip()


def page_query(url):
    q = parse_qs(urlsplit(url).query)
    return {k: v[0] for k, v in q.items() if k in ('rubric_id', 'per', 'page')
            and len(v) == 1 and re.fullmatch(r'\d+', v[0])}


def public_item(item):
    # Values only from the explicitly reviewed public catalogue field allowlist.
    result = {k: item[k] for k in ('id', 'name', 'offer', 'link', 'description', 'enabled',
              'date_of_expiry', 'date_of_release', 'created_at', 'updated_at') if k in item}
    rubrics = item.get('rubrics')
    if isinstance(rubrics, list):
        result['rubrics'] = [{k: r[k] for k in ('id', 'name') if k in r} if isinstance(r, dict) else r for r in rubrics]
    if any(isinstance(v, str) and len(v) > 20000 for v in result.values()):
        raise ValueError('public_field_size_bound')
    return result


def dom_capture(raw):
    soup = BeautifulSoup(raw, 'html.parser')
    node = soup.select_one('qy-benefits-page')
    if node is None:
        raise RuntimeError('catalogue_dom_missing')
    for n in list(node.select('script,style,noscript,svg,textarea,iframe')):
        if n.parent is not None:
            n.decompose()
    for n in list(node.select('input')):
        if n.get('type') != 'radio':
            n.decompose()
    for n in node.find_all(True):
        n.attrs = {k: v for k, v in n.attrs.items()
                   if k in ('class', 'href', 'src', 'data-src', 'alt', 'role', 'aria-label', 'type', 'value', 'name', 'for', 'id')}
    cards = []
    for c in node.select('qy-benefit-teaser'):
        def text(sel):
            n = c.select_one(sel)
            return compact(n.get_text(' ', strip=True)) if n else ''
        a = c.select_one('.BenefitTeaser-Title a')
        cards.append({'name': text('.BenefitTeaser-Title'), 'category': text('.BenefitTeaser-Rubric'),
                      'offer': text('.BenefitTeaser-OfferText'), 'link': a.get('href', '') if a else '',
                      'text': compact(c.get_text(' ', strip=True))})
    controls = [{'value': n.get('value'), 'type': n.get('type')} for n in node.select('input[type="radio"]')]
    return str(node), cards, controls


async def main():
    OUT.mkdir(exist_ok=True)
    report = {'observed_at': datetime.now(timezone.utc).isoformat(),
              'one_off_public_ui_inspection': True, 'production_robots_gate_unchanged': True,
              'source_account_login': False, 'direct_api_requests': 0,
              'credential_values_read_or_replayed': False, 'published': False,
              'rubrics': [], 'network_pages': [], 'catalogues': [], 'errors': []}
    tasks = []
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        context = await browser.new_context(locale='ru-RU', viewport={'width': 1440, 'height': 1000})
        async def route(r):
            u = urlsplit(r.request.url)
            if r.request.method not in ('GET', 'HEAD', 'OPTIONS'):
                return await r.abort()
            if u.scheme not in ('https', 'data', 'blob'):
                return await r.abort()
            if u.scheme == 'https' and u.netloc not in (HOST, 'benefits.konsierge.com', 'files-kons.s3.amazonaws.com'):
                return await r.abort()
            if re.search(r'/(?:auth|login|register|activate|account)(?:/|$)', u.path, re.I):
                return await r.abort()
            await r.continue_()
        await context.route('**/*', route)
        page = await context.new_page()
        async def response(res):
            u = urlsplit(res.url)
            if u.netloc != 'benefits.konsierge.com' or u.path not in ('/api/client/v1/benefits', '/api/client/v1/rubrics'):
                return
            event = {'path': u.path, 'query': page_query(res.url), 'status': res.status,
                     'received_at': datetime.now(timezone.utc).isoformat()}
            if res.status != 200:
                report['errors'].append({**event, 'reason': 'native_response_refused'})
                return
            try:
                data = await res.json()
                if not isinstance(data.get('result'), list):
                    raise ValueError('native_result_not_list')
                if u.path.endswith('/rubrics'):
                    rubrics = [{k: x[k] for k in ('id', 'name') if k in x} for x in data['result']]
                    if report['rubrics'] and report['rubrics'] != rubrics:
                        raise ValueError('rubric_inventory_changed')
                    report['rubrics'] = rubrics
                else:
                    meta = data.get('page', {})
                    event['page'] = {k: meta[k] for k in ('total_pages', 'count', 'total_count', 'current_page', 'next_page') if k in meta}
                    event['items'] = [public_item(x) for x in data['result']]
                    report['network_pages'].append(event)
            except Exception as e:
                report['errors'].append({**event, 'reason': type(e).__name__})
        def enqueue(res):
            tasks.append(asyncio.create_task(response(res)))
        page.on('response', enqueue)
        async def settle():
            await page.wait_for_timeout(600)
            if tasks:
                await asyncio.gather(*tasks)
        async def capture(url, name):
            start = len(report['network_pages'])
            res = await page.goto(url, wait_until='domcontentloaded', timeout=30000)
            if res is None or res.status != 200 or urlsplit(page.url).netloc != HOST:
                raise RuntimeError('public_page_not_ready')
            await settle()
            await page.wait_for_selector('qy-benefit-teaser', timeout=15000)
            stalls = 0
            complete = False
            for _ in range(55):
                await settle()
                current = report['network_pages'][start:]
                count = await page.locator('qy-benefit-teaser').count()
                if current and count == current[-1]['page']['total_count'] and current[-1]['page']['next_page'] is None:
                    complete = True
                    break
                if count > 500 or report['errors']:
                    raise RuntimeError('native_read_failed_or_card_budget')
                await page.evaluate('window.scrollTo(0,0)')
                await page.wait_for_timeout(300)
                await page.evaluate('window.scrollTo(0,document.body.scrollHeight)')
                try:
                    await page.wait_for_function('(n)=>document.querySelectorAll("qy-benefit-teaser").length>n', arg=count, timeout=12000)
                    stalls = 0
                except BrowserTimeout:
                    stalls += 1
                    if stalls >= 2:
                        break
            await settle()
            raw, cards, controls = dom_capture(await page.content())
            (OUT / (name + '.html')).write_text(raw)
            current = report['network_pages'][start:]
            r = {'url': url, 'file': name + '.html', 'sha256': hashlib.sha256(raw.encode()).hexdigest(),
                 'cards': cards, 'controls': controls, 'native_pages': len(current),
                 'native_item_count': sum(len(x['items']) for x in current),
                 'scroll_stop': 'native_last_page_and_count' if complete else 'incomplete',
                 'loader_present': bool(await page.locator('qy-benefits-page qy-loader').count())}
            report['catalogues'].append(r)
            print(json.dumps({k: v for k, v in r.items() if k not in ('cards', 'controls')}, ensure_ascii=False), flush=True)
            if not complete:
                raise RuntimeError('catalogue_not_complete')
        try:
            await capture(ROOT, 'all')
            for rubric in report['rubrics']:
                ident = str(rubric.get('id', ''))
                if not re.fullmatch(r'[1-9]\d{0,6}', ident) or not rubric.get('name'):
                    raise RuntimeError('invalid_native_rubric')
                await capture(ROOT + '?rubric_id=' + ident, 'rubric-' + ident)
        except Exception as e:
            report['errors'].append({'phase': 'browser', 'reason': str(e) if isinstance(e, RuntimeError) else type(e).__name__})
        finally:
            if tasks:
                await asyncio.gather(*tasks)
            await context.close()
            await browser.close()
            (OUT / 'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2))
            print(json.dumps({'rubrics': report['rubrics'], 'errors': report['errors'], 'pages': len(report['network_pages'])}, ensure_ascii=False))

if __name__ == '__main__':
    asyncio.run(main())
