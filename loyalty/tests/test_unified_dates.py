import unittest,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parents[1]))
from unified_normalization import make_input

class LegacyValidityTests(unittest.TestCase):
 def row(self,status):return {'id':'legacy-date','origin':'loyalty_partner_benefits','row':5,'fields':{'Статус':{'value':status}}}
 def test_observation_date_is_not_offer_expiry(self):
  self.assertIsNone(make_input(self.row('Актуальность не подтверждена на 12.09.2026'))['valid_until'])
 def test_partner_since_date_is_not_offer_expiry(self):
  self.assertIsNone(make_input(self.row('Текущий; партнер с 27.02.2026'))['valid_until'])
 def test_explicit_end_still_parsed(self):
  self.assertEqual(make_input(self.row('Текущий до 30.09.2026 по странице партнёра'))['valid_until'],'2026-09-30')
