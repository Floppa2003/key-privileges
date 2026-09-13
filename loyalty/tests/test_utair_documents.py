"""A public signed redirect is transient transport, never a stored credential."""
import asyncio, json, sys, unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).parents[1]))
try:
 import utair_documents as m
except ImportError:
 m=None
NOW='2026-09-14T00:00:00+00:00'
class DocumentTests(unittest.TestCase):
 def setUp(self): self.assertIsNotNone(m,'Public rule-document collector not implemented')
 def test_download_host_does_not_allow_redirect_to_private_or_unreviewed_origin(self):
  self.assertEqual(m.checked_download_target('https://eu-s3.beelinecloud.ru/docs/a.pdf?X-Amz-Signature=abc'),'https://eu-s3.beelinecloud.ru/docs/a.pdf?X-Amz-Signature=abc')
  for u in ('http://eu-s3.beelinecloud.ru/a.pdf','https://eu-s3.beelinecloud.ru.evil.test/a.pdf','https://user:pass@eu-s3.beelinecloud.ru/a.pdf','https://127.0.0.1/a.pdf'):
   with self.subTest(u=u):
    with self.assertRaises(ValueError):m.checked_download_target(u)
 def test_document_title_and_page_count_are_checked_without_inventing_expiry(self):
  pages=['Поколения Utair - двойные мили\nДля молодежи 16–25 лет. Покупка билета и полет в одном месяце. Промокод UYOUTHWM. Мили действуют три года.']
  r=m.parse_document('JdyRTA',pages,'a'*64,NOW)
  self.assertEqual(r['record_kind'],'program_rules');self.assertEqual(r['source_url'],'https://ut0.ru/JdyRTA')
  self.assertIsNone(r['valid_until']);self.assertIn('UYOUTHWM',r['promo_codes'])
  self.assertEqual(r['details']['pages'][0]['text'],pages[0])
  for ps in ([pages[0].replace('Поколения Utair','Чужая программа')],pages+pages):
   with self.assertRaises(ValueError):m.parse_document('JdyRTA',ps,'a'*64,NOW)
 def test_same_pdf_merges_aliases_but_not_different_content_with_same_title(self):
  a=m.parse_document('TlYigt',['Консьерж-сервис по бронированию и переоформлению билетов без сборов\nПравила Platinum'*3,'Вторая страница правил '*10],'a'*64,NOW)
  b=m.parse_document('bFwqtV',['Консьерж-сервис по бронированию и переоформлению билетов без сборов\nПравила Platinum'*3,'Вторая страница правил '*10],'a'*64,NOW)
  rs=m.merge_documents([a,b]);self.assertEqual(len(rs),1);self.assertEqual(len(rs[0]['details']['public_aliases']),2)
  b['details']['document_sha256']='b'*64
  self.assertEqual(len(m.merge_documents([a,b])),2)
 def test_document_cannot_be_relabelled_as_checked_partner_discount(self):
  from normalized import content_hash,validate_offer
  r=m.parse_document('JdyRTA',['Поколения Utair - двойные мили\nПубличные условия для участников программы.'*3],'a'*64,NOW)
  r['record_kind']='partner_offer';r['content_sha256']=content_hash(r)
  with self.assertRaises(ValueError):validate_offer(r)
class CollectionTests(unittest.IsolatedAsyncioTestCase):
 async def asyncSetUp(self):self.assertIsNotNone(m,'Public rule-document collector not implemented')
 async def test_late_document_refusal_preserves_previous_data_and_hides_signed_url(self):
  class Client:
   async def read(self,url,**kwargs):return '<a href="https://ut0.ru/JdyRTA">Правила</a><a href="https://ut0.ru/ZNxBpY">Правила</a>'
  cfg={'id':'utair_rule_documents','url':'https://media.utair.ru/status'};report={'errors':[]}
  first=m.parse_document('JdyRTA',['Поколения Utair - двойные мили\nПубличные условия для участников программы.'*3],'a'*64,NOW)
  with patch.object(m,'DOCUMENTS',{k:m.DOCUMENTS[k] for k in ('JdyRTA','ZNxBpY')}),patch.object(m,'fetch_document',side_effect=[first,RuntimeError('http_403 secret-url')]):
   rows=await m.collect_documents(Client(),cfg,report,NOW,100)
  self.assertEqual(len(rows),1);self.assertTrue(report['errors']);self.assertNotIn('secret-url',json.dumps(report))
if __name__=='__main__':unittest.main()

class SparseTailTests(unittest.TestCase):
 def test_reviewed_sparse_table_tail_is_preserved_not_mistaken_for_scan(self):
  pages=['Бизнес-такси Яндекс Ultima или бизнес-трансфер i’way для поездки в аэропорт\n'+'Правила транспортной услуги. '*10,'Вторая страница условий. '*10,'Третья страница условий. '*10,'Глубина (см) 22 24 26 \n']
  self.assertEqual(m.parse_document('hXfkMF',pages,'a'*64,NOW)['details']['pages'][3]['text'],pages[3])
  pages[3]='Неизвестно 100'
  with self.assertRaises(ValueError):m.parse_document('hXfkMF',pages,'a'*64,NOW)

class DispatcherTests(unittest.IsolatedAsyncioTestCase):
 async def test_main_dispatcher_publishes_supplemental_rules_not_html_fallback(self):
  import collect_normalized as c
  from sheets_normalized import prepare
  class Client:
   def __init__(self,b,u):self.policy=None
   async def __aenter__(self):return self
   async def __aexit__(self,*a):pass
   async def robots(self):self.policy=True
   async def read(self,u,**kw):return '<a href="https://ut0.ru/JdyRTA">Правила</a>'
  record=m.parse_document('JdyRTA',['Поколения Utair - двойные мили\nПубличные условия для участников программы.'*3],'a'*64,NOW)
  with patch.object(c,'PublicSource',Client),patch.object(m,'DOCUMENTS',{'JdyRTA':m.DOCUMENTS['JdyRTA']}),patch.object(m,'fetch_document',return_value=record):
   report,rows=await c.one(None,{'id':'utair_rule_documents','name':'Utair rules','mode':'utair_documents','url':m.ROOT},NOW,100)
  self.assertEqual(report['status'],'ok');self.assertEqual(len(rows),1)
  self.assertEqual(len(prepare({'schema_version':2,'run_id':'test-utair','observed_at':NOW,'sources':[report],'records':rows})['parser_offers']),1)
