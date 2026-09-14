import copy,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parents[1]))
from unified_inputs import HEADERS,inputs_from_tables,clean_atom,atom_from_cell
from unified_normalization import normalize_record
class InputTests(unittest.TestCase):
 def test_formats_only_change_percent_semantics(self):
  self.assertEqual(clean_atom({'value':'x','format':'General'}),{'value':'x'})
  self.assertEqual(clean_atom({'value':.2,'format':'0.00%'}),{'value':.2,'format':'%'})
 def test_input_values_cannot_be_overridden_by_formatted_text(self):
  self.assertEqual(atom_from_cell({'userEnteredValue':{'numberValue':.2},'formattedValue':'90%','userEnteredFormat':{'numberFormat':{'pattern':'0%'}}})['value'],.2)
 def test_missing_source_not_silent(self):
  with self.assertRaises(ValueError):inputs_from_tables({})
 def test_wrong_header_is_not_reinterpreted(self):
  with self.assertRaises(ValueError):inputs_from_tables({'parser_offers':[[{'value':'Wrong'}]]})
 def test_actual_formula_stays_formula_not_fetched_url(self):
  a=atom_from_cell({'userEnteredValue':{'formulaValue':'=1+1'},'effectiveValue':{'numberValue':2}})
  self.assertEqual(a,{'formula':'=1+1','value':2})
if __name__=='__main__':unittest.main()

class CanonicalSnapshotTests(unittest.TestCase):
 def test_styled_trailing_rows_do_not_change_inventory_or_snapshot(self):
  from unified_normalization import INPUT_TABS,digest
  tables={name:[[] for _ in range(header-1)]+[[{'value':h} for h in HEADERS[name]]] for name,(header,_) in INPUT_TABS.items()}
  tables['yandex_discounts_complete_all'].append([{'value':'Demo'}])
  padded=copy.deepcopy(tables)
  for name in padded:padded[name].extend([[{'format':'General'}]]*5)
  first,inventory1=inputs_from_tables(tables);second,inventory2=inputs_from_tables(padded)
  self.assertEqual(digest(first),digest(second));self.assertEqual(inventory1,inventory2)

class UnexpectedColumnTests(unittest.TestCase):
 def test_additional_populated_column_is_not_silently_dropped(self):
  from unified_normalization import INPUT_TABS
  tables={name:[[] for _ in range(header-1)]+[[{'value':h} for h in HEADERS[name]]] for name,(header,_) in INPUT_TABS.items()}
  tables['yandex_discounts_complete_all'][0].append({'value':'Unexpected source field'})
  with self.assertRaises(ValueError):inputs_from_tables(tables)
