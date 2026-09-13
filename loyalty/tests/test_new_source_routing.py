"""Exercise the production dispatcher, not just standalone mapper helpers."""
import json,sys,unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).parents[1]))
import collect_normalized as collector
import selection_source
from test_selection_source import snapshot,NOW
from test_tier_sources import URAL
class PublicPage:
 def __init__(self,browser,url):self.browser=browser;self.url=url;self.policy=None
 async def __aenter__(self):return self
 async def __aexit__(self,*args):return False
 async def robots(self):self.policy=True
 async def read(self,url,**kwargs):return URAL
class RoutingTests(unittest.IsolatedAsyncioTestCase):
 def test_registry_has_independent_sources_not_relabelled_bolshe(self):
  cfg=json.loads((Path(__file__).parents[1]/'sources_normalized.json').read_text())
  modes={c['id']:c['mode'] for c in cfg}
  self.assertEqual(modes.get('t2_selection_public'),'selection')
  self.assertEqual(modes.get('utair_tiers'),'utair_tiers')
  self.assertEqual(modes.get('ural_tiers'),'ural_tiers')
  self.assertEqual(modes['t2_bolshe'],'t2')
 async def test_actual_dispatcher_returns_selection_records(self):
  async def read(client,key,limit):return [snapshot()],{'discovered':1,'errors':[]}
  cfg={'id':'t2_selection_public','mode':'selection','name':'T2 Selection','url':'https://msk.t2.ru/bolshe/selection'}
  with patch.object(collector,'PublicSource',PublicPage),patch.object(selection_source,'read_region_previews',read):
   report,rows=await collector.one(None,cfg,NOW,500)
  self.assertEqual(report['status'],'ok');self.assertEqual(len(rows),1)
  self.assertEqual(rows[0]['source_id'],'t2_selection_public');self.assertEqual(report['normalized'],1)
 async def test_actual_dispatcher_returns_three_ural_tiers(self):
  cfg={'id':'ural_tiers','mode':'ural_tiers','name':'Крылья уровни','url':'https://www.uralairlines.ru/wings_rules/'}
  with patch.object(collector,'PublicSource',PublicPage):report,rows=await collector.one(None,cfg,NOW,500)
  self.assertEqual(len(rows),3);self.assertEqual(report['normalized'],3);self.assertEqual(report['status'],'ok')
