"""Raw capture geometry regressions; no browser, source or provider requests.

The production scroll loop rejected 37k/38k pages despite its 40960px cap.
The image guard also used one error for excessive width and excessive height,
discarding already-read text. These controlled inputs exercise capture_page,
the actual PNG tiler and manifest admission rather than an alternate parser.
"""
from contextlib import contextmanager
import io
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, patch

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / 'loyalty'), str(ROOT)]
import merchant_queue as queue
import merchant_extract as extractor
from diagnostics.deepseek_acceptance import tile_png


URL = 'https://fixture.example/offer'
TEXT = 'Geometry merchant\nAll original conditions, including the last clause.'
HTML = '<html><body><h1>Geometry merchant</h1><p>All original conditions, including the last clause.</p></body></html>'


def png(width, height):
    # A small palette keeps the 40-megapixel boundary fixtures inexpensive.
    image = Image.new('P', (width, height))
    image.putpalette([0, 0, 0, 200, 30, 10] + [0] * 762)
    image.putpixel((width - 1, height - 1), 1)
    data = io.BytesIO()
    image.save(data, format='PNG')
    return data.getvalue()


class Page:
    def __init__(self, width=1024, height=1024, *, screenshot_size=None, stuck=False, grows=False):
        self.width, self.height = width, height
        self.screenshot_size = screenshot_size
        self.y = 0
        self.scrolls = 0
        self.screenshots = 0
        self.stuck, self.grows = stuck, grows
        self.url = URL

    async def set_viewport_size(self, size):
        self.viewport = size

    async def evaluate(self, expression, arg=None):
        if 'scrollY' in expression:
            return {'x': 0, 'y': self.y, 'w': self.viewport['width'], 'h': self.viewport['height'],
                    'width': max(self.width, self.viewport['width']), 'total': self.height}
        if 'window.scrollBy' in expression:
            self.scrolls += 1
            if not self.stuck:
                self.y = min(self.y + 900, max(0, self.height - self.viewport['height']))
            if self.grows:
                self.height += 900
        elif 'window.scrollTo' in expression:
            self.y = 0

    async def wait_for_timeout(self, _):
        pass

    def locator(self, selector):
        if selector != 'body':
            raise AssertionError(selector)
        return SimpleNamespace(inner_text=AsyncMock(return_value=TEXT))

    async def screenshot(self, **_):
        self.screenshots += 1
        return png(*(self.screenshot_size or (self.width, self.height)))


class Source:
    def __init__(self, page):
        self.page = page
        self.response = object()

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_):
        pass

    async def navigate(self, url):
        if url != URL:
            raise AssertionError('Unexpected source URL')
        return 200, HTML

    @contextmanager
    def observe_navigation(self, **_):
        yield [self.response]

    async def document_content(self, latest):
        return 200, HTML


class CaptureGeometryTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    async def capture(self, page, ident='geometry', *, source=None):
        target = {'id': ident, 'url': URL, 'partner': 'Geometry merchant', 'program': 'Public programme'}
        with patch('public_transport.PublicSource', return_value=source or Source(page)), \
                patch.object(queue.evidence, 'prepare_public_page', AsyncMock(return_value={
                    'scope': 'page', 'target_found': True, 'content_ready': True})):
            return await queue.capture_page(None, target, self.root)

    async def test_tall_pages_inside_existing_cap_keep_every_row_and_the_last_clause(self):
        for height in (37000, 38000, 40960):
            with self.subTest(height=height):
                page = Page(height=height)
                spec = await self.capture(page, 'height_' + str(height))
                self.assertEqual((self.root / spec['text']).read_text(), TEXT)
                tiles = [Image.open(io.BytesIO((self.root / name).read_bytes())) for name in spec['images']]
                self.assertEqual(sum(tile.height for tile in tiles), height)
                self.assertEqual(tiles[-1].convert('RGB').getpixel((1023, tiles[-1].height - 1)), (200, 30, 10))
                self.assertLessEqual(len(tiles), 40)
                self.assertLessEqual(page.scrolls, 46)
                manifest = self.root / 'manifest.json'
                extractor.save(manifest, {'documents': [spec]})
                self.assertEqual(len(extractor.load_manifest(manifest)), 1)

    async def test_height_over_cap_preserves_initial_html_and_exact_failed_geometry(self):
        page = Page(height=40961)
        with self.assertRaisesRegex(ValueError, 'image_budget_no_truncation'):
            await self.capture(page)
        folder = self.root / 'geometry'
        self.assertEqual((folder / 'source.html').read_text(), HTML)
        info = json.loads((folder / 'capture-diagnostics.json').read_text())
        self.assertEqual(info['status'], 'failed')
        self.assertEqual(info['stage'], 'scroll')
        self.assertEqual(info['budget_failure']['reason'], 'height')
        self.assertEqual(info['document']['height'], 40961)
        self.assertEqual(info['source_url'], URL)
        self.assertEqual(info['http_status'], 200)
        self.assertEqual(page.screenshots, 0)
        self.assertFalse(list(folder.glob('page-*.png')))

    async def test_late_screenshot_growth_preserves_text_and_actual_png_dimensions(self):
        page = Page(screenshot_size=(1025, 20481))
        with self.assertRaisesRegex(ValueError, 'image_budget_no_truncation'):
            await self.capture(page)
        folder = self.root / 'geometry'
        self.assertEqual((folder / 'source.html').read_text(), HTML)
        self.assertEqual((folder / 'visible-text.txt').read_text(), TEXT)
        info = json.loads((folder / 'capture-diagnostics.json').read_text())
        self.assertEqual(info['status'], 'failed')
        self.assertEqual(info['stage'], 'screenshot')
        self.assertEqual(info['screenshot']['width'], 1025)
        self.assertEqual(info['screenshot']['height'], 20481)
        self.assertEqual(info['screenshot']['required_tiles'], 42)
        self.assertEqual(info['budget_failure']['reason'], 'tile_count')
        self.assertEqual(len(info['screenshot']['sha256']), 64)
        self.assertFalse(list(folder.glob('page-*.png')))

    async def test_known_oversized_rectangle_is_rejected_before_allocating_screenshot(self):
        page = Page(width=2049, height=20480)
        with self.assertRaisesRegex(ValueError, 'image_budget_no_truncation'):
            await self.capture(page)
        folder = self.root / 'geometry'
        info = json.loads((folder / 'capture-diagnostics.json').read_text())
        self.assertEqual(info['stage'], 'screenshot_preflight')
        self.assertEqual(info['budget_failure']['reason'], 'tile_count')
        self.assertEqual(info['document'], {'width': 2049, 'height': 20480})
        self.assertEqual(page.screenshots, 0)
        self.assertEqual((folder / 'visible-text.txt').read_text(), TEXT)

    async def test_non_scrolling_page_stops_with_explicit_incomplete_capture(self):
        page = Page(height=38000, stuck=True)
        with self.assertRaisesRegex(ValueError, 'scroll_budget_no_truncation'):
            await self.capture(page)
        info = json.loads((self.root / 'geometry/capture-diagnostics.json').read_text())
        self.assertEqual(info['status'], 'failed')
        self.assertFalse(info['scroll']['bottom_reached'])
        self.assertLessEqual(page.scrolls, 46)
        self.assertEqual(page.screenshots, 0)

    async def test_growing_page_stops_at_height_cap_without_silently_cutting_tail(self):
        page = Page(height=2000, grows=True)
        with self.assertRaisesRegex(ValueError, 'image_budget_no_truncation'):
            await self.capture(page)
        info = json.loads((self.root / 'geometry/capture-diagnostics.json').read_text())
        self.assertEqual(info['status'], 'failed')
        self.assertEqual(info['budget_failure']['reason'], 'height')
        self.assertGreater(info['document']['height'], 40960)
        self.assertLessEqual(page.scrolls, 46)
        self.assertEqual(page.screenshots, 0)

    async def test_partial_capture_never_enters_queue_manifest(self):
        page = Page(height=40961)
        target = {'id': 'geometry', 'url': URL, 'partner': 'Geometry merchant', 'program': 'Public programme'}
        browser = SimpleNamespace(close=AsyncMock())
        class Playwright:
            async def __aenter__(self):
                return SimpleNamespace(chromium=SimpleNamespace(launch=AsyncMock(return_value=browser)))
            async def __aexit__(self, *_):
                pass
        out = self.root / 'prepared'
        with patch('playwright.async_api.async_playwright', return_value=Playwright()), \
                patch('public_transport.PublicSource', return_value=Source(page)), \
                patch.object(queue, 'discover_targets', return_value=[target]), \
                patch.object(queue.evidence, 'prepare_public_page', AsyncMock(return_value={
                    'scope': 'page', 'target_found': True, 'content_ready': True})):
            result = await queue.prepare_queue(self.root / 'state.json', self.root / 'catalog.json', out, 1)
        self.assertEqual(result['captured'], 0)
        self.assertEqual(result['observations'][0]['status'], 'failed')
        self.assertEqual(json.loads((out / 'manifest.json').read_text()), {'documents': []})
        self.assertEqual((out / 'geometry/source.html').read_text(), HTML)

    async def test_verified_resources_finish_before_final_document_and_screenshot_reads(self):
        page = Page()
        source = Source(page)
        events = []
        original_screenshot = page.screenshot
        async def finish():
            events.append('finish')
            return {'resource_generation': 3, 'responses': []}
        async def document(_):
            events.append('document')
            return 200, HTML
        async def text(**_):
            events.append('text')
            return TEXT
        async def screenshot(**kwargs):
            events.append('screenshot')
            return await original_screenshot(**kwargs)
        source.finish_capture = finish
        source.document_content = document
        page.locator = lambda _: SimpleNamespace(inner_text=text)
        page.screenshot = screenshot
        spec = await self.capture(page, source=source)
        self.assertEqual(events, ['finish', 'document', 'text', 'screenshot', 'finish'])
        self.assertEqual(spec['capture']['transport']['resource_generation'], 3)

    async def test_resource_change_after_screenshot_refuses_capture_without_recapture(self):
        page = Page()
        source = Source(page)
        source.finish_capture = AsyncMock(side_effect=[{'resource_generation': 3}, {'resource_generation': 4}])
        with self.assertRaisesRegex(ValueError, 'capture_resources_changed'):
            await self.capture(page, source=source)
        info = json.loads((self.root / 'geometry/capture-diagnostics.json').read_text())
        self.assertEqual(info['status'], 'failed')
        self.assertEqual(info['stage'], 'transport_validation')
        self.assertEqual(info['transport_generation_before'], 3)
        self.assertEqual(info['transport']['resource_generation'], 4)
        self.assertEqual(page.screenshots, 1)
        self.assertEqual((self.root / 'geometry/visible-text.txt').read_text(), TEXT)
        self.assertFalse(list((self.root / 'geometry').glob('page-*.png')))

    async def test_late_verified_resource_refusal_stays_failed(self):
        page = Page()
        source = Source(page)
        source.finish_capture = AsyncMock(side_effect=[{'resource_generation': 3}, RuntimeError('capture_tls_http_403')])
        with self.assertRaisesRegex(RuntimeError, 'capture_tls_http_403'):
            await self.capture(page, source=source)
        info = json.loads((self.root / 'geometry/capture-diagnostics.json').read_text())
        self.assertEqual(info['status'], 'failed')
        self.assertEqual(info['stage'], 'transport_validation')
        self.assertFalse(list((self.root / 'geometry').glob('page-*.png')))


class ImageGeometryTests(unittest.TestCase):
    def test_two_dimensional_tiles_reconstruct_all_pixels_in_row_major_order(self):
        image = Image.new('RGB', (1027, 2051), 'white')
        draw = ImageDraw.Draw(image)
        for x in (0, 1023, 1024, 1026):
            draw.line((x, 0, x, 2050), fill=(x % 251, 90, 15))
        for y in (0, 1023, 1024, 2047, 2048, 2050):
            draw.line((0, y, 1026, y), fill=(30, y % 251, 240))
        buf = io.BytesIO(); image.save(buf, format='PNG')
        pieces = tile_png(buf.getvalue())
        self.assertEqual(len(pieces), 6)
        restored = Image.new('RGB', image.size)
        for index, raw in enumerate(pieces):
            part = Image.open(io.BytesIO(raw))
            self.assertLessEqual(part.width, 1024)
            self.assertLessEqual(part.height, 1024)
            restored.paste(part, ((index % 2) * 1024, (index // 2) * 1024))
        self.assertEqual(restored.tobytes(), image.tobytes())

    def test_forty_tiles_are_allowed_but_forty_one_or_more_are_not(self):
        self.assertEqual(len(tile_png(png(2048, 20480))), 40)
        for size in ((40961, 1), (1, 40961), (1025, 20481)):
            with self.subTest(size=size), self.assertRaisesRegex(ValueError, 'image_budget_no_truncation'):
                tile_png(png(*size))


if __name__ == '__main__':
    unittest.main(verbosity=2)
