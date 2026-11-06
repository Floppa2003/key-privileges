"""A reviewed mileage formula cannot rescue a suffix of a malformed number."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from known_rules import CONFIG, earning_rules, parse_known_rule
from test_known_rules import RETAIL, NOW
import test_known_rules as known_fixtures
from test_public_product_rules import sample as gpb_fixture


class KnownRuleNumericBoundaries(unittest.TestCase):
    def test_malformed_earning_or_basis_rejects_required_source_formula(self):
        for old, new in (('1 миля', '1.500.5 миля'), ('1 миля', '1 00 миля'),
                         ('70 руб.', '1 00 руб.'), ('70 руб.', '1.500.5 руб.')):
            with self.subTest(new=new):
                with self.assertRaisesRegex(ValueError, 'retail_earning_rule_changed'):
                    parse_known_rule('af_bootwood_rules', RETAIL.replace(old,new),
                                     CONFIG['af_bootwood_rules']['url'], NOW)

    def test_valid_grouping_keeps_both_formula_values(self):
        result = earning_rules('1,5 мили за каждые потраченные 1.500,50 руб.')
        self.assertEqual([(x['value'], x['basis_amount']) for x in result], [('1.5', '1500.5')])

    def test_invalid_formula_does_not_hide_a_following_valid_formula(self):
        result = earning_rules('1.500.5 мили за каждые потраченные 70 руб.; '
                               '2 мили за каждые потраченные 100 руб.')
        self.assertEqual([(x['value'], x['basis_amount']) for x in result], [('2', '100')])

    def test_gpb_cost_cap_and_minimum_cannot_use_malformed_numeric_tokens(self):
        for old, new in (('399 ₽ в месяц', '1.500.5 ₽ в месяц'),
                         ('Максимум миль в месяц 3 000', 'Максимум миль в месяц 1 00'),
                         ('месяц - 5 000 ₽', 'месяц - 1 00 ₽')):
            with self.subTest(new=new):
                with self.assertRaises(ValueError):
                    parse_known_rule('af_gpb_rules', gpb_fixture().replace(old,new),
                                     CONFIG['af_gpb_rules']['url'], NOW)

    def test_gpb_valid_grouped_subscription_amount_is_supported(self):
        row, = parse_known_rule('af_gpb_rules', gpb_fixture().replace('399 ₽ в месяц', '1.500,50 ₽ в месяц'),
                                CONFIG['af_gpb_rules']['url'], NOW)
        self.assertEqual(row['details']['mileage_options'][1]['monthly_subscription_rub'], '1500.5')

    def test_smartavia_malformed_quantity_cannot_become_its_last_digit(self):
        html = known_fixtures.SmartaviaTests().fixture().replace('10 сегментов', '1.500.5 сегментов', 1)
        with self.assertRaises(ValueError):
            parse_known_rule('smartavia_rules', html, CONFIG['smartavia_rules']['url'], NOW)

    def test_earning_formula_does_not_consume_a_preceding_numeric_heading(self):
        for title in ('Тариф 3', 'Тариф 1+0.'):
            with self.subTest(title=title):
                html = RETAIL.replace('<p>1 миля', '<h4>' + title + '</h4><p>1 миля')
                row, = parse_known_rule('af_bootwood_rules', html,
                                        CONFIG['af_bootwood_rules']['url'], NOW)
                self.assertEqual([(x['value'], x['basis_amount']) for x in row['details']['earning_rules']],
                                 [('1', '70')])

    def test_gpb_monthly_price_does_not_consume_a_preceding_numeric_heading(self):
        for title in ('Новая опция 3', 'Новая опция 1.'):
            with self.subTest(title=title):
                extra = ('<div class="TariffsMsbItemContent_root__new"><h5>' + title + '</h5>'
                         '<p>499 ₽ в месяц</p><p>Мили «Аэрофлот Бонус» 4 мили за 150 ₽ покупок</p>'
                         '<p>Максимум миль в месяц 8000</p></div>')
                row, = parse_known_rule('af_gpb_rules', gpb_fixture() + extra,
                                        CONFIG['af_gpb_rules']['url'], NOW)
                self.assertEqual(row['details']['mileage_options'][-1]['monthly_subscription_rub'], '499')


if __name__ == '__main__':
    unittest.main()
