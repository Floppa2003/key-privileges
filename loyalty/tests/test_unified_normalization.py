"""Real transformations; no network, private codes or live workbook fixtures."""
import copy
import unittest
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parents[1]))
try:
    from unified_normalization import normalize_record, validate_normalized, normalize_inputs, make_input
except ImportError:
    normalize_record = validate_normalized = normalize_inputs = make_input = None

def record(**updates):
    r=dict(id='fixture:1',origin='parser_offers',source_row=2,program='S7 Priority',partner='Example',title='Example',kind='partner_offer',benefit='Скидка 15% на первый заказ от 1500 ₽; максимум скидки 300 ₽.',conditions='Не суммируется с другими акциями.',activation='',codes=[],rates=[],details={},valid_from=None,valid_until=None,source_url='https://example.com/offer',benefit_url='https://example.com/offer',link_kind='detail_page',observed_at='2026-09-13T00:00:00+00:00',source_status='published',source_id='s7',source_warnings=[],privacy='public',original={'unchanged':'raw evidence'})
    r.update(updates)
    return r

class UnifiedTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(normalize_record,'Unified normalization is not implemented')
    def norm(self,**kw): return normalize_record(record(**kw),as_of='2026-09-14')
    def test_source_preserved_and_unknown_validity_not_invented(self):
        r=record();before=copy.deepcopy(r);n=normalize_record(r,as_of='2026-09-14')
        self.assertEqual(r,before);self.assertEqual(n['raw'],r)
        self.assertIsNone(n['validity']['until']);self.assertEqual(n['validity']['status'],'unknown')
        self.assertEqual(n['provenance']['observed_at'],r['observed_at'])
    def test_minimum_and_cap_are_not_discounts(self):
        n=self.norm();self.assertTrue(any(x['kind']=='discount' and x['value']=='15' for x in n['benefits']))
        self.assertFalse(any(x['value'] in ('1500','300') for x in n['benefits']))
        self.assertTrue(any(x['kind']=='minimum_purchase' and x['value']=='1500' for x in n['conditions']))
        self.assertTrue(any(x['kind']=='benefit_cap' and x['value']=='300' for x in n['conditions']))
    def test_mile_percentage_is_not_cash_discount(self):
        n=self.norm(benefit='До 13% суммы бронирования милями.',conditions='')
        self.assertEqual(n['benefits'][0]['kind'],'earn_miles');self.assertEqual(n['benefits'][0]['unit'],'percent');self.assertEqual(n['benefits'][0]['reward_unit'],'miles')
    def test_earning_and_redemption_distinct(self):
        d={'earning_rules':[{'value':'1','unit':'miles','basis_amount':'70','basis_unit':'RUB','evidence':'1 миля за 70 руб'}], 'redemption_rules':{'max_order_percent':'30','minimum_cash_percent':'70','evidence':'Не более 30% милями, 70% деньгами'}}
        n=self.norm(benefit='1 миля за 70 руб',details=d,kind='program_rules')
        self.assertTrue(any(x['kind']=='earn_miles' and x['basis_value']=='70' for x in n['benefits']))
        self.assertTrue(any(x['kind']=='redeem_rewards' and x['value']=='30' for x in n['benefits']))
        self.assertTrue(all(not x['standalone_offer'] for x in n['benefits']))
    def test_scoped_table_code_is_not_inferred_from_digits(self):
        d={'table_benefits':{'components':[{'scope':{'kind':'card_type','value':'Серебряный'},'rate':{'kind':'discount','value':'7','unit':'percent','qualifier':'exact'},'promo_codes':['TEST10'],'evidence':{'header':['Карта','Скидка','Код'],'row':['Серебряный','7%','TEST10'],'table_index':0,'row_index':1}}],'issues':[]}}
        n=self.norm(details=d)
        scoped=[x for x in n['benefits'] if x['method']=='structured_table'][0]
        self.assertEqual(scoped['value'],'7');self.assertEqual(scoped['scope']['card_type'],'Серебряный')
        self.assertTrue(any(x['value']=='TEST10' and x['scope'].get('card_type')=='Серебряный' for x in n['codes']))
    def test_audience_codes_and_reward_lifetime_not_expiry(self):
        d={'audiences':[{'audience':'youth','age_min':16,'age_max':25,'promo_code':'EXAMPLEYOUTH','evidence':['от 16 до 25 лет','код EXAMPLEYOUTH']}],'reward_multiplier':2,'reward_multiplier_evidence':'двойные мили','reward_lifetime_years':3,'reward_lifetime_evidence':'срок миль 3 года'}
        n=self.norm(details=d,benefit='Двойные мили',kind='program_rules')
        self.assertEqual(n['codes'][0]['scope']['audience'],'youth');self.assertIsNone(n['validity']['until'])
        self.assertTrue(any(x['kind']=='reward_multiplier' and x['value']=='2' for x in n['benefits']))
    def test_bank_commission_not_reward(self):
        d={'mileage_options':[{'label':'Option','miles':'2.5','basis_rub':'100','monthly_cap_miles':'5000','monthly_subscription_rub':'399','evidence':'2,5 мили за 100 ₽; комиссия 1,5% минимум 50 ₽'}],'minimum_evidence':'Покупки от 5000 ₽','monthly_minimum_purchases_rub':'5000'}
        n=self.norm(benefit='Комиссия 1,5%, минимум 50 ₽',details=d,kind='program_rules')
        self.assertTrue(any(x['kind']=='earn_miles' and x['value']=='2.5' for x in n['benefits']))
        self.assertFalse(any(x['value']=='1.5' for x in n['benefits']))
        self.assertTrue(any(x['kind']=='subscription_cost' and x['value']=='399' for x in n['costs']))
    def test_unknown_pdf_table_not_mapped_to_entitlements(self):
        n=self.norm(benefit='Gold Platinum\n1 2\nБизнес-зал',details={'pages':[{'number':1,'text':'Gold Platinum\n1 2\nБизнес-зал'}]},kind='program_rules')
        self.assertFalse(any(x.get('value') in ('1','2') for x in n['benefits']))
        self.assertIn('pdf_table_semantics_not_inferred',n['quality']['issues'])
    def test_raw_inbox_neighbour_text_is_not_an_offer(self):
        n=self.norm(origin='parser_inbox',kind='raw_page',benefit='Другие предложения\nСкидка 50%',privacy='unclassified')
        self.assertEqual(n['benefits'],[]);self.assertEqual(n['quality']['level'],'evidence_only')
    def test_source_validation_detects_changed_quote(self):
        n=self.norm();validate_normalized(n)
        n['benefits'][0]['evidence']['text']='fabricated'
        with self.assertRaises(ValueError):validate_normalized(n)
    def test_no_codes_guessed_from_year(self):
        n=self.norm(benefit='Скидка 10% в 2026 году. Получите промокод в SMS.',conditions='')
        self.assertEqual([x for x in n['codes'] if x['value']],[])
        self.assertTrue(any(x['delivery']=='sms' for x in n['codes']))
    def test_legacy_status_does_not_verify_current_eligibility(self):
        n=self.norm(origin='loyalty_partner_benefits',source_status='Текущий',privacy='private',valid_until='2025-12-31')
        self.assertEqual(n['validity']['status'],'expired');self.assertEqual(n['quality']['verification'],'legacy_not_reverified')
        self.assertIsNone(n['eligibility_verified'])
    def test_duplicate_phrases_collapsed_inside_record(self):
        n=self.norm(benefit='Скидка 10%.',conditions='Скидка 10%.')
        self.assertEqual(len([x for x in n['benefits'] if x['value']=='10']),1)
    def test_cross_programme_no_silent_merge(self):
        a=record(id='a',program='S7 Priority');b=record(id='b',program='Аэрофлот Бонус')
        result=normalize_inputs([a,b],as_of='2026-09-14')
        self.assertEqual(len(result['records']),2);self.assertNotEqual(result['records'][0]['program']['key'],result['records'][1]['program']['key'])
    def test_parse_first_and_following_purchase_separately(self):
        n=self.norm(benefit='Скидка 20% на первый заказ; скидка 10% на последующие заказы.',conditions='')
        self.assertEqual({(x['value'],x['scope'].get('purchase_stage')) for x in n['benefits']},{('20','first'),('10','repeat')})
    def test_explicit_card_membership_not_free_or_verified(self):
        n=self.norm(program='No Name Card',benefit='Коктейль в подарок при предъявлении карты.',conditions='')
        self.assertTrue(any(x['kind']=='gift' for x in n['benefits']))
        self.assertIsNone(n['eligibility_verified'])
    def test_private_public_export_filter(self):
        result=normalize_inputs([record(id='a'),record(id='b',privacy='private',origin='VG_community_offers')],as_of='2026-09-14',public_only=True)
        self.assertEqual([x['id'] for x in result['records']],['a'])
    def test_numeric_legacy_percent_requires_percent_format(self):
        cell={'value':0.2,'display':'20%','format':'0%'}
        raw={'id':'a','origin':'yandex_discounts_complete_all','row':2,'fields':{'Service Name':{'value':'Example'},'Category':{'value':'Goods'},'Discount':cell}}
        x=make_input(raw);self.assertIn('20%',x['benefit'])
        raw['fields']['Discount']={'value':0.2,'display':'0.2','format':'0.0'}
        self.assertNotIn('%',make_input(raw)['benefit'])
    def test_all_terms_reference_their_own_record(self):
        n=self.norm()
        for group in ('benefits','conditions','costs','codes'):
            for x in n[group]:self.assertEqual(x['record_id'],n['id'])
    def test_missing_partner_not_filled_from_title(self):
        n=self.norm(partner=None,title='Скидка 10%')
        self.assertIsNone(n['partner']['name'])

if __name__=='__main__':unittest.main()

class NormalizationRegressionTests(unittest.TestCase):
    def test_english_fixed_discount_parsed_as_rub_not_percent(self):
        n=normalize_record(record(origin='yandex_discounts_complete_all',benefit='2000 RUB off first order',conditions=''),as_of='2026-09-14')
        self.assertTrue(any(x['value']=='2000' and x['unit']=='RUB' for x in n['benefits']))
    def test_explicit_code_labels_are_scopes_not_part_of_code(self):
        n=normalize_record(record(details={'explicit_code_cell':'DEMO1 (tickets); DEMO2 (show); none for exhibitions'},codes=[],benefit='Discount 10%',conditions=''),as_of='2026-09-14')
        self.assertEqual({x['value'] for x in n['codes']},{'DEMO1','DEMO2'})
        self.assertEqual(n['codes'][0]['scope'],{'source_label':'tickets'})
    def test_scoped_code_does_not_gain_unscoped_duplicate(self):
        d={'audiences':[{'audience':'youth','promo_code':'DEMO1','evidence':'DEMO1 for youth'}]}
        n=normalize_record(record(details=d,codes=['DEMO1']),as_of='2026-09-14')
        self.assertEqual(len([x for x in n['codes'] if x['value']=='DEMO1']),1)
    def test_percent_reward_points_not_cashback_cash(self):
        n=normalize_record(record(benefit='Кешбэк 20% бонусными баллами на следующую покупку.',conditions=''),as_of='2026-09-14')
        self.assertEqual(n['benefits'][0]['kind'],'earn_points');self.assertEqual(n['benefits'][0]['reward_unit'],'points')
    def test_explicit_date_interval_not_dropped(self):
        raw={'id':'date','origin':'yandex_discounts_complete_all','row':2,'fields':{'Service Name':{'value':'Example'},'Validity':{'value':'2026-02-14 to 2026-04-05'}}}
        x=make_input(raw);self.assertEqual(x['valid_from'],'2026-02-14');self.assertEqual(x['valid_until'],'2026-04-05')

class EvidenceBoundaryTests(unittest.TestCase):
 def test_public_mode_rejects_nonempty_manual_comment(self):
  r=record(original={'fields':{'Ручной комментарий':{'value':'private-note-synthetic'}}})
  with self.assertRaises(ValueError):normalize_inputs([r],as_of='2026-09-14',public_only=True)
 def test_changed_numeric_value_fails_integrity(self):
  n=normalize_record(record(),as_of='2026-09-14');n['benefits'][0]['value']='99'
  with self.assertRaises(ValueError):validate_normalized(n)
 def test_foreign_condition_reference_is_rejected(self):
  n=normalize_record(record(),as_of='2026-09-14');n['benefits'][0]['condition_ids']=['nonexistent']
  with self.assertRaises(ValueError):validate_normalized(n)

class RangeAndGiftTests(unittest.TestCase):
 def test_both_discount_range_bounds_survive(self):
  n=normalize_record(record(benefit='Скидка 5–15% на услуги.',conditions=''),as_of='2026-09-14')
  r=n['benefits'][0];self.assertEqual(r.get('value_min'),'5');self.assertEqual(r['value'],'15');self.assertEqual(r['qualifier'],'range')
 def test_excluded_gift_certificate_does_not_create_free_gift(self):
  n=normalize_record(record(benefit='Discount 10%; gift certificates excluded.',conditions=''),as_of='2026-09-14')
  self.assertFalse(any(r['kind']=='gift' for r in n['benefits']))
 def test_points_reward_not_lost_as_cash_or_price(self):
  n=normalize_record(record(benefit='Получите 500 бонусов за покупку.',conditions=''),as_of='2026-09-14')
  self.assertTrue(any(r['kind']=='earn_points' and r['value']=='500' for r in n['benefits']))
 def test_points_spending_not_earning(self):
  n=normalize_record(record(benefit='Спишите 500 баллов при оплате.',conditions=''),as_of='2026-09-14')
  self.assertFalse(any(r['kind']=='earn_points' for r in n['benefits']))
