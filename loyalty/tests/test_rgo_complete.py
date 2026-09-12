"""Real public DOM fragments captured in run 34714132335, not invented selectors."""
from pathlib import Path
import sys,unittest
sys.path.insert(0,str(Path(__file__).parents[1]))
from adapters import extract

class RgoCompleteTests(unittest.TestCase):
    def offer(self,slug):
        raw=(Path(__file__).with_name('fixtures_live')/f'rgo-{slug}.html').read_text()
        return extract('rgo',raw,f'https://rgo.ru/membership/loyalty-program/{slug}/','2026-09-12T19:00:00+00:00')[0]
    def test_expiry_and_exclusions_come_from_actual_inner_block(self):
        r=self.offer('etnomir')
        self.assertIn('31.12.2025',r['conditions_text'])
        self.assertIn('не суммируются',r['conditions_text'])
        self.assertIn('Центральная Азия',r['conditions_text'])
        self.assertEqual(r['valid_until'],'2025-12-31')
        self.assertEqual(r['validity_status'],'expired_by_published_end')
    def test_debrett_actual_ten_percent_not_only_restaurant_description(self):
        r=self.offer('restoran-debrett')
        self.assertTrue(any(x['kind']=='discount' and x['value']=='10' for x in r['rates']))
        self.assertIn('Предъявите членский билет',r['conditions_text'])
    def test_rzd_bonus_keeps_uplift_and_claiming_instructions(self):
        r=self.offer('programma-rzhd-bonus')
        self.assertIn('на 10% больше баллов',r['conditions_text'])
        self.assertIn('номер членского билета и номер РЖД Бонус',r['conditions_text'])
    def test_current_paddock_no_longer_publishes_old_karting_gift(self):
        r=self.offer('gostinitsa-paddok-3-zvezdy')
        self.assertIn('бронирование любого номера',r['conditions_text'])
        self.assertNotIn('минут в подарок',r['conditions_text'])
