import json,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parents[1]))
from fixtures import fixture
from adapters import mir_detail
NOW='2026-09-12T15:00:00+00:00'
URL='https://vamprivet.ru/promo/transport/ekspress-v-aeroport-s-vygodoy-i-komfortom-1/'
class NullableMirTests(unittest.TestCase):
 def test_missing_payment_badge_is_not_a_failed_offer(self):
  d=json.loads(fixture('mir_detail.json'));d['data']['content']['promoDetail']['promo']['promoAction']['promoBadges']=None
  rs=mir_detail(d,URL,NOW);self.assertEqual(len(rs),1);self.assertEqual(rs[0]['details']['payment_badges'],[])
 def test_null_short_description_preserves_rate_and_conditions(self):
  d=json.loads(fixture('mir_detail.json'));d['data']['content']['promoDetail']['promo']['promoAction']['desc']['text']=None
  r=mir_detail(d,URL,NOW)[0];self.assertIn('5%',r['benefit_text']);self.assertIn('1 500',r['conditions_text'])
