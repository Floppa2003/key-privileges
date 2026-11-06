"""Nordwind earning sections retain source text across harmless markup."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1]))
from nordwind_catalog import parse_catalog
from normalized import validate_offer
from test_nordwind_catalog import NOW, card, document


class NordwindEarningBoundaryTests(unittest.TestCase):
    def parse(self, raw):
        try:
            return parse_catalog(raw, NOW)
        except ValueError as exc:
            self.fail('An owned earning section was rejected: ' + str(exc))

    def test_inline_amount_markup_keeps_the_card_formula(self):
        own = card().replace('200 ₽ - 7 миль', '<strong>200 ₽</strong> - <em>7 миль</em>')
        rows = self.parse(document(own + card('Other', 'Другой отель', '10', '99')))
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]['partner_name'], 'Новый отель')
        self.assertEqual(rows[0]['benefit_text'], 'За каждые потраченные 200 ₽ - 7 миль NORDWIND КЛУБ.')
        self.assertEqual([(r['value'], r['basis_amount']) for r in rows[0]['details']['earning_rules']], [('7', '200')])
        self.assertNotIn('99', rows[0]['benefit_text'])
        validate_offer(rows[0])

    def test_inline_markup_inside_the_earning_label_is_not_a_new_section(self):
        raw = document().replace('Мили к начислению:', 'Мили <span>к начислению</span>:')
        row = self.parse(raw)[0]
        self.assertEqual(row['details']['earning_rules'][0]['value'], '7')
        self.assertEqual(row['details']['earning_rules'][0]['basis_amount'], '200')

    def test_explicit_inline_heading_still_owns_its_following_text(self):
        for label in ('Мили к начислению:', 'Мили к начислению :'):
            with self.subTest(label=label):
                raw = document().replace('<b>Мили к начислению:</b><p>', '<p><b>' + label + '</b>')
                row = self.parse(raw)[0]
                self.assertEqual(row['benefit_text'], 'За каждые потраченные 200 ₽ - 7 миль NORDWIND КЛУБ.')
                self.assertEqual(row['details']['earning_rules'][0]['value'], '7')

    def test_wrapped_label_retains_original_condition_lines(self):
        raw = document().replace('Мили к начислению:', 'Мили<br>к начислению:')
        row = self.parse(raw)[0]
        self.assertEqual(row['details']['earning_rules'][0]['basis_amount'], '200')
        self.assertIn('Мили\nк начислению:', row['conditions_text'])

    def test_wrapped_formula_stops_at_the_next_owned_heading(self):
        raw = document().replace('200 ₽ - 7 миль', '200 ₽<br>- 7 миль')
        raw = raw.replace('Телефон 1234567', 'Отдел: 99 миль за каждые 10 ₽')
        row = self.parse(raw)[0]
        self.assertEqual(row['benefit_text'], 'За каждые потраченные 200 ₽\n- 7 миль NORDWIND КЛУБ.')
        self.assertEqual([(r['value'], r['basis_amount']) for r in row['details']['earning_rules']], [('7', '200')])
        self.assertNotIn('99', row['benefit_text'])
        self.assertIn('Отдел: 99 миль', row['conditions_text'])
        validate_offer(row)

    def test_duplicate_wrapped_earning_labels_are_ambiguous(self):
        extra = '<b>МИЛИ<br>К НАЧИСЛЕНИЮ:</b><p>За каждые 10 ₽ - 99 миль.</p>'
        raw = document().replace('<b>Контакты:</b>', extra + '<b>Контакты:</b>')
        with self.assertRaises(ValueError):
            parse_catalog(raw, NOW)

    def test_empty_earning_section_cannot_borrow_a_redemption_heading(self):
        raw = document().replace('<p>За каждые потраченные 200 ₽ - 7 миль NORDWIND КЛУБ.</p>', '')
        raw = raw.replace('<b>Контакты:</b>', '<b>Мили к списанию:</b><p>До 99 миль за заказ.</p><b>Контакты:</b>')
        with self.assertRaises(ValueError):
            parse_catalog(raw, NOW)

    def test_multiple_owned_formulas_are_retained_without_selecting_one(self):
        extra = '<p>Для другого тарифа: за каждые 10 ₽ - 99 миль.</p>'
        raw = document().replace('<b>Контакты:</b>', extra + '<b>Контакты:</b>')
        row = self.parse(raw)[0]
        self.assertIn('200 ₽ - 7 миль', row['benefit_text'])
        self.assertIn('за каждые 10 ₽ - 99 миль', row['benefit_text'])
        self.assertEqual(row['details']['earning_rules'], [])
        self.assertIn('earning_formula_not_structurally_parsed', row['warnings'])

    def test_already_decoded_literal_text_is_not_parsed_again(self):
        raw = document().replace('Дополнительные услуги исключены.', 'Код &lt;VIP&gt;; текст &amp;lt;KEEP&amp;gt;.')
        row = self.parse(raw)[0]
        self.assertIn('Код <VIP>; текст &lt;KEEP&gt;.', row['conditions_text'])
        validate_offer(row)


if __name__ == '__main__':
    unittest.main()
