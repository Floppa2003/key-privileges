import json,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parents[1]))
from fixtures import fixture
from adapters import mir_detail
from normalized import make_offer,normalize_rates
NOW='2026-09-12T15:00:00+00:00'

class NullableSourceFieldsTests(unittest.TestCase):
 def test_mir_null_prefix_is_not_a_failed_offer(self):
  d=json.loads(fixture('mir_detail.json'));p=d['data']['content']['promoDetail']['promo']['promoAction'];p['desc']['number']['PREFIX']=None
  rs=mir_detail(d,'https://vamprivet.ru/promo/transport/ekspress-v-aeroport-s-vygodoy-i-komfortom-1/',NOW)
  self.assertEqual(len(rs),1);self.assertIn('5%',rs[0]['benefit_text'])
 def test_ural_empty_partner_does_not_discard_other_records(self):
  from adapters import ural_catalog
  d={'category':[{'id':'3','name':'Отели','text':'Только прямое бронирование'}],'partners':[{'id':'a','name':'A','category':'3','text':{'detail':'Скидка 10%'}},{'id':'b','name':'B','text':{'detail':''}}]}
  rs=ural_catalog(d,'https://www.uralairlines.ru/partners/?ajax=partners&action=default',NOW)
  self.assertEqual(len(rs),1);self.assertIn('Только прямое',rs[0]['conditions_text'])

class MirPaginationTests(unittest.TestCase):
 def test_source_pagination_overrides_first_page_but_keeps_payment_filter(self):
  from adapters import mir_page_url
  url=mir_page_url('/promo/?page_catalog_list=1&payment_type=sbp','/api/moskva-i-mo/promo/filter-json?page_catalog_list=2','https://vamprivet.ru/promo/')
  self.assertEqual(url,'https://vamprivet.ru/api/moskva-i-mo/promo/filter-json?page_catalog_list=2&payment_type=sbp')

class MoreLexicalTests(unittest.TestCase):
 def test_sentence_period_is_not_part_of_unquoted_promo(self):
  r=make_offer('moskvich','x','M','X','Скидка 15% по промокоду SHORTABB. При предъявлении карты','https://moskvichmag.ru/programma-loyalnosti/',NOW)
  self.assertEqual(r['promo_codes'],['SHORTABB'])
 def test_discount_label_after_percent_and_latin_c_are_supported(self):
  rates=normalize_rates('5% скидка при покупке; Cкидка 10% при демонстрации карты')
  self.assertEqual([(x['kind'],x['value']) for x in rates],[('discount','5'),('discount','10')])
