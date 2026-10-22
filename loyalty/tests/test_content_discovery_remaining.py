"""Mutation regressions for live admission gates found during the follow-up audit."""
import copy
import sys
import unittest
from pathlib import Path
from bs4 import BeautifulSoup
sys.path.insert(0, str(Path(__file__).parents[1]))
from normalized import validate_offer
from test_ekp_public_20260925 import parse, FIX
from test_hse_alumni import card, page, section, NOW
from hse_alumni import parse_catalog


class RemainingDiscoveryTests(unittest.TestCase):
    def test_ladoga_new_percentage_is_source_data(self):
        raw=(FIX/'ladoga.html').read_text().replace('При бронировании','Скидка 10% на проживание. При бронировании')
        row,=parse(raw=raw)
        self.assertIn('10%',row['benefit_text'])
        self.assertEqual(row['details']['gift']['duration_hours'],2)
        validate_offer(row)

    def test_ladoga_new_gift_item_preserved_without_old_item_assignment(self):
        raw=(FIX/'ladoga.html').read_text().replace('сапбордов','лодок')
        row,=parse(raw=raw)
        self.assertIn('лодок',row['benefit_text'])
        self.assertIsNone(row['details'].get('gift'))
        validate_offer(row)

    def test_ladoga_new_notes_count_not_two(self):
        dom=BeautifulSoup((FIX/'ladoga.html').read_text(),'html.parser')
        dom.body.append(BeautifulSoup('<div>*ВНИМАНИЕ! Новое третье условие</div><div>*ВНИМАНИЕ! Четвёртое условие</div>','html.parser'))
        row,=parse(raw=str(dom))
        self.assertEqual(len(row['details']['general_page_notes']),3)
        self.assertNotIn('Четвёртое',row['conditions_text'])

    def test_ladoga_all_owned_program_cards_and_stable_ids(self):
        dom=BeautifulSoup((FIX/'ladoga.html').read_text(),'html.parser')
        original=dom.select_one('.js-product')
        other=copy.copy(original);other['data-product-lid']='new-product-42'
        other.select_one('.js-product-name').string='Новое предложение ЕКП'
        other.select_one('.t778__descr').string='Скидка 13% на проживание по вторникам.'
        original.insert_before(other)
        rows=parse(raw=str(dom))
        self.assertEqual(len(rows),2)
        self.assertEqual(len({r['id'] for r in rows}),2)
        self.assertIn(parse()[0]['id'],{r['id'] for r in rows})
        self.assertTrue(any('13%' in r['benefit_text'] for r in rows))

    def test_ladoga_unclassified_owned_block_not_another_cards_gift(self):
        dom=BeautifulSoup((FIX/'ladoga.html').read_text(),'html.parser')
        dom.select_one('.t778__descr').string='Подробности в новом разделе.'
        row,=parse(raw=str(dom))
        self.assertEqual(row['record_kind'],'source_observation')
        self.assertEqual(row['rates'],[])
        self.assertIsNone(row['details'].get('gift'))

    def test_ladoga_current_eligibility_links_are_not_frozen(self):
        raw=(FIX/'ladoga.html').read_text().replace('capabilities?capability=offer','new-conditions')
        row,=parse(raw=raw)
        self.assertEqual(row['details']['published_links'],['https://ekp.spb.ru/new-conditions'])
        self.assertFalse(row['details']['linked_page_read'])

    def test_hse_new_unanchored_name_joins_current_catalogue(self):
        raw=page(card('new','Новое дело'),'<div class="builder-section"><h2>Новое дело</h2><p>Скидка 17%</p></div>')
        row,=parse_catalog(raw,NOW)
        self.assertEqual(row['record_kind'],'partner_offer')
        self.assertEqual(row['rates'][0]['value'],'17')
        validate_offer(row)

    def test_hse_renamed_unanchored_card_not_historical_alias(self):
        from test_hse_unanchored import fixture
        raw=fixture().replace('Морда довольна','Новый бренд').replace('mordapechat','new-anchor')
        before,row,after=parse_catalog(raw,NOW)
        self.assertEqual(row['promo_codes'],['PRINT_ONLY'])
        self.assertNotIn('PRINT_ONLY',before['promo_codes'])
        self.assertEqual(after['promo_codes'],['OTHER_ONLY'])
        validate_offer(row)

    def test_hse_partial_business_name_is_not_a_match(self):
        raw=page(card('new','Клуб'),'<div class="builder-section"><h2>Клубника</h2><p>Скидка 77%</p></div>')
        row,=parse_catalog(raw,NOW)
        self.assertEqual(row['record_kind'],'source_observation')

    def test_hse_two_new_unanchored_names_keep_scope(self):
        raw=page(card('first','Первая марка')+card('second','Вторая марка'),
            '<div class="builder-section"><h2>Вторая марка</h2><p>Скидка 19%</p></div>'
            '<div class="builder-section"><h2>Первая марка</h2><p>Скидка 7%</p></div>')
        rows=parse_catalog(raw,NOW)
        self.assertEqual([r['rates'][0]['value'] for r in rows],['7','19'])
        for row in rows:validate_offer(row)

    def test_ladoga_prepayment_is_not_a_second_discount(self):
        for clause in ('Скидка 10% при предоплате 100%.', 'Скидка 10% при 100% предоплате.'):
            dom=BeautifulSoup((FIX/'ladoga.html').read_text(),'html.parser')
            dom.select_one('.t778__descr').string=clause
            row,=parse(raw=str(dom))
            self.assertEqual([r['value'] for r in row['rates']],['10'])
            self.assertIn('100%',row['conditions_text'])
            validate_offer(row)

    def test_flystation_raw_rate_matches_scoped_reward_term(self):
        from flystation_source import inventory, SOURCE
        from public_reward_projection import make_record
        raw='<section class="promotions"><div class="promotions__slider-item-text"><p>Новое предложение</p><p>Скидка 12% при предоплате 50%.</p></div></section>'
        evidence,=inventory(raw)
        row=make_record(SOURCE,evidence,NOW)
        self.assertEqual([r['value'] for r in row['rates']],['12'])
        validate_offer(row)

    def test_hse_ambiguous_current_names_do_not_borrow_a_heading(self):
        raw=page(card('first','Одна марка')+card('second','Одна марка'),
                 '<div class="builder-section"><h2>Одна марка</h2><p>Скидка 17%</p></div>')
        rows=parse_catalog(raw,NOW)
        self.assertEqual(len(rows),2)
        for row in rows:
            self.assertEqual(row['record_kind'],'source_observation')
            self.assertEqual(row['benefit_text'],'')
            self.assertEqual(row['details']['public_catalog_block']['detail_state'],'ambiguous_heading')

    def test_smartavia_arbitrary_plan_label_does_not_require_1_plus_n(self):
        from test_known_rules import SmartaviaTests, parse as parse_rule
        raw=SmartaviaTests().fixture().replace('Тариф 1+0','Тариф Семейный')
        rows=parse_rule('smartavia_rules',raw)
        row=next(r for r in rows if r['details'].get('subscription_plan',{}).get('label')=='Семейный')
        self.assertIsNone(row['details']['subscription_plan']['additional_travelers'])
        self.assertTrue(row['details']['subscription_plan']['annual_rub'])

if __name__=='__main__':unittest.main()
