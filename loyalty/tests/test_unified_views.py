import copy,hashlib,json,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parents[1]))
try:
 from unified_views import prepare_views, retire_missing, SCHEMAS
except ImportError:prepare_views=retire_missing=SCHEMAS=None
from test_unified_normalization import record
from unified_normalization import normalize_inputs
class ViewTests(unittest.TestCase):
 def setUp(self):self.assertIsNotNone(prepare_views,'Unified views are not implemented')
 def test_every_row_matches_declared_schema(self):
  result=normalize_inputs([record()],as_of='2026-09-14');views=prepare_views(result)
  for key,rows in views.items():
   for row in rows:self.assertEqual(len(row),len(SCHEMAS[key]));self.assertTrue(all(isinstance(x,str) for x in row))
 def test_unobserved_component_retired_not_claimed_expired(self):
  old=[['ID','data','state','snapshot'],['x','old','current','old-snapshot']]
  rows=retire_missing(old,[['y','new','current','new-snapshot']],4)
  self.assertEqual(rows,[['y','new','current','new-snapshot'],['x','old','retired_from_normalization','old-snapshot']])
 def test_retiring_does_not_modify_previous_input(self):
  old=[['ID','data','state','snapshot'],['x','old','current','s','manual']];before=copy.deepcopy(old)
  retire_missing(old,[],4);self.assertEqual(old,before)
 def test_same_snapshot_is_deterministic(self):
  r=normalize_inputs([record()],as_of='2026-09-14')
  self.assertEqual(prepare_views(r),prepare_views(copy.deepcopy(r)))
 def test_numeric_rule_release_does_not_reuse_preceding_generation(self):
  r=normalize_inputs([record()],as_of='2026-09-14');views=prepare_views(r)
  # Reproduce the published 1.0.2 generation contract independently. Changing
  # semantics must invalidate it even when source inputs and as_of are identical.
  previous=hashlib.sha256(json.dumps([r['audit']['source_snapshot_sha256'],r['as_of'],'1.0.2'],
      ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()
  generations={row[-1] for rows in views.values() for row in rows}
  self.assertEqual(len(generations),1)
  self.assertNotIn(previous,generations)
  self.assertNotEqual(r['normalizer_version'],'1.0.2')
 def test_numeric_invariance_release_invalidates_103_generation(self):
  original=record();unchanged=copy.deepcopy(original)
  r=normalize_inputs([original],as_of='2026-09-14');views=prepare_views(r)
  previous=hashlib.sha256(json.dumps([r['audit']['source_snapshot_sha256'],r['as_of'],'1.0.3'],
      ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()
  self.assertTrue(all(row[-1]!=previous for rows in views.values() for row in rows))
  self.assertNotEqual(r['normalizer_version'],'1.0.3')
  self.assertEqual(original,unchanged)
 def test_derived_views_do_not_include_original_input_tab(self):
  self.assertNotIn('parser_offers',SCHEMAS);self.assertNotIn('loyalty_partner_benefits',SCHEMAS)
 def test_corporate_codes_are_in_private_views_not_dropped(self):
  r=normalize_inputs([record(privacy='private',origin='yandex_discounts_complete_all',codes=['SYNTHETIC'])],as_of='2026-09-14')
  rows=prepare_views(r)['normalized_codes'];self.assertEqual(rows[0][4],'SYNTHETIC')
if __name__=='__main__':unittest.main()

class StatusViewTests(unittest.TestCase):
 def test_published_period_does_not_hide_suspended_source(self):
  from test_unified_normalization import record
  from unified_normalization import normalize_inputs
  data=normalize_inputs([record(source_status='archived',details={'source_prize_suspended':True})],as_of='2026-09-14')
  rows=prepare_views(data)['normalized_records']
  self.assertIn('Статус источника',SCHEMAS['normalized_records'])
  self.assertEqual(rows[0][SCHEMAS['normalized_records'].index('Статус источника')],'archived')
  self.assertIn('true',rows[0][SCHEMAS['normalized_records'].index('Доступность JSON')])
