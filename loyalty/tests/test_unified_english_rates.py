"""English rate labels own local percentages, not every number in a source cell."""
import copy
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from unified_normalization import make_input, normalize_record, pointer, validate_normalized


def source_input(benefit, *, origin='parser_offers', conditions='', details=None):
    if origin == 'parser_offers':
        values = {
            'Программа': 'Example', 'Партнёр': 'Example', 'Заголовок': 'Example',
            'Тип записи': 'partner_offer', 'Выгода': benefit, 'Условия': conditions,
            'Источник': 'https://example.com/offer', 'Тип ссылки': 'detail_page',
            'Получено UTC': '2026-11-05T00:00:00+00:00', 'Статус источника': 'published',
            'Детали JSON': json.dumps(details or {}, ensure_ascii=False),
        }
    else:
        values = {'Service Name': 'Example', 'Discount': benefit, 'Notes': conditions}
    return make_input(dict(id='fixture:english-rates', origin=origin, row=2,
                           fields={k: {'value': v} for k, v in values.items()}))


class EnglishRateOwnershipTests(unittest.TestCase):
    def project(self, benefit, **kwargs):
        raw = source_input(benefit, **kwargs)
        before = copy.deepcopy(raw)
        result = normalize_record(raw, as_of='2026-11-06')
        self.assertEqual(raw, before)
        self.assertEqual(result['raw'], before)
        self.assertEqual(result['provenance']['observed_at'], before['observed_at'])
        validate_normalized(result)
        for item in result['benefits']:
            self.assertIn(item['evidence']['text'], pointer(before, item['evidence']['path']))
        return result

    def rates(self, benefit, **kwargs):
        return [(b['kind'], b['value'], b['unit'], b['qualifier'])
                for b in self.project(benefit, **kwargs)['benefits']]

    def test_discount_does_not_own_next_sentence_prepayment(self):
        self.assertEqual(self.rates('Discount 10%. 100% prepayment is required.'),
                         [('discount', '10', 'percent', 'exact')])

    def test_discount_and_cashback_keep_their_local_labels(self):
        self.assertEqual(self.rates('Discount 10%. Cashback 5%.'),
                         [('discount', '10', 'percent', 'exact'),
                          ('cashback', '5', 'percent', 'exact')])

    def test_same_sentence_prepayment_is_not_discount(self):
        self.assertEqual(self.rates('Discount 10% with 100% prepayment.'),
                         [('discount', '10', 'percent', 'exact')])

    def test_postfix_reward_label_does_not_own_later_payment_percentage(self):
        for body, kind, value in (
                ('10% off, 100% prepayment.', 'discount', '10'),
                ('5% cashback, commission 2%.', 'cashback', '5')):
            with self.subTest(body=body):
                self.assertEqual(self.rates(body), [(kind, value, 'percent', 'exact')])
        self.assertEqual(self.rates('100% off first order.'),
                         [('discount', '100', 'percent', 'exact')])

    def test_payment_tax_and_commission_percentages_are_not_rewards(self):
        cases = (
            ('Discount 10%. Tax 20% is included.', 'discount', '10'),
            ('10% off with 100% prepayment.', 'discount', '10'),
            ('Cashback 5%, payment of 100% is required.', 'cashback', '5'),
            ('Cashback 5%, commission 2%.', 'cashback', '5'),
            ('Commission 2%, cashback 5%.', 'cashback', '5'),
            ('Payment 100%, discount 10%.', 'discount', '10'),
            ('Discount 10%, taxes 20%.', 'discount', '10'),
            ('Discount 10%, 20% VAT.', 'discount', '10'),
            ('Cashback 5%, fee 2%.', 'cashback', '5'),
        )
        for body, kind, value in cases:
            with self.subTest(body=body):
                self.assertEqual(self.rates(body), [(kind, value, 'percent', 'exact')])
        self.assertEqual(self.rates('Discount available with 100% prepayment.'), [])

    def test_explicit_discount_on_commission_is_preserved(self):
        for body in ('10% discount on commission.', 'Discount on commission 10%.'):
            with self.subTest(body=body):
                self.assertEqual(self.rates(body), [('discount', '10', 'percent', 'exact')])

    def test_parallel_discount_on_commission_keeps_its_explicit_subject(self):
        self.assertEqual(self.rates('Discount on delivery 10% and on commission 50%.'),
                         [('discount', '10', 'percent', 'exact'),
                          ('discount', '50', 'percent', 'exact')])
        self.assertEqual(self.rates('Discount10% with commission50%'),
                         [('discount', '10', 'percent', 'exact')])

    def test_mixed_language_labels_do_not_duplicate_or_relabel_rates(self):
        cases = (
            'Скидка 10%, cashback 5%.', 'Discount 10%, кешбэк 5%.',
            'Скидка10%, cashback5%', 'Discount10%,кешбэк5%',
            '10% скидка, 5% cashback.', '10% off, 5% кешбэк.',
        )
        for body in cases:
            with self.subTest(body=body):
                self.assertEqual(self.rates(body),
                                 [('discount', '10', 'percent', 'exact'),
                                  ('cashback', '5', 'percent', 'exact')])

    def test_qualifiers_are_local_and_decimal_points_are_not_sentence_breaks(self):
        self.assertEqual(self.rates('Discount up to 12.5%. Cashback 5%.'),
                         [('discount', '12.5', 'percent', 'up_to'),
                          ('cashback', '5', 'percent', 'exact')])
        self.assertEqual(self.rates('10% off, cashback up to 5%.'),
                         [('discount', '10', 'percent', 'exact'),
                          ('cashback', '5', 'percent', 'up_to')])

    def test_labels_do_not_cross_sentence_or_field_boundaries(self):
        for punctuation in ('.', '!', '?'):
            body = 'Discount 10%' + punctuation + ' 20% payment is required.'
            with self.subTest(body=body):
                self.assertEqual(self.rates(body), [('discount', '10', 'percent', 'exact')])
        self.assertEqual(self.rates('Discount 10%.', conditions='100% prepayment.'),
                         [('discount', '10', 'percent', 'exact')])
        self.assertEqual(self.rates('Discount.', conditions='10%.'), [])

    def test_unlabelled_percent_is_allowed_only_in_legacy_discount_cell(self):
        for origin in ('yandex_discounts_complete_all', 'VG_community_offers'):
            with self.subTest(origin=origin):
                self.assertEqual(self.rates('12.5%', origin=origin, conditions='100%'),
                                 [('discount', '12.5', 'percent', 'exact')])
        self.assertEqual(self.rates('12.5%'), [])

    def test_english_fixed_rub_discounts_remain_amounts_with_original_evidence(self):
        cases = (
            ('2000 RUB off first order', '2000', 'exact'),
            ('Up to 1500.50 RUB discount', '1500.5', 'up_to'),
            ('1,000,000 RUB off', '1000000', 'exact'),
            ('2000 RUB off. Commission 3%.', '2000', 'exact'),
        )
        for body, value, qualifier in cases:
            with self.subTest(body=body):
                result = self.project(body)
                self.assertEqual([(b['kind'], b['value'], b['unit'], b['qualifier'])
                                  for b in result['benefits']],
                                 [('discount', value, 'RUB', qualifier)])
                self.assertEqual(result['benefits'][0]['evidence'],
                                 {'path': '/benefit', 'text': body})

    def test_unrelated_words_and_unassigned_pdf_tables_are_not_rate_labels(self):
        for body in ('CashbackClub 100% prepayment.', 'Discounted 100% payment.',
                     'Office 20% tax.', 'Turn off notifications. Payment 100%.'):
            with self.subTest(body=body):
                self.assertEqual(self.rates(body), [])
        self.assertEqual(self.rates('Discount 10%', details={'pages': [{'text': 'Discount 10%'}]}), [])

    def test_miles_fallback_cannot_bypass_unassigned_pdf_guard(self):
        body = 'Cashback5% милями'
        self.assertEqual(self.rates(body, details={'pages': [{'text': body}]}), [])
        result = self.project(body)
        self.assertEqual([(b['kind'], b['value'], b['unit'], b['reward_unit'])
                          for b in result['benefits']],
                         [('earn_miles', '5', 'percent', 'miles')])


if __name__ == '__main__':
    unittest.main()
