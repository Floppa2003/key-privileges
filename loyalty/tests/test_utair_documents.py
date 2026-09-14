"""Discover fresh shortlinks and content without a snapshot-specific registry."""
import sys,unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).parents[1]))
import utair_documents as m
from document_text import extract_pdf,document_records
from test_document_text import pdf,NOW

def record(key='NewKey1',value='New document rules'):
 doc=extract_pdf(pdf([value]))
 return document_records('utair_rule_documents','document:'+key,'Utair Status','Utair','https://ut0.ru/'+key,NOW,doc,parent_source=m.ROOT,parent_sha256='a'*64)

class DocumentTests(unittest.TestCase):
 def test_new_unregistered_links_are_discovered_and_duplicates_removed(self):
  rs=m.discover_documents('<a href="https://ut0.ru/NewKey1">New rules</a><a href="https://ut0.ru/NewKey2">Other rules</a><a href="https://ut0.ru/NewKey1">PDF</a>')
  self.assertEqual([r['key'] for r in rs],['NewKey1','NewKey2'])
  self.assertEqual(rs[0]['labels'],['New rules','PDF'])
 def test_invalid_shortlinks_are_not_requested(self):
  for u in ('https://ut0.ru/a?token=secret','https://ut0.ru/a/b','http://ut0.ru/a','https://user:pass@ut0.ru/a'):
   with self.assertRaises(ValueError):m.checked_shortlink(u)
 def test_transient_target_host_stays_bounded(self):
  self.assertEqual(m.checked_download_target('https://eu-s3.beelinecloud.ru/docs/a.pdf?X-Amz-Signature=abc'),'https://eu-s3.beelinecloud.ru/docs/a.pdf?X-Amz-Signature=abc')
  for u in ('https://evil.example/a.pdf','https://eu-s3.beelinecloud.ru.evil/a.pdf','http://eu-s3.beelinecloud.ru/a.pdf'):
   with self.assertRaises(ValueError):m.checked_download_target(u)
 def test_new_document_identity_and_values_are_not_whitelisted(self):
  r=record('BrandNew2027','Changed rules 432')[0]
  self.assertIn('432',r['conditions_text']);self.assertEqual(r['source_url'],'https://ut0.ru/BrandNew2027')
 def test_identical_aliases_merge_but_different_text_does_not(self):
  a=record('NewKey1');b=record('NewKey2')
  rs=m.merge_documents(a+b);self.assertEqual(len(rs),1);self.assertEqual(len(rs[0]['details']['public_aliases']),2)
  self.assertEqual(len(m.merge_documents(a+record('NewKey3','Changed content'))),2)
class CollectionTests(unittest.IsolatedAsyncioTestCase):
 async def test_late_refusal_preserves_live_rows_and_sanitizes_error(self):
  class Client:
   async def read(self,*a,**k):return '<a href="https://ut0.ru/NewKey1">Rules</a><a href="https://ut0.ru/NewKey2">Rules</a>'
  report={'errors':[]}
  with patch.object(m,'fetch_document',side_effect=[record(),RuntimeError('secret signed URL')]):
   rs=await m.collect_documents(Client(),{'id':'utair_rule_documents','url':m.ROOT},report,NOW,500)
  self.assertEqual(len(rs),1);self.assertTrue(report['errors']);self.assertNotIn('secret',str(report))
if __name__=='__main__':unittest.main()
