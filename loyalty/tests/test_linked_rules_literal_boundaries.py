"""Linked rule evidence crosses DOM, publisher, and common-view boundaries intact."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1]))
import aeroflot_linked_rules as aero
import coral_linked_rules as coral
import ekp_linked_rules as ekp
from normalized import validate_offer
from sheets_normalized import prepare, SCHEMAS
from unified_normalization import make_input, normalize_record
import test_aeroflot_linked_rules as af
import test_coral_import as cf
import test_coral_linked_rules as cr
import test_ekp_linked_rules as ef


INLINE_HTML = ('Промокод SUM<span>MER</span>26; ставка 1<b>,</b>5%; '
               'метка &lt;VIP&gt;; сущность &amp;lt;tag&amp;gt;. '
               'Оплата принимается заранее. Все дополнительные условия услуги сохранены.')
INLINE_TEXT = ('Промокод SUMMER26; ставка 1,5%; '
               'метка <VIP>; сущность &lt;tag&gt;. '
               'Оплата принимается заранее. Все дополнительные условия услуги сохранены.')
PRE_LINES = ('Промокод SUMMER26', 'ОГРАНИЧЕНИЯ',
             'Условия применяются к указанной услуге, ограничения приведены в полном тексте правил.')


def project(row):
    bundle = {'schema_version': 2, 'run_id': 'literal-rules:1', 'observed_at': row['observed_at'],
              'records': [row], 'sources': [{
                  'source_id': row['source_id'], 'name': 'Public rules', 'root': row['source_url'],
                  'status': 'ok', 'normalized': 1, 'discovered': 1, 'failed': 0,
                  'coverage': 'one public rule', 'region': None, 'errors': [],
                  'observed_at': row['observed_at'],
              }]}
    values = prepare(bundle)['parser_offers'][0]
    raw = make_input({'id': row['id'], 'origin': 'parser_offers', 'row': 2,
                      'fields': {key: {'value': value}
                                 for key, value in zip(SCHEMAS['parser_offers'], values)}})
    return normalize_record(raw, as_of=row['observed_at'][:10])


def coral_row(contents, heading='Правила нового сервиса'):
    raw = cf.html(cr.RULE, '<header>Чужая скидка 99%</header><section class="article">'
                  '<h1>' + heading + '</h1>' + contents
                  + '</section><footer>Чужой промокод HIDDEN99</footer>')
    entry = coral.discover([cr.parent()])[0]
    return coral.map_rule(cf.obs(cr.RULE, raw), entry, cf.NOW)


def ekp_row(contents, heading='Условия услуги'):
    raw = ('<html><head><title>Публичные условия</title></head><body>'
           '<header>Чужая скидка 99%</header><main><h1>' + heading + '</h1>'
           + contents + '</main><footer>Чужой промокод HIDDEN99</footer></body></html>').encode()
    data = ekp.clean_html(raw).encode()
    entry = ekp.discover(ef.base([ef.parent(url=ef.HTML)]), ef.CLOCK)[0][0]
    return ekp.rows_for(data, entry, ef.receipt(ef.HTML, data), ef.NOW)[0]


class LinkedRuleLiteralBoundaries(unittest.TestCase):
    def assert_condition_only(self, row, expected):
        validate_offer(row)
        self.assertEqual(row['conditions_text'], expected)
        self.assertEqual(row['rates'], [])
        normalized = project(row)
        self.assertEqual(normalized['benefits'], [])
        self.assertEqual(normalized['codes'], [])
        self.assertEqual(normalized['costs'], [])
        self.assertEqual([c['evidence']['text'] for c in normalized['conditions']], [expected])

    def test_coral_inline_text_and_entities_survive_to_common_rules(self):
        row = coral_row('<p>' + INLINE_HTML + '</p>')
        self.assert_condition_only(row, 'Правила нового сервиса\n' + INLINE_TEXT)

    def test_ekp_inline_text_and_entities_survive_to_common_rules(self):
        row = ekp_row('<p>' + INLINE_HTML + '</p>')
        self.assert_condition_only(row, 'Условия услуги\n' + INLINE_TEXT)

    def test_preformatted_cr_crlf_and_lf_keep_condition_boundaries(self):
        for newline in ('\r', '\r\n', '\n'):
            contents = '<pre>' + newline.join(PRE_LINES) + '</pre>'
            for build, heading in ((coral_row, 'Правила нового сервиса'),
                                   (ekp_row, 'Условия услуги')):
                with self.subTest(newline=repr(newline), source=build.__name__):
                    self.assert_condition_only(build(contents), heading + '\n' + '\n'.join(PRE_LINES))

    def test_explicit_br_keeps_rule_conditions_separate(self):
        first = 'Срок подачи заявки — 7 дней.'
        second = ('При отмене заказа действуют условия услуги; весь текст исключений '
                  'приведён в опубликованном документе.')
        for build, heading in ((coral_row, 'Правила нового сервиса'),
                               (ekp_row, 'Условия услуги')):
            with self.subTest(source=build.__name__):
                row = build('<p>' + first + '<br>' + second + '</p>')
                self.assert_condition_only(row, heading + '\n' + first + '\n' + second)

    def test_coral_rule_heading_is_not_split_inside_a_word(self):
        try:
            row = coral_row('<p>' + INLINE_HTML + '</p>', heading='Пра<span>ви</span>ла нового сервиса')
        except ValueError as exc:
            self.fail('A valid owned heading was rejected after inline markup: ' + str(exc))
        self.assertEqual(row['title'], 'Правила нового сервиса')
        self.assert_condition_only(row, 'Правила нового сервиса\n' + INLINE_TEXT)

    def test_coral_rule_table_cells_preserve_literal_values_without_promoting_them(self):
        table = ('<table><tr><th>Метка</th><th>Ставка</th></tr><tr>'
                 '<td>SUM<span>MER</span>26 &lt;VIP&gt;</td>'
                 '<td>1<b>,</b>5%</td></tr></table>')
        row = coral_row('<p>' + INLINE_HTML + '</p>' + table)
        self.assertEqual(row['details']['public_rule']['tables'], [
            [['Метка', 'Ставка'], ['SUMMER26 <VIP>', '1,5%']],
        ])
        self.assertEqual(row['tables'], [])
        self.assert_condition_only(row, 'Правила нового сервиса\n' + INLINE_TEXT
                                   + '\nМетка Ставка\nSUMMER26 <VIP> 1,5%')

    def test_coral_unread_link_keeps_its_literal_label(self):
        row = coral_row('<p>' + INLINE_HTML + '</p>'
                        '<a href="https://coralbonus.ru/pravila-dopolneniya/">'
                        'Ус<span>ло</span>вия &lt;VIP&gt;</a>')

        self.assertEqual(row['details']['public_rule']['unread_links'], [{
            'url': 'https://coralbonus.ru/pravila-dopolneniya/', 'label': 'Условия <VIP>',
        }])
        self.assert_condition_only(row, 'Правила нового сервиса\n' + INLINE_TEXT + '\nУсловия <VIP>')

    def test_ekp_rule_discovery_keeps_the_owned_link_label_word(self):
        bundle = ef.base([ef.parent(url=ef.HTML, label='Ус<span>ло</span>вия услуги')])
        entries, inventory = ekp.discover(bundle, ef.CLOCK)

        self.assertEqual([entry['url'] for entry in entries], [ef.HTML])
        self.assertEqual(entries[0]['parents'][0]['label'], 'Условия услуги')
        self.assertEqual(inventory['links'][0]['labels'], ['Условия услуги'])

    def test_equivalent_ekp_headings_allow_a_structural_line_break(self):
        try:
            row = ekp_row('<h1>Условия услуги</h1><p>' + INLINE_HTML + '</p>',
                          heading='Условия<br>услуги')
        except ValueError as exc:
            self.fail('Equivalent owned headings were rejected after a line break: ' + str(exc))

        self.assertEqual(row['title'], 'Условия\nуслуги')
        self.assert_condition_only(row, 'Условия\nуслуги\nУсловия услуги\n' + INLINE_TEXT)

    def test_aeroflot_excluded_product_names_remain_literal_in_common_rules(self):
        raw = af.page(('one',), total=1, next_page=False).replace(
            b'>one</a>', '>Товар A<span>B</span>; &lt;VIP&gt;; &amp;lt;tag&amp;gt;</a>'.encode())
        data = aero.clean_html(raw, af.FINAL)
        fields = aero.catalog_fields(data, af.FINAL)
        self.assertEqual(fields['products'], [{
            'url': 'https://stoletov.ru/catalog/item/one/',
            'name': 'Товар AB; <VIP>; &lt;tag&gt;',
        }])
        entry = aero.discover(af.base(), af.CLOCK)[0][0]
        row = aero.make_rows(entry, {'final_url': af.FINAL}, data,
                             af.CLOCK.isoformat(), fields=fields, complete=True)[0]
        self.assert_condition_only(row,
            'Товары-исключения\nБаллы на эти товары не начисляются.\n\n'
            'Товар AB; <VIP>; &lt;tag&gt; — https://stoletov.ru/catalog/item/one/')

    def test_aeroflot_catalogue_heading_is_not_split_inside_a_word(self):
        raw = af.page(('one',), total=1, next_page=False).replace(
            'Товары-исключения'.encode(), 'Товары-иск<span>лючения</span>'.encode())
        try:
            fields = aero.catalog_fields(aero.clean_html(raw, af.FINAL), af.FINAL)
        except ValueError as exc:
            self.fail('A valid owned catalogue heading was rejected after inline markup: ' + str(exc))

        self.assertEqual(fields['title'], 'Товары-исключения')
        self.assertEqual(fields['total'], 1)
        self.assertEqual(fields['products'], [{
            'url': 'https://stoletov.ru/catalog/item/one/', 'name': 'one',
        }])

    def test_aeroflot_catalogue_heading_keeps_a_structural_line_break(self):
        raw = af.page(('one',), total=1, next_page=False).replace(
            'Товары-исключения'.encode(), 'Товары<br>исключения'.encode())
        try:
            fields = aero.catalog_fields(aero.clean_html(raw, af.FINAL), af.FINAL)
        except ValueError as exc:
            self.fail('A valid owned catalogue heading was rejected after a line break: ' + str(exc))

        self.assertEqual(fields['title'], 'Товары\nисключения')
        self.assertEqual(fields['total'], 1)

    def test_aeroflot_catalogue_count_accepts_adjacent_inline_label(self):
        raw = af.page(('one',), total=1, next_page=False).replace(
            '1 товаров'.encode(), '<span>1</span>товар'.encode())
        try:
            fields = aero.catalog_fields(aero.clean_html(raw, af.FINAL), af.FINAL)
        except ValueError as exc:
            self.fail('A valid source counter was rejected with an adjacent inline label: ' + str(exc))

        self.assertEqual(fields['total'], 1)
        self.assertEqual(fields['products'], [{
            'url': 'https://stoletov.ru/catalog/item/one/', 'name': 'one',
        }])


if __name__ == '__main__':
    unittest.main()
