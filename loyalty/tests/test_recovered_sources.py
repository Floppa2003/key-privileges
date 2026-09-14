"""Public access recovery: exact bounds, evidence identity, and no trust promotion."""
import copy,json,sys,time,unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).parents[1]))
from recovered_contract import (SOURCES,CA_FILES,HTTP_WARNING,collection_url,http_url,
    checked_config,transport_evidence)
from recovered_sources import (ScopedReader,public_post_record,collect_loyals,parse_bank_page)
from normalized import validate_offer,content_hash,canonical_url
from sheets_normalized import prepare
NOW='2026-09-14T13:00:00+00:00'
def cfg(sid='loyals'):
 s=SOURCES[sid];return {'id':sid,'url':s['url'],'access_profile':s['profile'],'name':sid,'mode':'recovered'}
def post(i=1,body='<p>Скидка 10% на заказ от 2000 рублей. Не суммируется с другими скидками.</p>'):
 return {'id':i,'status':'publish','type':'post','title':{'rendered':'Партнер'},
  'content':{'protected':False,'rendered':body},'link':f'https://loyals.ru/?p={i}',
  'date_gmt':'2021-03-24T00:00:00','modified_gmt':'2025-08-12T00:00:00'}
def record(p=None):
 return public_post_record(p or post(),cfg(),NOW,collection_url(1),0,'a'*64)
def rehash(r):r['content_sha256']=content_hash(r);return r
class ContractTests(unittest.TestCase):
 def test_default_transport_still_rejects_http(self):
  from model import clean_url
  with self.assertRaises(ValueError):clean_url('http://loyals.ru/')
 def test_only_exact_anonymous_http_api_allowed(self):
  for u in ['http://loyals.ru/wp-admin/','http://loyals.ru/wp-json/wp/v2/users',
     'http://loyals.ru:80/','http://loyals.ru.evil/','http://user@loyals.ru/',
     collection_url(1)+'&password=x',collection_url(1)+'#fake',collection_url(1)+'&page=2',
     collection_url(1).replace('page=1','page=11')]:
   with self.subTest(url=u),self.assertRaises(ValueError):http_url(u)
 def test_config_does_not_inherit_http_for_other_source(self):
  for bad in [{**cfg(),'url':'https://loyals.ru/'},{**cfg(),'access_profile':'default'},
              {**cfg('af_vtb_rules'),'url':'https://www.vtb.ru/another/'}]:
   with self.assertRaises(ValueError):checked_config(bad)
 def test_source_is_actual_collection_not_unfetched_card(self):
  r=record();self.assertEqual(r['source_url'],collection_url(1));self.assertEqual(r['locator'],'/0')
  self.assertIsNone(r['benefit_url']);self.assertFalse(r['details']['publisher_canonical_url_fetched'])
 def test_public_dates_never_become_offer_dates(self):
  r=record();self.assertIsNone(r['valid_from']);self.assertIsNone(r['valid_until'])
  self.assertEqual(r['details']['source_modified_at_gmt'],'2025-08-12T00:00:00')
 def test_empty_published_post_is_preserved_not_promoted(self):
  r=record(post(body=''));self.assertEqual(r['record_kind'],'source_observation')
  self.assertFalse(r['rates']);self.assertFalse(r['benefit_text']);self.assertTrue(r['details']['empty_body'])
 def test_private_protected_and_wrong_type_rejected(self):
  for p in [{**post(),'status':'private'},{**post(),'type':'page'},
            {**post(),'content':{'protected':True,'rendered':'secret'}},{**post(),'id':True}]:
   with self.assertRaises(ValueError):record(p)
 def test_status_scheme_and_trust_cannot_be_promoted(self):
  for key,val in [('source_status','published'),('benefit_url','https://loyals.ru/?p=1'),
                  ('source_url',collection_url(1).replace('http:','https:')),('valid_until','2030-01-01')]:
   r=record();r[key]=val
   with self.assertRaises(ValueError):validate_offer(rehash(r))
  r=record();r['details']['transport']['authenticated']=True
  with self.assertRaises(ValueError):validate_offer(rehash(r))
  r=record();r['warnings'].remove(HTTP_WARNING)
  with self.assertRaises(ValueError):validate_offer(rehash(r))
 def test_source_body_cannot_diverge_from_public_post(self):
  r=record();r['details']['public_post']['content']['rendered']='Different body'
  with self.assertRaises(ValueError):validate_offer(rehash(r))
 def test_stable_post_id_independent_of_page(self):
  a=record();b=public_post_record(post(),cfg(),NOW,collection_url(2),12,'b'*64)
  self.assertEqual(a['id'],b['id']);self.assertNotEqual(a['content_sha256'],b['content_sha256'])
 def test_single_empty_post_bundle_can_be_published_as_evidence(self):
  r=record(post(body=''));s={'source_id':'loyals','name':'Loyals','root':cfg()['url'],
   'status':'ok','normalized':1,'discovered':1,'failed':0,'errors':[],'region':None,
   'coverage':'advertised collection','observed_at':NOW}
  result=prepare({'schema_version':2,'run_id':'test:1','observed_at':NOW,'records':[r],'sources':[s]})
  self.assertEqual(len(result['parser_offers']),1)
class FakeReader:
 def __init__(self,pages,total=None,fail_page=None):self.pages=pages;self.total=total;self.fail_page=fail_page;self.calls=[]
 def read(self,u):
  self.calls.append(u)
  if u==cfg()['url']:
   return {},b'<link rel="https://api.w.org/" href="https://loyals.ru/wp-json/"><a href="https://loyals.ru/?p=1">Partner</a>'
  from urllib.parse import parse_qs,urlsplit
  n=int(parse_qs(urlsplit(u).query)['page'][0])
  if n==self.fail_page:raise RuntimeError('http_403')
  total=self.total if self.total is not None else sum(len(p) for p in self.pages)
  return {'X-WP-Total':str(total),'X-WP-TotalPages':str(len(self.pages))},json.dumps(self.pages[n-1]).encode()
class PaginationTests(unittest.TestCase):
 def collect(self,reader,limit=500):
  r={'errors':[]};rows=collect_loyals(reader,cfg(),r,NOW,limit);return rows,r,json.loads(r['coverage'])
 def test_all_pages_and_empty_post_kept(self):
  rows,r,c=self.collect(FakeReader([[post()],[post(2,'')]]))
  self.assertEqual(len(rows),2);self.assertFalse(r['errors']);self.assertTrue(c['complete_api_collection'])
 def test_failure_keeps_previous_observation(self):
  rows,r,c=self.collect(FakeReader([[post()],[post(2)]],fail_page=2))
  self.assertEqual(len(rows),1);self.assertFalse(c['complete_api_collection']);self.assertTrue(r['errors'])
 def test_duplicate_id_partial_not_false_complete(self):
  rows,r,c=self.collect(FakeReader([[post()],[post()]]))
  self.assertEqual(len(rows),1);self.assertTrue(r['errors']);self.assertFalse(c['complete_api_collection'])
 def test_post_limit_is_explicit(self):
  rows,r,c=self.collect(FakeReader([[post(),post(2)]]),1)
  self.assertEqual(len(rows),1);self.assertTrue(r['errors']);self.assertEqual(c['stop_reason'],'record_limit')
 def test_missing_homepage_id_reported(self):
  rows,r,c=self.collect(FakeReader([[post(2)]]))
  self.assertTrue(r['errors']);self.assertEqual(c['homepage_ids_missing'],[1])
 def test_inconsistent_advertised_count_is_not_complete(self):
  rows,r,c=self.collect(FakeReader([[post()]],total=7))
  self.assertTrue(r['errors']);self.assertFalse(c['complete_api_collection'])
 def test_discovery_does_not_execute_unadvertised_api(self):
  reader=FakeReader([[post()]])
  reader.read=lambda u:({},b'<html>No API here</html>')
  with self.assertRaises(ValueError):self.collect(reader)
VTB='''<h1>Дебетовая карта Привилегия Аэрофлот</h1><section class="xNativeSection">Дебетовая карта Привилегия Аэрофлот</section><section class="xNativeSection">Как начисляются мили по карте ВТБ. За каждые 90 ₽ вы получите 3 мили. </section><section id="how" class="xNativeSection">Прайм Аэрофлот 4 мили за 100 ₽</section><section id="premium" class="xNativeSection">Премиум-обслуживание при выполнении условий, или комиссия 3990 ₽ в месяц</section>'''
URALSIB='''<h1>Приветственные баллы РЖД за оформление карты</h1><section id="textBlock">В период с 01.09.2023 по 15.03.2024 оформить заявку на карту. Максимум 14000 баллов. Покупки от 3000 рублей.</section><footer>Кешбэк 35%</footer>'''
NSPK='''<div class="pages-press-center-details-article-slug">16 июля 2026. Держатели ЕКП смогут экономить: кешбэк 5%. Необходимо согласиться с условиями на vamprivet.ru.</div>'''
class BankTests(unittest.TestCase):
 def test_vtb_related_product_not_mapped_to_main_card(self):
  r=parse_bank_page('af_vtb_rules',VTB,NOW)
  self.assertNotIn('Прайм',r['conditions_text']);self.assertEqual(r['details']['earning_rules'][0]['basis_amount'],'90')
  self.assertIsNone(r['valid_until'])
 def test_uralsib_original_period_is_archived(self):
  r=parse_bank_page('uralsib_rzd_rules',URALSIB,NOW)
  self.assertEqual(r['valid_from'],'2023-09-01');self.assertEqual(r['valid_until'],'2024-03-15')
  self.assertEqual(r['validity_status'],'expired_by_published_end');self.assertNotIn('35%',r['conditions_text'])
 def test_nspk_is_supplementary_not_complete_rules(self):
  r=parse_bank_page('nspk_ekp_rules',NSPK,NOW)
  self.assertEqual(r['source_status'],'public_announcement_not_full_rules');self.assertIsNone(r['benefit_url'])
  self.assertIsNone(r['valid_until'])
 def test_bank_rules_cannot_be_promoted_to_standalone_offer(self):
  r=parse_bank_page('af_vtb_rules',VTB,NOW);r['record_kind']='partner_offer'
  with self.assertRaises(ValueError):validate_offer(rehash(r))
 def test_missing_or_ambiguous_scope_rejected(self):
  for raw in [NSPK+NSPK,'<p>Other bank has cashback</p>']:
   with self.assertRaises(ValueError):parse_bank_page('nspk_ekp_rules',raw,NOW)
 def test_uralsib_missing_period_not_assumed(self):
  with self.assertRaises(ValueError):parse_bank_page('uralsib_rzd_rules',URALSIB.replace('15.03.2024','later'),NOW)
class Response:
 def __init__(self,status=200,body=b'OK',headers=None):self.status_code=status;self.body=body;self.headers=headers or {}
 def __enter__(self):return self
 def __exit__(self,*a):pass
 def iter_content(self,n):yield self.body
class ReaderTests(unittest.TestCase):
 def reader(self,sid):return ScopedReader(cfg(sid),{},time.monotonic()+90)
 def test_host_scope_before_network(self):
  r=self.reader('af_vtb_rules')
  with patch.object(r.session,'get') as get:
   with self.assertRaises(ValueError):r._get('https://evil.example/')
   get.assert_not_called()
  r.__exit__()
 def test_certificate_download_cannot_redirect(self):
  r=self.reader('af_vtb_rules')
  with patch.object(r.session,'get',return_value=Response(302,headers={'Location':'https://evil.example/'})):
   with self.assertRaisesRegex(RuntimeError,'unexpected_source_redirect'):r._get(CA_FILES[0][0],ca_download=True)
  r.__exit__()
 def test_tls_failure_not_retried_or_disabled(self):
  import requests
  r=self.reader('af_vtb_rules')
  with patch.object(r.session,'get',side_effect=requests.exceptions.SSLError('bad cert')) as get:
   with self.assertRaisesRegex(RuntimeError,'certificate'):r._get(cfg('af_vtb_rules')['url'])
   self.assertEqual(get.call_count,1);self.assertIs(get.call_args.kwargs['verify'],True)
  r.__exit__()
 def test_no_http_follow_to_invalid_https(self):
  r=self.reader('loyals')
  with patch.object(r.session,'get',return_value=Response(302,headers={'Location':'https://loyals.ru/'})) as get:
   with self.assertRaisesRegex(RuntimeError,'unexpected_source_redirect'):r._get(cfg()['url'])
   self.assertEqual(get.call_count,1)
  r.__exit__()
 def test_uralsib_same_url_redirect_reuses_session_and_verified_tls(self):
  r=self.reader('uralsib_rzd_rules');u=cfg('uralsib_rzd_rules')['url']
  with patch('recovered_sources.time.sleep'),patch.object(r.session,'get',side_effect=[Response(302,headers={'Location':u}),Response()]) as get:
   self.assertEqual(r._get(u)[0],200);self.assertEqual(get.call_count,2)
   self.assertTrue(all(c.kwargs['verify'] is True for c in get.call_args_list))
  r.__exit__()
 def test_retry_after_stops(self):
  r=self.reader('loyals')
  with patch.object(r.session,'get',return_value=Response(503,headers={'Retry-After':'60'})) as get:
   with self.assertRaisesRegex(RuntimeError,'rate_limited'):r._get(cfg()['url'])
   self.assertEqual(get.call_count,1)
  r.__exit__()
 def test_http_data_exceeds_size_limit_rejected(self):
  r=self.reader('loyals')
  with patch('recovered_sources.MAX_BYTES',2),patch.object(r.session,'get',return_value=Response(body=b'123')):
   with self.assertRaisesRegex(RuntimeError,'too_large'):r._get(cfg()['url'])
  r.__exit__()
if __name__=='__main__':unittest.main()
