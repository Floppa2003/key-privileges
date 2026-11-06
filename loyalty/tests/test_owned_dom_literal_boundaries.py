"""Owned source fields survive inline markup and one-time entity decoding."""
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1]))
from adapters import extract
from normalized import validate_offer
from partner_pages import CONFIG
from sheets_normalized import SCHEMAS, prepare
from unified_normalization import make_input, normalize_record
import coral_catalog
import test_coral_catalog as coral
import test_coral_catalog_repair as coral_repair
import test_ekp_merchant_public as merchant
import test_ekp_public_20260925 as stays
import test_ilocked_ekp as ilocked
import test_sacvoyage_rzd as sacvoyage

MARKUP = 'Метка &lt;VIP&gt;; сущность &amp;lt;tag&amp;gt;.'
LITERAL = 'Метка <VIP>; сущность &lt;tag&gt;.'
ROSTELECOM = '''<section class="content_section"><h1>Ростелеком — Единая карта петербуржца</h1><div class="news-detail"><span class="newsdata">16.12.2025</span><p>В рамках партнерства новые клиенты могут подключить услугу «Домашний интернет» всего за 1 рубль и получить скидку 20% на абонентскую плату. Для действующих абонентов «Ростелекома», являющихся держателями ЕКП, предусмотрена скидка 10% на услугу «Домашний интернет». Подробная информация о программе лояльности доступна в карточке партнера.</p></div></section>'''


def publication(row):
    """Exercise the real validated source-to-parser-sheet serialization."""
    validate_offer(row)
    report = dict(source_id=row['source_id'], name=row['program'], root=row['source_url'],
                  status='ok', discovered=1, normalized=1, failed=0,
                  coverage='fixture_owned_block', region=None, errors=[], observed_at=row['observed_at'])
    bundle = dict(schema_version=2, run_id='literal-dom:fixture', observed_at=row['observed_at'],
                  sources=[report], records=[row])
    values, = prepare(bundle)['parser_offers']
    return dict(zip(SCHEMAS['parser_offers'], values))


class IlockedLiteralBoundaryTests(unittest.TestCase):
    def parse(self, raw):
        row, = extract(ilocked.SID, raw, ilocked.URL, ilocked.NOW)
        return row

    def test_inline_quest_title_keeps_its_literal_identity_through_publication(self):
        raw = ilocked.page(title='QuestA<span>B</span> ' + MARKUP)
        row = self.parse(raw)
        self.assertEqual(row['title'], 'QuestAB ' + LITERAL)
        self.assertEqual(publication(row)['Заголовок'], 'QuestAB ' + LITERAL)

    def test_inline_rate_and_code_are_not_split_between_text_nodes(self):
        for body in (ilocked.claim(code='FIXTURE<span>_ONLY</span>'),
                     ilocked.claim(rate='17<b>,</b>5')):
            with self.subTest(body=body):
                row = self.parse(ilocked.page(body))
                self.assertEqual(row['promo_codes'], ['FIXTURE_ONLY'])
                self.assertEqual(row['rates'][0]['value'], '17.5')
                self.assertNotIn('OTHER_ONLY', json.dumps(row))
                self.assertEqual(json.loads(publication(row)['Промокоды JSON']), ['FIXTURE_ONLY'])

    def test_intro_retains_paragraphs_and_treats_br_as_whitespace(self):
        body = ilocked.claim().replace('Для владельцев', 'Для<br>владельцев').replace(
            '. Перед игрой', '.<br>Перед игрой')
        raw = ilocked.page(body).replace('Synthetic deposit 1234 RUB;', 'Synthetic deposit<br>1234 RUB;')
        row = self.parse(raw)
        self.assertIn('Для владельцев', row['benefit_text'])
        self.assertIn('FIXTURE_ONLY. Перед игрой', row['benefit_text'])
        self.assertIn('саму карту!\nВАЖНО:', row['conditions_text'])
        self.assertIn('Synthetic deposit 1234 RUB;', row['conditions_text'])
        self.assertNotIn('OTHER_ONLY', json.dumps(row))
        publication(row)

    def test_break_before_discount_label_keeps_rate_through_the_common_reader(self):
        body = ilocked.claim().replace('% СКИДКА', '%<br>СКИДКА')
        row = self.parse(ilocked.page(body))
        self.assertIn('17,5% СКИДКА', row['benefit_text'])
        self.assertEqual([(rate['kind'], rate['value']) for rate in row['rates']], [('discount', '17.5')])
        self.assertIn('17,5% СКИДКА', row['rates'][0]['evidence'])
        published = publication(row)
        raw = make_input({'id': row['id'], 'origin': 'parser_offers', 'row': 2,
                          'fields': {key: {'value': value} for key, value in published.items()}})
        common = normalize_record(raw, as_of='2026-11-06')
        self.assertEqual([(benefit['kind'], benefit['value']) for benefit in common['benefits']
                          if benefit['unit'] == 'percent'], [('discount', '17.5')])
        self.assertEqual(common['raw']['benefit'], row['benefit_text'])

    def test_discount_label_in_another_paragraph_cannot_supply_the_rate(self):
        body = ilocked.claim().replace('% СКИДКА', '%</p><p>СКИДКА')
        with self.assertRaisesRegex(ValueError, 'ilocked_ekp_benefit_or_code_ambiguous'):
            self.parse(ilocked.page(body))

    def test_certificate_restriction_decodes_once_and_keeps_breaks(self):
        fixture = ilocked.IlockedCertificateTests()
        raw = fixture.page('На игры по подарочным<br>сертификатам скидки не распространяются. ' + MARKUP)
        row, = extract(fixture.SID, raw, fixture.URL, ilocked.NOW)
        expected = 'На игры по подарочным\nсертификатам скидки не распространяются. ' + LITERAL
        self.assertEqual(row['conditions_text'], expected)
        self.assertEqual(publication(row)['Условия'], expected)
        self.assertEqual(row['rates'], [])
        self.assertEqual(row['promo_codes'], [])


class EkpPublicLiteralBoundaryTests(unittest.TestCase):
    def assert_common_discount(self, row, expected):
        self.assertEqual([(rate['kind'], rate['value']) for rate in row['rates']], [('discount', expected)])
        published = publication(row)
        raw = make_input({'id': row['id'], 'origin': 'parser_offers', 'row': 2,
                          'fields': {key: {'value': value} for key, value in published.items()}})
        common = normalize_record(raw, as_of='2026-11-06')
        self.assertEqual({benefit['value'] for benefit in common['benefits']
                          if benefit['kind'] == 'discount' and benefit['unit'] == 'percent'}, {expected})

    def test_merchant_br_before_rate_keeps_source_and_common_values(self):
        cases = [('domknigi', 'скидка 10%', 'скидка<br>10%', '10'),
                 ('itc', '-15%', '-<br>15%', '15')]
        for name, old, new, expected in cases:
            with self.subTest(source=name):
                raw = (merchant.FIXTURES / (name + '.html')).read_text().replace(old, new)
                row, = merchant.parse(name, raw)
                self.assert_common_discount(row, expected)

    def test_ladoga_br_in_current_discount_clause_keeps_rate_and_paragraphs(self):
        from bs4 import BeautifulSoup
        soup = BeautifulSoup((stays.FIX / 'ladoga.html').read_text(), 'html.parser')
        description = soup.select_one('.t778__descr')
        description.clear()
        description.append(BeautifulSoup('<p>Скидка<br>10% при бронировании.</p><p>Только по предварительному согласованию.</p>', 'html.parser'))
        row, = stays.parse('ladoga', str(soup))
        self.assert_common_discount(row, '10')
        self.assertIn('при бронировании.\nТолько по', row['conditions_text'])

    def test_domknigi_inline_rate_is_the_same_source_claim(self):
        raw = (merchant.FIXTURES / 'domknigi.html').read_text().replace('10%', '1<span>0</span>%')
        row, = merchant.parse('domknigi', raw)
        self.assertEqual(row['rates'][0]['value'], '10')
        self.assertIn('скидка 10%', publication(row)['Выгода'])

    def test_domknigi_conditions_keep_literal_entities_and_explicit_breaks(self):
        raw = (merchant.FIXTURES / 'domknigi.html').read_text().replace(
            'Дом книги и Единая', 'Дом<br>книги и Единая').replace(
            'Условия и ограничения:', 'Условия и ограничения:</p><p>' + MARKUP)
        row, = merchant.parse('domknigi', raw)
        self.assertIn('Дом книги и Единая', row['benefit_text'])
        self.assertIn('Условия и ограничения:\n' + LITERAL, row['conditions_text'])
        self.assertIn(LITERAL, publication(row)['Условия'])

    def test_ladoga_inline_quantity_keeps_the_gift_and_minimum_stay(self):
        raw = (stays.FIX / 'ladoga.html').read_text().replace('от 2х суток', 'от <span>2</span>х суток')
        row, = stays.parse('ladoga', raw)
        self.assertEqual(row['details']['minimum_stay']['value'], 2)
        self.assertEqual(row['details']['gift']['duration_hours'], 2)
        self.assertEqual([v['quantity'] for v in row['details']['gift']['options']], [2, 2])
        published = json.loads(publication(row)['Детали JSON'])
        self.assertEqual(published['minimum_stay']['value'], 2)

    def test_ladoga_original_description_and_structured_evidence_keep_breaks(self):
        raw = (stays.FIX / 'ladoga.html').read_text().replace(
            'При бронировании', '<p>' + MARKUP + '</p>При бронировании').replace('от 2х суток', 'от 2х<br>суток')
        row, = stays.parse('ladoga', raw)
        self.assertIn(LITERAL + '\nПри бронировании', row['conditions_text'])
        self.assertIn('от 2х суток', row['details']['minimum_stay']['evidence'])
        self.assertIn('от 2х суток', row['details']['gift']['evidence'])
        self.assertIn('При бронировании от 2х суток', row['benefit_text'])
        self.assertIn('При бронировании от 2х суток', row['redemption_text'])
        self.assertIn(LITERAL, publication(row)['Условия'])


class PartnerPageLiteralBoundaryTests(unittest.TestCase):
    def test_published_link_label_preserves_inline_text_and_entities(self):
        for markup, expected in (('wrong-<span>label</span>.example', 'wrong-label.example'),
                                 (MARKUP, LITERAL)):
            with self.subTest(markup=markup):
                raw = sacvoyage.page().replace('wrong-label.example', markup)
                row, = extract(sacvoyage.SID, raw, sacvoyage.URL, sacvoyage.NOW)
                self.assertEqual(row['details']['published_links'],
                                 [{'label': expected, 'href': 'https://sacvoyage.ru/'}])
                details = json.loads(publication(row)['Детали JSON'])
                self.assertEqual(details['published_links'][0]['label'], expected)

    def test_rostelecom_inline_rate_preserves_two_audiences(self):
        sid = 'ekp_rostelecom'
        raw = ROSTELECOM.replace('скидку 20%', 'скидку 2<span>0</span>%')
        rows = extract(sid, raw, CONFIG[sid]['url'], sacvoyage.NOW)
        self.assertEqual(len(rows), 2)
        for row in rows:
            expected = '20' if row['details']['audience'] == 'new_customers' else '10'
            self.assertEqual([rate['value'] for rate in row['rates']], [expected])
            self.assertIn('скидк', publication(row)['Выгода'])
            self.assertEqual(row['details']['article_published_at'], '2025-12-16')

    def test_rostelecom_br_before_rate_keeps_both_audiences_in_common_view(self):
        sid = 'ekp_rostelecom'
        raw = ROSTELECOM.replace('скидку 20%', 'скидку<br>20%').replace('скидка 10%', 'скидка<br>10%')
        rows = extract(sid, raw, CONFIG[sid]['url'], sacvoyage.NOW)
        for row in rows:
            expected = '20' if row['details']['audience'] == 'new_customers' else '10'
            self.assertEqual([rate['value'] for rate in row['rates']], [expected])
            published = publication(row)
            source = make_input({'id': row['id'], 'origin': 'parser_offers', 'row': 2,
                                 'fields': {key: {'value': value} for key, value in published.items()}})
            common = normalize_record(source, as_of='2026-11-06')
            self.assertIn(expected, {benefit['value'] for benefit in common['benefits']
                                    if benefit['kind'] == 'discount' and benefit['unit'] == 'percent'})

    def test_rostelecom_section_boundaries_use_original_breaks(self):
        sid = 'ekp_rostelecom'
        raw = ROSTELECOM.replace('новые клиенты', 'новые<br>клиенты').replace(
            '. Для действующих', '.<br>Для действующих').replace(
            '. Подробная', '.<br>Подробная')
        rows = extract(sid, raw, CONFIG[sid]['url'], sacvoyage.NOW)
        self.assertIn('новые клиенты', rows[0]['benefit_text'])
        self.assertIn('новые\nклиенты', rows[0]['conditions_text'])
        self.assertNotIn('Для действующих', rows[0]['benefit_text'])
        self.assertNotIn('20%', rows[1]['benefit_text'])
        self.assertTrue(all(row['redemption_text'].startswith('Подробная информация') for row in rows))


class CoralSideFieldLiteralBoundaryTests(unittest.TestCase):
    def promo_record(self, raw):
        return coral_catalog.detail(raw, 'coral_promo',
                                    {'url': coral_catalog.PROMO + 'future/', 'title': 'Бонусы нового путешествия'},
                                    coral.NOW, {})

    def test_inline_table_number_agrees_with_the_original_body(self):
        row = self.promo_record(coral.promo().replace('1234', '12<span>34</span>'))
        self.assertEqual(row['tables'][0][1][1], '1234')
        details = json.loads(publication(row)['Детали JSON'])
        self.assertEqual(details['tables'][0][1][1], '1234')

    def test_inline_unresolved_template_cannot_pass_catalogue_readiness(self):
        entry = {'url': coral_catalog.CLUB + 'gifts/', 'title': 'Подарки'}
        raw = coral.doc('<section class="ng-scope"><h1>Подарки</h1><div id="categoryProductsList">'
                        '<div class="product-box referal"><a href="' + coral.URL + '">x</a></div>'
                        '<div class="product-box base">{<span>{</span>vm.loading}}</div></div></section>',
                        entry['url'])
        with self.assertRaisesRegex(ValueError, 'coral_category_not_rendered'):
            coral_catalog.category_cards(raw, entry)

    def test_table_context_and_cells_decode_entities_once(self):
        raw = coral.promo().replace('Первая область', 'Первая<br>область. ' + MARKUP).replace(
            'Регион А', 'Регион А. ' + MARKUP)
        row = self.promo_record(raw)
        self.assertEqual(row['details']['public_coral_block']['table_contexts'], ['Первая\nобласть. ' + LITERAL])
        self.assertEqual(row['tables'][0][1][0], 'Регион А. ' + LITERAL)
        publication(row)

    def test_inline_redemption_heading_keeps_the_owned_instructions(self):
        raw = coral.product().replace('Как воспользоваться', 'Как вос<span>пользоваться</span>')
        row = coral.CoralMappingTests().record(raw)
        self.assertIn('Введите код при заказе.', row['redemption_text'])
        self.assertIn('Введите код при заказе.', publication(row)['Как получить'])

    def test_public_link_label_is_a_literal_not_another_html_document(self):
        row = coral.CoralMappingTests().record(coral.product().replace('Сайт партнера', MARKUP))
        self.assertEqual(row['details']['public_coral_block']['links'][0]['label'], LITERAL)
        self.assertIn(LITERAL, row['conditions_text'])
        publication(row)

    def test_ticket_notice_identity_accepts_inline_markup_and_keeps_breaks(self):
        raw = coral_repair.ticket().replace('купить билеты нужно', 'ку<span>пить</span> билеты<br>нужно')
        row = coral_repair.PublicTicketTests().read(raw)
        expected = 'Чтобы купить билеты\nнужно авторизоваться на сайте'
        self.assertEqual(row['details']['public_coral_block']['authentication_notice'], expected)
        self.assertIn(expected, row['redemption_text'])
        self.assertEqual(row['details']['redemption_mode'], 'ticket_purchase')
        self.assertFalse(row['details']['private_coupon_issued'])
        self.assertNotIn('PRIVATE', json.dumps(row))
        publication(row)


if __name__ == '__main__':
    unittest.main()
