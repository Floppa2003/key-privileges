"""Owned card and tier text survives inline DOM, publication, and common input."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1]))
import selection_source as selection
import tier_sources as tiers
import t2_source as t2
import utair_support as utair
from normalized import validate_offer
from sheets_normalized import prepare, SCHEMAS
from unified_normalization import make_input, normalize_record
import test_selection_source as sf
import test_tier_sources as tf
import test_utair_support as uf


ENTITY_HTML = 'Метка &lt;VIP&gt;; сущность &amp;lt;tag&amp;gt;.'
ENTITY_TEXT = 'Метка <VIP>; сущность &lt;tag&gt;.'
FIXTURES = Path(__file__).with_name('fixtures_live')


def project(row):
    validate_offer(row)
    bundle = {'schema_version': 2, 'run_id': 'dom-boundaries:1',
              'observed_at': row['observed_at'], 'records': [row], 'sources': [{
                  'source_id': row['source_id'], 'name': 'Public source', 'root': row['source_url'],
                  'status': 'ok', 'normalized': 1, 'discovered': 1, 'failed': 0,
                  'coverage': 'owned fixture', 'region': None, 'errors': [],
                  'observed_at': row['observed_at'],
              }]}
    values = prepare(bundle)['parser_offers'][0]
    raw = make_input({'id': row['id'], 'origin': 'parser_offers', 'row': 2,
                      'fields': {key: {'value': value}
                                 for key, value in zip(SCHEMAS['parser_offers'], values)}})
    return normalize_record(raw, as_of=row['observed_at'][:10])


class SelectionDomBoundaries(unittest.TestCase):
    def test_inline_identity_and_date_keep_the_same_public_card(self):
        original = selection.preview_record(sf.snapshot(), 'msk', sf.NOW)
        card = sf.CARD.replace('Доступ', 'До<span>ступ</span>').replace('MILE', 'MI<b>LE</b>')
        popup = sf.POPUP.replace('30 сентября', '3<span>0</span> сентября')
        try:
            row = selection.preview_record(sf.snapshot(card, popup), 'msk', sf.NOW)
        except ValueError as exc:
            self.fail('An equivalent owned public card was rejected: ' + str(exc))
        self.assertEqual(row['title'], 'Доступ в бизнес-залы')
        self.assertEqual(row['partner_name'], 'MILE·ON·AIR')
        self.assertEqual(row['id'], original['id'])
        self.assertEqual(row['valid_until'], '2026-09-30')
        self.assertEqual(row['details']['published_hints'], ['Акция действует до 30 сентября 2026'])
        common = project(row)
        self.assertEqual(common['validity']['until'], '2026-09-30')
        self.assertEqual(common['kind'], 'tier_benefit')
        self.assertIsNone(common['eligibility_verified'])

    def test_inline_code_decimal_and_entities_reach_common_input_intact(self):
        description = 'Скидка 17<b>,</b>5% по промокоду SUM<span>MER</span>26. ' + ENTITY_HTML
        popup = sf.POPUP.replace(
            'Доступ в бизнес-залы аэропортов Москвы, Санкт-Петербурга и Екатеринбурга', description)
        row = selection.preview_record(sf.snapshot(popup=popup), 'msk', sf.NOW)
        expected = ('Скидка 17,5% по промокоду SUMMER26. ' + ENTITY_TEXT
                    + '\nАкция действует до 30 сентября 2026')
        self.assertEqual(row['conditions_text'], expected)
        self.assertEqual(row['promo_codes'], ['SUMMER26'])
        common = project(row)
        self.assertEqual(common['raw']['conditions'], expected)
        self.assertEqual({c['value'] for c in common['codes']}, {'SUMMER26'})

    def test_pre_and_br_preserve_description_boundaries(self):
        for newline in ('\r', '\r\n', '\n'):
            with self.subTest(newline=repr(newline)):
                popup = sf.POPUP.replace(
                    'Доступ в бизнес-залы аэропортов Москвы, Санкт-Петербурга и Екатеринбурга',
                    '<p>Начало<br>Ограничения</p><pre>Первая' + newline + 'Вторая</pre>')
                row = selection.preview_record(sf.snapshot(popup=popup), 'msk', sf.NOW)
                expected = 'Начало\nОграничения\nПервая\nВторая\nАкция действует до 30 сентября 2026'
                self.assertEqual(row['conditions_text'], expected)
                self.assertEqual(project(row)['raw']['conditions'], expected)

    def test_wrapped_heading_matches_without_rewriting_published_title(self):
        card = sf.CARD.replace('Доступ в бизнес-залы', 'Доступ<br>в бизнес-залы')
        try:
            row = selection.preview_record(sf.snapshot(card=card), 'msk', sf.NOW)
        except ValueError as exc:
            self.fail('The existing wrapped-heading layout was rejected: ' + str(exc))
        self.assertEqual(row['title'], 'Доступ\nв бизнес-залы')
        self.assertEqual(row['details']['popup_title'], 'ДОСТУП В БИЗНЕС-ЗАЛЫ')


class TierDomBoundaries(unittest.TestCase):
    def test_inline_flight_count_keeps_full_quantity_and_literal_evidence(self):
        raw = tf.URAL.replace('15 полетов', '1<span>5</span> полетов').replace(
            '200 000 рублей', '200 000 рублей. ' + ENTITY_HTML)
        row = tiers.ural_tiers(raw, tf.NOW)[1]
        qualification = row['details']['qualification']
        self.assertEqual(qualification['flights'], 15)
        self.assertEqual(qualification['spend_rub'], '200000')
        self.assertEqual(qualification['operator'], 'OR')
        self.assertIn(ENTITY_TEXT, qualification['evidence'])
        self.assertEqual(project(row)['raw']['details']['qualification']['flights'], 15)

    def test_inline_tab_name_price_and_tooltip_preserve_qualification(self):
        raw = tf.HEADER.replace('>Basic<', '>Ba<span>sic</span><').replace(
            'c 10 тыс. руб.', 'c 1<b>0</b> тыс. руб.').replace(
            'календарном году', 'календарном году. ' + ENTITY_HTML)
        tabs = tiers.utair_tabs(raw)
        self.assertEqual(list(tabs), ['Start', 'Basic'])
        self.assertEqual(tabs['Basic']['spend_rub'], '10000')
        self.assertEqual(tabs['Basic']['window'], 'calendar_year')
        self.assertEqual(tabs['Basic']['scope_text'],
                         'Потраченных на полеты с Utair, совершённые в календарном году. ' + ENTITY_TEXT)

    def test_wrapped_tab_price_and_window_still_match_but_evidence_keeps_lines(self):
        raw = tf.HEADER.replace('c 10 тыс. руб.', 'c<br>10 тыс. руб.').replace(
            'календарном году', 'календарном<br>году')
        tab = tiers.utair_tab(raw, 'Basic')
        self.assertEqual(tab['spend_rub'], '10000')
        self.assertEqual(tab['window'], 'calendar_year')
        self.assertEqual(tab['qualification_text'], 'c\n10 тыс. руб.')
        self.assertTrue(tab['scope_text'].endswith('календарном\nгоду'))

    def test_link_label_and_intro_evidence_are_not_parsed_twice(self):
        panel = tf.PANEL.replace('Подробнее', 'Под<span>роб</span>нее ' + ENTITY_HTML)
        intro = ('<div class="t-rec">Программа лояльности Utair Status: сервисы '
                 'с 1<span>0</span> 000 ₽, потраченных на полеты. ' + ENTITY_HTML + '</div>')
        context = tiers.utair_intro_context(intro)
        self.assertEqual(context['spend_rub_values'], ['10000'])
        self.assertIn(ENTITY_TEXT, context['observations'][0]['evidence'])
        row = tiers.utair_tier(panel, tiers.utair_tab(tf.HEADER, 'Basic'),
                              'Общие исключения: чартерные рейсы.', tf.NOW, intro_context=context)
        self.assertEqual(row['details']['linked_rules'], [
            {'label': 'Подробнее ' + ENTITY_TEXT, 'url': 'https://ut0.ru/abc'},
        ])
        self.assertEqual(project(row)['raw']['details']['linked_rules'], row['details']['linked_rules'])


class T2DomBoundaries(unittest.TestCase):
    def mixx_litres(self, raw):
        return next(row for row in t2.page_records('t2_mixx', raw, sf.NOW)
                    if 'каталогу более' in row['benefit_text'])

    def test_inline_service_name_keeps_partner_and_id(self):
        raw = (FIXTURES / 't2-mixx.html').read_text()
        original = self.mixx_litres(raw)
        row = self.mixx_litres(raw.replace('Литрес:', 'Лит<span>рес</span>:'))
        self.assertEqual(row['partner_name'], 'Литрес')
        self.assertEqual(row['id'], original['id'])
        self.assertEqual(row['details']['membership_component'], 'selectable_replacement')

    def test_literal_service_text_survives_publisher_and_common_input(self):
        raw = (FIXTURES / 't2-mixx.html').read_text().replace('Литрес:', 'Литрес: ' + ENTITY_HTML)
        row = self.mixx_litres(raw)
        expected = 'Литрес: ' + ENTITY_TEXT + ' доступ к каталогу более 280 тысяч электронных книг'
        self.assertEqual(row['benefit_text'], expected)
        self.assertEqual(project(row)['raw']['benefit'], expected)

    def test_wrapped_fixed_service_claim_keeps_its_rate_to_common(self):
        raw = (FIXTURES / 't2-mixx.html').read_text().replace('скидка 15%', 'скидка<br>15%')
        row = next(row for row in t2.page_records('t2_mixx', raw, sf.NOW)
                   if row['partner_name'] == 'Lamoda')
        self.assertEqual(row['benefit_text'], 'скидка 15% на Lamoda')
        self.assertEqual([(r['kind'], r['value']) for r in row['rates']], [('discount', '15')])
        self.assertIn(('discount', '15'), {(b['kind'], b['value']) for b in project(row)['benefits']})

    def test_separate_paragraphs_are_not_a_wrapped_fixed_service_rate(self):
        raw = (FIXTURES / 't2-mixx.html').read_text().replace('скидка 15%', 'скидка<p>15%</p>')
        row = next(row for row in t2.page_records('t2_mixx', raw, sf.NOW)
                   if row['partner_name'] == 'Lamoda')
        self.assertIn('скидка\n15%\n', row['benefit_text'])
        self.assertEqual(row['rates'], [])
        self.assertNotIn(('discount', '15'), {(b['kind'], b['value']) for b in project(row)['benefits']})

    def test_inline_selection_identity_is_still_the_owned_card(self):
        raw = (FIXTURES / 't2-selection.html').read_text().replace('T2 SELECTION', 'T2 SEL<span>EC</span>TION')
        try:
            row, = t2.page_records('t2_selection', raw, sf.NOW)
        except ValueError as exc:
            self.fail('The same owned Selection card was rejected: ' + str(exc))
        self.assertEqual(row['native_id'], 'premium-participation')
        self.assertIn('711', row['benefit_text'])
        self.assertNotIn('МЕЖДУНАРОДНЫЙ РОУМИНГ', row['conditions_text'])

    def test_missing_owned_selection_text_still_rejects_the_card(self):
        raw = (FIXTURES / 't2-selection.html').read_text().replace('card-kit-t2__text', 'unrelated-text')
        with self.assertRaises(ValueError):
            t2.page_records('t2_selection', raw, sf.NOW)

    def test_wrapped_selection_claim_keeps_explicit_rate_to_common(self):
        for claim in ('Скидки<br>15%', 'Скидки 15<br>%'):
            with self.subTest(claim=claim):
                raw = (FIXTURES / 't2-selection.html').read_text().replace('Скидки', claim)
                row, = t2.page_records('t2_selection', raw, sf.NOW)
                self.assertEqual([(r['kind'], r['value']) for r in row['rates']],
                                 [('discount', '15')])
                self.assertTrue(row['benefit_text'].startswith(claim.replace('<br>', ' ')))
                self.assertIn(claim.replace('<br>', '\n'), row['conditions_text'])
                self.assertEqual([(b['kind'], b['value']) for b in project(row)['benefits']],
                                 [('discount', '15')])

    def test_separate_blocks_in_selection_claim_do_not_supply_rate_context(self):
        raw = (FIXTURES / 't2-selection.html').read_text().replace('Скидки', 'Скидки<p>15%</p>')
        row, = t2.page_records('t2_selection', raw, sf.NOW)
        self.assertTrue(row['benefit_text'].startswith('Скидки\n15%\n'))
        self.assertEqual(row['rates'], [])
        self.assertEqual(project(row)['benefits'], [])

    def test_inline_phone_digits_survive_wrapped_claim_with_line_in_evidence(self):
        raw = (FIXTURES / 't2-selection.html').read_text().replace('711', '7<span>11</span>').replace(
            ', а\u00a0также', ',<br>а\u00a0также')
        row, = t2.page_records('t2_selection', raw, sf.NOW)
        expected = ('Скидки в сервисах Яндекса, приоритетное обслуживание в салонах T2 '
                    'и по выделенной линии 711, а также другие преимущества программы')
        self.assertEqual(row['benefit_text'], expected)
        self.assertEqual(project(row)['raw']['benefit'], expected)
        self.assertIn('711,\nа также', row['conditions_text'])


class UtairSupportDomBoundaries(unittest.TestCase):
    def test_inline_ancestor_label_remains_a_partner_section(self):
        row, = utair.parse_article(uf.fixture(group='Ко<span>пить</span> мили'), uf.NOW)
        self.assertEqual(row['record_kind'], 'partner_offer')
        self.assertEqual(row['partner_name'], 'Новый партнер')
        self.assertEqual(row['details']['public_article_block']['section_path'], ['Копить мили'])
        self.assertEqual([(r['kind'], r['value']) for r in row['rates']], [('miles', '17')])

    def test_inline_partner_and_link_label_preserve_native_identity(self):
        original, = utair.parse_article(uf.fixture(name='PartnerAB'), uf.NOW)
        row, = utair.parse_article(uf.fixture(name='PartnerA<span>B</span>'), uf.NOW)
        self.assertEqual(row['partner_name'], 'PartnerAB')
        self.assertEqual(row['id'], original['id'])
        self.assertEqual(row['details']['public_article_block']['links'], [
            {'label': 'PartnerAB', 'url': 'https://partner.example/new'},
        ])

    def test_inline_mileage_and_entities_survive_record_binding_and_common(self):
        raw = uf.fixture(rate='17<b>,</b>5').replace('бронирования.', 'бронирования. ' + ENTITY_HTML)
        try:
            row, = utair.parse_article(raw, uf.NOW)
        except ValueError as exc:
            self.fail('Literal owned text failed source-record binding: ' + str(exc))
        expected = 'Новый партнер — до 17,5% милями от стоимости бронирования. ' + ENTITY_TEXT
        self.assertEqual(row['conditions_text'], expected)
        self.assertEqual([(r['kind'], r['value']) for r in row['rates']], [('miles', '17.5')])
        common = project(row)
        self.assertEqual(common['raw']['conditions'], expected)
        self.assertEqual({(b['kind'], b['value']) for b in common['benefits']}, {('earn_miles', '17.5')})

    def test_wrapped_percent_miles_claim_keeps_its_rate_to_common(self):
        raw = uf.fixture().replace('17% милями', '17%<br>милями')
        row, = utair.parse_article(raw, uf.NOW)
        expected = 'Новый партнер — до 17% милями от стоимости бронирования.'
        self.assertEqual(row['benefit_text'], expected)
        self.assertEqual([(r['kind'], r['value']) for r in row['rates']], [('miles', '17')])
        common = project(row)
        self.assertEqual(common['raw']['conditions'], expected)
        self.assertEqual({(b['kind'], b['value']) for b in common['benefits']}, {('earn_miles', '17')})

    def test_separate_paragraphs_do_not_attach_miles_to_an_untyped_percent(self):
        raw = uf.fixture().replace('17% милями', '17%</p><p>милями')
        row, = utair.parse_article(raw, uf.NOW)
        self.assertIn('17%\nмилями', row['benefit_text'])
        self.assertEqual(row['rates'], [])
        self.assertEqual(project(row)['benefits'], [])

    def test_wrapped_section_and_pre_lines_preserve_owner_and_evidence(self):
        raw = uf.fixture(group='Копить<br>мили').replace(
            'бронирования.', 'бронирования.</p><pre>Первая\r\nВторая</pre><p>Ограничения<br>конец')
        row, = utair.parse_article(raw, uf.NOW)
        self.assertEqual(row['record_kind'], 'partner_offer')
        self.assertEqual(row['details']['public_article_block']['section_path'], ['Копить\nмили'])
        expected = ('Новый партнер — до 17% милями от стоимости бронирования.'
                    '\nПервая\nВторая\nОграничения конец')
        self.assertEqual(row['conditions_text'], expected)
        self.assertEqual(project(row)['raw']['conditions'], expected)


if __name__ == '__main__':
    unittest.main()
