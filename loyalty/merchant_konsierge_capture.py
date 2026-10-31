"""Targeted evidence acquisition from Konsierge's ordinary anonymous catalogue.

No discount parsing, predetermined partner names, direct API replay, login or
synthetic page rendering. Native response objects supply the full descriptions
which the teaser UI does not display. Original target cards supply the PNGs.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import time
from urllib.parse import urlsplit

from playwright.async_api import TimeoutError as BrowserTimeout
from konsierge_catalog import ROOT, SOURCE, category_id
from konsierge_source import allowed_read, public_item, API_HOST
from merchant_evidence import InputNotReady, VERSION, attach_snapshot, native_text


def handles(target: dict) -> bool:
    return (target.get('url') == ROOT and
            (target.get('source_id') == SOURCE or any(r.get('source_id') == SOURCE
             for r in target.get('source_records', []))))


def source_identity(target: dict) -> tuple[set[int], list[str]]:
    wanted = set(); urls = []
    for row in target.get('source_records', []):
        if row.get('source_id') != SOURCE:
            continue
        raw = row.get('details', {}).get('public_item', {})
        ident = row.get('native_id')
        if isinstance(ident, str) and re.fullmatch(r'[1-9]\d*', ident):
            ident = int(ident)
            if raw.get('id') not in (None, ident):
                raise InputNotReady('catalogue_native_identity_conflict')
            wanted.add(ident)
        for cat in row.get('details', {}).get('public_categories', []):
            url = cat.get('url')
            try:
                category_id(url)
            except (TypeError, ValueError, AttributeError):
                continue
            if url not in urls:
                urls.append(url)
    if ROOT not in urls:
        urls.append(ROOT)
    return wanted, urls


async def capture(browser, target: dict, out: Path) -> dict:
    from diagnostics.deepseek_acceptance import store, tile_png
    wanted, urls = source_identity(target)
    folder = out / target['id']; folder.mkdir(exist_ok=True)
    context = await browser.new_context(locale='ru-RU', viewport={'width':1024,'height':1024}, service_workers='block')
    pending = set(); items = {}; ordered_ids = []; pages = []; errors = []
    lock = asyncio.Lock(); last_read = 0.0
    try:
        async def route(r):
            nonlocal last_read
            request = r.request
            if not allowed_read(request.method, request.url):
                return await r.abort()
            if urlsplit(request.url).netloc == API_HOST:
                async with lock:
                    await asyncio.sleep(max(0, last_read + 1 - time.monotonic()))
                    last_read = time.monotonic()
            await r.continue_()
        await context.route('**/*', route)
        page = await context.new_page()

        async def read(res):
            try:
                if res.status != 200:
                    errors.append('native_http_' + str(res.status)); return
                data = await res.json()
                if not isinstance(data.get('result'), list):
                    errors.append('native_result_missing'); return
                for value in data['result']:
                    ident = value.get('id')
                    if type(ident) is not int:
                        continue
                    ordered_ids.append(ident)
                    if ident in wanted or (not wanted and value.get('name') == target['partner']):
                        items[ident] = public_item(value)
                pages.append({'url': res.url, 'status': res.status,
                              'received_at': datetime.now(timezone.utc).isoformat(), 'page': data.get('page')})
            except (ValueError, TypeError, KeyError) as exc:
                errors.append(type(exc).__name__)

        def enqueue(res):
            u = urlsplit(res.url)
            if u.netloc == API_HOST and u.path == '/api/client/v1/benefits':
                task = asyncio.create_task(read(res)); pending.add(task)
                task.add_done_callback(pending.discard)
        page.on('response', enqueue)
        selected = None
        for url in urls:
            items.clear(); ordered_ids.clear(); pages.clear(); errors.clear()
            response = await page.goto(url, wait_until='domcontentloaded', timeout=30000)
            if response is None or response.status != 200:
                raise InputNotReady('public_catalogue_http_unavailable')
            try:
                await page.wait_for_selector('qy-benefit-teaser', timeout=15000)
            except BrowserTimeout:
                continue
            stalls = 0
            for _ in range(45):
                await page.wait_for_timeout(250)
                if pending:
                    await asyncio.gather(*list(pending))
                if (wanted and wanted.issubset(items)) or (not wanted and items):
                    selected = [items[k] for k in sorted(wanted or items)]
                    break
                if pages and (pages[-1].get('page') or {}).get('next_page', 'unknown') is None:
                    break
                count = await page.locator('qy-benefit-teaser').count()
                await page.locator('qy-benefit-teaser').last.scroll_into_view_if_needed()
                await page.mouse.wheel(0,1200)
                await page.evaluate('window.scrollTo(0,document.body.scrollHeight)')
                try:
                    await page.wait_for_function('(n)=>document.querySelectorAll("qy-benefit-teaser").length>n', arg=count, timeout=6000)
                    stalls = 0
                except BrowserTimeout:
                    stalls += 1
                    if stalls >= 2:
                        break
            if selected:
                break
        if pending:
            await asyncio.gather(*list(pending))
        if not selected:
            raise InputNotReady('target_not_acquired_from_public_catalogue')

        images = []; image_hashes = set(); card_texts = []; card_html = []
        for value in selected:
            # Native ID is the identity. DOM title+label corroborate the screenshot;
            # no source image URL or merchant name is hardcoded.
            candidates = page.locator('qy-benefit-teaser').filter(
                has=page.locator('.BenefitTeaser-Title').get_by_text(value['name'], exact=True))
            candidates = candidates.filter(has=page.locator('.BenefitTeaser-OfferText').get_by_text(value['offer'], exact=True))
            count = await candidates.count()
            if not count:
                raise InputNotReady('native_target_card_not_rendered')
            if count > 1:
                marker = f'/benefit/image/{value["id"]}/'
                by_image = candidates.filter(has=page.locator(f'img[data-src*="{marker}"], img[src*="{marker}"]'))
                if await by_image.count() == 1:
                    candidates = by_image; count = 1
                else:
                    # Reconcile against native page order instead of choosing a neighbour.
                    matches = [n for n, ident in enumerate(ordered_ids) if ident == value['id']]
                    all_cards = page.locator('qy-benefit-teaser')
                    if len(matches) != 1 or await all_cards.count() != len(ordered_ids):
                        raise InputNotReady('target_card_identity_ambiguous')
                    candidates = all_cards.nth(matches[0]); count = 1
                    text = await candidates.inner_text()
                    if value['name'] not in text or value['offer'] not in text:
                        raise InputNotReady('target_card_identity_changed')
            await candidates.scroll_into_view_if_needed()
            try:
                await page.wait_for_function('(e)=>Array.from(e.querySelectorAll("img")).every(i=>i.complete&&i.naturalWidth>0)', arg=await candidates.element_handle(), timeout=5000)
            except BrowserTimeout:
                # Missing decorative image does not erase the available native terms.
                pass
            card_texts.append(await candidates.inner_text())
            card_html.append(await candidates.evaluate('(e)=>e.outerHTML'))
            for raw in tile_png(await candidates.screenshot(animations='disabled', timeout=30000)):
                digest = hashlib.sha256(raw).hexdigest()
                if digest not in image_hashes:
                    images.append(raw); image_hashes.add(digest)
        # Keep all acquired page text, as context, without substituting it for the
        # full description in the targeted native objects.
        body = await page.locator('body').inner_text(timeout=15000)
        text = native_text(selected) + '\nTARGET_CARDS:\n' + '\n\n'.join(card_texts) + '\nPAGE_CONTEXT:\n' + body
        (folder/'target-cards.html').write_text('\n'.join(card_html), encoding='utf-8')
        (folder/'source.html').write_text(await page.content(), encoding='utf-8')
        native_name = target['id'] + '/native-source.json'
        (out/native_name).write_text(json.dumps({'items':selected,'responses':pages},ensure_ascii=False,indent=2),encoding='utf-8')
        spec = store(out, target['id'], {'partner':target['partner'],'program':target['program'],
                     'as_of':datetime.now(timezone.utc).date().isoformat()}, text, images, source_url=page.url)
        spec.update(evidence_version=VERSION, capture_scope={'version':VERSION, 'target_resolved':True,
                     'kind':'public_native_items_and_complete_cards', 'native_ids':[v['id'] for v in selected],
                     'observed_at':datetime.now(timezone.utc).isoformat()}, attachments=[native_name])
        spec['sha256'][native_name] = hashlib.sha256((out/native_name).read_bytes()).hexdigest()
        return attach_snapshot(spec,target,out)
    finally:
        for task in pending:
            task.cancel()
        if pending:
            await asyncio.gather(*list(pending),return_exceptions=True)
        await context.close()
