"""Captured public HSE clauses keep each rate's own purchase-stage restriction."""
import copy
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from unified_normalization import normalize_record, validate_normalized
from test_unified_normalization import record


FIXTURE = Path(__file__).parent / 'fixtures/reconciled/hse_purchase_stages_20261114.json'


class HSENativePurchaseStages(unittest.TestCase):
    def test_captured_rates_do_not_inherit_the_sibling_purchase_stage(self):
        for case in json.loads(FIXTURE.read_text())['cases']:
            with self.subTest(partner=case['partner']):
                literal = case['public_clause']
                raw = record(
                    id=case['anchor'],
                    program=case['program'], partner=case['partner'],
                    title=case['partner'], source_url=case['source_url'],
                    observed_at=case['observed_at'], benefit=literal,
                    conditions=literal, activation='', codes=[], rates=[],
                    details={
                        'scope': 'only_cards_in_current_public_partner_inventory',
                        'public_catalog_block': {'anchor': case['anchor'], 'body': literal},
                    })
                before = copy.deepcopy(raw)
                result = normalize_record(raw, as_of='2026-11-14')
                self.assertEqual(raw, before)
                self.assertEqual(result['raw'], before)
                validate_normalized(result)
                self.assertEqual(
                    [[b['value'], b['scope'].get('purchase_stage')]
                     for b in result['benefits']], case['expected'])
                rule, = result['conditions']
                self.assertEqual(rule['kind'], 'owned_partner_rules')
                self.assertEqual(rule['evidence'], {'path': '/conditions', 'text': literal})
                for benefit in result['benefits']:
                    self.assertEqual(benefit['condition_ids'], [rule['id']])
                    self.assertEqual(benefit['condition_linkage'], 'full_owned_record_rules')
                    self.assertTrue(benefit['remaining_record_rules_require_review'])
                    self.assertTrue(benefit['scope']['programme_membership_not_verified'])
                    self.assertEqual(benefit['scope']['anchor'], case['anchor'])
                    self.assertEqual(benefit['evidence']['path'], '/benefit')
                    self.assertIn(benefit['evidence']['text'], literal)


if __name__ == '__main__':
    unittest.main()
