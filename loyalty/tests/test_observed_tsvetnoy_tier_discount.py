"""An actual tier's atelier discount is not merely an untyped privilege."""
import copy
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from public_reward_projection import make_record
from tsvetnoy_source import source_fields
from test_observed_campaign_periods import retained_without_dates
from unified_normalization import normalize_record


CASE = json.loads((Path(__file__).parent /
    'fixtures_live/observed-tsvetnoy-tier-discount-20261114.json').read_text())


class ObservedTsvetnoyTierDiscount(unittest.TestCase):
    def test_atelier_rate_is_owned_by_start_tier_without_pricing_status_progress(self):
        before = copy.deepcopy(CASE['evidence'])
        fields = source_fields(CASE['evidence'])
        row = make_record(CASE['source'], CASE['evidence'], CASE['observed_at'])
        result = normalize_record(retained_without_dates(row), as_of='2026-11-14')
        self.assertEqual(CASE['evidence'], before)
        discounts = [b for b in result['benefits'] if b['kind'] == 'discount']
        self.assertEqual([(b['value'], b['unit'], b['scope']['member_tier']) for b in discounts],
                         [('10', 'percent', 'Старт')])
        self.assertFalse(discounts[0]['standalone_offer'])
        self.assertIn('ателье NIKKO', discounts[0]['scope']['source_clause'])
        self.assertTrue(all(b['value'] is None for b in result['benefits'] if b['kind'] != 'discount'))
        self.assertEqual(row['benefit_text'], fields['benefit'])
        self.assertIn('Двойные накопления', result['raw']['benefit'])
        self.assertNotIn('earn_points', [b['kind'] for b in result['benefits']])


if __name__ == '__main__':
    unittest.main()
