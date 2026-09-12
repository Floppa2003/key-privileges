"""Public response/DOM fixtures from 34714291645. Adjacent recommendations excluded."""
import copy,importlib.util,json,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parents[1]))
NOW='2026-09-12T19:00:00+00:00'
F=Path(__file__).with_name('fixtures_live')
class T2Tests(unittest.TestCase):
    def module(self):
        self.assertIsNotNone(importlib.util.find_spec('t2_source'),'No normalized T2 adapter')
        import t2_source
        return t2_source
    def test_catalog_keeps_same_offer_identity_conditions_and_source_dates(self):
        m=self.module();data=json.loads((F/'t2-catalog.json').read_text())
        data['data']['recommendations']=[{'name':'UNRELATED 99%'}]
        rows=m.catalog_records(data,NOW)
        self.assertEqual(len(rows),4)
        r=rows[0];self.assertEqual(r['partner_name'],'Юрент')
        self.assertIn('не более двух промокодов',r['conditions_text'])
        self.assertEqual(r['valid_until'],'2026-09-15')
        self.assertIn('SMS',r['redemption_text'])
        self.assertNotIn('UNRELATED',json.dumps(rows,ensure_ascii=False))
        self.assertIsNone(r['benefit_url'])
    def test_company_display_name_not_campaign_internal_name(self):
        rows=self.module().catalog_records(json.loads((F/'t2-catalog.json').read_text()),NOW)
        self.assertEqual(rows[2]['partner_name'],'SOKOLOV')
        self.assertEqual(rows[2]['details']['source_partner_name'],'SOKOLOV_август26')
    def test_duplicate_ids_fail_instead_of_silent_dedup(self):
        data=json.loads((F/'t2-catalog.json').read_text());data['data']['offers']*=2
        with self.assertRaises(ValueError):self.module().catalog_records(data,NOW)
    def test_error_payload_is_not_an_empty_success(self):
        with self.assertRaises(ValueError):self.module().catalog_records({'meta':{'status':'ERROR'},'data':{'offers':[]}},NOW)
    def test_mixx_configurable_and_fixed_services_not_all_promised_together(self):
        rows=self.module().page_records('t2_mixx',(F/'t2-mixx.html').read_text(),NOW)
        lamoda=next(r for r in rows if r['partner_name']=='Lamoda')
        self.assertEqual(lamoda['details']['membership_component'],'fixed')
        kion=next(r for r in rows if r['partner_name']=='КИОН')
        self.assertEqual(kion['details']['membership_component'],'selectable_replacement')
        self.assertEqual(next(r for r in rows if r['partner_name']=='Флаувау')['rates'][0]['value'],'500')
        self.assertTrue(any(r['partner_name']=='GPTMobile' for r in rows))
    def test_two_speaker_models_keep_different_subscription_lengths(self):
        rows=self.module().page_records('t2_mixx_s',(F/'t2-mixx_s.html').read_text(),NOW)
        self.assertEqual(len(rows),2)
        self.assertEqual([r['details']['required_subscription_months'] for r in rows],[6,3])
        self.assertTrue(all(r['valid_until']=='2026-09-30' for r in rows))
        self.assertTrue(all('одном чеке' in r['conditions_text'] for r in rows))
    def test_expired_powerbank_privilege_stays_expired(self):
        r=self.module().page_records('t2_powerbank',(F/'t2-powerbank.html').read_text(),NOW)[0]
        self.assertEqual(r['valid_until'],'2026-07-28')
        self.assertEqual(r['validity_status'],'expired_by_published_end')
        self.assertIn('3 суток',r['conditions_text'])
    def test_premium_card_does_not_invent_yandex_percentage(self):
        r=self.module().page_records('t2_selection',(F/'t2-selection.html').read_text(),NOW)[0]
        self.assertIn('711',r['benefit_text'])
        self.assertEqual(r['rates'],[])
