"""Retained typed rates must not also become unscoped lexical awards."""
import copy
import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).parents[1]))
from unified_normalization import normalize_record, validate_normalized
from test_unified_normalization import record

SOURCE = json.loads((Path(__file__).parent / 'fixtures' /
                     'observed_structured_reward_rules_20261114.json').read_text())


class ObservedStructuredRewardTests(unittest.TestCase):
    def common(self, name):
        raw = record(**copy.deepcopy(SOURCE[name]), activation='')
        before = copy.deepcopy(raw)
        result = normalize_record(raw, as_of='2026-11-14')
        validate_normalized(result)
        self.assertEqual(result['raw'], before)
        self.assertEqual(raw, before)
        return result

    def test_domina_singular_owned_formula_keeps_its_purchase_base_once(self):
        result = self.common('domina')
        rewards = [b for b in result['benefits'] if b['kind'] == 'earn_miles']
        self.assertEqual([(b['value'], b['basis_value'], b['basis_unit']) for b in rewards],
                         [('1', '100', 'RUB')])

    def test_primbank_tiers_keep_their_bases_without_duplicate_flat_miles(self):
        result = self.common('primbank')
        rewards = [b for b in result['benefits'] if b['kind'] == 'earn_miles']
        self.assertEqual([(b['value'], b['basis_value'], b['basis_unit']) for b in rewards],
                         [('1', '100', 'RUB'), ('2', '100', 'RUB'), ('3', '100', 'RUB'),
                          ('500', None, None)])
        for reward, bounds in zip(rewards, [('10000', '75000'), ('75000', '150000'), ('150000', '300000')]):
            self.assertEqual((reward['scope']['monthly_spend_from_rub'], reward['scope']['monthly_spend_to_rub']), bounds)
            self.assertIsNone(reward['scope']['lower_inclusive'])
            self.assertIsNone(reward['scope']['upper_inclusive'])
            caps = [c for c in result['conditions'] if c['id'] in reward['condition_ids'] and c['kind'] == 'reward_cap']
            self.assertEqual([(c['value'], c['unit'], c['scope'].get('period')) for c in caps],
                             [('9000', 'miles', 'month')])

    def test_gazprombank_option_rates_and_their_caps_remain_paired(self):
        result = self.common('gazprombank')
        rewards = [b for b in result['benefits'] if b['kind'] == 'earn_miles']
        self.assertEqual([(b['value'], b['basis_value'], b['basis_unit']) for b in rewards],
                         [('1.5', '100', 'RUB'), ('2.5', '100', 'RUB')])
        for reward, amount in zip(rewards, ('3000', '5000')):
            caps = [c for c in result['conditions'] if c['id'] in reward['condition_ids'] and c['kind'] == 'reward_cap']
            self.assertEqual([(c['value'], c['unit']) for c in caps], [(amount, 'miles')])
            self.assertEqual(caps[0]['scope']['option'], reward['scope']['option'])


if __name__ == '__main__':
    unittest.main()
