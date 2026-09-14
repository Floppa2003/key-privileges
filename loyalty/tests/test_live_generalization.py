"""Sparse native layers and multi-part PDFs are layout cases, not document IDs."""
import sys,unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).parents[1]))
from test_document_text import pdf,NOW
from normalized import make_offer

class SparseNativeTests(unittest.TestCase):
 def test_sparse_contact_layer_over_image_text_needs_ocr(self):
  from document_text import needs_page_ocr
  self.assertTrue(needs_page_ocr('Contact person and contact@example.invalid. Click here.',100))
  self.assertTrue(needs_page_ocr('',0))
  self.assertFalse(needs_page_ocr('22 24 26',0))
  self.assertFalse(needs_page_ocr('Full document conditions and requirements. '*100,2))
 def test_ocr_preserves_native_layer_separately(self):
  from document_text import extract_pdf
  native='Contact person and contact@example.invalid. Click here.'
  with patch('document_text.needs_page_ocr',return_value=True),patch('document_text.ocr_page',return_value=('Fresh image text 173',{'words':4})):
   doc=extract_pdf(pdf([native]))
  self.assertEqual(doc['pages'][0]['native_text'],native)
  self.assertEqual(doc['pages'][0]['text'],'Fresh image text 173')

class PartCountTests(unittest.IsolatedAsyncioTestCase):
 async def test_actual_dispatcher_counts_parts_separately_from_physical_files(self):
  import collect_normalized as m
  from sheets_normalized import prepare
  async def collect(cfg,report,now,limit):
   report['discovered']=2
   return [make_offer('rgo',str(i),'Example','Partner','Public description','https://rgo.ru/membership/loyalty-program/example/',now) for i in range(5)]
  with patch.object(m,'collect_recovered',collect):
   report,rows=await m.one(None,{'id':'rgo','name':'Example','url':'https://rgo.ru/membership/loyalty-program/example/','mode':'recovered'},NOW,500)
  self.assertEqual(report['discovered_items'],2);self.assertEqual(report['discovered'],5)
  prepare({'schema_version':2,'run_id':'part-count-test','observed_at':NOW,'sources':[report],'records':rows})
if __name__=='__main__':unittest.main()
