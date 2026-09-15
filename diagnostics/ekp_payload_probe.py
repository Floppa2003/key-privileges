"""Bounded public EKP investigation. No publication, login, or API replay."""
from __future__ import annotations
import asyncio
import hashlib
import json
import os
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin, urlsplit, urlunsplit
from bs4 import BeautifulSoup
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'loyalty'))
from installed_browser import installed_chrome
from public_transport import PublicSource, check_response

ROOT = 'https://ekp.spb.ru/capabilities/loyalty/'
OUT = Path('ekp-payload-output')
SECRET = re.compile(r'token|password|secret|cookie|session|csrf', re.I)


def safe_url(value):
    try:
        u = urlsplit(value)
        if u.scheme not in ('https', 'http') or not u.hostname or u.username or u.password:
            return ''
        return urlunsplit((u.scheme, u.netloc, u.path, '', ''))
    except ValueError:
        return ''


def scrub(value):
    if isinstance(value, dict):
        return {k: scrub(v) for k, v in value.items() if not SECRET.search(k)}
    if isinstance(value, list):
        return [scrub(v) for v in value]
    if isinstance(value, str) and value.startswith(('https://', 'http://')):
        return safe_url(value)
    return value


def public_dom(raw, url):
    soup = BeautifulSoup(raw, 'html.parser')
    for node in soup.select('script,style,noscript,form,input,textarea,iframe,[hidden]'):
        node.decompose()
    for node in soup.find_all(True):
        for attr in list(node.attrs):
            if attr not in ('id', 'class', 'href', 'title', 'role', 'aria-label', 'aria-current', 'aria-disabled', 'disabled'):
                del node.attrs[attr]
        if node.has_attr('href'):
            node['href'] = safe_url(urljoin(url, node['href']))
    return str(soup)


def cards(raw):
    soup = BeautifulSoup(raw, 'html.parser')
    result = []
    for anchor in soup.select('main a[href]'):
        url = urljoin(ROOT, anchor['href'])
        u = urlsplit(url)
        if u.scheme != 'https' or u.netloc != 'ekp.spb.ru' or not re.fullmatch(r'/capabilities/loyalty/tiles/[0-9]+/?', u.path):
            continue
        box = anchor.find_parent(class_='v-card')
        title = box.select_one('.v-card-title') if box else None
        result.append({'url': safe_url(url), 'has_query': bool(u.query),
                       'owned': box is not None, 'title': title.get_text(' ', strip=True) if title else '',
                       'login_notice': bool(box and 'Требуется авторизация' in box.get_text(' ', strip=True))})
    return result


async def run():
    OUT.mkdir(exist_ok=True)
    started = time.monotonic()
    report = {'run_id': os.getenv('GITHUB_RUN_ID'), 'commit': os.getenv('GITHUB_SHA'),
              'replica': os.getenv('REPLICA'), 'observed_at': datetime.now(timezone.utc).isoformat(),
              'stage': 'startup', 'navigation': [], 'api': [], 'dom': [], 'production_write': False}
    pending = set()
    def save():
        (OUT / 'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2))
    async def capture_api(response):
        entry = {'url': safe_url(response.url), 'status': response.status,
                 'seconds': round(time.monotonic() - started, 3)}
        report['api'].append(entry)
        try:
            if response.status != 200 or response.headers.get('retry-after'):
                entry['error'] = 'http_refusal_or_retry_after'
                return
            body = await asyncio.wait_for(response.text(), 12)
            if len(body.encode()) > 6000000:
                raise ValueError('response_size_bound')
            check_response(response.status, body)
            data = json.loads(body)
            entry['raw_sha256'] = hashlib.sha256(body.encode()).hexdigest()
            entry['type'] = type(data).__name__
            entry['keys'] = list(data) if isinstance(data, dict) else None
            entry['file'] = 'api-' + str(len(report['api'])) + '.json'
            (OUT / entry['file']).write_text(json.dumps(scrub(data), ensure_ascii=False, indent=2))
            entry['body_completed'] = True
        except Exception as exc:
            entry['error'] = type(exc).__name__
        finally:
            save()
    async def snapshot(page, label):
        raw = await asyncio.wait_for(page.content(), 6)
        clean = public_dom(raw, page.url)
        file = label + '.html'
        (OUT / file).write_text(clean)
        entry = {'file': file, 'url': safe_url(page.url), 'seconds': round(time.monotonic() - started, 3),
                 'raw_sha256': hashlib.sha256(raw.encode()).hexdigest(), 'cards': cards(raw),
                 'main_chars': len(BeautifulSoup(raw, 'html.parser').select_one('main').get_text(' ', strip=True))
                               if BeautifulSoup(raw, 'html.parser').select_one('main') else 0}
        report['dom'].append(entry)
        save()
        return entry
    try:
        async with installed_chrome() as (context, page):
            client = PublicSource(None, ROOT)
            client.context = context
            client.page = page
            client.deadline = time.monotonic() + 170
            report['stage'] = 'robots'
            save()
            try:
                await asyncio.wait_for(client.robots(), 60)
            finally:
                report['robots'] = getattr(client, 'robots_info', {})
                save()
            client.check_url(ROOT)
            def observe(response):
                u = urlsplit(response.url)
                if response.request.is_navigation_request() and response.frame == page.main_frame:
                    report['navigation'].append({'url': safe_url(response.url), 'status': response.status})
                if u.netloc == 'ekp.spb.ru' and u.path.startswith('/api/portal/loyalty/'):
                    task = asyncio.create_task(capture_api(response))
                    pending.add(task)
                    task.add_done_callback(pending.discard)
            page.on('response', observe)
            try:
                report['stage'] = 'catalog'
                save()
                try:
                    await page.goto(ROOT, wait_until='commit', timeout=25000)
                except Exception as exc:
                    report['navigation_error'] = type(exc).__name__
                first = None
                for attempt in range(12):
                    if report['navigation'] and report['navigation'][-1]['status'] >= 400:
                        raise RuntimeError('target_http_refusal')
                    if any(x.get('error') == 'http_refusal_or_retry_after' for x in report['api']):
                        raise RuntimeError('api_http_refusal')
                    try:
                        snap = await snapshot(page, 'listing-' + str(attempt))
                        if snap['cards']:
                            first = snap
                            break
                    except asyncio.TimeoutError:
                        report['dom_timeout'] = True
                    await asyncio.sleep(2)
                if first is None:
                    raise RuntimeError('no_catalog_cards')
                report['stage'] = 'pagination'
                save()
                button = page.get_by_role('button', name=re.compile('^Показать еще$'))
                await button.click(timeout=8000)
                old = {x['url'] for x in first['cards']}
                for attempt in range(8):
                    await asyncio.sleep(2)
                    snap = await snapshot(page, 'expanded-' + str(attempt))
                    if {x['url'] for x in snap['cards']} - old:
                        report['pagination_new_cards'] = len({x['url'] for x in snap['cards']} - old)
                        break
                eligible = [x for x in first['cards'] if x['owned'] and not x['login_notice']]
                if not eligible:
                    raise RuntimeError('no_ungated_card')
                target = eligible[0]['url']
                client.check_url(target)
                report['stage'] = 'detail'
                report['selected_card'] = eligible[0]
                save()
                await page.goto(target, wait_until='domcontentloaded', timeout=25000)
                await asyncio.sleep(5)
                await snapshot(page, 'detail')
                if pending:
                    await asyncio.wait_for(asyncio.gather(*list(pending), return_exceptions=True), 15)
                report['stage'] = 'evidence_collected'
            finally:
                page.remove_listener('response', observe)
                for task in list(pending):
                    task.cancel()
                if pending:
                    await asyncio.gather(*list(pending), return_exceptions=True)
    except Exception as exc:
        report['error'] = str(exc) if isinstance(exc, RuntimeError) else type(exc).__name__
    finally:
        report['finished_at'] = datetime.now(timezone.utc).isoformat()
        report['elapsed_seconds'] = round(time.monotonic() - started, 3)
        save()
        (OUT / 'executed-probe.py').write_bytes(Path(__file__).read_bytes())
    return report['stage'] == 'evidence_collected'


if __name__ == '__main__':
    raise SystemExit(0 if asyncio.run(run()) else 1)
