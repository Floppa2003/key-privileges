"""Source-shaped HTML cases where markup must not change literal offer evidence."""
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1]))
from adapters import extract, s7_detail
from normalized import make_offer, validate_offer
from recovered_contract import collection_url
from recovered_sources import parse_bank_page, public_post_record


NOW = '2026-11-05T00:00:00+00:00'
MOSKVICH_URL = 'https://moskvichmag.ru/programma-loyalnosti/'


def moskvich_offer(markup, name='Example'):
    html = ('<div class="lpp-card"><h3 class="lpp-card__name">' + name + '</h3>'
            '<div class="lpp-card__conditions">' + markup + '</div></div>')
    rows = extract('moskvich', html, MOSKVICH_URL, NOW)
    if len(rows) != 1:
        raise AssertionError('Fixture must produce one source card')
    return rows[0]


class HtmlTextBoundaryTests(unittest.TestCase):
    def test_inline_markup_does_not_change_literal_promo_code(self):
        row = moskvich_offer('Промокод SUM<span>MER</span>26. Скидка 13%.')

        self.assertEqual(row['promo_codes'], ['SUMMER26'])
        self.assertEqual(row['benefit_text'], 'Промокод SUMMER26. Скидка 13%.')

    def test_inline_markup_does_not_change_decimal_discount(self):
        row = moskvich_offer('Скидка 1<span>,</span>5%.')

        self.assertEqual([(r['kind'], r['value']) for r in row['rates']],
                         [('discount', '1.5')])
        self.assertEqual(row['benefit_text'], 'Скидка 1,5%.')

    def test_block_boundaries_keep_payment_percentage_out_of_discount(self):
        for markup in (
            '<p>Скидка 10%.</p><p>Предоплата 30%.</p>',
            '<div>Скидка 10%.</div><div>Предоплата 30%.</div>',
            '<ul><li>Скидка 10%.</li><li>Предоплата 30%.</li></ul>',
            'Скидка 10%.<br>Предоплата 30%.',
        ):
            with self.subTest(markup=markup):
                row = moskvich_offer(markup)
                self.assertEqual([(r['kind'], r['value']) for r in row['rates']],
                                 [('discount', '10')])
                self.assertEqual(row['conditions_text'], 'Скидка 10%.\nПредоплата 30%.')

    def test_explicit_inline_spaces_remain_in_multiword_code(self):
        for markup in (
            'Промокод <b>MOSKVICH </b><i>MAG</i>. Скидка 10%.',
            'Промокод <b>MOSKVICH</b> <i>MAG</i>. Скидка 10%.',
            'Промокод <b>MOSKVICH</b><i> MAG</i>. Скидка 10%.',
        ):
            with self.subTest(markup=markup):
                row = moskvich_offer(markup)
                self.assertEqual(row['promo_codes'], ['MOSKVICH MAG'])
                self.assertEqual(row['benefit_text'], 'Промокод MOSKVICH MAG. Скидка 10%.')

    def test_comments_scripts_and_styles_do_not_become_offer_evidence(self):
        row = moskvich_offer(
            'Скидка 1<!-- source layout --><span>0</span>%. '
            '<script>"Промокод HIDDEN90; Скидка 90%"</script>'
            '<style>.x:after { content: "Промокод HIDDEN80; Скидка 80%"; }</style>'
            'Промокод SUM<!-- tracking note --><b>MER</b>26.')

        self.assertEqual(row['benefit_text'], 'Скидка 10%. Промокод SUMMER26.')
        self.assertEqual(row['promo_codes'], ['SUMMER26'])
        self.assertEqual([r['value'] for r in row['rates']], ['10'])

    def test_inert_template_does_not_supply_a_visible_coupon(self):
        row = moskvich_offer('Скидка 10%.'
                             '<template>Промокод INERT90. Скидка 90%.</template>')

        self.assertEqual(row['benefit_text'], 'Скидка 10%.')
        self.assertEqual(row['promo_codes'], [])
        self.assertEqual([r['value'] for r in row['rates']], ['10'])

    def test_preformatted_text_keeps_explicit_line_boundaries(self):
        row = moskvich_offer('<pre>Скидка 10%.\nПредоплата 30%.</pre>')

        self.assertEqual(row['conditions_text'], 'Скидка 10%.\nПредоплата 30%.')
        self.assertEqual([r['value'] for r in row['rates']], ['10'])

    def test_preformatted_cr_and_crlf_are_line_breaks_not_coupon_spaces(self):
        for newline in ('\n', '\r\n', '\r'):
            with self.subTest(newline=repr(newline)):
                row = moskvich_offer('<pre>' + newline.join(
                    ('Промокод SUMMER26', 'ОГРАНИЧЕНИЯ', 'Скидка 10%.')) + '</pre>')
                self.assertEqual(row['promo_codes'], ['SUMMER26'])
                self.assertEqual(row['conditions_text'],
                                 'Промокод SUMMER26\nОГРАНИЧЕНИЯ\nСкидка 10%.')

    def test_deep_finite_inline_markup_does_not_exhaust_python_stack(self):
        markup = '<span>' * 1200 + 'Скидка 10%' + '</span>' * 1200
        try:
            row = moskvich_offer(markup)
        except RecursionError:
            self.fail('A finite source DOM must not require recursive Python traversal')

        self.assertEqual(row['benefit_text'], 'Скидка 10%')
        self.assertEqual([r['value'] for r in row['rates']], ['10'])

    def test_escaped_markup_remains_literal_after_offer_normalization(self):
        row = moskvich_offer(
            '<p>Текст &lt;b&gt;SUMMER26&lt;/b&gt;; метка &amp;lt;tag&amp;gt;.</p>'
            '<p>Скидка 10%.</p>', name='A &amp;amp; B')

        self.assertEqual(row['partner_name'], 'A &amp; B')
        self.assertEqual(row['benefit_text'],
                         'Текст <b>SUMMER26</b>; метка &lt;tag&gt;.\nСкидка 10%.')
        validate_offer(json.loads(json.dumps(row, ensure_ascii=False)))

    def test_s7_html_fields_keep_source_inline_and_block_boundaries(self):
        state = {'offer': {'partners': {'example': {
            'offer': {'code': 'example'},
            'partner': {'code': 'example', 'description': 'Example — Partner',
                        'priorityDetails': {
                            'rule': '<p>Промокод SUM<span>MER</span>26.</p>'
                                    '<p>Скидка 1<b>,</b>5%.</p>',
                            'details': '<p>Скидка 1,5%.</p><p>Предоплата 30%.</p>',
                            'steps': ['<p>Укажите &lt;literal&gt;.</p>']}},
            'category': {},
        }}}}
        row = s7_detail(state, 'https://marketplace.s7.ru/partners/offer/example', NOW)[0]

        self.assertEqual(row['promo_codes'], ['SUMMER26'])
        self.assertEqual([r['value'] for r in row['rates']], ['1.5'])
        self.assertEqual(row['conditions_text'], 'Скидка 1,5%.\nПредоплата 30%.')
        self.assertEqual(row['redemption_text'], 'Укажите <literal>.')

    def test_reviewed_partner_page_keeps_inline_code_and_fractional_rate(self):
        raw = ('<article><p>Аэрофлот Бонус. Промокод SUM<span>MER</span>26.</p>'
               '<p>Скидка 1<span>,</span>5%.</p></article>')
        row = extract('af_viprooms', raw, 'https://vip-rooms.ru/partner/aeroflot', NOW)[0]

        self.assertEqual(row['promo_codes'], ['SUMMER26'])
        self.assertEqual([r['value'] for r in row['rates']], ['1.5'])
        self.assertEqual(row['conditions_text'],
                         'Аэрофлот Бонус. Промокод SUMMER26.\nСкидка 1,5%.')

    def test_recovered_tables_keep_inline_literal_code_and_rate(self):
        table = ('<table><tr><th>Промокод</th><th>Скидка</th></tr>'
                 '<tr><td>SUM<span>MER</span>26</td><td>1<b>,</b>5%</td></tr></table>')
        post = {'id': 1, 'status': 'publish', 'type': 'post',
                'title': {'rendered': 'Партнер'},
                'content': {'protected': False, 'rendered': '<p>Партнерская скидка</p>' + table},
                'link': 'https://loyals.ru/?p=1'}
        loyals = public_post_record(post, {'name': 'Loyals'}, NOW,
                                    collection_url(1), 0, 'a' * 64)
        uralsib = parse_bank_page(
            'uralsib_rzd_rules', '<h1>Приветственные баллы РЖД за оформление карты</h1>'
            '<section id="textBlock">В период с 01.09.2023 по 15.03.2024 оформить заявку.'
            + table + '</section>', NOW)

        for row in (loyals, uralsib):
            with self.subTest(source=row['source_id']):
                self.assertEqual(row['tables'], [[['Промокод', 'Скидка'], ['SUMMER26', '1,5%']]])
                self.assertEqual(row['promo_codes'], ['SUMMER26'])
                self.assertEqual(row['details']['table_benefits']['components'][0]['rate']['value'], '1.5')
                validate_offer(json.loads(json.dumps(row, ensure_ascii=False)))

    def test_recovered_article_keeps_inline_literal_code(self):
        row = parse_bank_page(
            'nspk_ekp_rules', '<div class="pages-press-center-details-article-slug">'
            '<p>Держатели ЕКП смогут экономить. Скидка 10% на vamprivet.ru.</p>'
            '<p>Промокод SUM<span>MER</span>26.</p></div>', NOW)

        self.assertEqual(row['promo_codes'], ['SUMMER26'])
        self.assertEqual(row['conditions_text'],
                         'Держатели ЕКП смогут экономить. Скидка 10% на vamprivet.ru.\nПромокод SUMMER26.')

    def test_already_extracted_plain_evidence_keeps_newlines_and_literal_markup(self):
        row = make_offer('moskvich', 'plain', 'Москвич', 'Example',
                         'Текст <b>SUMMER26</b>.\nСкидка 10%.\nПредоплата 30%.',
                         MOSKVICH_URL, NOW)

        self.assertEqual(row['benefit_text'],
                         'Текст <b>SUMMER26</b>.\nСкидка 10%.\nПредоплата 30%.')
        self.assertEqual([r['value'] for r in row['rates']], ['10'])
        validate_offer(json.loads(json.dumps(row, ensure_ascii=False)))


if __name__ == '__main__':
    unittest.main()
