"""Regression cases for source scope/costs/lifecycle, not live website claims."""
import copy,json,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parents[1]))
from expansion_common import ExcludedOffer,check_period,reported,exclusion,sha,SOURCES
from public_reward_projection import make_record,validate_record
from sheets_normalized import SCHEMAS,prepare
from source_lifecycle import validate_inventories,reconcile_rows,health_summary
from test_lifecycle_pipeline import reader
from x5_partners import source_fields as xfields,decode_loader,page_data
from magnit_partners import source_fields as mfields,period,practical_content
from tsvetnoy_source import source_fields as tfields,current_document
from gorod_source import source_fields as gfields

OLD='2026-09-22T12:00:00+00:00';NEW='2026-09-23T12:00:00+00:00'

def x5(native='222'):
    title='Скидка 7% на бронирование за 200 баллов X5 Клуба'
    return dict(native=native,url='https://x5club.ru/partners/'+native,page_sha256='a'*64,
        card=dict(idOffer=int(native),nameOffer=title,cost=200,type='purchased',startDate='2026-06-04 00:00:00',endDate='2026-12-31 23:59:59',namePartnerOffer='Авито',namePartner=None),
        heading=title,partner='Авито',period='Действует 04.06.2026 - 31.12.2026',activation='Получить индивидуальный код в X5. Ввести его при бронировании.',
        conditions='Не суммируется. Один промокод используется один раз; доступен не только для первой покупки.',category='Путешествия')

def coupon():
    return dict(native='coupon:19560',url='https://gorodtroika.ru/bonus-plus/coupons/19560',kind='coupon',page_sha256='b'*64,
        data=dict(id=19560,name='Скидка 10% на кофе',available=True,partner=dict(id=3507,name='Tasty Coffee',subtitle='Еда',available=True),
            price=dict(new=5,currencies=['coins']),terms='От 1000 ₽; кроме сортов недели и месяца.',endAt='2026-12-31T23:59:59',couponEndAt='2026-12-31T23:59:59',
            howToAsList=['Получите купон.','Введите код в корзине.']))

def gorod():
    return dict(native='partner:3211',url='https://gorodtroika.ru/partners/3211',kind='partner',page_sha256='c'*64,catalogue_regions=['Москва'],data=dict(
        partner=dict(id=3211,name='Отелло',categoriesAsText='Путешествия',specialConditions='Собрать корзину после перехода.',bubbles=[],howTo=dict(items=[dict(name='Перейдите на сайт; начисление в течение 40 дней.')])),
        earn=dict(hold=dict(description='Начисление в течение 96 рабочих дней'),bonusConditions=[dict(id=1,name='Новый клиент, промокод'),dict(id=2,name='Действующий клиент')],
            bonusByLevel=[dict(level=dict(id=6,number=7,name='Хранитель',experience=6600,percent=80),amount=505.4,percent=5.3,conditions={'1':dict(amount=505.4),'2':dict(percent=5.3)})]),spend=None))

def tsvet():
    cells=['БРЕНД**','0%','3%','5%','\uf0fc','Предъявить карту.']
    return dict(native='brand:2 этаж:БРЕНД**',url='https://tsvetnoy.com/pdf/current.pdf',document=dict(key='current.pdf',active=True),row=dict(page=3,floor='2 этаж',cells=cells),
        page_sha256='d'*64,footnotes='** На часть товаров скидка не распространяется. Скидки не суммируются.',tier_conditions='Стандарт: 100 000; Плюс: 600 000.',registration='Зарегистрируйтесь; цифровая карта в кабинете.')

def magnit():
    title='420 бонусов и подписка за 1 рубль'
    return dict(native='1787',url='https://magnit.ru/partners/1787',page_sha256='e'*64,title=title,catalogue_title=title,partner='СберПрайм',category='Подписки',
        content='<p>Сроки акции: с 07.09.2026 по 31.12.2026.</p><p>Для новых клиентов: 420 бонусов, 1 рубль за 30 дней, далее 399 рублей в месяц.</p>',
        steps='Перейдите на сайт. Оплатите подписку.',disclaimer='Промокоды не суммируются.')

def bundle(sid,es,now=OLD,all_ids=None,excluded=None,errors=None):
    rows=[make_record(sid,e,now)for e in es]
    report=dict(source_id=sid,name='Synthetic test',root=rows[0]['source_url']if rows else'https://x5club.ru/partners',status='partial'if errors else'ok',normalized=len(rows),failed=len(errors or[]),errors=errors or[],observed_at=now,region=None)
    reported(report,rows,all_ids or[e['native']for e in es],excluded or{})
    return dict(schema_version=2,run_id='test:'+now,observed_at=now,sources=[report],records=rows)

class CatalogueExpansion(unittest.TestCase):
    def test_all_four_sources_registered_with_hosts(self):
        from normalized import HOSTS
        cfg=json.loads(Path(__file__).parents[1].joinpath('sources_normalized.json').read_text())
        self.assertTrue(SOURCES<=set(HOSTS));self.assertTrue(SOURCES<=set(c['id']for c in cfg))
    def test_x5_points_cost_is_not_roubles(self):
        f=xfields(x5());self.assertIn('200 баллов',f['conditions']);self.assertNotIn('200 ₽',f['conditions'])
    def test_x5_repeat_customer_scope_survives(self):self.assertIn('не только',xfields(x5())['conditions'])
    def test_x5_heading_change_fails(self):
        e=x5();e['heading']='Скидка 20%'
        with self.assertRaises(ValueError):xfields(e)
    def test_x5_date_version_conflict_fails(self):
        e=x5();e['period']='Действует 04.06.2026 - 31.10.2026'
        with self.assertRaises(ValueError):xfields(e)
    def test_x5_unknown_exchange_type_fails(self):
        e=x5();e['card']['type']='unreviewed'
        with self.assertRaises(ValueError):xfields(e)
    def test_loader_rejects_wrong_route(self):
        with self.assertRaises(ValueError):decode_loader('[{"_1":2},"root",null]')
    def test_loader_rejects_cycles(self):
        with self.assertRaises(ValueError):decode_loader('[{"_1":0},"cycle"]')
    def test_expired_date_is_not_fresh(self):
        with self.assertRaises(ExcludedOffer):check_period(None,'2026-03-31',OLD)
    def test_not_started_date_is_not_current(self):
        with self.assertRaises(ExcludedOffer):check_period('2026-12-01',None,OLD)
    def test_lottery_not_coupon_discount(self):self.assertEqual(exclusion('Промокод на лотерейный билет'),'gambling_or_lottery')
    def test_loan_not_reward_catalogue(self):self.assertEqual(exclusion('Деньги на любые цели от 0%'),'financial_or_acquisition_ad')
    def test_magnit_other_subscription_cost_kept(self):
        f=mfields(magnit());self.assertIn('399 рублей',f['conditions']);self.assertEqual(f['valid_until'],'2026-12-31')
    def test_magnit_explicit_russian_dates(self):
        self.assertEqual(period('Общий срок проведения акции:\nс 14 ноября 2025 по 31 марта 2026'),('2025-11-14','2026-03-31'))
    def test_magnit_company_pitch_not_terms(self):
        text=practical_content('<p>6% новым; 3% действующим</p><b>О партнере</b><p>500000 довольных клиентов</p>')
        self.assertNotIn('500000',text);self.assertIn('3%',text)
    def test_magnit_catalogue_version_change_stops(self):
        e=magnit();e['catalogue_title']='999 бонусов'
        with self.assertRaises(ValueError):mfields(e)
    def test_coupon_coins_not_roubles(self):
        f=gfields(coupon());self.assertIn('жетоны',f['conditions']);self.assertNotIn('5 рублей',f['conditions']);self.assertIn('1000',f['conditions'])
    def test_coupon_free_distinct(self):
        e=coupon();e['data']['price']={'new':0,'currencies':[]};self.assertIn('бесплатно',gfields(e)['conditions'])
    def test_coupon_cost_without_currency_stops(self):
        e=coupon();e['data']['price']['currencies']=[]
        with self.assertRaises(ValueError):gfields(e)
    def test_coupon_mixed_cost_and_min_cash_kept(self):
        e=coupon();e['data']['price']={'new':150,'currencies':['roubles','bonuses']};e['data']['message']={'title':'От 30 ₽','body':'Остальное бонусами'}
        f=gfields(e);self.assertIn('От 30 ₽',f['conditions']);self.assertIn('рубли, бонусы',f['conditions'])
    def test_coupon_unavailable_not_published(self):
        e=coupon();e['data']['available']=False
        with self.assertRaises(ExcludedOffer):gfields(e)
    def test_gorod_level_uplift_not_reward(self):
        f=gfields(gorod());self.assertNotIn('80%',f['benefit']);self.assertIn('505.4 бонусов',f['benefit']);self.assertIn('5.3% бонусами',f['benefit'])
    def test_gorod_reward_unit_and_scope(self):
        f=gfields(gorod());self.assertEqual({x['reward_unit']for x in f['terms']},{'Gorod_bonus_not_cash'});self.assertEqual(f['terms'][0]['scope']['member_level_id'],6)
    def test_gorod_conflicting_accrual_period_visible(self):
        f=gfields(gorod());self.assertIn('source_conflicting_accrual_times_preserved',f['warnings']);self.assertIn('96',f['conditions']);self.assertIn('40',f['activation'])
    def test_gorod_missing_condition_identity_stops(self):
        e=gorod();e['data']['earn']['bonusConditions'].pop()
        with self.assertRaises(ValueError):gfields(e)
    def test_tsvetnoy_tier_rates_not_max_for_everyone(self):
        f=tfields(tsvet());self.assertIn('Старт: 0%',f['benefit']);self.assertEqual([x['value']for x in f['terms']],['3','5']);self.assertEqual(f['terms'][1]['scope']['member_tier'],'Плюс')
    def test_tsvetnoy_footnote_preserved(self):self.assertIn('не распространяется',tfields(tsvet())['conditions'])
    def test_tsvetnoy_accumulation_not_cashback(self):
        e=tsvet();e['row']['cells'][1:4]=['-']*3
        with self.assertRaises(ExcludedOffer):tfields(e)
    def test_tsvetnoy_active_file_must_be_unique(self):
        d={'active':True,'type':'loyalyty_program_discount','key':'test.pdf'}
        with self.assertRaises(ValueError):current_document([d,d])
    def test_tsvetnoy_new_file_discovered(self):
        d={'active':True,'type':'loyalyty_program_discount','key':'new.pdf'}
        self.assertEqual(current_document([d])['key'],'new.pdf')
    def test_owned_fields_cannot_be_forged(self):
        r=make_record('gorod_public',coupon(),OLD);r['benefit_text']='Скидка 100%'
        with self.assertRaises(ValueError):validate_record(r)
    def test_all_source_projections_reach_real_reader(self):
        for sid,e in [('x5_partners_public',x5()),('magnit_partners_public',magnit()),('gorod_public',coupon()),('tsvetnoy_public',tsvet())]:
            b=bundle(sid,[e]);row=prepare(b)['parser_offers'][0];view,reason=reader(row,OLD[:10]);self.assertIsNone(reason);self.assertIsNotNone(view)
    def test_unfinished_inventory_not_healthy(self):
        b=bundle('x5_partners_public',[x5()],all_ids=['222','230']);self.assertFalse(health_summary(b)[0]['healthy'])
    def test_complete_inventory_missing_record_is_error(self):
        b=bundle('x5_partners_public',[x5()]);b['records']=[]
        with self.assertRaises(ValueError):validate_inventories(b)
    def test_explicit_exclusion_fully_accounted(self):
        b=bundle('x5_partners_public',[x5()],all_ids=['222','85'],excluded={'85':'gambling_or_lottery'});self.assertTrue(health_summary(b)[0]['healthy'])
    def test_failed_source_does_not_retire_old_rows(self):
        old=bundle('x5_partners_public',[x5()]);new=bundle('x5_partners_public',[x5('230')],NEW,errors=[{'reason':'timeout'}]);existing=[SCHEMAS['parser_offers']]+prepare(old)['parser_offers']
        result=reconcile_rows(new,existing,prepare(new)['parser_offers']);self.assertEqual(len(result),1)
    def test_complete_absence_holds_without_source_time_change(self):
        old=bundle('x5_partners_public',[x5()]);new=bundle('x5_partners_public',[x5('230')],NEW);original=prepare(old)['parser_offers'][0]
        result=reconcile_rows(new,[SCHEMAS['parser_offers'],original+['manual note']],prepare(new)['parser_offers']);held=next(r for r in result if r[0]==original[0])
        self.assertEqual(held[22],OLD);self.assertEqual(held[:20],original[:20]);self.assertIsNone(reader(held,NEW[:10])[0])
    def test_old_write_does_not_restore_new_hold(self):
        old=bundle('x5_partners_public',[x5()]);new=bundle('x5_partners_public',[x5('230')],NEW);original=prepare(old)['parser_offers'][0]
        held=reconcile_rows(new,[SCHEMAS['parser_offers'],original],prepare(new)['parser_offers']);self.assertEqual(reconcile_rows(old,[SCHEMAS['parser_offers']]+held,prepare(old)['parser_offers']),[])
    def test_fresh_return_restores(self):
        old=bundle('x5_partners_public',[x5()]);new=bundle('x5_partners_public',[x5('230')],NEW);original=prepare(old)['parser_offers'][0]
        held=reconcile_rows(new,[SCHEMAS['parser_offers'],original],prepare(new)['parser_offers']);fresh=bundle('x5_partners_public',[x5()], '2026-09-24T12:00:00+00:00')
        out=reconcile_rows(fresh,[SCHEMAS['parser_offers']]+held,prepare(fresh)['parser_offers']);r=next(r for r in out if r[0]==original[0]);self.assertNotIn('_lifecycle',json.loads(r[20]));self.assertIsNotNone(reader(r,'2026-09-24')[0])
    def test_freshness_after_seven_days(self):
        row=prepare(bundle('gorod_public',[coupon()]))['parser_offers'][0];self.assertIsNotNone(reader(row,'2026-09-29')[0]);self.assertIsNone(reader(row,'2026-09-30')[0])

if __name__=='__main__':unittest.main()
