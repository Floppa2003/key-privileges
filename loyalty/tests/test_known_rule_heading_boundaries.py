"""Reviewed section labels retain their original text spans across layout changes."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1]))
from known_rules import CONFIG, parse_known_rule

NOW = '2026-09-14T08:00:00+00:00'
RETAIL_EARNING = '<p>1 миля начисляется за каждые потраченные 70 руб.</p><p>Мили начисляются после доставки.</p>'
RETAIL_REDEMPTION = '<p>Можно оплатить не более 30% заказа. При этом 70% необходимо оплатить деньгами.</p>'
SKYSHOP_EARNING = '<p>2 мили за каждые потраченные 50 руб.</p><p>Мили начисляются после доставки.</p>'
SKYSHOP_REDEMPTION = '<p>Получение премии: списать 99 миль за каждые потраченные 1 руб.</p>'
IWAY_EARNING = '<p>При заказе через турагентство 1 миля за каждые потраченные 90 ₽.</p><p>При заказе поездки в i’way 1 миля за каждые потраченные 50 ₽.</p>'


def parse(source, html):
    return parse_known_rule(source, html, CONFIG[source]['url'], NOW)[0]


def retail(source, first='Условия начислений:', second='Условия списаний:', *, reverse=False):
    parts = ['<h3>' + first + '</h3>' + RETAIL_EARNING,
             '<h3>' + second + '</h3>' + RETAIL_REDEMPTION]
    if reverse:
        parts.reverse()
    body = '<h1>Аэрофлот Бонус</h1>' + ''.join(parts)
    if source == 'af_bootwood_rules':
        return '<div class="afl">' + body + '</div>'
    return '<main class="main"><div class="container">' + body + '</div></main>'


def skyshop(first='Условия начислений:', second='Условия получения премий:', *, reverse=False):
    parts = ['<h3>' + first + '</h3>' + SKYSHOP_EARNING,
             '<h3>' + second + '</h3>' + SKYSHOP_REDEMPTION]
    if reverse:
        parts.reverse()
    return '<div class="wysiwyg-field"><h1>Аэрофлот Бонус</h1>' + ''.join(parts) + '</div>'


def iway(first='Накопить мили', second='Использовать мили', *, reverse=False):
    parts = ['<div class="condition_earn"><h3>' + first + '</h3>' + IWAY_EARNING + '</div>',
             '<h3>' + second + '</h3><p>Корпоративные поездки исключены.</p>']
    if reverse:
        parts.reverse()
    return '<main><div class="promo"><p>Аэрофлот Бонус. Акция действует в июне.</p>' + ''.join(parts) + '</div></main>'


class KnownRuleHeadingBoundaryTests(unittest.TestCase):
    def test_retail_heading_variants_keep_owned_earning_and_redemption(self):
        variants = [('Условия<br>начислений:', 'Условия<br>списаний:'),
                    ('УСЛОВИЯ НАЧИСЛЕНИЙ:', 'УСЛОВИЯ СПИСАНИЙ:'),
                    ('Условия начислений', 'Условия списаний'),
                    ('Условия начислений :', 'Условия списаний :')]
        for source in ('af_bootwood_rules', 'af_wolford_rules'):
            baseline = parse(source, retail(source))
            for first, second in variants:
                with self.subTest(source=source, first=first):
                    row = parse(source, retail(source, first, second))
                    self.assertEqual(row['id'], baseline['id'])
                    self.assertEqual(row['details']['earning_rules'][0]['basis_amount'], '70')
                    self.assertEqual(row['details']['redemption_rules']['max_order_percent'], '30')
                    self.assertEqual(row['details']['redemption_rules']['minimum_cash_percent'], '70')
                    self.assertEqual(row['details']['earning_conditions'],
                                     '1 миля начисляется за каждые потраченные 70 руб.\nМили начисляются после доставки.')
                    self.assertIn(row['details']['earning_conditions'], row['conditions_text'])
                    self.assertIn(row['details']['redemption_rules']['evidence'], row['conditions_text'])

    def test_skyshop_heading_variants_do_not_promote_redemption_to_earning(self):
        variants = [('Условия<br>начислений:', 'Условия получения<br>премий:'),
                    ('УСЛОВИЯ НАЧИСЛЕНИЙ:', 'УСЛОВИЯ ПОЛУЧЕНИЯ ПРЕМИЙ:'),
                    ('Условия начислений', 'Условия получения премий')]
        for first, second in variants:
            with self.subTest(first=first):
                row = parse('af_skyshop_rules', skyshop(first, second))
                rules = row['details']['earning_rules']
                self.assertEqual([(rule['value'], rule['basis_amount']) for rule in rules], [('2', '50')])
                self.assertNotIn('99 миль', row['benefit_text'])
                self.assertIn('99 миль', row['details']['redemption_rules']['evidence'])
                self.assertIn('50 руб.\nМили начисляются', row['benefit_text'])
                self.assertIn(row['details']['redemption_rules']['evidence'], row['conditions_text'])

    def test_iway_heading_variants_keep_channels_and_promotion_separate(self):
        variants = [('Накопить<br>мили', 'Использовать<br>мили'),
                    ('НАКОПИТЬ МИЛИ', 'ИСПОЛЬЗОВАТЬ МИЛИ'),
                    ('Накопить мили :', 'Использовать мили :')]
        for first, second in variants:
            with self.subTest(first=first):
                row = parse('af_iway_rules', iway(first, second))
                rates = {rule['channel']: rule['basis_amount'] for rule in row['details']['earning_rules']}
                self.assertEqual(rates, {'travel_agent': '90', 'direct': '50'})
                self.assertIn('Акция действует в июне.', row['details']['promotional_teaser']['evidence'])
                self.assertNotIn('1 миля', row['details']['promotional_teaser']['evidence'])
                self.assertIn('Корпоративные поездки исключены.', row['details']['redemption_rules']['evidence'])
                self.assertNotIn('1 миля', row['details']['redemption_rules']['evidence'])
                self.assertIn(row['details']['redemption_rules']['evidence'], row['conditions_text'])

    def test_duplicate_owned_headings_are_ambiguous(self):
        cases = [('af_bootwood_rules', retail('af_bootwood_rules'), 'Условия начислений:'),
                 ('af_wolford_rules', retail('af_wolford_rules'), 'Условия списаний:'),
                 ('af_skyshop_rules', skyshop(), 'Условия получения премий:'),
                 ('af_iway_rules', iway(), 'Накопить мили'),
                 ('af_iway_rules', iway(), 'Использовать мили')]
        for source, html, heading in cases:
            with self.subTest(source=source, heading=heading):
                duplicated = html.replace('<h3>' + heading + '</h3>',
                                          '<h3>' + heading + '</h3><h3>' + heading.upper() + '</h3>')
                with self.assertRaises(ValueError):
                    parse(source, duplicated)

    def test_reversed_owned_sections_are_rejected(self):
        cases = [('af_bootwood_rules', retail('af_bootwood_rules', reverse=True)),
                 ('af_wolford_rules', retail('af_wolford_rules', reverse=True)),
                 ('af_skyshop_rules', skyshop(reverse=True)),
                 ('af_iway_rules', iway(reverse=True))]
        for source, html in cases:
            with self.subTest(source=source):
                with self.assertRaises(ValueError):
                    parse(source, html)


if __name__ == '__main__':
    unittest.main()
