"""The configured production path must publish rule records, not merely read HTML."""
import json,sys,unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).parents[1]))
import collect_normalized as collector
from known_rules import CONFIG
from test_known_rules import RETAIL,NOW
from sheets_normalized import prepare
from test_normalized_sync import bundle

class PublicPage:
 def __init__(self,browser,url):self.url=url;self.policy=None
 async def __aenter__(self):return self
 async def __aexit__(self,*_):return False
 async def robots(self):self.policy=True
 async def read(self,url,**kwargs):
  if url!=self.url:raise AssertionError('Unexpected URL')
  return RETAIL

class KnownRoutingTests(unittest.IsolatedAsyncioTestCase):
 async def test_real_dispatcher_returns_program_rules_and_can_prepare_publication(self):
  c={'id':'af_bootwood_rules','name':'Bootwood rules','url':CONFIG['af_bootwood_rules']['url'],'mode':'known_rules'}
  with patch.object(collector,'PublicSource',PublicPage):report,rows=await collector.one(None,c,NOW,500)
  self.assertEqual(report['status'],'ok');self.assertEqual(report['normalized'],1)
  self.assertEqual(rows[0]['record_kind'],'program_rules')
  d={'schema_version':2,'run_id':'test:1','observed_at':NOW,'sources':[report],'records':rows}
  out=prepare(d);self.assertEqual(out['parser_offers'][0][5],'program_rules')
 def test_more_than_fifty_legitimate_source_reports_are_not_dropped(self):
  d=bundle();base=d['sources'][0]
  configured=json.loads((Path(__file__).parents[1]/'sources_normalized.json').read_text())
  # Distinct configured identities; the test guards against the old 50-report cap.
  extras=[{'id':sid,'name':c['title'],'url':c['url']} for sid,c in CONFIG.items() if sid not in {x['id'] for x in configured}]
  configs=configured+extras
  d['sources']=[{**base,'source_id':c['id'],'name':c['name'],'root':c['url'],
   'status':'ok' if c['id']=='s7' else 'failed','discovered':1 if c['id']=='s7' else 0,
   'normalized':1 if c['id']=='s7' else 0} for c in configs]
  out=prepare(d)
  self.assertGreater(len(configs),50)
  self.assertEqual(len(out['parser_coverage']),len(configs));self.assertEqual(len(out['parser_offers']),1)
 def test_payload_above_the_bounded_source_budget_is_refused(self):
  d=bundle();d['sources']=[{**d['sources'][0],'source_id':'x'+str(i)} for i in range(129)]
  with self.assertRaises(ValueError):prepare(d)

SIM_HTML='''<div class="article-content">Замена SIM. Курьерская доставка SIM-карты. Стоимость услуги – 200 руб. Дополнительно оплачивается замена SIM-карты – 100 руб. Для участников программы T2 Selection услуга предоставляется бесплатно. На 24 часа ограничиваются SMS.</div>'''
class DelayedArticle:
 def __init__(self,url,redirect=False):self.url=url;self.ready=False;self.redirect=redirect
 async def wait_for_function(self,script,*,arg,timeout):
  if arg!={'selector':'.article-content','text':'Дополнительно оплачивается замена SIM-карты'} or timeout!=8000:
   raise AssertionError('Changed the reviewed content readiness contract')
  self.ready=True
  if self.redirect:self.url='https://msk.t2.ru/login'
 async def content(self):return SIM_HTML if self.ready else '<div class="article-content">Загрузка</div>'
class DelayedSimSource(PublicPage):
 redirect=False
 def __init__(self,browser,url):super().__init__(browser,url);self.page=DelayedArticle(url,self.redirect)
 async def read(self,url,**kwargs):
  if url!=self.url or kwargs!={'render':True}:raise AssertionError('Expected the public rendered SIM page')
  return await self.page.content()
class SimReadinessTests(unittest.IsolatedAsyncioTestCase):
 async def run_source(self,cls):
  c={'id':'t2_sim_rules','name':'SIM rules','url':CONFIG['t2_sim_rules']['url'],'mode':'known_rules'}
  with patch.object(collector,'PublicSource',cls):return await collector.one(None,c,NOW,500)
 async def test_late_article_is_read_before_extraction_not_dropped_as_missing_rules(self):
  report,rs=await self.run_source(DelayedSimSource)
  self.assertEqual(report['status'],'ok');self.assertEqual(len(rs),1)
  self.assertEqual(rs[0]['details']['fees']['replacement_rub'],'100')
  self.assertEqual(rs[0]['details']['fees']['delivery_selection_rub'],'0')
 async def test_readiness_redirect_never_publishes_content_from_another_page(self):
  class Redirected(DelayedSimSource):redirect=True
  report,rs=await self.run_source(Redirected)
  self.assertEqual(rs,[]);self.assertEqual(report['status'],'failed')
