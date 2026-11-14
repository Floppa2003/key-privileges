"""Literal earned-credit and redemption percentages from retained source clauses."""
import copy
import json
from pathlib import Path
import sys
import unittest
from jsonschema import Draft202012Validator

sys.path.insert(0, str(Path(__file__).parents[1]))
from unified_normalization import normalize_record, validate_normalized
from normalized import make_offer, validate_offer, normalize_rates
from test_dom_card_boundaries import project
from test_unified_normalization import record

CASES = json.loads((Path(__file__).parent / 'fixtures' /
                   'observed_reward_percentages_20261114.json').read_text())


class ObservedRewardPercentageTests(unittest.TestCase):
    def test_fresh_source_offer_retains_existing_rate_schema(self):
        schema=json.loads((Path(__file__).parents[1]/'offer.schema.json').read_text())
        for name,source,program,partner in (
                ('tripster_preposed_point_percent','ural','Крылья','Tripster'),
                ('sravni_explicit_point_percent','mir','Привет!','Сравни.ру')):
            case=next(c for c in CASES if c['name']==name)
            with self.subTest(source=source):
                offer=make_offer(source,'observed-reward-schema',program,partner,
                                 case['text'],case['source_url'],'2026-11-14T00:00:00+00:00')
                validate_offer(offer)
                Draft202012Validator(schema).validate(offer)
                self.assertFalse(any(r['kind']=='points' for r in offer['rates']))
                self.assertFalse(any(r['kind']=='points' for r in normalize_rates(case['text'])))
                common=project(offer)
                self.assertTrue(any(b['kind']=='earn_points' and b['value']==case['expected'][0]['value']
                                    for b in common['benefits']))

    def test_source_percentages_keep_their_literal_direction_and_unit(self):
        for case in CASES:
            with self.subTest(case=case['name']):
                details = ({'declared_benefit_type': case['declared_benefit_type']}
                           if case.get('declared_benefit_type') else {})
                raw = record(benefit=case['text'], conditions='', activation='', rates=[],
                             details=details, origin='loyalty_partner_benefits' if details else 'parser_offers',
                             source_url=case['source_url'], benefit_url=case['source_url'])
                before = copy.deepcopy(raw)
                normalized = normalize_record(raw, as_of='2026-11-14')
                self.assertEqual(raw, before)
                self.assertEqual(normalized['raw'], before)
                validate_normalized(normalized)
                actual = normalized['benefits']
                for expected in case['expected']:
                    self.assertTrue(any(all(benefit.get(k) == v for k, v in expected.items())
                                        for benefit in actual), (expected, actual))
                for expected in case.get('expected_conditions', []):
                    self.assertTrue(any(all(term.get(k) == v for k, v in expected.items())
                                        for term in normalized['conditions']), expected)
                for rate, caps in case.get('cap_links', {}).items():
                    reward=next(b for b in actual if b['kind']=='earn_points' and b['value']==rate)
                    linked=[c['value'] for c in normalized['conditions']
                            if c['kind']=='benefit_cap' and c['id'] in reward['condition_ids']]
                    self.assertEqual(linked,caps)
                expected_kinds = {b['kind'] for b in case['expected']}
                self.assertEqual({b['kind'] for b in actual}, expected_kinds)
                if expected_kinds == {'redeem_rewards'}:
                    self.assertFalse(any(b['kind'].startswith('earn') for b in actual))
                if case['name'] == 'unisim_balance_credit_and_denial':
                    self.assertTrue(all('не начисляются' not in b['evidence']['text'] for b in actual))
                    self.assertTrue(all(b['reward_unit'] is None for b in actual))


if __name__ == '__main__':
    unittest.main()
