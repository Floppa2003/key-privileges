"""Typed constraints are local evidence, never guessed global eligibility."""
import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parents[1]))
from normalized import make_offer
NOW='2026-09-12T20:00:00+00:00'
def record(value):
 return make_offer('moskvich','fixture','Карта','Партнёр',value,'https://moskvichmag.ru/programma-loyalnosti/',NOW)
class ConstraintTests(unittest.TestCase):
 def test_order_minimum_and_discount_cap_have_different_roles(self):
  data=record('Скидка 15% на первый заказ от 1 500 ₽. Максимальная скидка — 1 000 ₽.')
  rows=data['details'].get('lexical_conditions',[])
  self.assertTrue(any(x.get('kind')=='minimum_purchase' and x.get('value')=='1500' and x['unit']=='RUB' for x in rows))
  self.assertTrue(any(x.get('kind')=='maximum_benefit' and x.get('value')=='1000' for x in rows))
  self.assertTrue(any(x.get('kind')=='first_purchase' for x in rows))
 def test_non_stacking_preserves_exact_qualification(self):
  rows=record('Скидка 10%. Не суммируется с другими промокодами, но действует на распродажу.')['details'].get('lexical_conditions',[])
  self.assertTrue(any(x['kind']=='stacking_restriction' and 'но действует на распродажу' in x['evidence'] for x in rows))
 def test_tariff_price_is_not_minimum_order_or_maximum_benefit(self):
  rows=record('Тариф от 450 ₽ в месяц. Интернет на все — 100 ₽ в месяц.')['details'].get('lexical_conditions',[])
  self.assertEqual(rows,[])
 def test_cap_not_inferred_from_uncertain_neighbor(self):
  rows=record('Доставка — не более 500 ₽. Скидка 10%.') ['details'].get('lexical_conditions',[])
  self.assertFalse(any(x['kind']=='maximum_benefit' for x in rows))
 def test_no_customer_qualification_is_invented(self):
  self.assertEqual(record('Скидка 10% при предъявлении карты.')['details'].get('lexical_conditions',[]),[])
