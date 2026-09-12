"""Unknown PDF bytes cannot inherit an earlier visual review."""
import hashlib,importlib.util,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parents[1]))

class ReviewedPdfTests(unittest.TestCase):
    def module(self):
        self.assertIsNotNone(importlib.util.find_spec('reviewed_pdf'),'No reviewed-image-PDF adapter')
        import reviewed_pdf
        return reviewed_pdf
    def test_changed_pdf_is_not_silently_reused(self):
        m=self.module()
        with self.assertRaisesRegex(ValueError,'review_required'):
            m.extract_rgo_pdf(b'%PDF-1.4 changed document',m.RGO_BEELINE_URL,'2026-09-12T19:00:00+00:00')
    def test_non_pdf_bytes_cannot_be_treated_as_pdf(self):
        m=self.module()
        with self.assertRaisesRegex(ValueError,'not_a_pdf'):
            m.extract_rgo_pdf(b'<title>Access denied</title>',m.RGO_BEELINE_URL,'2026-09-12T19:00:00+00:00')
    def test_wrong_source_url_is_rejected_before_profile_use(self):
        m=self.module()
        with self.assertRaisesRegex(ValueError,'not_the_reviewed_url'):
            m.extract_rgo_pdf(b'%PDF-1.4', 'https://evil.invalid/a.pdf','2026-09-12T19:00:00+00:00')
    def test_review_contains_prices_not_fictitious_discount(self):
        m=self.module();r=m.make_beeline_offer('2026-09-12T19:00:00+00:00')
        self.assertEqual(r['details']['price_components'][0]['value'],'450')
        self.assertEqual(r['details']['price_components'][0]['qualifier'],'at_least')
        self.assertEqual(r['details']['price_components'][1]['value'],'100')
        self.assertFalse(any(x['kind']=='discount' for x in r['rates']))
        self.assertIsNone(r['valid_until'])
        self.assertIn('5 устройств',r['benefit_text'])
        self.assertEqual(r['details']['extraction_method'],'digest_bound_visual_review')

class PdfTransportTests(unittest.IsolatedAsyncioTestCase):
    def client(self,status,data):
        from public_transport import PublicSource
        from protego import Protego
        class Response:
            url='https://rgo.ru/test.pdf'
            headers={'content-type':'application/pdf'}
            async def body(self):return data
        response=Response();response.status=status
        class Requests:
            async def fetch(self,*args,**kwargs):return response
        c=PublicSource(None,response.url)
        c.context=type('Context',(),{'request':Requests()})()
        c.policy=Protego.parse('')
        return c
    async def test_pdf_transport_checks_http_status(self):
        c=self.client(403,b'Forbidden')
        self.assertTrue(hasattr(c,'read_pdf'),'Missing bounded PDF transport')
        with self.assertRaisesRegex(RuntimeError,'http_403'):await c.read_pdf('https://rgo.ru/test.pdf')
    async def test_pdf_transport_rejects_html_and_passes_pdf_bytes(self):
        c=self.client(200,b'<html>not PDF</html>')
        self.assertTrue(hasattr(c,'read_pdf'))
        with self.assertRaisesRegex(RuntimeError,'not_a_pdf'):await c.read_pdf('https://rgo.ru/test.pdf')
        c=self.client(200,b'%PDF-1.7 public document')
        self.assertEqual(await c.read_pdf('https://rgo.ru/test.pdf'),b'%PDF-1.7 public document')
