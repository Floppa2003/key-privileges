import copy
import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parents[1]))
from normalized import make_offer,normalize_rates,validate_offer

NOW='2026-09-12T15:00:00+00:00'
class NormalizationTests(unittest.TestCase):
 def test_discount_and_miles_are_not_added_or_converted_to_cash(self):
  rates=normalize_rates('Скидка 17% + 500 миль в подарок')
  self.assertEqual([(r['kind'],r['value'],r['unit']) for r in rates],[('discount','17','percent'),('miles','500','miles')])
 def test_up_to_and_fractional_rate_keep_their_basis(self):
  rates=normalize_rates('До 6,5 миль за каждые 100 ₽')
  self.assertEqual(len(rates),1)
  self.assertEqual({k:rates[0][k] for k in ['kind','value','unit','qualifier','basis_amount','basis_unit']},{'kind':'miles','value':'6.5','unit':'miles','qualifier':'up_to','basis_amount':'100','basis_unit':'RUB'})
 def test_percentage_range_not_two_unconditional_rates(self):
  rates=normalize_rates('Скидка 5–15% в зависимости от уровня')
  self.assertEqual([(x['value'],x.get('min_value'),x['qualifier']) for x in rates],[('15','5','range')])
 def test_purchase_threshold_is_not_a_discount(self):
  rates=normalize_rates('Скидка 10% при покупке от 1 500 ₽')
  self.assertEqual([(x['kind'],x['unit']) for x in rates],[('discount','percent')])
 def test_percent_without_a_benefit_role_stays_unclassified(self):
  self.assertEqual(normalize_rates('Рейтинг доверия 99% и более 1000 клиентов'),[])
 def test_unknown_end_is_null_not_perpetual(self):
  r=make_offer('s7','sample','S7','Brand','10%','https://marketplace.s7.ru/partners/offer/sample',NOW)
  self.assertIsNone(r['valid_until']);self.assertEqual(r['validity_status'],'not_stated')
 def test_explicit_past_end_is_not_current(self):
  r=make_offer('s7','sample','S7','Brand','Скидка 10%','https://marketplace.s7.ru/partners/offer/sample',NOW,valid_until='2025-12-31')
  self.assertEqual(r['validity_status'],'expired_by_published_end')
 def test_stable_id_does_not_change_when_rate_changes(self):
  a=make_offer('s7','sample','S7','Brand','Скидка 10%','https://marketplace.s7.ru/partners/offer/sample',NOW)
  b=make_offer('s7','sample','S7','Brand','Скидка 15%','https://marketplace.s7.ru/partners/offer/sample',NOW)
  self.assertEqual(a.get('id'),b.get('id'));self.assertNotEqual(a.get('content_sha256'),b.get('content_sha256'))
 def test_shared_page_is_not_an_invented_detail_url(self):
  r=make_offer('noname','card1','No Name','Brand','Скидка 10%','https://nonameburo.com/card',NOW,link_kind='page_block',locator='#rec1 [data-elem-id="1"]')
  self.assertIsNone(r['benefit_url']);self.assertEqual(r['source_url'],'https://nonameburo.com/card')
 def test_tampering_with_terms_fails_validation(self):
  r=make_offer('s7','sample','S7','Brand','Скидка 10%','https://marketplace.s7.ru/partners/offer/sample',NOW)
  r['benefit_text']='Скидка 90%'
  with self.assertRaises(ValueError):validate_offer(r)
 def test_no_silent_truncation(self):
  with self.assertRaises(ValueError):make_offer('s7','s','S7','Brand','x'*50000,'https://marketplace.s7.ru/partners/offer/s',NOW)
 def test_no_fake_source_or_token_url(self):
  with self.assertRaises(ValueError):make_offer('s7','s','S7','Brand','Скидка 10%','https://evil.example/s',NOW)
  with self.assertRaises(ValueError):make_offer('s7','s','S7','Brand','Скидка 10%','https://marketplace.s7.ru/s?token=private',NOW)

if __name__=='__main__':unittest.main()

class PromoBoundaryTests(unittest.TestCase):
 def test_multiword_code_is_not_silently_truncated(self):
  r=make_offer('moskvich','verba','Карта Москвича','Verba','Скидка 5% по промокоду MOSKVICH MAG при бронировании','https://moskvichmag.ru/programma-loyalnosti/',NOW)
  self.assertEqual(r['promo_codes'],['MOSKVICH MAG'])
 def test_quoted_code_and_lowercase_instruction_are_distinguished(self):
  r=make_offer('noname','x','No Name','X','Промокод «NONAME BURO»; получить промокод из приложения','https://nonameburo.com/card',NOW)
  self.assertEqual(r['promo_codes'],['NONAME BURO'])
