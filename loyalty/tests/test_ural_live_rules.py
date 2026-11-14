"""Regression from the complete public rules DOM observed on 2026-11-14."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1]))
from tier_sources import ural_tiers


class UralLiveRulesTests(unittest.TestCase):
    def test_any_number_of_flights_spend_alternative_is_not_a_second_count(self):
        raw = (Path(__file__).parent / 'fixtures/reconciled/ural_wings_rules_20261114.html').read_text()
        try:
            rows = ural_tiers(raw, '2026-11-14T00:00:00+00:00')
        except ValueError as exc:
            self.fail(f'The captured public rules were rejected: {exc}')

        # Hand-checked against each tier's own qualification paragraph.
        actual = []
        for row in rows:
            q = row['details']['qualification']
            actual.append((row['details']['tier'], q['registration'], q['flights'],
                           q['spend_rub'], q['operator'], q['window'],
                           q['window_years'], q['required_previous_tier']))
        self.assertEqual(actual, [
            ('Синий', True, None, None, None, None, None, None),
            ('Серебряный', False, 15, '200000', 'OR', 'calendar_year', 1, None),
            ('Золотой', False, 25, '400000', 'OR', 'calendar_year', 1, 'Серебряный'),
        ])
        self.assertIn('любого количества полетов', rows[1]['details']['qualification']['evidence'])
        self.assertIn('любого количества полетов', rows[2]['details']['qualification']['evidence'])


if __name__ == '__main__':
    unittest.main()
