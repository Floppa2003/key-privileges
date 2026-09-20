"""Reader-quality regressions. Synthetic/public snippets only; no workbook data."""
import copy
import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parents[1]))
from catalogue_view import build_catalogue, record_row, clean_plain, units
from catalogue_publish import literal, padded
NOW='2026-09-20'

def record(benefit='Скидка 10% на меню', **kw):
    raw={'id':'x','origin':'parser_offers','source_row':2,'program':'Test card',
         'partner':'Cafe','title':'Cafe','kind':'partner_offer','benefit':benefit,
         'conditions':'Не распространяется на алкоголь. Не суммируется с другими акциями.',
         'activation':'Предъявите карту перед оплатой.','details':{},
         'source_url':'https://example.org/cafe','source_status':'published',
         'observed_at':'2026-09-20T00:00:00Z','original':{'fields':{}}}
    raw.update(kw)
    return {'id':raw['id'],'raw':raw,'codes':[], 'validity':{'status':'not_stated'}}

class ReaderTests(unittest.TestCase):
    def row(self,n):return record_row(n,NOW)[0]
    def test_no_post_or_raw_page_is_an_offer(self):
        for kind in ('announcement','raw_page','source_observation'):
            self.assertIsNone(self.row(record('Маршрут выходного дня — получите скидку',kind=kind)))
    def test_expired_and_archived_not_reader_offers(self):
        n=record();n['validity']['status']='expired'
        self.assertIsNone(self.row(n))
        self.assertIsNone(self.row(record(source_status='archived')))
    def test_generic_and_technical_names_are_rejected(self):
        for name in ('Подробнее','Презентация PowerPoint','special:abcdef'):
            self.assertIsNone(self.row(record(partner=name,title=name)))
        self.assertIsNone(self.row(record('Привилегия',conditions='',activation='')))
    def test_empty_partner_page_has_no_invented_rate(self):
        self.assertIsNone(self.row(record('',conditions='На лабораторные исследования',activation='')))
    def test_statistics_and_breakfast_are_not_rewards(self):
        for value in ('80% родителей отмечают рост успеваемости.',
                      'В меню — авторская кухня, завтраки и классические десерты.'):
            self.assertIsNone(self.row(record(value,conditions='',activation='')))
    def test_cyrillic_lookalike_and_short_percentage_preserved(self):
        for value in ('Cкидка 10% на меню','20% на первый визит, далее 10%',
                      '13% милями от стоимости брони','Промокод HSE -15%'):
            self.assertEqual(self.row(record(value))[2],value)
    def test_non_numeric_perk_survives(self):
        self.assertIn('в подарок',self.row(record('Бокал игристого в подарок при заказе меню'))[2])
    def test_own_rules_and_code_preserved(self):
        n=record(conditions='Скидка только на первый заказ от 3 000 ₽; лимит 500 ₽. Исключены акционные товары.')
        n['codes']=[{'delivery':'literal','value':'СЛОВО10','scope':{}}]
        row=self.row(n)
        self.assertEqual(row[3],'Код: СЛОВО10')
        for v in ('первый','3 000','500','Исключены'):self.assertIn(v,' '.join(row[2:6]))
    def test_code_text_never_becomes_a_formula(self):
        self.assertEqual(literal('=SUM(A1:A9)'),{'userEnteredValue':{'stringValue':'=SUM(A1:A9)'}})
    def test_private_local_offer_does_not_require_a_public_url(self):
        row=self.row(record('20%',origin='VG_community_offers',kind='legacy_offer',source_url='',details={'region':'Москва'}))
        self.assertEqual(row[9],'');self.assertIn('Москва',row[5])
    def test_different_cities_programmes_tiers_and_rules_not_merged(self):
        rows=[record(id=str(i),program='P'+str(i%2),conditions='Город '+str(i),details={'tier':str(i)}) for i in range(4)]
        self.assertEqual(build_catalogue(rows,as_of=NOW)['counts']['kept'],4)
    def test_exact_duplicate_drops_once(self):
        result=build_catalogue([record(),record(id='y')],as_of=NOW)
        self.assertEqual(result['counts']['kept'],1)
        self.assertEqual(result['removed'][0]['reason'],'точный дубль')
    def test_original_inputs_are_unchanged(self):
        n=record();before=copy.deepcopy(n);build_catalogue([n],as_of=NOW);self.assertEqual(n,before)
    def test_loyals_drops_menu_review_before_card_clause(self):
        value='В меню — завтраки и десерты. Обладателям карты Loyals полагается скидка 15% на все меню.'
        row=self.row(record(value,conditions=value,program='Loyals',details={'public_post':{'id':1}}))
        self.assertEqual(row[2],'Обладателям карты Loyals полагается скидка 15% на все меню.')
        self.assertNotIn('завтраки',' '.join(row[2:6]))
    def test_rgo_drops_ordinary_free_parking(self):
        value='Для гостей есть бесплатная парковка. При предъявлении членского билета РГО предоставляется скидка 10% на бронирование.'
        row=self.row(record(value,conditions=value,program='Программа лояльности членов РГО'))
        self.assertIn('скидка 10%',row[2]);self.assertNotIn('парковка',' '.join(row[2:6]))
    def test_rzd_owns_points_not_merchants_generic_discount(self):
        value='Yota: скидка 15% для семей.\nПолучайте 1 балл за каждые 8 рублей в категории «Модемы и роутеры» и 254 балла за SIM-карту.\nНельзя использовать промокоды.\nПрограмма «РЖД Бонус» не несет ответственность за доставку.'
        row=self.row(record(value,conditions=value,program='РЖД Бонус',details={'retrieval_method':'google_import_public_text_v1'}))
        self.assertNotIn('15%', ' '.join(row[2:6]))
        for v in ('254','8 рублей','Модемы','Нельзя'):self.assertIn(v,' '.join(row[2:6]))
    def test_coral_inventory_free_books_not_actual_gift(self):
        body='В каталоге 400000 бесплатных книг.\nТолько для владельцев CoralBonus — 2 книги в подарок и скидка 25%.\nУсловия акции\nСкидка действует 3 дня после активации, только на одну покупку.'
        row=self.row(record('2 книги в подарок и скидка 25%',conditions=body,details={'public_coral_block':{'body':body}}))
        alltext=' '.join(row[2:6]);self.assertNotIn('400000',alltext)
        for v in ('25%','3 дня','одну покупку'):self.assertIn(v,alltext)
    def test_ural_stats_not_free_weeks(self):
        body='80% родителей отмечают успехи. Специальное предложение для участников «Крылья»: «Синяя» карта — 2 недели бесплатного обучения; «Золотая» — 4 недели. Только для новых клиентов.'
        row=self.row(record(body,conditions=body,program='Уральские авиалинии — «Крылья»'))
        self.assertNotIn('80%',' '.join(row[2:6]))
        for v in ('2 недели','4 недели','новых'):self.assertIn(v,' '.join(row[2:6]))
    def test_hse_keeps_prepaid_and_code_not_school_marketing(self):
        body='Наша миссия — обучение.\nСкидка 15% по промокоду HSE.\nПри условии предоплаты 100%.\nДля применения промокода, можно написать в Telegram.'
        row=self.row(record('Скидка 15% по промокоду HSE',conditions=body,activation=body,source_status='public_hse_partner_detail'))
        text=' '.join(row[2:6]);self.assertNotIn('Наша миссия',text)
        for v in ('15%','HSE','предоплаты 100%','Telegram'):self.assertIn(v,text)
    def test_mir_source_templates_keep_caps_and_currency_change(self):
        templates=[{'name':'need_to_register_cards','text':'Перед оплатой проверьте регистрацию карты.'},
                   {'name':'conditions','text':'Только Mir Supreme. Оплата QR-кодом не участвует.'},
                   {'name':'limits','text':'Не более 5 000 ₽ в месяц.'},
                   {'name':'disclamer','text':'С 01.10.2026 отдельные банки начисляют бонусы вместо денег.'}]
        row=self.row(record('Кешбэк 7% за оплату',conditions='Старый дубль',activation='Все преимущества карты и новости',details={'templates':templates,'catalog_profiles':['mir']}))
        text=' '.join(row[2:6]);self.assertNotIn('Все преимущества',text)
        for v in ('Mir Supreme','QR-кодом','5 000','01.10.2026','бонусы'):self.assertIn(v,text)
    def test_bulleted_rate_keeps_scope_and_not_truncated(self):
        value='Держателям карты предоставляются скидки:\n10% на первый заказ;\n5% на повторные заказы.'
        row=self.row(record(value,conditions=value))
        self.assertIn('10%',' '.join(row[2:6]));self.assertIn('повторные',' '.join(row[2:6]))
    def test_unrelated_fragment_not_made_a_benefit(self):
        self.assertIsNone(self.row(record('На исследования',conditions='',activation='')))
    def test_no_literal_backslash_n_in_rendered_text(self):
        row=self.row(record('Скидка 10%',details={'templates':[{'name':'conditions','text':'Первый заказ.\nОт 100 ₽.'}],'catalog_profiles':['mir']}))
        self.assertFalse(any('\\n' in v for v in row))
    def test_padding_readback(self):
        self.assertEqual(padded([['a'],['b','c']],2),[['a',''],['b','c']])
if __name__=='__main__':unittest.main()
