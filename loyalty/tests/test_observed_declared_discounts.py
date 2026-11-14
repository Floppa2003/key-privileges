"""Retained source labels and literal price reductions keep their own roles."""
import copy
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from normalized import normalize_rates
from unified_normalization import normalize_record, validate_normalized
from test_unified_normalization import record


CASES = json.loads((Path(__file__).parent /
    'fixtures/reconciled/declared_discounts_20261114.json').read_text())['cases']


class ObservedDeclaredDiscounts(unittest.TestCase):
    def test_owned_discount_fields_and_actual_price_reductions(self):
        for index, case in enumerate(CASES):
            with self.subTest(case=index):
                details = ({'declared_benefit_type': case['declared_type']}
                           if case['declared_type'] else {})
                raw = record(origin=case['origin'], source_id=case['origin'],
                             program=None, partner=None, title='',
                             source_url=case.get('source_url'), benefit_url=None,
                             benefit=case['text'], conditions='', activation='',
                             privacy='public' if case['origin'] == 'parser_offers' else 'private',
                             kind='partner_offer' if case['origin'] == 'parser_offers' else 'legacy_offer',
                             details=details)
                before = copy.deepcopy(raw)
                n = normalize_record(raw, as_of='2026-11-14')
                self.assertEqual(raw, before)
                self.assertEqual(n['raw'], before)
                validate_normalized(n)
                discounts = [b for b in n['benefits'] if b['kind'] == 'discount']
                self.assertEqual([b['value'] for b in discounts], case['expected_discounts'])
                self.assertTrue(all(b['qualifier'] == case['expected_qualifier'] for b in discounts))
                self.assertTrue(all(b['evidence']['path'] == '/benefit' for b in discounts))

    def test_public_source_price_reduction_phrases_work_before_storage(self):
        for case in CASES:
            if case['origin'] != 'parser_offers':
                continue
            with self.subTest(source=case['source_url']):
                rates = normalize_rates(case['text'])
                self.assertEqual([r['value'] for r in rates if r['kind'] == 'discount'],
                                 case['expected_discounts'])


if __name__ == '__main__':
    unittest.main()
