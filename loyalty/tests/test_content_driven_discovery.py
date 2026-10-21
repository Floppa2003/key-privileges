"""Counterfactual content changes, not a growing list of accepted examples."""
import copy
import sys
import unittest
from pathlib import Path
from bs4 import BeautifulSoup

sys.path.insert(0, str(Path(__file__).parents[1]))
import flystation_source as fly
import mantera_source as mantera
import mantera_partners as partners
import tier_sources as tiers
import tsvetnoy_source as tsvetnoy
from test_tier_sources import URAL, HEADER, NOW
from test_public_reward_sources import html

FLY = Path(__file__).parent.joinpath('fixtures_live/flystation-promotions.html').read_text()


class ContentDrivenDiscovery(unittest.TestCase):
    def test_flystation_new_named_reward_is_parsed_without_allowlist(self):
        soup = BeautifulSoup(FLY, 'html.parser')
        node = BeautifulSoup('<div class="promotions__slider-item-text"><p>Звёздный четверг</p>'
                             '<p>Скидка 17% на полёты по четвергам. Запишитесь заранее.</p></div>', 'html.parser').div
        soup.select_one('section.promotions').append(node)
        entries = fly.inventory(str(soup))
        self.assertEqual(len(entries), 7)
        fields = fly.source_fields(next(e for e in entries if e['title'] == 'Звёздный четверг'))
        self.assertIn('17%', fields['benefit'])
        self.assertIn('по четвергам', fields['conditions'])

    def test_flystation_renaming_does_not_choose_other_extractor(self):
        original = fly.source_fields(fly.inventory(FLY)[0])
        renamed = fly.source_fields(fly.inventory(FLY.replace('Раннее бронирование', 'Любое новое имя'))[0])
        self.assertEqual(original['terms'], renamed['terms'])
        self.assertEqual(original['conditions'], renamed['conditions'])

    def test_flystation_new_gift_is_not_a_price_only_exclusion(self):
        raw = FLY.replace('Хочу ЕЩЁ!', 'Седьмое предложение').replace(
            'Дополнительные 1,5 минуты', 'Дарим пробное занятие при покупке абонемента. Дополнительные 1,5 минуты')
        fields = fly.source_fields(next(e for e in fly.inventory(raw) if e['title'] == 'Седьмое предложение'))
        self.assertIn('пробное занятие', fields['benefit'])
        self.assertIn('при покупке абонемента', fields['conditions'])

    def test_mantera_new_tier_is_data(self):
        soup = BeautifulSoup(html('mantera-faq.html'), 'html.parser')
        block = next(n for n in soup.select('.MuiAccordion-root') if 'Какие статусы существуют' in n.get_text())
        li = soup.new_tag('li'); li.string = 'Исследователь — статус с начислением 11%, списанием 42%, при покупках от 190 000 рублей.'
        block.select_one('ul').append(li)
        rows = mantera.parse(str(soup), NOW)
        self.assertEqual(len(rows), 6)
        row = next(r for r in rows if 'Исследователь' in r['title'])
        self.assertIn('11%', row['benefit_text']); self.assertIn('42%', row['benefit_text'])

    def test_mantera_reordered_tiers_keep_own_rates(self):
        soup = BeautifulSoup(html('mantera-faq.html'), 'html.parser')
        block = next(n for n in soup.select('.MuiAccordion-root') if 'Какие статусы существуют' in n.get_text())
        ul = block.select_one('ul'); ul.insert(0, ul.find_all('li', recursive=False)[-1].extract())
        rows = mantera.parse(str(soup), NOW)
        old = mantera.parse(html('mantera-faq.html'), NOW)
        self.assertEqual({r['id']: r['benefit_text'] for r in rows}, {r['id']: r['benefit_text'] for r in old})

    def test_mantera_rewording_questions_and_pilot_does_not_freeze_content(self):
        raw = html('mantera-faq.html').replace('пилотного запуска', 'пилотной работы').replace(
            'ограниченном числе отелей', 'отдельных отелях').replace('365 дней', '400 дней').replace(
            'Нужно ли платить за участие в программе?', 'Какова стоимость участия?')
        rows = mantera.parse(raw, NOW)
        self.assertEqual(len(rows), 5)
        self.assertIn('400 дней', rows[0]['conditions_text'])
        self.assertIn('отдельных отелях', rows[0]['conditions_text'])
        self.assertIn('бесплатное', rows[0]['conditions_text'])

    def test_mantera_partner_table_discovers_names_count_and_order(self):
        table = [['Новый', 'от 123 рублей', '9%', 'до 31%'],
                 ['Другой', 'от 456 рублей', '12%', 'до 50%']]
        self.assertEqual([t[0] for t in partners.read_table(table)], ['Новый', 'Другой'])

    def test_ural_new_tier_is_not_silently_skipped(self):
        extra = '<h2>Платиновый уровень</h2><ul><li>Присваивается за 45 полетов.</li></ul><p>12% от суммы авиабилета.</p>'
        rows = tiers.ural_tiers(URAL.replace('</div><footer>', extra + '</div><footer>'), NOW)
        self.assertEqual(len(rows), 4)
        self.assertEqual(rows[-1]['details']['tier'], 'Платиновый')
        self.assertEqual(rows[-1]['details']['flight_bonus_rates'][0]['value'], '12')

    def test_utair_new_label_and_count_discovered_from_tab_geometry(self):
        tabs = tiers.utair_tabs(HEADER.replace('Basic', 'Explorer'))
        self.assertEqual(list(tabs), ['Start', 'Explorer'])
        self.assertEqual(tabs['Explorer']['spend_rub'], '10000')

    def test_tsvetnoy_arbitrary_tiers_discovered(self):
        raw = '<main>' + ''.join('<div class="loyality-terms__slide"><h3 class="loyality-terms__card-title">' + name + '</h3><p>Скидка 5%.</p></div>'
                                 for name in ('Первый', 'Второй', 'Третий', 'Четвёртый'))
        raw += '<div class="loyality-get-card">Зарегистрируйтесь. Цифровая карта.</div></main>'
        table, _ = tsvetnoy.tier_evidence(raw)
        self.assertEqual(list(table), ['Первый', 'Второй', 'Третий', 'Четвёртый'])


class AdditionalContentDiscovery(unittest.TestCase):
    def test_mantera_hotel_new_tier_and_reworded_faq(self):
        import mantera_hotel as hotel
        from test_public_reward_sources import common
        soup=BeautifulSoup(html('mantera-congress.html'),'html.parser')
        row=BeautifulSoup('<tr><td>Исследователь</td><td>от 12345 рублей</td><td>6%</td><td>до 22%</td></tr>','html.parser').tr
        soup.select_one('tbody').append(row)
        source=str(soup).replace('Нужно ли платить за участие в программе?','Какова стоимость участия?')
        from test_public_reward_sources import NOW as PUBLIC_NOW
        record=hotel.parse(source,PUBLIC_NOW)
        self.assertEqual(len(common(record)['benefits']),6)
        self.assertIn('Какова стоимость участия?',record['conditions_text'])

    def test_unknown_redemption_alias_preserved_not_guessed(self):
        from test_mantera_partners import pair
        from test_public_reward_sources import common
        rows,_=pair(b=html('mantera-redemption.html').replace('Долина 960, Кортьярд и Марриотт','Неизвестный отель'))
        self.assertTrue(rows)
        for row in rows:
            self.assertIn('Неизвестный отель',row['conditions_text'])
            self.assertNotIn('redeem_points',[b['kind'] for b in common(row)['benefits']])

    def test_new_exact_redemption_name_resolves_from_current_roster(self):
        from test_mantera_partners import pair
        from test_public_reward_sources import common
        s=BeautifulSoup(html('mantera-partners.html'),'html.parser')
        n=s.new_tag('li');n.string='Новый отель 4*';s.select_one('.accordion__item-content ul').append(n)
        rows,_=pair(str(s),html('mantera-redemption.html').replace('Долина 960, Кортьярд и Марриотт','Новый отель'))
        row=next(r for r in rows if r['partner_name']=='Новый отель 4*')
        self.assertEqual(len([b for b in common(row)['benefits'] if b['kind']=='redeem_points']),5)

    def test_tsum_new_card_not_in_historical_names(self):
        from tsum_alfa import extract_tsum,SOURCE_ID,URL
        source=Path(__file__).parent.joinpath('fixtures_live/tsum-alfa.html').read_text()
        soup=BeautifulSoup(source,'html.parser')
        node=copy.copy(soup.select('[class*="AlfaOnly__bounsWrapper___"]')[1])
        for text in list(node.find_all(string=True)):
            text.replace_with(str(text).replace('Orange','Purple').replace('8%','17%'))
        soup.select('[class*="AlfaOnly__bounsWrapper___"]')[-1].insert_after(node)
        rows=extract_tsum(SOURCE_ID,soup,URL,NOW,{})
        purple=next(r for r in rows if r['details']['tsum_tier']=='Purple')
        self.assertEqual(purple['rates'][0]['value'],'17')
        self.assertEqual(len(rows),4)

    def test_tsum_faq_heading_is_data_not_contract(self):
        from tsum_alfa import extract_tsum,SOURCE_ID,URL
        source=Path(__file__).parent.joinpath('fixtures_live/tsum-alfa.html').read_text().replace(
            'Как начисляется кешбэк в ЦУМе?','Как получить бонусы?')
        rows=extract_tsum(SOURCE_ID,BeautifulSoup(source,'html.parser'),URL,NOW,{})
        self.assertTrue(all('Как получить бонусы?' in r['conditions_text'] for r in rows))

    def test_mixx_new_service_and_automatic_rule_from_source(self):
        from t2_source import page_records
        source=Path(__file__).parent.joinpath('fixtures_live/t2-mixx.html').read_text()
        source=source.replace('Нейросети GPTMobile','Новый сервис Nebula')
        source=source.replace('Онлайн-кинотеатр КИОН','Онлайн-кинотеатр КИОН подключится автоматически')
        rows=page_records('t2_mixx',source,NOW)
        self.assertTrue(any('Nebula' in r['partner_name'] for r in rows))
        kion=next(r for r in rows if r['partner_name']=='КИОН')
        self.assertEqual(kion['details']['membership_component'],'included_automatically')

    def test_mixx_new_fixed_benefit_discovered(self):
        from t2_source import page_records
        source=Path(__file__).parent.joinpath('fixtures_live/t2-mixx.html').read_text().replace(
            'скидка 15% на', 'скидка 8% на НовыйМагазин, скидка 15% на')
        rows=page_records('t2_mixx',source,NOW)
        row=next(r for r in rows if r['partner_name']=='НовыйМагазин')
        self.assertEqual(row['rates'][0]['value'],'8')
        self.assertEqual(row['details']['membership_component'],'fixed')

    def test_third_speaker_model_with_new_title(self):
        from t2_source import page_records
        source=Path(__file__).parent.joinpath('fixtures_live/t2-mixx_s.html').read_text()
        source=source.replace('</ol>','<li>при покупке подписки MiXX S на 9 месяцев — скидку 22% на Другую колонку.</li></ol>')
        rows=page_records('t2_mixx_s',source,NOW)
        self.assertEqual(len(rows),3)
        self.assertEqual(rows[-1]['details']['required_subscription_months'],9)
        self.assertEqual(rows[-1]['rates'][0]['value'],'22')

    def test_utair_new_partner_and_tier_are_discovered_without_fetch(self):
        from partner_pages import utair_partners
        source='<div id="rec774882292" class="uc-showmore3"><a href="https://newpartner.example/">17% милями для уровней Diamond и Explorer</a></div>'
        rows=utair_partners(BeautifulSoup(source,'html.parser'),'https://media.utair.ru/status',NOW)
        self.assertEqual(len(rows),1)
        self.assertEqual(rows[0]['partner_name'],'newpartner.example')
        self.assertEqual(rows[0]['details']['tier_rates'][0]['tiers'],['Diamond','Explorer'])

    def test_sacvoyage_new_section_and_renaming(self):
        from test_sacvoyage_loyalty import page,SID,URL
        from adapters import extract
        source=page().replace('Реферальная программа','Новая программа').replace(
            '<p>Условия могут меняться.', '<p><strong>Третий вариант</strong></p><p>Скидка 18% на второе проживание.</p><p>Условия могут меняться.')
        rows=extract(SID,source,URL,NOW)
        self.assertEqual(len(rows),3)
        self.assertEqual(rows[-1]['rates'][0]['value'],'18')
        self.assertNotIn('корпоративным',rows[-1]['conditions_text'])

    def test_new_bank_product_option_has_own_rates(self):
        from test_public_product_rules import sample,URL
        from known_rules import parse_known_rule
        source=sample()+'<div class="TariffsMsbItemContent_root__new"><h5>Новая опция</h5><p>499 ₽ в месяц</p><p>Мили «Аэрофлот Бонус» 4 мили за 150 ₽ покупок</p><p>Максимум миль в месяц 8000</p></div>'
        options=parse_known_rule('af_gpb_rules',source,URL,NOW)[0]['details']['mileage_options']
        self.assertEqual(len(options),3)
        self.assertEqual(options[-1]['label'],'Новая опция')
        self.assertEqual((options[-1]['miles'],options[-1]['basis_rub']),('4','150'))

    def test_artparking_new_service_and_count(self):
        from test_ekp_merchant_public import parse,FIXTURES
        source=(FIXTURES/'artparking.html').read_text().replace('Промокод edkarta</p>',
            'Промокод edkarta<br/>Мастерские www.workshops.example – 19% Промокод NEWCODE</p>')
        rows=parse('artparking',source)
        self.assertEqual(len(rows),3)
        self.assertEqual(rows[-1]['rates'][0]['value'],'19')
        self.assertEqual(rows[-1]['promo_codes'],['NEWCODE'])
        self.assertNotIn('оплачивать заранее',rows[-1]['conditions_text'])

    def test_current_code_and_tiers_are_not_identity_markers(self):
        from known_rules import CONFIG,parse_known_rule
        rows=parse_known_rule('ural_triangle_rules','<div class="content -detail"><div class="ustyle">Крылья: скидка 19% по промокоду NEWCODE.</div></div>',CONFIG['ural_triangle_rules']['url'],NOW)
        self.assertIn('NEWCODE',rows[0]['promo_codes'])

    def test_valueerror_diagnostic_code_kept_but_secrets_not_logged(self):
        from collect_normalized import error_record
        self.assertEqual(error_record(ValueError('source_changed'), 'parse')['reason'],'source_changed')
        self.assertEqual(error_record(ValueError('token=secret'), 'parse')['reason'],'ValueError')

    def test_json_roundtrip_preserves_current_evidence_projection(self):
        import json
        from normalized import validate_offer
        import mantera_hotel
        from test_mantera_partners import pair
        rows=mantera.parse(html('mantera-faq.html'),NOW)+[mantera_hotel.parse(html('mantera-congress.html'),NOW)]+pair()[0]
        for row in rows:validate_offer(json.loads(json.dumps(row,sort_keys=True)))



class LiteralContentSafety(unittest.TestCase):
    def test_prepayment_percentage_is_not_an_extra_discount(self):
        from content_discovery import literal_benefits
        claims,terms=literal_benefits('Скидка 10% при предоплате 50% стоимости заказа.')
        self.assertEqual([(t['kind'],t['value']) for t in terms],[('discount','10')])
        self.assertIn('50%',claims[0])

    def test_negative_gift_is_not_a_benefit(self):
        from content_discovery import literal_benefits
        for body in ('Мы не дарим пробное занятие.', 'Бесплатных подарков не предоставляется.'):
            self.assertEqual(literal_benefits(body),([],[]))

    def test_price_only_inventory_is_evidence_not_a_publishable_discount(self):
        from test_flystation import RAW,OLD
        import flystation_source as fly
        from public_reward_projection import make_record
        from test_public_reward_sources import common
        from catalogue_view import record_row
        e=next(e for e in fly.inventory(RAW) if e['native']=='extra-time')
        n=common(make_record(fly.SOURCE,e,'2026-09-22T10:42:11+00:00'))
        self.assertEqual(n['benefits'],[])
        self.assertIsNone(record_row(n,'2026-09-22')[0])


if __name__ == '__main__':
    unittest.main()
