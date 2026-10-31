"""Real Chromium tests with controlled HTTP only; no source/provider network."""
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'loyalty'), str(ROOT / 'loyalty/tests')]
from playwright.async_api import async_playwright
import merchant_queue as q
import merchant_extract as m
from test_merchant_evidence import record


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


if __name__ == '__main__':
    unittest.main(verbosity=2)
