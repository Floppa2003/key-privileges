"""Observed exchange direction and purchase denominators remain part of rewards."""
import copy
import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).parents[1]))
from normalized import normalize_rates
from unified_normalization import normalize_record, validate_normalized
from test_unified_normalization import record

HERE = Path(__file__).parent / 'fixtures'
FORMULAS = json.loads((HERE / 'observed_reward_formulas_20261114.json').read_text())
WRAPPED = json.loads((HERE / 'observed_wrapped_reward_formulas_20261114.json').read_text())


class ObservedRewardFormulaTests(unittest.TestCase):
    def common(self, source):
        raw = record(benefit=source['text'], conditions='', activation='',
                     source_url=source['source_url'], details={})
        before = copy.deepcopy(raw)
        result = normalize_record(raw, as_of='2026-11-14')
        self.assertEqual(raw, before)
        self.assertEqual(result['raw'], before)
        validate_normalized(result)
        return result

    def test_real_reward_formulas_preserve_their_denominators(self):
        for source in FORMULAS:
            with self.subTest(url=source['source_url'], text=source['text']):
                result = self.common(source)
                rewards = [b for b in result['benefits']
                           if (b['kind'], b['value'], b['unit']) ==
                           (source['kind'], source['value'], source['unit'])]
                self.assertEqual(len(rewards), 1)
                reward = rewards[0]
                self.assertEqual((reward['basis_value'], reward['basis_unit']),
                                 (source['basis_value'], source['basis_unit']))
                for key, value in source['scope'].items():
                    self.assertEqual(reward['scope'].get(key), value)
                self.assertFalse(any(b['value'] == source['basis_value'] and
                                     b['unit'] == source['basis_unit'] and
                                     b['id'] != reward['id'] for b in result['benefits']))
                self.assertIn(reward['evidence']['text'], source['text'])

    def test_mistral_per_day_rate_is_a_bounded_award_not_a_daily_payout_cap(self):
        source = next(s for s in FORMULAS if s['value'] == '800')
        result = self.common(source)
        reward, = result['benefits']
        self.assertEqual((reward['value'], reward['qualifier'], reward['basis_value'], reward['basis_unit']),
                         ('800', 'up_to', '1', 'day'))
        self.assertFalse(any(c['kind'] == 'benefit_cap' for c in result['conditions']))

    def test_rzd_native_soft_wrap_keeps_both_owned_purchase_formulas(self):
        for source in WRAPPED:
            with self.subTest(url=source['source_url']):
                result = self.common(source)
                self.assertEqual([(b['kind'], b['value'], b['basis_value'], b['basis_unit'],
                                   b['scope'].get('purchase_stage')) for b in result['benefits']],
                                 [('earn_points', '1', source['first_basis'], 'RUB', 'first'),
                                  ('earn_points', '1', source['repeat_basis'], 'RUB', 'repeat')])
                for reward in result['benefits']:
                    self.assertIn(reward['evidence']['text'], source['text'])


if __name__ == '__main__':
    unittest.main()
