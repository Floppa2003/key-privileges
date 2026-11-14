"""Actual public coupon labels and redemption channels keep their source roles."""
import copy
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from promo_codes import extract_promocodes
from test_unified_normalization import record
from unified_normalization import normalize_record, validate_normalized


CASES = json.loads((Path(__file__).parent / 'fixtures/reconciled/coupon_completion_20261114.json').read_text())['cases']


class NativeCouponCompletion(unittest.TestCase):
    def test_fresh_public_clauses_preserve_literals_and_actual_issuance(self):
        for case in CASES:
            with self.subTest(case=case['name']):
                result = extract_promocodes(case['public_clause'])
                self.assertEqual(result['codes'], case['expected_codes'])
                self.assertEqual(sorted({d['method'] for d in result['delivery']}),
                                 sorted(case['expected_delivery']))

    def test_retained_public_clauses_remove_false_delivery_without_changing_raw(self):
        for case in CASES:
            with self.subTest(case=case['name']):
                fields = {'benefit': '', 'conditions': '', 'activation': ''}
                fields[case['field']] = case['public_clause']
                raw = record(id=case['name'],
                             source_url=case['source_url'], observed_at=case['observed_at'],
                             program=case['program'], partner=case['partner'],
                             kind=case['kind'], codes=[], rates=[], **fields,
                             details={'promo_code_delivery': [
                                 {'kind': 'delivery_reference', 'method': method,
                                  'evidence': case['public_clause']}
                                 for method in case['retained_delivery']]})
                before = copy.deepcopy(raw)
                result = normalize_record(raw, as_of='2026-11-14')
                self.assertEqual(raw, before)
                self.assertEqual(result['raw'], before)
                validate_normalized(result)
                self.assertEqual(sorted({c['value'] for c in result['codes'] if c['value'] is not None}),
                                 sorted(case['expected_codes']))
                self.assertEqual(sorted({c['delivery'] for c in result['codes'] if c['value'] is None}),
                                 sorted(case['expected_delivery']))


if __name__ == '__main__':
    unittest.main()
