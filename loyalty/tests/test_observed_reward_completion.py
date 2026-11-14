"""Verbatim retained source clauses: nominal limits, exchange and gifted bonuses."""
import copy
import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).parents[1]))
from normalized import normalize_rates
from unified_normalization import normalize_record, validate_normalized
from test_unified_normalization import record


SOURCE = json.loads((Path(__file__).parent / 'fixtures' /
                     'observed_reward_roles_20261114.json').read_text())


class ObservedRewardCompletionTests(unittest.TestCase):
    def common(self, source, *, rates=(), origin='parser_offers'):
        raw = record(benefit=source['text'], conditions='', activation='',
                     rates=list(rates), details={}, origin=origin,
                     source_url=source['source_url'], benefit_url=source['source_url'])
        before = copy.deepcopy(raw)
        result = normalize_record(raw, as_of='2026-11-14')
        self.assertEqual(raw, before)
        self.assertEqual(result['raw'], before)
        validate_normalized(result)
        return result

    def test_utair_redemption_equations_are_not_mileage_awards(self):
        source = SOURCE['utair_redemption']
        self.assertEqual(normalize_rates(source['text']), [])
        result = self.common(source)
        self.assertEqual(result['benefits'], [])
        self.assertIn('1 миля = 1 рубль', result['raw']['benefit'])

    def test_vkusomania_exchange_minimum_is_not_mileage_award(self):
        source = SOURCE['vkusomania_exchange']
        self.assertEqual(normalize_rates(source['text']), [])
        result = self.common(source, origin='loyalty_partner_benefits')
        self.assertEqual(result['benefits'], [])
        self.assertIn('минимально 1 200 бонусов для обмена бонусов и 100 миль для обмена миль',
                      result['raw']['benefit'])

    def test_coral_gifted_bonus_awards_keep_their_literal_units_and_bounds(self):
        for source in SOURCE['coral_awards']:
            with self.subTest(url=source['source_url'], text=source['text']):
                result = self.common(source)
                self.assertEqual([(b['kind'], b['value'], b['unit'], b['reward_unit'], b['qualifier'])
                                  for b in result['benefits']],
                                 [('earn_points', source['value'], 'points', 'points', source['qualifier'])])
                self.assertEqual(result['benefits'][0]['evidence']['text'], source['text'])

    def test_rzd_quoted_prior_campaign_is_not_a_second_bonus_award(self):
        result = self.common(SOURCE['rzd_campaign_reference'])
        self.assertEqual([(b['kind'], b['value']) for b in result['benefits']],
                         [('earn_points', '3800')])

    def test_otello_caps_are_linked_to_their_own_tiered_percentages(self):
        source = SOURCE['otello_caps']
        self.assertEqual([(r['kind'], r['value'], r['unit']) for r in normalize_rates(source['text'])],
                         [('miles', '10', 'percent'), ('miles', '8', 'percent')])
        result = self.common(source)
        self.assertEqual([(b['kind'], b['value'], b['unit']) for b in result['benefits']],
                         [('earn_miles', '10', 'percent'), ('earn_miles', '8', 'percent')])
        conditions = {c['id']: c for c in result['conditions']}
        for benefit, amount, tiers in zip(result['benefits'], ('3000', '2000'),
                                         (['Silver', 'Gold', 'Platinum'], ['Start', 'Basic', 'Bronze'])):
            self.assertEqual(benefit['scope']['tiers'], tiers)
            cap, = [conditions[key] for key in benefit['condition_ids']
                    if conditions[key]['kind'] == 'benefit_cap']
            self.assertEqual((cap['value'], cap['unit'], cap['qualifier'], cap['basis_value'], cap['basis_unit']),
                             (amount, 'miles', 'up_to', '1', 'order'))
            self.assertEqual(cap['scope']['tiers'], tiers)
            self.assertIn('Лимит начисления за один заказ', cap['evidence']['text'])


if __name__ == '__main__':
    unittest.main()
