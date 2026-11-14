"""Actual legacy privilege components keep owned discounts and named tiers."""
import copy
import json
from pathlib import Path
import unittest

from unified_normalization import normalize_record, validate_normalized
from test_unified_normalization import record

CASES=json.loads((Path(__file__).parent/'fixtures/observed_owned_privilege_discounts_20261114.json').read_text())

class ObservedOwnedPrivilegeDiscounts(unittest.TestCase):
    def test_component_discount_types_and_named_tiers(self):
        for case in CASES:
            with self.subTest(case=case['case']):
                raw=record(origin='loyalty_partner_benefits',kind='legacy_offer',
                           benefit=case['benefit'],conditions=case['conditions'],activation='',rates=[],
                           source_url=case['source_url'],
                           details={'declared_benefit_type':case['declared_type']})
                before=copy.deepcopy(raw)
                result=normalize_record(raw,as_of='2026-11-14')
                self.assertEqual(raw,before);self.assertEqual(result['raw'],before)
                validate_normalized(result)
                discounts=[b for b in result['benefits'] if b['kind']=='discount']
                if 'expected_values' in case:self.assertEqual([b['value'] for b in discounts],case['expected_values'])
                if 'expected_tiers' in case:
                    self.assertEqual([b['scope'].get('member_tier') for b in discounts],case['expected_tiers'])
                if case['case']=='museum_extended_comparator':
                    self.assertTrue(all(b['evidence']['path']=='/benefit' for b in discounts))
                if case['case'] in ('status_gold_partner','status_platinum_partner'):
                    partner_discount=next(b for b in discounts if b['value'] in ('10','20'))
                    self.assertEqual(partner_discount['evidence']['path'],'/conditions')
                    self.assertIn('Городских парильнях',partner_discount['evidence']['text'])
                if case['case']=='hotel_special_tariff_and_points':
                    self.assertEqual(discounts[0]['qualifier'],'up_to')
                    self.assertEqual([(b['value'],b['reward_unit']) for b in result['benefits'] if b['kind']=='redeem_rewards'],[('100','points')])
                if case['case']=='ticket_discount_and_staged_points':
                    points=[b for b in result['benefits'] if b['kind']=='earn_points']
                    self.assertEqual([b['value'] for b in points],['10','5'])
                    self.assertTrue(all(b['kind']!='cashback' for b in result['benefits']))
                    for value,cap in [('10','500'),('5','250')]:
                        reward=next(b for b in points if b['value']==value)
                        self.assertEqual([c['value'] for c in result['conditions'] if c['kind']=='benefit_cap' and c['id'] in reward['condition_ids']],[cap])

if __name__=='__main__':unittest.main()
