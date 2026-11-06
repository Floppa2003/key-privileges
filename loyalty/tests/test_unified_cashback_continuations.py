"""Literal payout continuations and exchange rates keep separate ownership.

All fixtures are synthetic; no workbook rows or source-specific identifiers.
"""
import copy
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from unified_normalization import normalize_record, validate_normalized
from test_unified_normalization import record


class CashbackContinuations(unittest.TestCase):
    def project(self, literal, **updates):
        raw = record(benefit=literal, conditions='', activation='', **updates)
        before = copy.deepcopy(raw)
        result = normalize_record(raw, as_of='2026-11-06')
        self.assertEqual(raw, before)
        self.assertEqual(result['raw'], before)
        validate_normalized(json.loads(json.dumps(result)))
        for item in result['benefits']:
            if item['evidence']['path'] == '/benefit':
                self.assertIn(item['evidence']['text'], literal)
        return result

    def rewards(self, literal):
        return [(b['kind'], b['value'], b['unit'], b['reward_unit'])
                for b in self.project(literal)['benefits']]

    def test_russian_amount_repayment_continues_the_same_cashback(self):
        cases = (
            ('Начислим 100% кешбэк за покупку билета. '
             'Полная стоимость вернется вам на счет в виде бонусов программы.',
             'earn_points', '100', 'points'),
            ('Кешбэк 10%. Сумма возвращается в бонусах.',
             'earn_points', '10', 'points'),
            ('Кешбэк 10%. Сумма будет начислена в баллах.',
             'earn_points', '10', 'points'),
            ('Кешбэк 10%. Эта сумма начисляется милями.',
             'earn_miles', '10', 'miles'),
        )
        for literal, kind, value, unit in cases:
            with self.subTest(literal=literal):
                self.assertEqual(self.rewards(literal), [(kind, value, 'percent', unit)])

    def test_english_amount_credit_continues_the_same_cashback(self):
        literal = 'Cashback 10%. The amount is credited in points.'
        self.assertEqual(self.rewards(literal),
                         [('earn_points', '10', 'percent', 'points')])

    def test_payment_and_negative_clauses_do_not_define_the_payout_unit(self):
        cases = (
            'Кешбэк 10%. Покупку можно оплатить бонусами.',
            'Кешбэк 10%. Кешбэк не начисляется баллами.',
            'Кешбэк 10%. Кешбэк не начисляется при оплате бонусами.',
            'Кешбэк 10%. Полная стоимость не вернется в виде бонусов.',
            'Кешбэк 10%. Сумма возвращается не бонусами.',
            'Кешбэк 10%. Стоимость доставки возвращается бонусами.',
            'Cashback 10%. You can pay with points.',
            'Cashback 10%. The amount is not credited in points.',
        )
        for literal in cases:
            with self.subTest(literal=literal):
                self.assertEqual(self.rewards(literal),
                                 [('cashback', '10', 'percent', None)])

    def test_continuation_does_not_cross_another_sentence_or_source_boundary(self):
        for literal in (
                'Кешбэк 10%. Подробности в правилах. Сумма вернется бонусами.',
                'Кешбэк 10%.\nСумма вернется бонусами.',
                'Кешбэк 10%.\n\nСумма вернется бонусами.'):
            with self.subTest(literal=literal):
                self.assertEqual(self.rewards(literal),
                                 [('cashback', '10', 'percent', None)])
        raw = record(benefit='Кешбэк 10%.', conditions='Сумма вернется бонусами.')
        result = normalize_record(raw, as_of='2026-11-06')
        self.assertEqual(result['raw'], raw)
        self.assertEqual([(b['kind'], b['value']) for b in result['benefits']],
                         [('cashback', '10')])

    def test_continuation_requires_one_rate_and_preserves_an_explicit_unit(self):
        cases = (
            ('Кешбэк 10% и 20%. Сумма вернется бонусами.',
             [('cashback', '10'), ('cashback', '20')]),
            ('Кешбэк 10%. Кешбэк 20%. Сумма вернется бонусами.',
             [('cashback', '10'), ('earn_points', '20')]),
            ('Кешбэк 10% рублями. Сумма вернется бонусами.',
             [('cashback', '10')]),
        )
        for literal, expected in cases:
            with self.subTest(literal=literal):
                self.assertCountEqual([(b['kind'], b['value'])
                                       for b in self.project(literal)['benefits']], expected)

    def test_exchange_equation_does_not_add_a_points_payment(self):
        cases = (
            ('Получите кешбэк 10% бонусами. Обмен по курсу 1 бонус = 1 рубль.',
             [('earn_points', '10', 'percent', 'points')]),
            ('Начислим 100% кешбэк за покупку билета. '
             'Полная стоимость вернется вам на счет в виде бонусов программы. '
             'Бонусы можно обменять по курсу 1 бонус = 1 рубль.',
             [('earn_points', '100', 'percent', 'points')]),
            ('Получите 500 баллов. Обмен по курсу 1 балл = 1 рубль.',
             [('earn_points', '500', 'points', 'points')]),
            ('Получите 500 баллов, обмен по курсу 1 балл = 1 рубль.',
             [('earn_points', '500', 'points', 'points')]),
            ('Получите 500 баллов и обменяйте их по курсу 1 балл = 1 рубль.',
             [('earn_points', '500', 'points', 'points')]),
            ('Получаете 100 000 бонусов за покупку. 1 бонус = 1 рубль.',
             [('earn_points', '100000', 'points', 'points')]),
        )
        for literal, expected in cases:
            with self.subTest(literal=literal):
                result = self.project(literal)
                self.assertEqual([(b['kind'], b['value'], b['unit'], b['reward_unit'])
                                  for b in result['benefits']], expected)
                self.assertEqual(result['benefits'][0]['evidence'],
                                 {'path': '/benefit', 'text': literal})

    def test_real_points_awards_keep_their_cash_equivalent(self):
        for literal, value in (
                ('Получите 500 баллов.', '500'),
                ('Получите 1 балл за каждые 70 рублей.', '1'),
                ('Начисляем по курсу 1 балл = 1 рубль покупки.', '1'),
                ('За обмен валюты начисляем по курсу 1 балл = 1 рубль покупки.', '1'),
                ('При конвертации валюты начисляем по курсу 1 балл = 1 рубль покупки.', '1'),
                ('Начисляем за обмен валюты по курсу 1 балл = 1 рубль покупки.', '1'),
                ('Начисляем при конвертации валюты по курсу 1 балл = 1 рубль покупки.', '1'),
                ('Получите 100 бонусов (= 100 рублей).', '100')):
            with self.subTest(literal=literal):
                self.assertEqual(self.rewards(literal),
                                 [('earn_points', value, 'points', 'points')])

    def test_additional_points_require_their_own_positive_award(self):
        for literal, value in (
                ('Получите 6 000 дополнительных бонусов на следующую поездку. '
                 '1 бонус = 1 рубль.', '6000'),
                ('Начислим 500 дополнительных баллов.', '500'),
                ('500 дополнительных баллов начисляются за покупку.', '500'),
                ('Получите 100 дополнительных бонусов (= 100 рублей).', '100')):
            with self.subTest(literal=literal):
                self.assertEqual(self.rewards(literal),
                                 [('earn_points', value, 'points', 'points')])
        for literal in (
                'Не получите 6000 дополнительных бонусов.',
                'Нельзя получить 6000 дополнительных бонусов.',
                'Не будут начислены 6000 дополнительных бонусов.',
                '6000 дополнительных бонусов не начисляются.',
                'Потратьте 6000 дополнительных баллов на следующую покупку.',
                'Получите скидку. Потратьте 6000 дополнительных баллов.',
                'Получите скидку за 6000 дополнительных баллов.'):
            with self.subTest(literal=literal):
                self.assertEqual(self.rewards(literal), [])

    def test_postfix_credit_does_not_award_a_rejected_or_replaced_amount(self):
        cases = (
            ('Не 500 дополнительных баллов начисляются, а 1000 дополнительных баллов.', []),
            ('Вместо 500 дополнительных баллов начисляются 1000 дополнительных баллов.',
             [('earn_points', '1000', 'points', 'points')]),
            ('Кроме 500 дополнительных баллов начисляются 1000 дополнительных баллов.',
             [('earn_points', '1000', 'points', 'points')]),
        )
        for literal, expected in cases:
            with self.subTest(literal=literal):
                self.assertEqual(self.rewards(literal), expected)

    def test_structured_points_earning_keeps_its_purchase_basis(self):
        literal = '1 балл за каждые 70 рублей.'
        details = {'earning_rules': [
            {'value': '1', 'unit': 'points', 'basis_amount': '70',
             'basis_unit': 'RUB', 'reward_unit': 'program_bonus',
             'evidence': literal}]}
        result = self.project(literal, details=details)
        self.assertEqual([(b['kind'], b['value'], b['unit'], b['basis_value'],
                           b['basis_unit'], b['reward_unit'])
                          for b in result['benefits']],
                         [('earn_points', '1', 'points', '70', 'RUB', 'program_bonus')])


if __name__ == '__main__':
    unittest.main()

