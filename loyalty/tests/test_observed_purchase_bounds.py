"""Purchase bounds from encountered public clauses retain their own roles."""
import copy
import json
import unittest
from pathlib import Path

from test_unified_normalization import record
from unified_normalization import normalize_record, validate_normalized


CASES = json.loads(Path(__file__).with_name('fixtures').joinpath(
    'reconciled/observed_purchase_bounds_20261114.json').read_text())['cases']


class ObservedPurchaseBounds(unittest.TestCase):
    def normalize(self, name):
        raw = record(**CASES[name])
        before = copy.deepcopy(raw)
        result = normalize_record(raw, as_of='2026-11-14')
        self.assertEqual(raw, before)
        self.assertEqual(result['raw'], before)
        validate_normalized(result)
        return result

    def test_native_minimum_sum_predicate_retains_500_ruble_requirement(self):
        result = self.normalize('s7_order_minimum')
        minima = [c for c in result['conditions'] if c['kind'] == 'minimum_purchase']
        self.assertEqual([(c['value'], c['unit'], c['qualifier']) for c in minima],
                         [('500', 'RUB', 'at_least')])

    def test_each_pharmacy_rate_keeps_its_own_upper_or_strict_lower_bound(self):
        result = self.normalize('pharmacy_purchase_bands')
        conditions = {c['id']: c for c in result['conditions']}
        links = [(b['value'], [(conditions[c]['kind'], conditions[c]['value'],
                              conditions[c]['qualifier']) for c in b['condition_ids']
                             if conditions[c]['kind'] in ('minimum_purchase', 'maximum_purchase')])
                 for b in result['benefits']]
        self.assertEqual(links, [
            ('5', [('maximum_purchase', '1500', 'up_to')]),
            ('7', [('minimum_purchase', '1500', 'greater_than')]),
        ])

    def test_one_ruble_trade_in_top_up_is_a_payment_requirement(self):
        result = self.normalize('trade_in_cash_top_up')
        self.assertEqual([(c['value'], c['unit'], c['qualifier']) for c in result['conditions']
                          if c['kind'] == 'minimum_cash_payment'], [('1', 'RUB', 'at_least')])
        self.assertFalse(any(c['kind'] == 'minimum_purchase' for c in result['conditions']))

    def test_named_photo_goods_do_not_hide_the_gifts_order_minimum(self):
        result = self.normalize('photo_qualified_order_minimum')
        minima = [c for c in result['conditions'] if c['kind'] == 'minimum_purchase']
        self.assertEqual(len(minima), 1)
        minimum, = minima
        self.assertEqual((minimum['value'], minimum['qualifier']), ('499', 'at_least'))
        gift, = result['benefits']
        self.assertEqual(gift['kind'], 'gift')
        self.assertIn(minimum['id'], gift['condition_ids'])

    def test_pre_discount_basket_total_keeps_its_phase_and_delivery_exclusion(self):
        result = self.normalize('photo_before_discount_total')
        minima = [c for c in result['conditions'] if c['kind'] == 'minimum_purchase']
        self.assertEqual(len(minima), 1)
        minimum, = minima
        self.assertEqual((minimum['value'], minimum['qualifier']), ('1099', 'at_least'))
        self.assertEqual(minimum['scope'], {'price_phase': 'before_discount',
                                           'delivery_included': False})

    def test_not_less_than_purchase_amount_is_linked_to_its_welcome_reward(self):
        result = self.normalize('uralsib_purchase_minimum')
        minima = [c for c in result['conditions'] if c['kind'] == 'minimum_purchase']
        self.assertEqual(len(minima), 1)
        minimum, = minima
        self.assertEqual((minimum['value'], minimum['qualifier']), ('3000', 'at_least'))
        reward, = [b for b in result['benefits'] if b['value'] == '14000']
        self.assertIn(minimum['id'], reward['condition_ids'])

    def test_excluded_large_orders_do_not_become_positive_purchase_minima(self):
        result = self.normalize('sportmaster_denied_purchase_control')
        self.assertFalse(any(c['kind'] in ('minimum_purchase', 'maximum_purchase')
                             for c in result['conditions']))
        self.assertTrue(any(c['kind'] == 'exclusion' for c in result['conditions']))


if __name__ == '__main__':
    unittest.main()
