"""Nominal reward declarations observed in retained source clauses."""
import copy
import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).parents[1]))
from unified_normalization import normalize_record, validate_normalized
from test_unified_normalization import record

CASES = json.loads((Path(__file__).parent / 'fixtures' /
                   'observed_nominal_rewards_20261114.json').read_text())


class ObservedNominalRewardTests(unittest.TestCase):
    def test_source_amounts_keep_their_literal_direction_and_basis(self):
        for case in CASES:
            with self.subTest(case=case['name']):
                details = ({'declared_benefit_type': case['declared_benefit_type']}
                           if case.get('declared_benefit_type') else {})
                source_fields={'benefit':'','conditions':'','activation':''}
                source_fields[case['field']]=case['text']
                raw = record(**source_fields, rates=[],
                             details=details, origin='loyalty_partner_benefits' if details else 'parser_offers',
                             source_url=case['source_url'], benefit_url=case['source_url'])
                before = copy.deepcopy(raw)
                normalized = normalize_record(raw, as_of='2026-11-14')
                self.assertEqual(raw, before)
                self.assertEqual(normalized['raw'], before)
                validate_normalized(normalized)
                actual = normalized['benefits']
                for expected in case['expected']:
                    self.assertTrue(any(all(benefit.get(k) == v for k, v in expected.items())
                                        for benefit in actual), (expected, actual))
                for expected in case.get('expected_conditions', []):
                    self.assertTrue(any(all(term.get(k) == v for k, v in expected.items())
                                        for term in normalized['conditions']), expected)
                for unexpected in case.get('absent', []):
                    self.assertFalse(any(all(term.get(k) == v for k, v in unexpected.items())
                                         for term in actual), (unexpected, actual))
                expected_kinds = {b['kind'] for b in case['expected']}
                self.assertEqual({b['kind'] for b in actual}, expected_kinds)
                if expected_kinds == {'redeem_rewards'}:
                    self.assertFalse(any(b['kind'].startswith('earn') for b in actual))
                if case['name']=='nominal_award_after_explicit_threshold':
                    award=next(b for b in actual if b['value']=='666')
                    self.assertIn('свыше 10 000 рублей',award['evidence']['text'])


if __name__ == '__main__':
    unittest.main()
