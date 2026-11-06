"""Currency abbreviations in explicit price bands retain their reward owner."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1]))
from normalized import make_offer, validate_offer


def published_record(body):
    row = make_offer('moskvich', 'price-bands', 'Карта', 'Партнёр', body,
                     'https://moskvichmag.ru/programma-loyalnosti/',
                     '2026-11-06T00:00:00Z')
    validate_offer(row)
    return row


class PriceBandRateTests(unittest.TestCase):
    def test_explicit_ruble_price_to_rate_separators_keep_the_rate(self):
        cases = [
            ('Скидка: от 1000 руб. — 5%, от 2000 руб. — 10%.',
             [('discount', '5', 'exact'), ('discount', '10', 'exact')]),
            ('Кешбэк: от 1000 руб. - 5%, от 2000 руб. - 10%.',
             [('cashback', '5', 'exact'), ('cashback', '10', 'exact')]),
            ('Скидка: от 1 000 руб. – до 5%, от 2 000 руб. – до 10%.',
             [('discount', '5', 'up_to'), ('discount', '10', 'up_to')]),
            ('Скидка: от 1000 руб. : 5%, от 2000 руб. : 10%.',
             [('discount', '5', 'exact'), ('discount', '10', 'exact')]),
            ('Скидка при оплате от 1000 руб. — 10%.',
             [('discount', '10', 'exact')]),
        ]
        for body, expected in cases:
            with self.subTest(body=body):
                row = published_record(body)
                self.assertEqual([(rate['kind'], rate['value'], rate['qualifier'])
                                  for rate in row['rates']], expected)
                self.assertEqual(row['benefit_text'], body)

    def test_ruble_sentence_ending_does_not_label_an_independent_percentage(self):
        for suffix in ['Предоплата 30%.', 'НДС 20%.', 'комиссия 10%.',
                       'Доля покупок 20%.', '20% покупателей.',
                       'Доля покупателей — 20%.']:
            with self.subTest(suffix=suffix):
                body = 'Скидка 5% при покупке от 1000 руб. ' + suffix
                row = published_record(body)
                self.assertEqual([(rate['kind'], rate['value']) for rate in row['rates']],
                                 [('discount', '5')])
                self.assertIn(suffix, row['benefit_text'])

    def test_price_band_does_not_capture_a_later_payment_condition(self):
        for suffix in [' при комиссии 20%.', ', предоплата 30%.',
                       '. Предоплата 30%.', '. Доля покупателей 20%.']:
            with self.subTest(suffix=suffix):
                row = published_record('Скидка от 1000 руб. — 10%' + suffix)
                self.assertEqual([(rate['kind'], rate['value']) for rate in row['rates']],
                                 [('discount', '10')])

    def test_fee_or_prepayment_amount_does_not_supply_another_discount(self):
        for suffix in ['комиссия за услугу 1000 руб. - 10%.',
                       'предоплата 1000 руб. - 10%.',
                       'комиссия за услугу от 1000 руб. - 10%.',
                       'предоплата от 1000 руб. - 10%.',
                       'штраф от 1000 руб. — 10%.',
                       'при согласии на комиссию от 1000 руб. — 10%.']:
            with self.subTest(suffix=suffix):
                row = published_record('Скидка 5%, ' + suffix)
                self.assertEqual([(rate['kind'], rate['value']) for rate in row['rates']],
                                 [('discount', '5')])

    def test_discount_explicitly_on_a_commission_keeps_its_price_band(self):
        for body in ['Скидка на комиссию от 1000 руб. — 50%.',
                     'Скидка на доставку 10% и на комиссию от 1000 руб. — 50%.']:
            with self.subTest(body=body):
                row = published_record(body)
                self.assertEqual([rate['value'] for rate in row['rates']],
                                 ['10', '50'] if 'доставку' in body else ['50'])


if __name__ == '__main__':
    unittest.main()
