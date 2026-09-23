"""Lossless whitespace, explicit on-site redemption, and native freshness coverage."""
import sys,unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).parents[1]))
from test_catalogue_expansion import magnit,coupon,OLD
from public_reward_projection import make_record,validate_record
from expansion_common import ExcludedOffer,PROGRAMS
from magnit_partners import source_fields as mf,period
from gorod_source import source_fields as gf
import ui_freshness as u
F='=ARRAYFORMULA(LET(d;FILTER(\'_ui_catalog\'!A2:Q;1);keep;hits*IF($B$4="";1;1);FILTER(d;keep)))'
OLD_PROGRAMMES=('Backit — денежный кешбэк','Club Avolta','Мантера Моменты')
class RemainingShapes(unittest.TestCase):
    def test_magnit_empty_step_does_not_change_evidence(self):
        e=magnit();e['steps']+='\n';validate_record(make_record('magnit_partners_public',e,OLD))
    def test_multiline_magnit_heading_is_not_different_offer(self):
        e=magnit();e['title']=e['title'].replace(' и ','\nи ');e['partner']+=' '
        validate_record(make_record('magnit_partners_public',e,OLD))
    def test_russian_year_suffix_period(self):
        self.assertEqual(period('Срок проведения акции: с 26.12.2025 года по 31.12.2026 года включительно'),('2025-12-26','2026-12-31'))
    def test_bonus_action_period(self):
        self.assertEqual(period('510 бонусов — для клиентов, выполнивших условия акции в период с 25.12.2025 по 31.12.2026 включительно'),('2025-12-25','2026-12-31'))
    def test_plain_physical_product_not_discount(self):
        e=coupon();e['data'].update(name='Карта «Тройка» с дизайном «Мобайл»',price={'new':599,'old':None,'currencies':['roubles']})
        with self.assertRaises(ExcludedOffer):gf(e)
    def test_coupon_partner_identity_revalidated(self):
        e=coupon();e['catalogue_partner_id']=999
        with self.assertRaises(ValueError):gf(e)
    def test_explicit_on_site_top_up_is_usable_instruction_not_invented_code(self):
        e=coupon();e['data']['howToAsList']=None;e['data']['address']={'details':'Россия, Балашиха'}
        e['data']['terms']='Купон дает скидку 20% с доплатой на месте: 2 993₽ вместо 3 990₽ на билет. Нажимая «Купить», вы принимаете условия Оферты.'
        f=gf(e);self.assertIn('2 993',f['activation']);self.assertIn('coupon_presentation_method_not_disclosed',f['warnings']);self.assertNotIn('QR',f['activation'])
    def test_missing_unknown_steps_still_fail(self):
        e=coupon();e['data']['howToAsList']=None
        with self.assertRaises(ValueError):gf(e)
    def test_native_ui_includes_all_new_programmes(self):
        f=u.upgrade_formula(F)
        for name in PROGRAMS.values():self.assertIn(name,f)
    def test_upgrade_exact_existing_three_programme_formula(self):
        with patch.object(u,'PROGRAMMES',OLD_PROGRAMMES):old=u.upgrade_formula(F)
        new=u.upgrade_formula(old)
        for name in PROGRAMS.values():self.assertIn(name,new)
        self.assertEqual(u.upgrade_formula(new),new)
    def test_modified_legacy_expiry_is_not_overwritten(self):
        with patch.object(u,'PROGRAMMES',OLD_PROGRAMMES):old=u.upgrade_formula(F)
        with self.assertRaises(ValueError):u.upgrade_formula(old.replace('TODAY()-7','TODAY()-9'))
if __name__=='__main__':unittest.main()
