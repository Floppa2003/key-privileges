"""Actual native benefit fields keep their discount amount and purchase stage."""
import copy
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from normalized import offer_rates, normalize_rates
from unified_normalization import normalize_record, validate_normalized
from test_unified_normalization import record


CASES = json.loads((Path(__file__).parent /
    'fixtures/reconciled/native_discount_wording_20261114.json').read_text())['cases']


class ObservedNativeDiscountWording(unittest.TestCase):
    def test_no_name_visit_rates_keep_first_and_repeat_from_owned_card(self):
        case = CASES[0]
        raw = record(source_id='parser_offers', program=case['program'],
                     partner=case['partner'], source_url=case['source_url'],
                     benefit_url=None, link_kind='page_block', benefit=case['text'],
                     conditions=case['text'], details=case['details'])
        before = copy.deepcopy(raw)
        result = normalize_record(raw, as_of='2026-11-14')
        validate_normalized(result)
        self.assertEqual(raw, before)
        self.assertEqual(result['raw'], before)
        self.assertEqual([(b['kind'], b['value'], b['unit'], b['scope'].get('purchase_stage'))
                          for b in result['benefits']],
                         [('discount', '20', 'percent', 'first'),
                          ('discount', '10', 'percent', 'repeat')])
        self.assertTrue(all(b['evidence']['path'] == '/benefit' for b in result['benefits']))

    def test_new_no_name_source_and_retained_card_agree_without_global_rate_guess(self):
        case = CASES[0]
        self.assertEqual([(r['kind'], r['value'], r['unit'])
                          for r in offer_rates(case['source_id'], case['text'])],
                         [('discount', '20', 'percent'), ('discount', '10', 'percent')])
        self.assertEqual(normalize_rates(case['text']), [])

    def test_utair_merch_nominal_is_a_ruble_discount(self):
        case = CASES[1]
        raw = record(origin='loyalty_partner_benefits', source_id='loyalty_partner_benefits',
                     privacy='private', kind='legacy_offer', program=case['program'],
                     partner=case['partner'], source_url=case['source_url'], benefit_url=None,
                     benefit=case['text'], conditions='',
                     details={'declared_benefit_type': 'Бесплатные сервисы + скидки'})
        before = copy.deepcopy(raw)
        result = normalize_record(raw, as_of='2026-11-14')
        validate_normalized(result)
        self.assertEqual(raw, before)
        self.assertEqual(result['raw'], before)
        self.assertEqual([(b['kind'], b['value'], b['unit'], b['qualifier'])
                          for b in result['benefits']],
                         [('discount', '5000', 'RUB', 'exact')])
        self.assertEqual([(r['kind'], r['value'], r['unit']) for r in normalize_rates(case['text'])],
                         [('discount', '5000', 'RUB')])


if __name__ == '__main__':
    unittest.main()
