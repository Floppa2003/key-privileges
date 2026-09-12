import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parents[1]))
from ural_ui import reconcile_partners
from normalized import make_offer
NOW='2026-09-12T10:00:00+00:00'
URL='https://www.uralairlines.ru/partners/'
def r(n):return make_offer('ural','partner_'+str(n),'Крылья','Partner '+str(n),'Скидка 10%',URL,NOW,link_kind='page_block',locator='#partner_'+str(n))
class UralTests(unittest.TestCase):
 def test_missing_api_terms_are_completed_only_by_same_native_id(self):
  rows,errors=reconcile_partners([{'id':1},{'id':2}],[r(1)],[r(1),r(2)])
  self.assertEqual([x['native_id'] for x in rows],['partner_1','partner_2']);self.assertEqual(errors,[])
 def test_html_neighbor_is_not_used_for_missing_partner(self):
  rows,errors=reconcile_partners([{'id':1},{'id':2}],[r(1)],[r(3)])
  self.assertEqual([x['native_id'] for x in rows],['partner_1']);self.assertEqual(errors[0]['native_id'],'partner_2')
 def test_duplicates_and_foreign_records_fail(self):
  with self.assertRaises(ValueError):reconcile_partners([{'id':1},{'id':1}],[r(1)],[])
  with self.assertRaises(ValueError):reconcile_partners([{'id':1}],[r(2)],[])
