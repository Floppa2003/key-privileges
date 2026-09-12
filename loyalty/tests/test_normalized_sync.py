import copy,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parents[1]))
from normalized import make_offer
from sheets_normalized import prepare
NOW='2026-09-12T15:00:00+00:00'
def bundle():
 r=make_offer('s7','s','S7','Brand','Скидка 10%','https://marketplace.s7.ru/partners/offer/s',NOW)
 return {'schema_version':2,'run_id':'42:1','observed_at':NOW,'records':[r],
  'sources':[{'source_id':'s7','name':'S7','root':'https://marketplace.s7.ru/partners/category/retail','status':'ok','discovered':1,'normalized':1,'failed':0,'coverage':'catalog_state','region':None,'errors':[],'observed_at':NOW}]}
class PublicationTests(unittest.TestCase):
 def test_normalized_payload_has_only_new_managed_tabs(self):
  rows=prepare(bundle());self.assertEqual(set(rows),{'parser_offers','parser_coverage'})
  self.assertEqual(len(rows['parser_offers'][0]),25)
  self.assertEqual(rows['parser_offers'][0][2],'Brand');self.assertEqual(rows['parser_offers'][0][-1],'42:1')
 def test_duplicate_or_wrong_count_prevents_publication(self):
  d=bundle();d['records']*=2
  with self.assertRaises(ValueError):prepare(d)
  d=bundle();d['sources'][0]['normalized']=2
  with self.assertRaises(ValueError):prepare(d)
 def test_failed_source_has_diagnostics_but_does_not_delete_old_data(self):
  d=bundle();d['records']=[];d['sources'][0].update(status='blocked',normalized=0,failed=1)
  out=prepare(d);self.assertEqual(out.get('parser_offers'),[]);self.assertEqual(len(out.get('parser_coverage',[])),1)
 def test_empty_bundle_cannot_claim_success(self):
  with self.assertRaises(ValueError):prepare({'schema_version':2,'run_id':'x','observed_at':NOW,'records':[],'sources':[]})
if __name__=='__main__':unittest.main()
