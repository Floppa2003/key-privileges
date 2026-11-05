"""Real Chromium geometry regressions using routed fixtures, without external I/O.

Run after installing Chromium: python diagnostics/test_capture_geometry_browser.py
All PNGs come from the real browser. No provider or official-site request is made.
"""
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest

from PIL import Image
from playwright.async_api import async_playwright

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'loyalty'), str(ROOT)]
import merchant_queue as queue
import merchant_extract as extractor


URL = 'https://fixture.example/geometry'


def page_html(width, height):
    return f'''<!doctype html><html><head><meta charset="utf-8"><style>
      html {{scroll-behavior:smooth}}
      html,body {{margin:0;padding:0}}
      body {{position:relative;width:{width}px;height:{height}px;background:rgb(250,250,250)}}
      h1 {{margin:0;font-size:16px}}
      #last {{position:absolute;right:0;bottom:1px;margin:0}}
      #edge {{position:absolute;left:0;bottom:0;width:100%;height:1px;background:rgb(200,30,10)}}
    </style></head><body><h1>Geometry merchant</h1><p>All original conditions.</p>
    <p id="last">Last clause at the bottom right.</p><div id="edge"></div></body></html>'''


class FixtureBrowser:
    def __init__(self, real, html):
        self.real, self.html = real, html
        self.requests = []

    async def new_context(self, **kwargs):
        context = await self.real.new_context(**kwargs)
        async def route(request):
            self.requests.append(request.request.url)
            if request.request.url == URL and request.request.resource_type == 'document':
                await request.fulfill(status=200, content_type='text/html; charset=utf-8', body=self.html)
            else:
                await request.abort()
        await context.route('**/*', route)
        return context


class CaptureGeometryBrowserTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.pw = await async_playwright().start()
        self.browser = await self.pw.chromium.launch(headless=True)

    async def asyncTearDown(self):
        await self.browser.close()
        await self.pw.stop()
        self.tmp.cleanup()

    async def capture(self, width, height, ident):
        browser = FixtureBrowser(self.browser, page_html(width, height))
        target = {'id': ident, 'url': URL, 'partner': 'Geometry merchant', 'program': 'Public programme'}
        return await queue.capture_page(browser, target, self.root)

    def diagnostics(self, ident):
        return json.loads((self.root / ident / 'capture-diagnostics.json').read_text())

    async def test_all_rows_survive_long_pages_including_the_exact_existing_limit(self):
        for height in (37000, 38000, 40960):
            with self.subTest(height=height):
                ident = 'height_' + str(height)
                spec = await self.capture(1024, height, ident)
                info = self.diagnostics(ident)
                self.assertEqual(info['status'], 'complete')
                self.assertEqual(info['screenshot']['height'], height)
                self.assertEqual(info['screenshot']['width'], 1024)
                self.assertTrue(info['scroll']['bottom_reached'])
                self.assertLessEqual(info['scroll']['steps'], 46)
                self.assertIn('Last clause at the bottom right.', (self.root / spec['text']).read_text())
                total_height = 0
                for name in spec['images']:
                    with Image.open(io.BytesIO((self.root / name).read_bytes())) as image:
                        total_height += image.height
                        self.assertLessEqual(image.width, 1024)
                        self.assertLessEqual(image.height, 1024)
                self.assertEqual(total_height, height)
                with Image.open(io.BytesIO((self.root / spec['images'][-1]).read_bytes())) as last:
                    self.assertEqual(last.convert('RGB').getpixel((1023, last.height - 1)), (200, 30, 10))
                manifest = self.root / 'manifest.json'
                extractor.save(manifest, {'documents': [spec]})
                self.assertEqual(len(extractor.load_manifest(manifest)[0]['images']), len(spec['images']))

    async def test_horizontal_overflow_keeps_the_right_edge_and_bottom_row(self):
        spec = await self.capture(1500, 1800, 'wide')
        info = self.diagnostics('wide')
        self.assertEqual(info['status'], 'complete')
        self.assertEqual(info['screenshot']['width'], 1500)
        self.assertEqual(info['screenshot']['height'], 1800)
        self.assertEqual(len(spec['images']), 4)
        layout = spec['image_layout']
        self.assertEqual([(r['x'], r['y']) for r in layout['tiles']], [(0, 0), (1024, 0), (0, 1024), (1024, 1024)])
        reconstructed = Image.new('RGB', (layout['width'], layout['height']))
        for region in layout['tiles']:
            with Image.open(io.BytesIO((self.root / region['image']).read_bytes())) as tile:
                self.assertEqual(tile.size, (region['width'], region['height']))
                reconstructed.paste(tile, (region['x'], region['y']))
        self.assertEqual(reconstructed.getpixel((1499, 1799)), (200, 30, 10))
        self.assertIn('Last clause at the bottom right.', (self.root / spec['text']).read_text())
        manifest = self.root / 'manifest.json'
        extractor.save(manifest, {'documents': [spec]})
        self.assertEqual(len(extractor.load_manifest(manifest)[0]['images']), 4)

    async def test_true_height_overflow_stays_failed_with_original_html(self):
        with self.assertRaisesRegex(ValueError, 'image_budget_no_truncation'):
            await self.capture(1024, 40961, 'overheight')
        info = self.diagnostics('overheight')
        self.assertEqual(info['status'], 'failed')
        self.assertEqual(info['stage'], 'scroll')
        self.assertEqual(info['budget_failure']['reason'], 'height')
        self.assertEqual(info['document']['height'], 40961)
        self.assertIn('Last clause at the bottom right.', (self.root / 'overheight/source.html').read_text())
        self.assertFalse(list((self.root / 'overheight').glob('page-*.png')))

    async def test_wide_rectangle_over_forty_tiles_stays_failed_with_original_text(self):
        with self.assertRaisesRegex(ValueError, 'image_budget_no_truncation'):
            await self.capture(2049, 20480, 'overtile')
        info = self.diagnostics('overtile')
        self.assertEqual(info['status'], 'failed')
        self.assertEqual(info['stage'], 'screenshot_preflight')
        self.assertEqual(info['budget_failure']['reason'], 'tile_count')
        self.assertEqual(info['expected_screenshot']['required_tiles'], 60)
        self.assertIn('Last clause at the bottom right.', (self.root / 'overtile/visible-text.txt').read_text())
        self.assertFalse(list((self.root / 'overtile').glob('page-*.png')))


if __name__ == '__main__':
    unittest.main(verbosity=2)
