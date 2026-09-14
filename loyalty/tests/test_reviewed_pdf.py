"""RGO accepts changed live documents; transport refusals still fail."""
import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parents[1]))
from test_document_text import pdf,NOW
from reviewed_pdf import extract_rgo_pdf
class LiveRgoPdfTests(unittest.TestCase):
 def test_any_discovered_rgo_pdf_is_read_from_its_bytes(self):
  for url,value in [('https://rgo.ru/upload/a.pdf','Offer changed 717'),('https://rgo.ru/upload/b.pdf','Another offer 833')]:
   r=extract_rgo_pdf(pdf([value]),url,NOW)[0]
   self.assertIn(value,r['conditions_text']);self.assertEqual(r['source_url'],url)
 def test_wrong_origin_is_rejected(self):
  with self.assertRaises(ValueError):extract_rgo_pdf(pdf(['x']),'https://evil.invalid/a.pdf',NOW)

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
