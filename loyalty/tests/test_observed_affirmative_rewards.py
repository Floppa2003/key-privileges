"""Affirmative awards from literal retained public source clauses."""
import copy
import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).parents[1]))
from unified_normalization import normalize_record, validate_normalized
from test_unified_normalization import record


SOURCE = json.loads((Path(__file__).parent / 'fixtures' /
                     'observed_affirmative_reward_amounts_20261114.json').read_text())


class ObservedAffirmativeRewardTests(unittest.TestCase):
    def test_literal_welcome_premium_gift_and_wrapped_awards_keep_reward_units(self):
        for source in [s for s in SOURCE if s['value'] is not None]:
            with self.subTest(url=source['source_url'], text=source['text']):
                raw = record(benefit=source['text'], conditions='', activation='',
                             source_url=source['source_url'], details={})
                before = copy.deepcopy(raw)
                result = normalize_record(raw, as_of='2026-11-14')
                validate_normalized(result)
                self.assertEqual(raw, before)
                self.assertEqual(result['raw'], before)
                rewards = [b for b in result['benefits'] if b['kind'] in ('earn_points', 'earn_miles')]
                self.assertEqual([(b['value'], b['unit'], b['reward_unit'], b['qualifier']) for b in rewards],
                                 [(source['value'], source['unit'], source['unit'], source['qualifier'])])
                self.assertIn(rewards[0]['evidence']['text'], source['text'])

    def test_accrual_lifetime_heading_does_not_award_the_next_conversion_equation(self):
        for source in [s for s in SOURCE if s['value'] is None]:
            raw = record(benefit=source['text'], conditions='', activation='',
                         source_url=source['source_url'], details={})
            result = normalize_record(raw, as_of='2026-11-14')
            self.assertEqual(result['benefits'], [])
            self.assertEqual(result['raw']['benefit'], source['text'])


if __name__ == '__main__':
    unittest.main()
