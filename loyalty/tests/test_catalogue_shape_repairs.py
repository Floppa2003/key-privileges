"""Regressions for public shapes observed in the first four-catalogue run."""
import copy,json,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parents[1]))
from test_catalogue_expansion import x5,gorod,coupon,OLD
from x5_partners import source_fields as xfields
from gorod_source import source_fields as gfields,coupon as parse_coupon
from public_reward_projection import make_record,validate_record

class ObservedShapes(unittest.TestCase):
    def test_exchange_end_only_date(self):
        e=x5();e['card']['type']='exchange';e['period']='Доступно до 31 дек. 2026 г.'
        self.assertEqual(xfields(e)['valid_until'],'2026-12-31')
    def test_exchange_expiry_mismatch_still_rejected(self):
        e=x5();e['card']['type']='exchange';e['period']='Доступно до 30 дек. 2026 г.'
        with self.assertRaises(ValueError):xfields(e)
    def test_quest_null_cost_not_called_free(self):
        e=x5();e['card']['type']='quest';e['card']['cost']=None
        e['conditions']='99 ₽ за пробный абонемент. Через 7 дней автопродление по полной стоимости.'
        f=xfields(e);self.assertNotIn('бесплат',f['conditions']);self.assertIn('автопродление',f['conditions'])
    def test_purchased_null_cost_still_rejected(self):
        e=x5();e['card']['cost']=None
        with self.assertRaises(ValueError):xfields(e)
    def test_source_exchange_ratio_preserved(self):
        e=x5();e['card']['type']='exchange';e['exchange_terms']='Обменивайте по курсу 122 баллы = 1 голос ВКонтакте.'
        self.assertIn('122',xfields(e)['benefit'])
    def test_trimmed_gorod_partner_replays(self):
        e=gorod();e['data']['partner']['name']+=' '
        r=make_record('gorod_public',e,OLD);validate_record(r)
    def test_no_extra_conditions_is_not_no_activation(self):
        e=gorod();e['data']['partner']['specialConditions']=None;e['data']['earn']['hold']=None
        f=gfields(e);self.assertIn('additional_conditions_not_disclosed',f['warnings'])
        validate_record(make_record('gorod_public',e,OLD))
    def test_no_partner_activation_still_rejected(self):
        e=gorod();e['data']['partner']['howTo']=None
        with self.assertRaises(ValueError):gfields(e)
    def test_coupon_short_title_not_identity(self):
        e=coupon();d=e['data'];data={'props':{'pageProps':{'initialStoreState':{'couponViewStore':{'couponData':d}}}}}
        raw='<script id="__NEXT_DATA__" type="application/json">'+json.dumps(data)+'</script>'
        r=parse_coupon(raw,{'id':d['id'],'name':'Купон на кофе','partner_id':d['partner']['id']},OLD)
        self.assertEqual(r['title'],d['name']);validate_record(r)
    def test_coupon_wrong_partner_still_rejected(self):
        e=coupon();d=e['data'];data={'props':{'pageProps':{'initialStoreState':{'couponViewStore':{'couponData':d}}}}}
        raw='<script id="__NEXT_DATA__" type="application/json">'+json.dumps(data)+'</script>'
        with self.assertRaises(ValueError):parse_coupon(raw,{'id':d['id'],'name':d['name'],'partner_id':999},OLD)
    def test_booster_owned_automatic_activation(self):
        e=coupon();e['data']['howToAsList']=None;e['data']['name']='Максимальный кешбэк от партнеров на 7 дней'
        e['data']['terms']='Бустер начинает действовать автоматически после покупки. Дополнительно вводить его данные никуда не требуется.'
        self.assertIn('автоматически',gfields(e)['activation']);validate_record(make_record('gorod_public',e,OLD))
    def test_unknown_null_coupon_activation_not_invented(self):
        e=coupon();e['data']['howToAsList']=None
        with self.assertRaises(ValueError):gfields(e)

if __name__=='__main__':unittest.main()
