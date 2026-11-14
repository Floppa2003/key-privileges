"""Encountered purchase qualifiers, tier windows and literal negative controls."""
import copy
import json
import unittest
from pathlib import Path

from test_unified_normalization import record
from unified_normalization import normalize_record, validate_normalized


CASES = json.loads(Path(__file__).with_name('fixtures').joinpath(
    'reconciled/observed_qualified_purchase_bounds_20261114.json').read_text())['cases']


class ObservedQualifiedPurchaseBounds(unittest.TestCase):
    def normalize(self, name):
        raw = record(**CASES[name])
        before = copy.deepcopy(raw)
        result = normalize_record(raw, as_of='2026-11-14')
        self.assertEqual(raw, before)
        self.assertEqual(result['raw'], before)
        validate_normalized(result)
        return result

    def bounds(self, result, benefit):
        terms = {c['id']: c for c in result['conditions']}
        return sorted((terms[c]['kind'], terms[c]['value'], terms[c]['qualifier'])
                      for c in benefit['condition_ids']
                      if terms[c]['kind'] in ('minimum_purchase', 'maximum_purchase'))

    def test_flat_range_keeps_both_ends_on_the_middle_cashback_rate(self):
        result = self.normalize('flat_range')
        self.assertEqual([(b['value'], self.bounds(result, b)) for b in result['benefits']], [
            ('5', [('maximum_purchase', '1999.99', 'up_to')]),
            ('7', [('maximum_purchase', '2999.99', 'up_to'),
                   ('minimum_purchase', '2000', 'at_least')]),
            ('10', [('minimum_purchase', '3000', 'at_least')]),
        ])

    def test_wrapped_purchase_bound_remains_on_the_fixed_discount(self):
        result = self.normalize('wrapped_purchase')
        self.assertEqual([(b['value'], self.bounds(result, b)) for b in result['benefits']], [
            ('5', [('maximum_purchase', '200000', 'up_to')]),
            ('10000', [('minimum_purchase', '200000', 'at_least')]),
        ])
        self.assertTrue(any('\nот 200 000' in c['evidence']['text']
                            for c in result['conditions'] if c['kind'] == 'minimum_purchase'))

    def test_goods_qualification_does_not_mix_three_pharmacy_bands(self):
        result = self.normalize('pharmacy_goods_bands')
        benefits = [b for b in result['benefits'] if 'покупке товаров' in b['evidence']['text']]
        self.assertEqual([(b['value'], self.bounds(result, b)) for b in benefits], [
            ('3', [('maximum_purchase', '2000', 'up_to')]),
            ('5', [('maximum_purchase', '2500', 'up_to'),
                   ('minimum_purchase', '2000', 'at_least')]),
            ('10', [('minimum_purchase', '2500', 'at_least')]),
        ])

    def test_named_goods_channels_and_card_conditions_keep_their_threshold(self):
        expected = {'delivery_qualified': '1500', 'merchant_qualified': '1500',
                    'first_merchant_qualified': '1000', 'cosmetics_qualified': '2000',
                    'pie_qualified': '3950', 'meal_qualified': '1000',
                    'service_qualified': '2000', 'card_qualified': '1000',
                    'card_category_qualified': '10000'}
        for name, amount in expected.items():
            with self.subTest(name=name):
                result = self.normalize(name)
                self.assertEqual([(c['value'], c['qualifier']) for c in result['conditions']
                                  if c['kind'] == 'minimum_purchase'], [(amount, 'at_least')])

    def test_explicit_total_spending_is_not_silently_a_single_order(self):
        result = self.normalize('aggregate_spending')
        minima = [c for c in result['conditions'] if c['kind'] == 'minimum_purchase']
        self.assertEqual(len(minima), 1)
        self.assertEqual((minima[0]['value'], minima[0]['scope']),
                         ('5000', {'spending_basis': 'aggregate'}))

    def test_one_order_total_is_not_aggregate_spending_across_purchases(self):
        result = self.normalize('single_order_total')
        minima = [c for c in result['conditions'] if c['kind'] == 'minimum_purchase']
        self.assertEqual([(c['value'], c['scope']) for c in minima], [('5000', {})])

    def test_sequential_visit_rate_does_not_override_the_independent_first_subscription(self):
        result = self.normalize('sequential_visit_rates')
        self.assertEqual([(b['value'], b['scope'].get('purchase_stage')) for b in result['benefits']],
                         [('20', 'first'), ('5', 'repeat'), ('10', 'first')])

    def test_relative_and_booking_price_comparators_keep_strictness(self):
        for name, amount in [('booking_strict', '150000'), ('relative_purchase', '10000')]:
            with self.subTest(name=name):
                result = self.normalize(name)
                self.assertEqual([(c['value'], c['qualifier']) for c in result['conditions']
                                  if c['kind'] == 'minimum_purchase'], [(amount, 'greater_than')])

    def test_excluded_order_or_policy_bands_are_not_positive_requirements(self):
        for name in ('denied_cost_band', 'denied_policy_band'):
            with self.subTest(name=name):
                result = self.normalize(name)
                self.assertFalse(any(c['kind'] in ('minimum_purchase', 'maximum_purchase')
                                     for c in result['conditions']))

    def test_tier_qualification_alternatives_are_not_direct_offer_purchase_bounds(self):
        result = self.normalize('tier_qualification')
        self.assertFalse(any(c['kind'] in ('minimum_purchase', 'maximum_purchase')
                             for c in result['conditions']))
        self.assertIn('две покупки общей стоимостью', result['raw']['conditions'])


if __name__ == '__main__':
    unittest.main()
