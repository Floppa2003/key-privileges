import sys
import tempfile
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from PIL import Image
import fitz
from playwright.async_api import async_playwright
from merchant_visual_capture import tile_spans, screenshot_pdf, hide_cookie_overlays, capture_page

class Tiles(unittest.TestCase):
    def test_tiles_cover_bottom_and_overlap_without_resizing(self):
        self.assertEqual(tile_spans(3500), [(0,1600),(1480,3080),(2960,3500)])
        self.assertEqual(tile_spans(100),[(0,100)])
    def test_invalid_geometry_is_rejected(self):
        for args in [(0,), (30,10,10), (20,-1,0), (20,5,-1)]:
            with self.subTest(args=args),self.assertRaises(ValueError):tile_spans(*args)
    def test_pdf_contains_identical_screenshot_pixels(self):
        with tempfile.TemporaryDirectory() as td:
            td=Path(td)
            im=Image.new('RGB',(128,3500),'white')
            for y in range(3500):
                for x in range(128):im.putpixel((x,y),((y*7)%256,(x*3)%256,y%256))
            im.save(td/'screen.png')
            pages=screenshot_pdf(td/'screen.png',td/'reading.pdf')
            self.assertEqual(len(pages),3)
            self.assertTrue((td/'reading.pdf').is_file())
            with fitz.open(td/'reading.pdf') as doc:
                self.assertEqual(len(doc),3)
                for page,span in zip(doc,pages):
                    pix=page.get_pixmap(matrix=fitz.Matrix(4/3,4/3),alpha=False)
                    actual=Image.frombytes('RGB',(pix.width,pix.height),pix.samples)
                    expected=im.crop((0,span['top'],128,span['bottom']))
                    self.assertEqual(actual.size,expected.size)
                    self.assertEqual(actual.tobytes(),expected.tobytes())

class CookieOverlays(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.pw=await async_playwright().start()
        import os
        args={'headless':True}
        if os.path.exists('/usr/bin/chromium'):args.update(executable_path='/usr/bin/chromium')
        self.browser=await self.pw.chromium.launch(**args)
        self.page=await self.browser.new_page(viewport={'width':900,'height':700})
    async def asyncTearDown(self):
        await self.browser.close();await self.pw.stop()
    async def test_cookie_overlay_hidden_only_in_derivative_without_clicking(self):
        await self.page.set_content('''<p id="offer">Держателям карты скидка 12%.</p>
        <div id="consent" style="position:fixed;bottom:0;background:white;width:100%;height:100px;z-index:50">Мы используем cookie для аналитики. <button onclick="window.didClick=true">Принять все</button></div>
        <footer>Политика использования cookie</footer>''')
        receipt=await hide_cookie_overlays(self.page)
        self.assertEqual(len(receipt),1)
        self.assertFalse(await self.page.locator('#consent').is_visible())
        self.assertTrue(await self.page.locator('#offer').is_visible())
        self.assertTrue(await self.page.locator('footer').is_visible())
        self.assertIsNone(await self.page.evaluate('window.didClick'))
        self.assertIn('cookie',receipt[0]['text'])
    async def test_never_hides_auth_wall_even_if_it_mentions_cookies(self):
        await self.page.set_content('''<div id="gate" style="position:fixed;inset:0">Для доступа необходимо войти в аккаунт. Мы используем cookies.</div>''')
        receipt=await hide_cookie_overlays(self.page)
        self.assertEqual(receipt,[])
        self.assertTrue(await self.page.locator('#gate').is_visible())
    async def test_normal_promotional_card_containing_cookie_word_is_not_removed(self):
        await self.page.set_content('<article>Скидка 20% на печенье Cookies.</article>')
        self.assertEqual(await hide_cookie_overlays(self.page),[])
        self.assertTrue(await self.page.locator('article').is_visible())
    async def test_capture_produces_secondary_native_pdf(self):
        await self.page.set_content('<h1>Example Club</h1><p>Cardholders save 12%.</p>')
        with tempfile.TemporaryDirectory() as td:
            out=Path(td)
            result=await capture_page(self.page,out)
            self.assertTrue((out/'native.pdf').is_file(),result['warnings'])
            with fitz.open(out/'native.pdf') as doc:
                self.assertIn('Cardholders save 12%', ''.join(p.get_text() for p in doc))
    async def test_cookie_named_promotional_overlay_is_not_hidden(self):
        await self.page.set_content('<aside id="offer" style="position:fixed;bottom:0">Скидка 20% на Cookies. Промокод COOKIE20.</aside>')
        self.assertEqual(await hide_cookie_overlays(self.page),[])
        self.assertTrue(await self.page.locator('#offer').is_visible())

if __name__=='__main__':unittest.main()
