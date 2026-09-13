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
  # Existing 48 plus the explicitly reviewed 23 rules; distinct real identities.
  extras=[{'id':sid,'name':c['title'],'url':c['url']} for sid,c in CONFIG.items() if sid not in {x['id'] for x in configured}]
  configs=configured+extras
  d['sources']=[{**base,'source_id':c['id'],'name':c['name'],'root':c['url'],
   'status':'ok' if c['id']=='s7' else 'failed','discovered':1 if c['id']=='s7' else 0,
   'normalized':1 if c['id']=='s7' else 0} for c in configs]
  out=prepare(d)
  self.assertEqual(len(out['parser_coverage']),71);self.assertEqual(len(out['parser_offers']),1)
 def test_payload_above_the_bounded_source_budget_is_refused(self):
  d=bundle();d['sources']=[{**d['sources'][0],'source_id':'x'+str(i)} for i in range(129)]
  with self.assertRaises(ValueError):prepare(d)
