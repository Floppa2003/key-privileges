"""Ownership regressions use unchanged public clauses from the actual source corpus."""
import copy
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from unified_normalization import normalize_record, validate_normalized
from normalized import normalize_rates
from test_unified_normalization import record


FIXTURE = Path(__file__).parent / 'fixtures/reconciled/condition_ownership_20261114.json'


class NativeConditionOwnership(unittest.TestCase):
    def test_first_visit_price_does_not_restrict_the_separate_subscription_discount(self):
        case = json.loads(FIXTURE.read_text())['cases'][0]
        raw = record(
            id=case['name'],
            **{k: case[k] for k in ('source_url', 'observed_at',
                                   'partner', 'program')},
            benefit=case['public_clause'], conditions='', activation='')
        before = copy.deepcopy(raw)
        result = normalize_record(raw, as_of='2026-11-14')
        self.assertEqual(raw, before)
        self.assertEqual(result['raw'], before)
        validate_normalized(result)
        self.assertEqual(
            [[b['kind'], b['value'], b['scope'].get('purchase_stage')]
             for b in result['benefits']], case['expected'])
        for benefit in result['benefits']:
            self.assertEqual(benefit['evidence']['path'], '/benefit')
            self.assertIn(benefit['evidence']['text'], case['public_clause'])

    def test_flattened_source_tiers_keep_only_their_own_purchase_minimum(self):
        for case in json.loads(FIXTURE.read_text())['cases']:
            if 'expected_minimum_links' not in case:
                continue
            with self.subTest(partner=case['partner']):
                raw = record(
                    id=case['name'],
                    **{k: case[k] for k in ('source_url', 'observed_at',
                                           'partner', 'program')},
                    benefit='', conditions=case['public_clause'], activation='')
                before = copy.deepcopy(raw)
                result = normalize_record(raw, as_of='2026-11-14')
                self.assertEqual(raw, before)
                self.assertEqual(result['raw'], before)
                validate_normalized(result)
                conditions = {c['id']: c for c in result['conditions']}
                actual = [
                    [b['kind'], b['value'], sorted(conditions[c]['value']
                     for c in b['condition_ids']
                     if conditions[c]['kind'] == 'minimum_purchase')]
                    for b in result['benefits']]
                self.assertEqual(actual, case['expected_minimum_links'])
                for benefit in result['benefits']:
                    self.assertEqual(benefit['evidence']['path'], '/conditions')
                    self.assertIn(benefit['evidence']['text'], case['public_clause'])

    def test_receipt_signature_is_not_a_subscription_charge(self):
        for case in json.loads(FIXTURE.read_text())['cases']:
            if 'expected_fee_reference' not in case:
                continue
            with self.subTest(partner=case['partner']):
                raw = record(
                    id=case['name'],
                    **{k: case[k] for k in ('source_url', 'observed_at',
                                           'partner', 'program')},
                    benefit='', conditions=case['public_clause'], activation='')
                before = copy.deepcopy(raw)
                result = normalize_record(raw, as_of='2026-11-14')
                self.assertEqual(raw, before)
                self.assertEqual(result['raw'], before)
                validate_normalized(result)
                self.assertEqual(
                    any(c['kind'] == 'fee_reference' for c in result['costs']),
                    case['expected_fee_reference'])

    def test_source_accrual_heading_owns_its_monetary_limit(self):
        for case in json.loads(FIXTURE.read_text())['cases']:
            if 'expected_monetary_cap' not in case:
                continue
            with self.subTest(partner=case['partner']):
                raw = record(
                    id=case['name'],
                    **{k: case[k] for k in ('source_url', 'observed_at',
                                           'partner', 'program')},
                    benefit='', conditions=case['public_clause'], activation='')
                before = copy.deepcopy(raw)
                result = normalize_record(raw, as_of='2026-11-14')
                self.assertEqual(raw, before)
                self.assertEqual(result['raw'], before)
                validate_normalized(result)
                caps = [c for c in result['conditions'] if c['kind'] in
                        ('benefit_cap', 'maximum_amount_reference')]
                self.assertEqual([[c['kind'], c['value'], c['unit']] for c in caps],
                                 [case['expected_monetary_cap']])
                self.assertEqual(caps[0]['evidence'],
                                 {'path': '/conditions', 'text': case['public_clause']})
                if 'expected_cap_basis' in case:
                    self.assertEqual([caps[0]['basis_value'], caps[0]['basis_unit']],
                                     case['expected_cap_basis'])

    def test_repeated_procedure_is_not_a_repeat_purchase_condition(self):
        for case in json.loads(FIXTURE.read_text())['cases']:
            if 'expected_condition_stage' not in case:
                continue
            with self.subTest(partner=case['partner']):
                raw = record(
                    id=case['name'],
                    **{k: case[k] for k in ('source_url', 'observed_at',
                                           'partner', 'program')},
                    benefit='', conditions=case['public_clause'], activation='')
                before = copy.deepcopy(raw)
                result = normalize_record(raw, as_of='2026-11-14')
                self.assertEqual(raw, before)
                self.assertEqual(result['raw'], before)
                validate_normalized(result)
                self.assertTrue(result['conditions'])
                self.assertEqual({c['scope'].get('purchase_stage')
                                  for c in result['conditions']},
                                 {case['expected_condition_stage']})

    def test_excluded_order_descriptions_do_not_become_discount_offers(self):
        for case in json.loads(FIXTURE.read_text())['cases']:
            if 'expected_benefits_outside_exclusion_list' not in case:
                continue
            with self.subTest(partner=case['partner']):
                raw = record(
                    id=case['name'],
                    **{k: case[k] for k in ('source_url', 'observed_at',
                                           'partner', 'program')},
                    benefit='', conditions=case['public_clause'], activation='')
                before = copy.deepcopy(raw)
                result = normalize_record(raw, as_of='2026-11-14')
                self.assertEqual(raw, before)
                self.assertEqual(result['raw'], before)
                validate_normalized(result)
                expected = case['expected_benefits_outside_exclusion_list']
                self.assertEqual([[b['kind'], b['value']] for b in result['benefits']],
                                 expected)
                self.assertEqual([[b['kind'], b['value']]
                                  for b in normalize_rates(case['public_clause'])], expected)
                self.assertIn(case['expected_exclusion_evidence'],
                              [c['evidence']['text'] for c in result['conditions']
                               if c['kind'] == 'exclusion'])

    def test_starred_reward_owns_its_unique_monetary_footnote(self):
        case = next(c for c in json.loads(FIXTURE.read_text())['cases']
                    if 'expected_footnote_cap' in c)
        raw = record(
            id=case['name'],
            **{k: case[k] for k in ('source_url', 'observed_at',
                                   'partner', 'program')},
            benefit='', conditions=case['public_clause'], activation='')
        before = copy.deepcopy(raw)
        result = normalize_record(raw, as_of='2026-11-14')
        self.assertEqual(raw, before)
        self.assertEqual(result['raw'], before)
        validate_normalized(result)
        cap, = [c for c in result['conditions'] if c['kind'] in
                ('benefit_cap', 'maximum_amount_reference')]
        self.assertEqual([cap['kind'], cap['value'], cap['unit']],
                         case['expected_footnote_cap'])
        self.assertEqual([cap['basis_value'], cap['basis_unit']],
                         case['expected_cap_basis'])
        self.assertEqual(cap['evidence'],
                         {'path': '/conditions', 'text': case['public_clause']})
        discount, = result['benefits']
        self.assertEqual([discount['kind'], discount['value']], ['discount', '100'])
        self.assertEqual(discount['evidence']['text'], case['owner_clause'])
        self.assertIn(cap['id'], discount['condition_ids'])


if __name__ == '__main__':
    unittest.main()
