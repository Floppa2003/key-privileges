"""Literal numeric ranges survive; invalid numeric tokens stay unparsed."""
import sys
import unittest
from decimal import InvalidOperation
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1]))
from hse_alumni import hse_rates, parse_catalog
from normalized import make_offer, normalize_rates
from test_hse_alumni import NOW, card, common, page, section


def terms(rows):
    return [(r['kind'], r['value'], r.get('min_value'), r['unit'], r['qualifier'])
            for r in rows]


class LiteralPercentageBoundaryTests(unittest.TestCase):
    def test_verbal_range_with_one_percent_sign_keeps_both_bounds(self):
        body = 'Скидки от 15 до 40% на абонементы'
        result = normalize_rates(body)
        self.assertEqual(terms(result), [('discount', '40', '15', 'percent', 'range')])
        self.assertEqual(result[0]['evidence'], body)

    def test_verbal_range_with_two_percent_signs_is_one_rate(self):
        cases = [('Скидка от 10% до 15% на все виды услуг по промокоду HSE.',
                  ('discount', '15', '10', 'percent', 'range')),
                 ('Кешбэк ОТ 2,5% ДО 7,5% на покупки.',
                  ('cashback', '7.5', '2.5', 'percent', 'range'))]
        for body, expected in cases:
            with self.subTest(body=body):
                result = normalize_rates(body)
                self.assertEqual(terms(result), [expected])
                self.assertEqual(result[0]['evidence'], body)

    def test_verbal_range_after_ruble_price_band_keeps_its_owner(self):
        result = normalize_rates('Скидка от 1000 руб. — от 5 до 10%.')
        self.assertEqual(terms(result), [('discount', '10', '5', 'percent', 'range')])

    def test_dash_range_with_both_percent_signs_is_one_rate(self):
        for body in ('Скидка 10%–15%', 'Скидка 10% - 15%', 'Скидка 10% — 15%'):
            with self.subTest(body=body):
                result = normalize_rates(body)
                self.assertEqual(terms(result), [('discount', '15', '10', 'percent', 'range')])
                self.assertEqual(result[0]['evidence'], body)
        self.assertEqual(terms(normalize_rates('Скидка 10% — кешбэк 15%')),
                         [('discount', '10', None, 'percent', 'exact'),
                          ('cashback', '15', None, 'percent', 'exact')])

    def test_reversed_or_out_of_bounds_range_is_not_partially_extracted(self):
        for body in ('Скидка 20–10%', 'Скидка 110–20%', 'Скидка от 20 до 10%',
                     'Скидка от 20% до 10%', 'Скидка от 110% до 120%',
                     'Скидка от 1 000 до 10%', 'Скидка 20%–10%',
                     'Скидка 110%–20%'):
            with self.subTest(body=body):
                self.assertEqual(normalize_rates(body), [])

    def test_invalid_numeric_groups_cannot_become_percentage_suffixes(self):
        for body in ('Скидка 1 000%', 'Скидка 1 00%', 'Скидка 1.2.3%',
                     'Скидка 1.500.5%', 'Скидка 1,500,5%'):
            with self.subTest(body=body):
                try:
                    result = normalize_rates(body)
                except InvalidOperation:
                    self.fail('Malformed source percentages must stay unparsed, not raise.')
                self.assertEqual(result, [])

    def test_published_discount_dash_and_list_markers_keep_their_rates(self):
        body = 'Дарим скидку -10% на повторные заказы и -20% на первый заказ'
        self.assertEqual(terms(normalize_rates(body)),
                         [('discount', '10', None, 'percent', 'exact'),
                          ('discount', '20', None, 'percent', 'exact')])
        for body in ('-5% скидка на всю линейку велосипедов', 'Скидка −5%'):
            with self.subTest(body=body):
                self.assertEqual(terms(normalize_rates(body)),
                                 [('discount', '5', None, 'percent', 'exact')])

    def test_comma_separated_rates_keep_existing_meaning(self):
        for body in ('Скидка 5%,10%,15%', 'Скидка 5%, 10%, 15%'):
            with self.subTest(body=body):
                self.assertEqual(terms(normalize_rates(body)),
                                 [('discount', value, None, 'percent', 'exact')
                                  for value in ('5', '10', '15')])
        self.assertEqual(terms(normalize_rates('Скидка 5, 10%')),
                         [('discount', '10', None, 'percent', 'exact')])
        self.assertEqual(terms(normalize_rates('Скидка 5,10%')),
                         [('discount', '5.1', None, 'percent', 'exact')])

    def test_list_markers_and_a_separate_following_rate_are_preserved(self):
        for body in ('- 10% скидка', '1. 10% скидка', 'Скидка — 10%'):
            with self.subTest(body=body):
                self.assertEqual(terms(normalize_rates(body)),
                                 [('discount', '10', None, 'percent', 'exact')])
        self.assertEqual(terms(normalize_rates('Скидка 20–10%; скидка 7%')),
                         [('discount', '7', None, 'percent', 'exact')])


class InternalPercentageSpanTests(unittest.TestCase):
    def parsed(self, value):
        try:
            return normalize_rates(value, with_spans=True)
        except TypeError:
            self.fail('The internal parser must retain distinct percentage occurrences.')

    def test_identical_rate_values_keep_distinct_internal_occurrences(self):
        body = 'Кешбэк 10% баллами + кешбэк 10% рублями'
        result = self.parsed(body)
        self.assertEqual([(r['kind'], r['value'], r['_percent_index']) for r in result],
                         [('cashback', '10', 0), ('cashback', '10', 1)])
        self.assertTrue(all(r['evidence'] == body for r in result))
        public = normalize_rates(body)
        self.assertEqual(len(public), 1)
        self.assertNotIn('_percent_index', public[0])

    def test_ordinal_counts_untyped_percentages_across_clause_boundaries(self):
        result = self.parsed('НДС 20%; Кешбэк 10% баллами; доля 3%; кешбэк 10% рублями')
        self.assertEqual([(r['value'], r['_percent_index']) for r in result],
                         [('10', 1), ('10', 3)])


class LiteralAmountBoundaryTests(unittest.TestCase):
    def offer(self, benefit, conditions=''):
        try:
            return make_offer('moskvich', 'numeric-boundary', 'Карта', 'Партнёр',
                              benefit, 'https://moskvichmag.ru/programma-loyalnosti/',
                              '2026-11-06T00:00:00Z', conditions=conditions)
        except InvalidOperation:
            self.fail('A malformed source amount must not abort the source record.')

    def test_malformed_ruble_amount_does_not_drop_independent_valid_rate(self):
        body = 'Скидка 1.500.5 рублей; скидка 7%'
        offer = self.offer(body)
        self.assertEqual(offer['benefit_text'], body)
        self.assertEqual(terms(offer['rates']), [('discount', '7', None, 'percent', 'exact')])

    def test_malformed_mileage_amount_or_basis_stays_unparsed(self):
        for body in ('1.500.5 миль за покупку', '3 мили за 1.500.5 ₽'):
            with self.subTest(body=body):
                offer = self.offer(body)
                self.assertEqual(offer['benefit_text'], body)
                self.assertEqual(offer['rates'], [])

    def test_malformed_numeric_conditions_do_not_abort_the_offer(self):
        body = 'Покупка от 1.500.5 рублей; максимальный размер скидки 1.500.5 рублей'
        offer = self.offer('Скидка 10%', body)
        self.assertEqual(offer['conditions_text'], body)
        self.assertEqual(offer['details']['lexical_conditions'], [])
        self.assertEqual(terms(offer['rates']), [('discount', '10', None, 'percent', 'exact')])

    def test_valid_grouped_amounts_and_single_decimal_keep_existing_meaning(self):
        cases = [('Скидка 1 500,50 ₽', '1500.5'), ('Скидка 1.500,50 ₽', '1500.5'),
                 ('Скидка 1,500.50 ₽', '1500.5'), ('Скидка 1.500.000 ₽', '1500000'),
                 ('Скидка 1.500 ₽', '1.5')]
        for body, value in cases:
            with self.subTest(body=body):
                self.assertEqual(terms(self.offer(body)['rates']),
                                 [('discount', value, None, 'RUB', 'exact')])


class HseNumericBoundaryTests(unittest.TestCase):
    def test_owned_coupon_fallback_does_not_publish_invalid_suffix(self):
        for body in ('Промокод BOUNDARY_ONLY на 20–10%',
                     'Промокод BOUNDARY_ONLY на 1 000%',
                     'Промокод BOUNDARY_ONLY на 1.2.3%'):
            with self.subTest(body=body):
                self.assertEqual(hse_rates(body), [])

    def test_hse_source_and_common_keep_invalid_text_without_a_rate(self):
        body = 'Промокод BOUNDARY_ONLY на 20–10%'
        row, = parse_catalog(page(card('boundary'), section('boundary', '<p>' + body + '</p>')), NOW)
        self.assertIn(body, row['conditions_text'])
        self.assertEqual(row['rates'], [])
        normalized = common(row)
        self.assertEqual(normalized['benefits'], [])
        self.assertIn(body, normalized['raw']['conditions'])

    def test_hse_verbal_range_survives_source_to_common(self):
        for body, low, high in [('Скидки от 15 до 40% на абонементы', '15', '40'),
                                ('Скидка от 10% до 15% на все виды услуг.', '10', '15'),
                                ('Скидка 10%–15% на все виды услуг.', '10', '15')]:
            with self.subTest(body=body):
                row, = parse_catalog(page(card('boundary'), section('boundary', '<p>' + body + '</p>')), NOW)
                self.assertEqual(terms(row['rates']), [('discount', high, low, 'percent', 'range')])
                normalized = common(row)
                self.assertEqual([(b['value'], b['value_min'], b['qualifier'])
                                  for b in normalized['benefits']], [(high, low, 'range')])
                self.assertIn(body, normalized['raw']['conditions'])

    def test_owned_implicit_valid_coupon_rate_is_preserved(self):
        self.assertEqual(terms(hse_rates('Промокод EXAMPLE_ONLY на 17,5%')),
                         [('discount', '17.5', None, 'percent', 'exact')])


if __name__ == '__main__':
    unittest.main()
