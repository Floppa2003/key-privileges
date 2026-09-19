"""One-off owner-requested public UI capture; no direct API or credential access."""
from __future__ import annotations
import asyncio, hashlib, json, re
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit, parse_qs, urlencode
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright

OUT = Path('category-check')
HOST = 'konsierge.com'
ROOT = 'https://konsierge.com/benefits'


def compact(value):
    return re.sub(r'\s+', ' ', value).strip()


def page_query(url):
    p = urlsplit(url)
    q = parse_qs(p.query)
    return {k: v[0] for k, v in q.items() if k in ('rubric_id', 'per', 'page')
            and len(v) == 1 and re.fullmatch(r'\d+', v[0])}


def public_item(item):
    # Whitelist public catalogue fields; never retain headers, cookies, client
    # configuration, full JSON bodies, contact data or account-related fields.
    result = {k: item[k] for k in ('id', 'name', 'offer', 'link', 'rubric_id', 'rubric_ids') if k in item}
    for key in ('description', 'conditions', 'terms', 'redemption', 'instructions'):
        value = item.get(key)
        if isinstance(value, str) and len(value) <= 12000:
            result[key] = value
    result['field_names'] = sorted(item)
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
        cards.append({'name': text('.BenefitTeaser-Title'),
                      'category': text('.BenefitTeaser-Rubric'),
                      'offer': text('.BenefitTeaser-OfferText'),
                      'link': a.get('href', '') if a else '',
                      'text': compact(c.get_text(' ', strip=True))})
    controls = []
    for n in node.select('input,select,option,label,[role="radio"],a[href]'):
        if n.find_parent('qy-benefit-teaser') is None:
            controls.append({'tag': n.name, 'text': compact(n.get_text(' ', strip=True)), 'attrs': dict(n.attrs)})
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
                    event['page'] = {k: v for k, v in meta.items() if v is None or isinstance(v, (bool, int))
                                     or isinstance(v, str) and re.fullmatch(r'\d+', v)} if isinstance(meta, dict) else meta
                    event['page_field_names'] = sorted(meta) if isinstance(meta, dict) else []
                    event['items'] = [public_item(x) for x in data['result']]
                    report['network_pages'].append(event)
            except Exception as e:
                report['errors'].append({**event, 'reason': type(e).__name__})
        def enqueue(res):
            tasks.append(asyncio.create_task(response(res)))
        page.on('response', enqueue)
        async def settle():
            await page.wait_for_timeout(900)
            if tasks:
                await asyncio.gather(*tasks)
        async def capture(url, name):
            start = len(report['network_pages'])
            res = await page.goto(url, wait_until='domcontentloaded', timeout=30000)
            if res is None or res.status != 200 or urlsplit(page.url).netloc != HOST:
                raise RuntimeError('public_page_not_ready')
            await settle()
            await page.wait_for_selector('qy-benefit-teaser', timeout=15000)
            stable = 0
            previous = -1
            for _ in range(55):
                count = await page.locator('qy-benefit-teaser').count()
                if count > 500:
                    raise RuntimeError('card_budget')
                if count == previous:
                    stable += 1
                else:
                    stable = 0
                if stable >= 3:
                    break
                previous = count
                await page.evaluate('window.scrollTo(0,0)')
                await page.wait_for_timeout(250)
                await page.evaluate('window.scrollTo(0,document.body.scrollHeight)')
                await settle()
            raw, cards, controls = dom_capture(await page.content())
            (OUT / (name + '.html')).write_text(raw)
            current = report['network_pages'][start:]
            r = {'url': url, 'file': name + '.html', 'sha256': hashlib.sha256(raw.encode()).hexdigest(),
                 'cards': cards, 'controls': controls, 'native_pages': len(current),
                 'native_item_count': sum(len(x['items']) for x in current), 'scroll_stop': 'stable' if stable >= 3 else 'budget',
                 'loader_present': bool(await page.locator('qy-benefits-page qy-loader').count())}
            report['catalogues'].append(r)
            print(json.dumps({k: v for k, v in r.items() if k not in ('cards', 'controls')}, ensure_ascii=False), flush=True)
        try:
            await capture(ROOT, 'all')
            # Exact category IDs come from the site's own response, never a range scan.
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
