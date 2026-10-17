import json,sys,tempfile,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import merchant_guard_eval as e

class GuardEval(unittest.TestCase):
    def test_frozen_observations_remain_review_only(self):
        p=Path(__file__).resolve().parents[1]/'experiments/merchant_general/block-observed.json'
        r=e.evaluate(p)
        self.assertTrue(r['passed']);self.assertFalse(r['publication_allowed'])
        by={x['id']:x for x in r['results']}
        self.assertIn('audience_missing',by['academia']['guard_reasons'][0])
        self.assertIn('event_not_cardholder_entitlement',by['teplohod']['guard_reasons'][0])
        self.assertEqual(by['elcom']['guard_status'],'review_required')

if __name__=='__main__':unittest.main()
