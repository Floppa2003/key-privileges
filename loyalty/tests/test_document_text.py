"""PDF and discovery mutations use generated input, never hardcoded live answers."""
import copy,hashlib,io,sys,unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).parents[1]))
from document_text import extract_pdf,document_records,page_groups,validate_document_record
from normalized import validate_offer,content_hash
NOW='2026-09-14T15:00:00+00:00'

def pdf(values,title='Live source title'):
 from pypdf import PdfWriter
 from pypdf.generic import DictionaryObject,NameObject,DecodedStreamObject
 writer=PdfWriter();writer.add_metadata({'/Title':title})
 for value in values:
  page=writer.add_blank_page(width=600,height=800)
  font=DictionaryObject({NameObject('/Type'):NameObject('/Font'),NameObject('/Subtype'):NameObject('/Type1'),NameObject('/BaseFont'):NameObject('/Helvetica')})
  page[NameObject('/Resources')]=DictionaryObject({NameObject('/Font'):DictionaryObject({NameObject('/F1'):writer._add_object(font)})})
  stream=DecodedStreamObject();stream.set_data(('BT /F1 12 Tf 50 700 Td ('+value.replace('\\','\\\\').replace('(','\\(').replace(')','\\)')+') Tj ET').encode('latin1'))
  page[NameObject('/Contents')]=writer._add_object(stream)
 out=io.BytesIO();writer.write(out);return out.getvalue()

def make_rows(doc,url='https://rgo.ru/upload/rules-new.pdf'):
 return document_records('rgo','pdf:test','RGO',None,url,NOW,doc,parent_source='https://rgo.ru/membership/loyalty-program/')

class GenericPdfTests(unittest.TestCase):
 def test_new_title_values_and_page_count_are_inputs_not_acceptance_constants(self):
  for pages,title in [(['Discount 13 percent. Rules for members.'],'First'),(['Discount 27 percent. New rules.','22 24 26','Additional page with changed requirements.'],'Other title')]:
   with patch('document_text.ocr_page',side_effect=AssertionError('Native text must not use OCR')):
    doc=extract_pdf(pdf(pages,title))
   self.assertEqual(doc['page_count'],len(pages));self.assertEqual(doc['title'],title)
   self.assertEqual(doc['errors'],[]);self.assertEqual([p['text'] for p in doc['pages']],pages)
   for row in make_rows(doc):validate_offer(row)
 def test_source_update_changes_text_hash_not_same_url_identity(self):
  a=make_rows(extract_pdf(pdf(['Discount 12 percent for members.'])))[0]
  b=make_rows(extract_pdf(pdf(['Discount 31 percent and new rules.'])))[0]
  self.assertEqual(a['id'],b['id']);self.assertNotEqual(a['content_sha256'],b['content_sha256'])
  self.assertIn('31 percent',b['conditions_text']);self.assertNotIn('12 percent',b['conditions_text'])
 def test_single_sparse_page_is_retained_without_manual_tail_whitelist(self):
  self.assertEqual(extract_pdf(pdf(['22 24 26']))['pages'][0]['text'],'22 24 26')
 def test_empty_native_layer_uses_ocr_once_and_keeps_warning(self):
  with patch('document_text.ocr_page',return_value=('Changed image text 735',{'minimum_numeric_confidence':77})) as ocr:
   doc=extract_pdf(pdf(['']))
  self.assertEqual(ocr.call_count,1);row=make_rows(doc)[0]
  self.assertEqual(row['source_status'],'public_rules_ocr_unverified')
  self.assertIn('735',row['conditions_text']);self.assertIn('ocr_text_unverified_no_manual_corrections',row['warnings'])
 def test_unavailable_ocr_does_not_invent_an_old_transcription(self):
  with patch('document_text.ocr_page',side_effect=RuntimeError('pdf_ocr_engine_unavailable')):
   doc=extract_pdf(pdf(['']))
  self.assertTrue(doc['errors']);r=make_rows(doc)[0]
  self.assertEqual(r['record_kind'],'source_observation');self.assertEqual(r['benefit_text'],'')
 def test_changed_page_text_cannot_be_hidden_by_rehashing_the_record(self):
  r=make_rows(extract_pdf(pdf(['Rules for this public document.'])))[0]
  r['details']['pages'][0]['text']='Fabricated benefit 99 percent'
  r['content_sha256']=content_hash(r)
  with self.assertRaises(ValueError):validate_offer(r)
 def test_dense_document_splits_without_truncation(self):
  value='Document word '*5000
  pages=[{'number':1,'text':value,'sha256':hashlib.sha256(value.encode()).hexdigest(),'method':'native_pdf_text'}]
  groups=page_groups(pages)
  self.assertGreater(len(groups),1)
  self.assertEqual(''.join(p['text'] for g in groups for p in g),value)
 def test_non_pdf_and_oversized_fail(self):
  with self.assertRaises(ValueError):extract_pdf(b'<html>Blocked</html>')
  with self.assertRaises(ValueError):extract_pdf(b'%PDF-'+b'0'*5_000_000)
 def test_historical_manual_profile_is_evidence_only_in_common_projection(self):
  from unified_normalization import normalize_record
  raw={'id':'x','program':'RGO','partner':'Example','title':'Legacy review','kind':'partner_offer','origin':'parser_offers','privacy':'public',
   'benefit':'Скидка 99%','conditions':'','redemption':'','details':{'extraction_method':'digest_bound_visual_review'}}
  r=normalize_record(raw,as_of='2026-09-14')
  self.assertEqual(r['benefits'],[]);self.assertEqual(r['quality']['level'],'evidence_only')
if __name__=='__main__':unittest.main()
