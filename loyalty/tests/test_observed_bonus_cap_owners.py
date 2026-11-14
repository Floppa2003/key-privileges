"""Complete observed multi-benefit blocks keep each point cap with its owner."""
import copy
import json
from pathlib import Path
import unittest
from unified_normalization import normalize_record,validate_normalized
from test_unified_normalization import record

CASES=json.loads((Path(__file__).parent/'fixtures/observed_bonus_cap_owners_20261114.json').read_text())

class ObservedBonusCapOwners(unittest.TestCase):
    def test_every_observed_cap_links_only_its_own_positive_rate(self):
        for case in CASES:
            with self.subTest(case=case['case'],origin=case['origin']):
                raw=record(origin=case['origin'],source_url=case['source_url'],
                           benefit=case['benefit'],conditions=case['conditions'],activation='',rates=[],
                           details={'declared_benefit_type':case['declared_type']} if case['declared_type'] else {})
                before=copy.deepcopy(raw);n=normalize_record(raw,as_of='2026-11-14')
                self.assertEqual(raw,before);self.assertEqual(n['raw'],before);validate_normalized(n)
                for value,owner_text,rate in case['caps']:
                    caps=[c for c in n['conditions'] if c['kind']=='benefit_cap' and c['value']==value
                          and c['unit']=='points' and owner_text in c['evidence']['text']]
                    self.assertEqual(len(caps),1,(value,owner_text,caps))
                    owners=[b for b in n['benefits'] if caps[0]['id'] in b.get('condition_ids',[])]
                    self.assertEqual(len(owners),1,(value,owner_text,owners))
                    self.assertEqual(owners[0]['value'],rate)
                    self.assertEqual(owners[0]['unit'],'percent')
                    self.assertIn(owner_text,owners[0]['evidence']['text'])
                    self.assertIn(owners[0]['kind'],('earn_points','earn_rewards'))

if __name__=='__main__':unittest.main()
