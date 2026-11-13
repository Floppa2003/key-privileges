"""Anonymized source clauses: a bound is not an additional earned benefit."""
import copy
import unittest

from normalized import normalize_rates
from unified_normalization import normalize_record, validate_normalized
from test_unified_normalization import record


class ObservedNumericCapsTests(unittest.TestCase):
    def common(self, benefit, conditions='', **updates):
        raw = record(benefit=benefit, conditions=conditions, activation='', **updates)
        before = copy.deepcopy(raw)
        result = normalize_record(raw, as_of='2026-11-13')
        self.assertEqual(raw, before)
        self.assertEqual(result['raw'], before)
        validate_normalized(result)
        return result

    def test_eligible_spend_ceiling_does_not_become_cashback_rate(self):
        for ending in (' от общего оборота по карте в месяц.', ''):
            clause = ('Кешбэк 7% начисляется на сумму оплаты в ресторанных группах акции, '
                      'не превышающую 30%' + ending)
            with self.subTest(ending=ending):
                self.assertEqual([(r['kind'], r['value']) for r in normalize_rates(clause)],
                                 [('cashback', '7')])
                result = self.common(clause)
                self.assertEqual([(b['kind'], b['value']) for b in result['benefits']],
                                 [('cashback', '7')])
                bound, = [c for c in result['conditions'] if c['kind'] == 'maximum_amount_reference']
                self.assertEqual((bound['value'], bound['unit'], bound['qualifier']),
                                 ('30', 'percent', 'up_to'))
                self.assertEqual(bound['evidence']['text'], clause)

    def test_combined_discount_ceiling_keeps_only_the_actual_discount(self):
        clauses = (
            ('Скидка 10% при предъявлении карты на кассе.\n',
             'Суммарная скидка, при совместном применении нескольких акций и программ '
             'лояльности, не может превышать 30% от стоимости товара.', '10', '30'),
            ('Скидка 7% на весь ассортимент магазинов. ',
             'Суммарная скидка при совместном применении нескольких акций и программ '
             'лояльности не может превышать 40% от стоимости товара.', '7', '40'),
            ('Скидка 10% на все услуги и товары.\n',
             'Скидка по карте суммируется с текущими скидками на момент обращения и '
             'по карте постоянного клиента, но не может превышать в сумме 20%.', '10', '20'),
        )
        for headline, cap, value, maximum in clauses:
            with self.subTest(maximum=maximum):
                text = headline + cap
                self.assertEqual([(r['kind'], r['value']) for r in normalize_rates(text)],
                                 [('discount', value)])
                result = self.common(text)
                self.assertEqual([(b['kind'], b['value']) for b in result['benefits']],
                                 [('discount', value)])
                bound, = [c for c in result['conditions'] if c['kind'] == 'benefit_cap']
                self.assertEqual((bound['value'], bound['unit'], bound['qualifier']),
                                 (maximum, 'percent', 'up_to'))
                self.assertIn(bound['evidence']['text'], text)

    def test_combined_cap_owns_the_ellipsis_after_the_discount(self):
        headline = 'Скидка 20% по промокоду.'
        cap = ('Скидка по акции суммируется со скидкой по карте клуба, '
               'но не может превышать 30% от первоначальной стоимости товаров.')
        self.assertEqual(normalize_rates(cap), [])
        result = self.common(headline, cap)
        self.assertEqual([(b['kind'], b['value']) for b in result['benefits']], [('discount', '20')])
        self.assertEqual([(c['kind'], c['value']) for c in result['conditions'] if c['kind'] == 'benefit_cap'],
                         [('benefit_cap', '30')])

    def test_redeemable_share_ceiling_keeps_the_fixed_discount(self):
        headline = 'Скидка 1 000 ₽ на лабораторные исследования.'
        cap = 'Скидка не может превышать 15% от суммы чека.'
        self.assertEqual(normalize_rates(cap), [])
        result = self.common(headline, cap)
        self.assertEqual([(b['kind'], b['value'], b['unit']) for b in result['benefits']],
                         [('discount', '1000', 'RUB')])
        self.assertEqual([(c['kind'], c['value']) for c in result['conditions']], [('benefit_cap', '15')])

    def test_combined_cap_keeps_the_bonus_award(self):
        text = ('Получите 2 000 бонусов программы лояльности клуба. '
                'Бонусы по промокоду суммируются со скидкой по карте клуба, '
                'но суммарный объём скидки не может превышать 30% '
                'от первоначальной стоимости товаров.')
        self.assertEqual(normalize_rates(text), [])
        result = self.common(text)
        self.assertEqual([(b['kind'], b['value']) for b in result['benefits']], [('earn_points', '2000')])
        self.assertEqual([(c['kind'], c['value']) for c in result['conditions'] if c['kind'] == 'benefit_cap'],
                         [('benefit_cap', '30')])

    def test_monthly_payout_ceiling_does_not_become_exact_miles(self):
        cap = 'Максимальный лимит выплаты кешбэк/миль в месяц⁹ 9 000 миль'
        for literal in (cap, cap.replace('выплаты ', 'выплаты \n')):
            with self.subTest(wrapped='\n' in literal):
                self.assertEqual(normalize_rates(literal), [])
                result = self.common('За каждые потраченные на покупки 100 руб. начисляется: '
                                     '• 1 миля при сумме покупок по карте в месяц '
                                     'от 10 000 руб. до 75 000 руб. ' + literal,
                                     details={'monthly_miles_cap': '9000', 'monthly_miles_cap_evidence': cap})
                self.assertEqual([(b['kind'], b['value'], b['basis_value']) for b in result['benefits']],
                                 [('earn_miles', '1', None)])
                bound, = result['conditions']
                self.assertEqual((bound['kind'], bound['value'], bound['unit'], bound['qualifier'], bound['scope']),
                                 ('reward_cap', '9000', 'miles', 'up_to', {'period': 'month'}))


if __name__ == '__main__':
    unittest.main()
