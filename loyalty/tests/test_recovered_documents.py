"""Changing live file listings, rates and bytes must not require a code edit."""
import hashlib,sys,time,unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).parents[1]))
from recovered_contract import linked_pdf_url,transport_evidence
from recovered_sources import ScopedReader,_collect
from test_recovered_sources import cfg,VTB,NOW,Response
from test_document_text import pdf
from normalized import validate_offer

class LinkedDocumentTests(unittest.TestCase):
 def test_only_new_same_host_public_files_allowed(self):
  good='https://www.vtb.ru/media/new-document-2027.pdf'
  self.assertEqual(linked_pdf_url(good,'af_vtb_rules'),good)
  for u in ['https://www.vtb.ru.evil/new.pdf','http://www.vtb.ru/new.pdf','https://www.vtb.ru/a.pdf?token=x','https://www.vtb.ru/../a.pdf','https://www.vtb.ru/%2e%2e/a.pdf','https://user@www.vtb.ru/a.pdf']:
   with self.assertRaises(ValueError):linked_pdf_url(u,'af_vtb_rules')
 def test_documents_must_be_bound_to_current_listing_before_request(self):
  r=ScopedReader(cfg('af_vtb_rules'),{},time.monotonic()+90)
  u='https://www.vtb.ru/media/new.pdf'
  with patch.object(r.session,'get') as get:
   with self.assertRaises(ValueError):r.read_document(u)
   get.assert_not_called()
  r.bind_document_links([{'url':u},{'url':u+' '},{'url':'https://evil.invalid/e.pdf'}])
  self.assertEqual(r.document_urls,{u})
  r.bind_document_links([{'url':'https://www.vtb.ru/media/later.pdf'}])
  with self.assertRaises(ValueError):r.allowed(u)
  r.__exit__()
 def test_direct_download_records_robots_and_keeps_verified_tls(self):
  from protego import Protego
  r=ScopedReader(cfg('af_vtb_rules'),{},time.monotonic()+90)
  u='https://www.vtb.ru/media/new.pdf';r.bind_document_links([{'url':u}])
  r.policy=Protego.parse('User-agent: *\nDisallow: /media/')
  data=pdf(['Public document rules 13 percent.'])
  with patch.object(r.session,'get',return_value=Response(body=data)) as get:
   received,meta=r.read_document(u)
  self.assertEqual(received,data);self.assertFalse(meta['robots_allows_crawling'])
  self.assertIs(get.call_args.kwargs['verify'],True);r.__exit__()
 def test_actual_collector_discovers_new_names_and_changed_content(self):
  class Reader:
   def __init__(self,*a):self.document_urls=set()
   def __enter__(self):return self
   def __exit__(self,*a):pass
   def read(self,url):return {},VTB.encode()
   def bind_document_links(self,links):self.document_urls={x['url'] for x in links}
   def read_document(self,url):return pdf([Reader.value]),{'robots_allows_crawling':True,'mode':'direct_advertised_public_file_download','http_status':200}
  parent_links=[{'label':'New rules','url':'https://www.vtb.ru/media/never-listed-before.pdf'}]
  outputs=[]
  for value in ('Rules 13 percent for members.','Rules 37 percent with new conditions.'):
   Reader.value=value;report={'errors':[]}
   with patch('recovered_sources.ScopedReader',Reader),patch('recovered_sources.linked_documents',return_value=parent_links):
    rows=_collect(cfg('af_vtb_rules'),report,NOW,500)
   self.assertEqual(len(rows),2);self.assertEqual(report['errors'],[])
   for row in rows:validate_offer(row)
   self.assertIn(value,rows[1]['conditions_text']);outputs.append(rows[1])
  self.assertEqual(outputs[0]['id'],outputs[1]['id'])
  self.assertNotEqual(outputs[0]['content_sha256'],outputs[1]['content_sha256'])
 def test_late_document_failure_keeps_parent_and_successful_pdf(self):
  links=[{'label':'One','url':'https://www.vtb.ru/media/one.pdf'},{'label':'Two','url':'https://www.vtb.ru/media/two.pdf'}]
  class Reader:
   def __init__(self,*a):self.document_urls=set()
   def __enter__(self):return self
   def __exit__(self,*a):pass
   def read(self,url):return {},VTB.encode()
   def bind_document_links(self,items):self.document_urls={x['url'] for x in items}
   def read_document(self,url):
    if url.endswith('two.pdf'):raise RuntimeError('document_http_403')
    return pdf(['Some fresh rules']),{'http_status':200}
  report={'errors':[]}
  with patch('recovered_sources.ScopedReader',Reader),patch('recovered_sources.linked_documents',return_value=links):
   rows=_collect(cfg('af_vtb_rules'),report,NOW,500)
  self.assertEqual(len(rows),2);self.assertEqual(report['errors'][0]['reason'],'document_http_403')
  self.assertEqual([d['status'] for d in rows[0]['details']['linked_document_inventory']],['read','failed'])
if __name__=='__main__':unittest.main()
