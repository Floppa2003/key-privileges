"""Every retained public Avolta card; no invented wording or currency inference."""
import copy
import json
import unittest
from pathlib import Path

import jsonschema

from normalized import validate_offer
from public_reward_projection import fields, make_record
from test_observed_campaign_periods import retained_without_dates
from unified_normalization import normalize_record


ROOT = Path(__file__).resolve().parents[1]
CASES = json.loads((ROOT / 'tests/fixtures_live/observed-avolta-numeric-rewards-20261114.json').read_text())['cases']
BY_NAME = {case['evidence']['name']: case for case in CASES}
SOURCE = 'club_avolta_public'


def projected(name):
    case = BY_NAME[name]
    row = make_record(SOURCE, case['evidence'], case['observed_at'])
    return normalize_record(retained_without_dates(row), as_of='2026-11-14')


def awards(name):
    return [b for b in projected(name)['benefits'] if b['kind'] in ('earn_points', 'earn_miles')]


class ObservedAvoltaNumericRewards(unittest.TestCase):
    def test_all_twenty_native_numeric_inventories(self):
        expected = {
            'The British Airways Club': [('earn_points', '1')],
            'Finnair Plus': [('earn_points', '1')],
            'Iberia Club': [('earn_points', '1')],
            'KrisFlyer': [('earn_miles', '1')],
            'Отели Raddison': [('earn_points', '3')],
            'Plaza': [('discount', '25')],
            'Hyde': [('discount', '15')],
            'Business Traveller': [('discount', '50')],
            'Direct Ferries': [('discount', '5')],
            'King Power': [('discount', '20'), ('discount', '10'), ('discount', '20'),
                           ('discount', '15'), ('discount', '10'), ('discount', '20'),
                           ('discount', '10'), ('discount', '20'), ('earn_points', '1000')],
            'Viator': [('discount', '12')],
            'Kolet': [('discount', '10')],
            'AVIS': [('discount', '10')],
            'SIXT': [('discount', '15')],
            'SIXT Ride': [('discount', '10')],
            'Autogrill': [('discount', '5'), ('discount', '5')],
            'Dragonpass': [('discount', '25')],
            'Aerotel Hotel Rewards': [('discount', '15')],
            'Global Hotel Alliance': [],
            'Aeroplan®': [('earn_points', '1')],
        }
        self.assertEqual(set(BY_NAME), set(expected))
        for name, wanted in expected.items():
            with self.subTest(name=name):
                self.assertEqual([(b['kind'], b['value']) for b in projected(name)['benefits']
                                  if b['value'] is not None], wanted)

    def test_named_programmes_keep_literal_currency_denominators(self):
        expected = {
            'Finnair Plus': ('earn_points', '1', 'points', '1', 'EUR', 'Avios', 'Finnair Plus'),
            'KrisFlyer': ('earn_miles', '1', 'miles', '2.5', 'USD', 'miles', 'KrisFlyer'),
            'Отели Raddison': ('earn_points', '3', 'points', '1', 'USD', 'Radisson_Rewards_points_not_cash', 'Radisson Rewards'),
            'King Power': ('earn_points', '1000', 'points', '5000', 'THB', 'King_Power_CARAT_not_cash', 'King Power'),
        }
        for name, wanted in expected.items():
            with self.subTest(name=name):
                found = awards(name)
                self.assertEqual(len(found), 1)
                b = found[0]
                self.assertEqual(tuple(b[k] for k in ('kind', 'value', 'unit', 'basis_value', 'basis_unit', 'reward_unit'))
                                 + (b['scope']['reward_program'],), wanted)
                self.assertEqual(b['qualifier'], 'exact')
                self.assertTrue(b['condition_ids'])

    def test_avios_explicit_alternatives_do_not_guess_country_currency_assignment(self):
        for name in ('The British Airways Club', 'Iberia Club'):
            with self.subTest(name=name):
                found = awards(name)
                self.assertEqual(len(found), 1)
                b = found[0]
                self.assertEqual((b['value'], b['unit'], b['reward_unit']), ('1', 'points', 'Avios'))
                self.assertIsNone(b['basis_value'])
                self.assertIsNone(b['basis_unit'])
                self.assertEqual(b['scope']['basis_alternatives'], [
                    {'value': '1', 'unit': 'GBP'}, {'value': '1', 'unit': 'EUR'}])
                self.assertTrue(b['scope']['basis_country_currency_assignment_not_stated'])
                self.assertIn('1 фунт стерлингов / 1 евро', b['scope']['source_clause'])

    def test_aeroplan_unspecified_dollars_do_not_become_us_or_canadian_dollars(self):
        found = awards('Aeroplan®')
        self.assertEqual(len(found), 1)
        b = found[0]
        self.assertEqual((b['value'], b['basis_value'], b['basis_unit'], b['reward_unit']),
                         ('1', '2', 'dollar_unspecified', 'Aeroplan_points_not_cash'))
        self.assertTrue(b['scope']['basis_currency_ambiguous'])
        self.assertIn('Канаде и США', b['scope']['source_clause'])

    def test_savings_wording_and_fixed_foreign_discount_are_not_lost(self):
        for name, value, unit, qualifier in (
                ('Direct Ferries', '5', 'percent', 'exact'),
                ('Viator', '12', 'percent', 'up_to'),
                ('Hyde', '15', 'dollar_unspecified', 'exact')):
            with self.subTest(name=name):
                found = [b for b in projected(name)['benefits'] if b['kind'] == 'discount']
                self.assertEqual([(b['value'], b['unit'], b['qualifier']) for b in found],
                                 [(value, unit, qualifier)])
                if name == 'Hyde':
                    self.assertTrue(found[0]['scope']['currency_ambiguous'])

    def test_every_actual_native_card_preserves_source_and_common_contracts(self):
        self.assertEqual(len(CASES), 20)
        schema = json.loads((ROOT / 'offer.schema.json').read_text())
        for case in CASES:
            with self.subTest(name=case['evidence']['name']):
                before = copy.deepcopy(case['evidence'])
                row = make_record(SOURCE, case['evidence'], case['observed_at'])
                validate_offer(row)
                jsonschema.validate(row, schema)
                raw = retained_without_dates(row)
                saved = copy.deepcopy(raw)
                n = normalize_record(raw, as_of='2026-11-14')
                self.assertEqual(case['evidence'], before)
                self.assertEqual(raw, saved)
                self.assertEqual(n['raw'], saved)
                self.assertFalse(any(b['kind'] == 'miles' for b in n['benefits']))
                for b in n['benefits']:
                    self.assertTrue(b['condition_ids'])
                    self.assertEqual(b['condition_linkage'], 'full_owned_record_rules')
                    if b['evidence']['path'] == '/conditions':
                        self.assertFalse(b['standalone_offer'])

    def test_non_numeric_privileges_and_conflicting_lounge_prices_stay_separate(self):
        for name in ('Kolet', 'Global Hotel Alliance'):
            self.assertTrue(any(b['kind'] == 'partner_privilege' for b in projected(name)['benefits']))
        dragon = projected('Dragonpass')
        self.assertEqual([(b['kind'], b['value']) for b in dragon['benefits']], [('discount', '25')])
        self.assertIn('source_conflict_lounge_admission_price_withheld', dragon['raw']['source_warnings'])


if __name__ == '__main__':
    unittest.main()
