"""Real Chromium tests with controlled HTTP only; no source/provider network."""
import asyncio
import base64
import copy
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'loyalty'), str(ROOT / 'loyalty/tests')]
from playwright.async_api import async_playwright, Error as BrowserError
import merchant_queue as q
import merchant_extract as m
import merchant_evidence as evidence
from public_transport import PublicSource
from test_merchant_evidence import record
from test_hse_alumni import page as hse_page, card as hse_card, section as hse_section
from hse_alumni import ROOT as HSE_ROOT, PROGRAM as HSE_PROGRAM


class RoutedBrowser:
    def __init__(self, real, html):
        self.real = real; self.html = html; self.visited = []

    async def new_context(self, **kwargs):
        context = await self.real.new_context(**kwargs)
        async def route(r):
            if r.request.resource_type == 'document':
                self.visited.append(r.request.url)
                await r.fulfill(status=200, content_type='text/html; charset=utf-8', body=self.html)
            else:
                await r.abort()
        await context.route('**/*', route)
        return context


class BrowserEvidenceTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.root = Path(self.tmp.name)
        self.pw = await async_playwright().start()
        self.browser = await self.pw.chromium.launch(headless=True)

    async def asyncTearDown(self):
        await self.browser.close(); await self.pw.stop(); self.tmp.cleanup()

    async def test_late_hydration_is_captured_not_loading_shell(self):
        html = '''<html><body><div id="content">Загрузка…</div><script>
        setTimeout(()=>document.querySelector('#content').innerHTML=
        '<h1>Independent merchant</h1><p>Скидка 17% при бронировании.</p>',3500);
        </script></body></html>'''
        browser = RoutedBrowser(self.browser, html)
        target = {'id':'hydration','url':'https://fixture.example/offer',
                  'partner':'Independent merchant','program':'Public programme'}
        spec = await q.capture_page(browser, target, self.root)
        text = (self.root / spec['text']).read_text()
        self.assertIn('Скидка 17% при бронировании.', text)
        self.assertNotIn('Загрузка', text)
        self.assertTrue(spec['capture']['target_found'])
        self.assertGreater(len(spec['images']), 0)

    async def test_extensionless_pdf_browser_download_is_captured_in_full(self):
        from test_document_text import pdf
        url = 'https://assets.finuslugi.ru/sc-disclosure/293d2bf4-16c4-46c6-87a5-0a2d35d18ad8'
        raw = pdf(['Independent merchant: page one', 'All conditions from page two'])
        real = self.browser
        visits, reads = [], []

        class Browser:
            async def new_context(self, **kwargs):
                context = await real.new_context(**kwargs)
                async def route(r):
                    if r.request.url == url and r.request.resource_type == 'document':
                        visits.append(r.request.url)
                        await r.fulfill(status=200, content_type='application/pdf', body=raw)
                    else:
                        await r.abort()
                await context.route('**/*', route)

                async def fetch(request_url, **options):
                    reads.append((request_url, options))
                    if request_url != url:
                        raise AssertionError('Unexpected request outside the fixture')
                    return SimpleNamespace(status=200, url=url, headers={'content-type': 'application/pdf'},
                                           body=AsyncMock(return_value=raw))
                return SimpleNamespace(new_page=context.new_page, close=context.close,
                                       request=SimpleNamespace(fetch=fetch))

        target = {'id': 'extensionless_pdf', 'url': url, 'partner': 'Independent merchant', 'program': 'Public programme'}
        spec = await q.capture_page(Browser(), target, self.root)
        self.assertEqual(visits, [url])
        self.assertEqual(len(reads), 1)
        self.assertEqual(reads[0][0], url)
        self.assertEqual(reads[0][1]['max_redirects'], 0)
        self.assertEqual((self.root / 'extensionless_pdf/source.pdf').read_bytes(), raw)
        self.assertEqual(len(spec['images']), 2)
        self.assertIn('All conditions from page two', (self.root / spec['text']).read_text())
        self.assertEqual(spec['capture']['scope'], 'pdf')
        self.assertTrue(spec['capture']['target_found'])

    async def test_content_race_waits_for_new_document_not_old_loaded_state(self):
        """Replay the observed error while a real ordinary navigation is pending."""
        start = 'https://fixture.example/initial'
        destination = 'https://fixture.example/current'
        requested = asyncio.Event()
        commit_allowed = asyncio.Event()
        visits = []
        context = await self.browser.new_context()
        page = await context.new_page()
        async def route(r):
            if r.request.url == start:
                visits.append(start)
                await r.fulfill(content_type='text/html', body='<html><body>Old loaded document</body></html>')
            elif r.request.url == destination:
                visits.append(destination)
                requested.set()
                await asyncio.wait_for(commit_allowed.wait(), timeout=5)
                await r.fulfill(content_type='text/html', body='''<html><head>
                    <script src="/late.js"></script></head>
                    <body>Complete new document and all conditions</body></html>''')
            elif r.request.url == 'https://fixture.example/late.js':
                await asyncio.sleep(0.2)  # The new DOMContentLoaded is observable.
                await r.fulfill(content_type='application/javascript', body='window.fixtureReady = true;')
            else:
                await r.abort()
        await context.route('**/*', route)
        source = PublicSource(None, start)
        source.page = page
        original_content = page.content
        injected = False
        async def racing_content():
            nonlocal injected
            if not injected:
                injected = True
                await page.evaluate('url => setTimeout(() => { location.href = url; }, 0)', destination)
                await asyncio.wait_for(requested.wait(), timeout=5)
                # This returns immediately for the old document. The transport
                # must wait for the new event registered before this content call.
                await page.wait_for_load_state('domcontentloaded', timeout=100)
                asyncio.get_running_loop().call_soon(commit_allowed.set)
                raise BrowserError('Page.content: Unable to retrieve content because the page is navigating and changing the content.')
            return await original_content()
        try:
            with patch.object(page, 'content', new=racing_content):
                status, body = await source.navigate(start)
            self.assertEqual(status, 200)
            self.assertIn('Complete new document and all conditions', body)
            self.assertNotIn('Old loaded document', body)
            self.assertEqual(visits, [start, destination])
            self.assertEqual(page.url, destination)
            self.assertTrue(await page.evaluate('window.fixtureReady'))
        finally:
            commit_allowed.set()
            await context.close()

    async def test_transient_missing_body_waits_for_target(self):
        page = await self.browser.new_page()
        try:
            await page.set_content('<html><body>Loading</body></html>')
            await page.evaluate('''() => {
                const body = document.body;
                body.remove();
                setTimeout(() => {
                    body.innerHTML = '<h1>Independent merchant</h1><p>Скидка 17%</p>';
                    document.documentElement.append(body);
                }, 500);
            }''')
            target = {'partner': 'Independent merchant', 'url': 'https://fixture.example/offer'}
            try:
                actual = await evidence.prepare_public_page(page, target)
            except Exception as exc:
                self.fail(f'Temporary missing body aborted readiness: {exc}')
            self.assertTrue(actual['target_found'])
            self.assertTrue(actual['content_ready'])
            self.assertIn('Скидка 17%', await page.locator('body').inner_text())
        finally:
            await page.close()

    async def test_record_reaches_manifest_and_real_capture_uses_existing_detail_url(self):
        row = record(); row['benefit_url'] = 'https://example.org/benefits/actual-published-link'
        target = q.discover_targets({'records':[row]}, {}, {})[0]
        browser = RoutedBrowser(self.browser, '<html><body><h1>Independent merchant</h1><p>Скидка 17%</p></body></html>')
        spec = await q.capture_page(browser, target, self.root)
        self.assertEqual(browser.visited, ['https://example.org/benefits/actual-published-link'])
        self.assertEqual(spec['source_records'], [row])
        manifest = self.root / 'manifest.json'; manifest.write_text(json.dumps({'documents':[spec]}))
        document = m.load_manifest(manifest)[0]
        self.assertEqual(document['source']['source_records'][0]['details']['public_item']['unknown_source_field'], ['retain', {'tail':19}])

    async def test_native_id_selects_target_after_lazy_loading_not_same_named_neighbour(self):
        row = record(name='Unseen test merchant', native='9876')
        row['source_id'] = 'konsierge_public'; row['source_url'] = 'https://konsierge.com/benefits'
        target = q.discover_targets({'records':[row]}, {}, {})[0]
        html = '''<html><body><div style="height:1500px">Catalogue</div>
        <qy-benefit-teaser><div class="BenefitTeaser-Title">Unseen test merchant</div>
        <img data-src="https://files-kons.s3.amazonaws.com/uploads/benefit/image/1111/a.png">
        <div class="BenefitTeaser-OfferText">Чужое предложение</div></qy-benefit-teaser>
        <script>let added=false;addEventListener('scroll',()=>{
        if(!added && scrollY>200){added=true;setTimeout(()=>{
        let n=document.createElement('qy-benefit-teaser');
        n.innerHTML='<div class="BenefitTeaser-Title">Unseen test merchant</div>'+
        '<img data-src="https://files-kons.s3.amazonaws.com/uploads/benefit/image/9876/a.png">'+
        '<div class="BenefitTeaser-OfferText">Целевая скидка 17%</div>';
        document.body.append(n)},800)}})</script></body></html>'''
        browser = RoutedBrowser(self.browser, html)
        spec = await q.capture_page(browser, target, self.root)
        self.assertIn('Целевая скидка 17%', (self.root / spec['text']).read_text())
        self.assertEqual(spec['capture']['native_ids'], ['9876'])
        self.assertTrue(spec['capture']['target_found'])
        self.assertEqual(spec['source_records'][0]['native_id'], '9876')

    async def test_hse_owned_sections_beyond_large_catalogue_keep_common_terms_and_full_detail(self):
        image = io.BytesIO()
        Image.new('RGB', (20, 20), 'black').save(image, format='PNG')
        source_image = 'data:image/png;base64,' + base64.b64encode(image.getvalue()).decode('ascii')
        details = hse_section('b', '<h2>B</h2><div style="height:51000px">Соседняя скидка 99%</div>')
        details += hse_section('a', '<h2>A</h2><p>Скидка 13% по карте</p>')
        details += '<div class="builder-section"><p>Не суммируется с другими акциями.</p></div>'
        details += '<div class="builder-section"><img src="' + source_image + '"></div>'
        raw = hse_page(details=details).replace(
            '<div class="post__text builder_content">',
            '<div class="post__text builder_content"><div class="builder-section">'
            '<p>Общие условия: карта выпускника предъявляется до оплаты.</p></div>')
        browser = RoutedBrowser(self.browser, '<html><body>' + raw + '</body></html>')
        target = {'id': 'hse_owned', 'url': HSE_ROOT, 'partner': 'a', 'program': HSE_PROGRAM}
        spec = await q.capture_page(browser, target, self.root)
        text = (self.root / spec['text']).read_text()
        self.assertIn('карта выпускника предъявляется до оплаты', text)
        self.assertIn('Скидка 13% по карте', text)
        self.assertIn('Не суммируется с другими акциями', text)
        self.assertNotIn('Соседняя скидка 99%', text)
        self.assertIn('Соседняя скидка 99%', (self.root / spec['source_html']).read_text())
        self.assertEqual(spec['capture']['scope'], 'hse_partner_sections')
        self.assertEqual(sum(r['role'] == 'detail' for r in spec['capture']['regions']), 3)
        visual_regions = [r for r in spec['capture']['regions'] if r['text'] == '']
        self.assertEqual(len(visual_regions), 1)
        self.assertEqual(visual_regions[0]['image_count'], 1)
        self.assertNotIn('image_layout', spec, 'Separate regions are not one continuous page image')
        manifest = self.root / 'hse-manifest.json'
        manifest.write_text(json.dumps({'documents': [spec]}))
        loaded = m.load_manifest(manifest)[0]
        self.assertIn('выбранных разделов', evidence.request_text(loaded))
        changed = copy.deepcopy(spec)
        changed['capture']['selection']['blocks'][0]['body'] = 'Подменённые условия'
        manifest.write_text(json.dumps({'documents': [changed]}))
        with self.assertRaisesRegex(ValueError, 'hse_scope_selection_mismatch'):
            m.load_manifest(manifest)
        changed = copy.deepcopy(spec)
        changed['capture']['scope'] = 'page'
        manifest.write_text(json.dumps({'documents': [changed]}))
        with self.assertRaisesRegex(ValueError, 'hse_scope_source_missing'):
            m.load_manifest(manifest)

    async def test_hse_preview_keeps_failed_source_without_admitting_offer(self):
        raw = hse_page(cards=hse_card('missing'), details='')
        target = {'id': 'hse_preview', 'url': HSE_ROOT, 'partner': 'missing', 'program': HSE_PROGRAM}
        with self.assertRaisesRegex(ValueError, 'hse_detail_missing'):
            await q.capture_page(RoutedBrowser(self.browser, raw), target, self.root)
        self.assertTrue((self.root / 'hse_preview/source.html').exists())
        diagnostic = json.loads((self.root / 'hse_preview/capture-diagnostics.json').read_text())
        self.assertEqual(diagnostic['status'], 'failed')
        self.assertFalse(list((self.root / 'hse_preview').glob('page-*.png')))

    async def test_hse_selected_region_still_obeys_image_budget(self):
        raw = hse_page(cards=hse_card('a'), details=hse_section('a',
            '<h2>A</h2><div style="height:41500px">Полные условия</div>'))
        target = {'id': 'hse_large', 'url': HSE_ROOT, 'partner': 'a', 'program': HSE_PROGRAM}
        with self.assertRaisesRegex(ValueError, 'image_budget_no_truncation'):
            await q.capture_page(RoutedBrowser(self.browser, raw), target, self.root)
        diagnostic = json.loads((self.root / 'hse_large/capture-diagnostics.json').read_text())
        self.assertEqual(diagnostic['status'], 'failed')


if __name__ == '__main__':
    unittest.main(verbosity=2)
