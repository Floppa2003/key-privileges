"""Published grouped amounts retain their values in the common projection."""
import unittest

from test_unified_normalization import record
from unified_normalization import normalize_record, validate_normalized


class CommonNumericLiteralTests(unittest.TestCase):
    def project(self,body):
        raw=record(benefit=body,conditions='',activation='')
        result=normalize_record(raw,as_of='2026-11-06')
        validate_normalized(result)
        self.assertEqual(result['raw'],raw)
        return result

    def test_purchase_threshold_and_cap_keep_grouped_amounts(self):
        result=self.project('Скидка 10% при заказе от 1.500,50 ₽. Максимальная скидка 1.000.000 ₽.')
        self.assertEqual([(c['kind'],c['value']) for c in result['conditions']],
                         [('minimum_purchase','1500.5'),('benefit_cap','1000000')])

    def test_grouped_points_are_not_parsed_as_a_tail_or_zero(self):
        for amount in ('1.000.000','1,000,000','1\u202f000\u202f000'):
            with self.subTest(amount=amount):
                result=self.project('Начисляется '+amount+' бонусов.')
                self.assertEqual([(b['kind'],b['value'],b['unit']) for b in result['benefits']],
                                 [('earn_points','1000000','points')])

    def test_english_ruble_discount_keeps_grouping_and_decimals(self):
        result=self.project('1,500.50 RUB discount')
        self.assertEqual([(b['kind'],b['value'],b['unit']) for b in result['benefits']],
                         [('discount','1500.5','RUB')])

    def test_commission_condition_does_not_erase_a_separate_explicit_reward(self):
        cases=[
            ('Скидка на комиссию 50%.',[('discount','50')]),
            ('Скидка на доставку 10% и на комиссию 50%.',[('discount','10'),('discount','50')]),
            ('Скидка 10%, комиссия 50%.',[('discount','10')]),
            ('Скидка 10% при комиссии 50%.',[('discount','10')]),
            ('Кешбэк 5%, комиссия 1%.',[('cashback','5')]),
            ('Комиссия 1,5%, минимум 50 ₽.',[]),
        ]
        for body,expected in cases:
            with self.subTest(body=body):
                result=self.project(body)
                self.assertEqual([(b['kind'],b['value']) for b in result['benefits']],expected)

    def test_parenthesized_bonus_caps_are_not_fixed_rewards(self):
        body='Получайте +10% бонусов (до 1000 бонусов).'
        result=self.project(body)
        self.assertEqual(result['benefits'],[])
        self.assertEqual([(c['kind'],c['value'],c['unit'],c['qualifier']) for c in result['conditions']],
                         [('benefit_cap','1000','points','up_to')])

    def test_separate_bonus_caps_remain_constraints_in_a_parallel_offer(self):
        result=self.project('Получайте +10% бонусов за первый заказ (до 500 бонусов) '
                            'и +5% за последующие (до 250 бонусов).')
        self.assertFalse(any(b['value'] in ('500','250') for b in result['benefits']))
        self.assertEqual([(c['kind'],c['value'],c['unit']) for c in result['conditions'] if c['kind']=='benefit_cap'],
                         [('benefit_cap','500','points'),('benefit_cap','250','points')])

    def test_explicit_bonus_awards_keep_their_values_and_bounds(self):
        for prefix,qualifier in [('', 'unspecified'),('до ', 'up_to'),('от ', 'at_least')]:
            with self.subTest(prefix=prefix):
                result=self.project('Получите '+prefix+'500 бонусов за покупку.')
                self.assertEqual([(b['kind'],b['value'],b['qualifier']) for b in result['benefits']],
                                 [('earn_points','500',qualifier)])
                self.assertEqual(result['conditions'],[])


if __name__=='__main__':
    unittest.main()
