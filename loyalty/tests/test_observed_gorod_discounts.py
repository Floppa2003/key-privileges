"""Observed public coupon discounts keep native price, eligibility and identity."""
import copy
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from gorod_source import source_fields
from public_reward_projection import make_record, validate_record
from test_source_availability_dates import stored_input
from unified_normalization import make_input, normalize_record, validate_normalized


RECORDS = json.loads(Path(__file__).with_name('fixtures').joinpath(
    'reconciled/gorod_coupon_discounts_20261114.json').read_text())['records']
CASES = {r['evidence']['native']: r for r in RECORDS}


def retained(native):
    case = CASES[native]
    row = make_record(case['source'], case['evidence'], case['observed_at'])
    source = stored_input({
        'schema_version': 2, 'run_id': '43612232710:1', 'observed_at': row['observed_at'],
        'records': [row], 'sources': [{
            'source_id': row['source_id'], 'name': row['program'], 'root': row['source_url'],
            'status': 'ok', 'normalized': 1, 'discovered': 1, 'failed': 0,
            'coverage': 'captured_public_native_object', 'region': None,
            'errors': [], 'observed_at': row['observed_at'],
        }],
    })
    return make_input(source)


class ObservedGorodDiscounts(unittest.TestCase):
    def normalize(self, native):
        raw = retained(native)
        before = copy.deepcopy(raw)
        result = normalize_record(raw, as_of='2026-11-14')
        self.assertEqual(raw, before)
        self.assertEqual(result['raw'], before)
        validate_normalized(result)
        return result

    def test_public_percent_nominal_and_upper_bound_discounts_reach_common_model(self):
        expected = {
            'coupon:19635': [('20', 'percent', 'exact')],
            'coupon:19648': [('15', 'percent', 'exact')],
            'coupon:19629': [('20', 'percent', 'exact')],
            'coupon:19547': [('50', 'percent', 'exact'), ('30', 'percent', 'exact')],
            'coupon:19659': [('50', 'percent', 'up_to'), ('30', 'percent', 'up_to')],
            'coupon:19669': [('1000', 'RUB', 'exact')],
            'coupon:19912': [('500', 'RUB', 'exact')],
        }
        for native, wanted in expected.items():
            with self.subTest(native=native):
                result = self.normalize(native)
                self.assertEqual([(b['value'], b['unit'], b['qualifier'])
                                  for b in result['benefits'] if b['kind'] == 'discount'], wanted)
                self.assertFalse(any(b['kind'] == 'partner_privilege' for b in result['benefits']))

    def test_explicit_first_and_repeat_coupon_names_keep_their_purchase_stage(self):
        for native, stage in [('coupon:19635', 'first'), ('coupon:19629', 'first'),
                              ('coupon:19648', 'repeat')]:
            with self.subTest(native=native):
                result = self.normalize(native)
                self.assertEqual([b['scope'].get('purchase_stage') for b in result['benefits']], [stage])

    def test_coupon_identity_and_price_conditions_remain_owned_by_every_component(self):
        for native in ('coupon:19547', 'coupon:19669', 'coupon:19912'):
            with self.subTest(native=native):
                raw = retained(native)
                result = self.normalize(native)
                conditions = {c['id']: c for c in result['conditions']}
                for benefit in result['benefits']:
                    self.assertEqual(benefit['scope']['coupon_id'],
                                     raw['details']['public_reward_evidence']['data']['id'])
                    self.assertTrue(benefit['scope']['coupon_purchase_or_activation_not_performed'])
                    linked = [conditions[c] for c in benefit['condition_ids']]
                    self.assertTrue(any(c['kind'] == 'owned_programme_rules' and
                                        c['evidence']['text'] == raw['conditions'] for c in linked))
                    self.assertTrue(any(c['kind'] == 'activation_step' and
                                        c['evidence']['text'] == raw['activation'] for c in linked))
                    if benefit['kind'] == 'discount':
                        self.assertEqual(benefit['evidence']['text'], raw['benefit'])
                    else:
                        self.assertEqual(benefit['kind'], 'earn_points')
                        self.assertEqual(benefit['scope']['occasion'], 'coupon_purchase')
                        self.assertEqual(benefit['evidence']['path'], '/conditions')
                        self.assertIn(benefit['evidence']['text'], raw['conditions'])

    def test_source_output_and_common_discount_components_agree(self):
        for native in ('coupon:19547', 'coupon:19659', 'coupon:19669'):
            with self.subTest(native=native):
                raw = retained(native)
                evidence = raw['details']['public_reward_evidence']
                before = copy.deepcopy(evidence)
                fields = source_fields(evidence)
                row = make_record('gorod_public', evidence, raw['observed_at'])
                validate_record(row)
                self.assertEqual(evidence, before)
                self.assertEqual((fields['conditions'], fields['activation'], fields['benefit']),
                                 (raw['conditions'], raw['activation'], raw['benefit']))
                self.assertEqual([(t.get('value'), t.get('unit'), t.get('qualifier'))
                                  for t in fields['terms'] if t['kind'] == 'discount'],
                                 [(r['value'], r['unit'], r['qualifier'])
                                  for r in row['rates'] if r['kind'] == 'discount'])

    def test_unquantified_booster_gift_and_plain_price_do_not_create_discount_rates(self):
        for native in ('coupon:2', 'coupon:19726', 'coupon:19383'):
            with self.subTest(native=native):
                result = self.normalize(native)
                self.assertEqual([b['kind'] for b in result['benefits']], ['partner_privilege'])
                self.assertIsNone(result['benefits'][0]['value'])

    def test_discounted_order_audience_in_partner_tiers_remains_point_accrual(self):
        result = self.normalize('partner:3240')
        self.assertTrue(result['benefits'])
        self.assertTrue(all(b['kind'] == 'earn_points' for b in result['benefits']))
        self.assertTrue(all(b['reward_unit'] == 'Gorod_bonus_not_cash' for b in result['benefits']))


if __name__ == '__main__':
    unittest.main()
