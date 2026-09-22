"""Dates from the owned promotion period, never the crossed-out base rate."""
import sys, unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parents[1]))
from promotion_period import promotion_dates
class PromotionDateTests(unittest.TestCase):
    def test_current_month_context_is_explicit(self):
        got=promotion_dates('Повышение с 01.09 по 30.09','Покупки с кэшбэком (Сентябрь 2026)','2026-09-22')
        self.assertEqual(got,('2026-09-01','2026-09-30'))
    def test_next_month_boundary_same_year(self):
        self.assertEqual(promotion_dates('Повышение 21.09 - 04.10','Xcom (Сентябрь 2026)','2026-09-22'),('2026-09-21','2026-10-04'))
    def test_expired_period_is_not_usable_or_old_rate_revived(self):
        with self.assertRaisesRegex(ValueError,'promotional_period_expired'):
            promotion_dates('до 21.09','Спортмастер (Сентябрь 2026)','2026-09-22')
    def test_stale_title_and_ambiguous_year_rejected(self):
        for title,period in [('X (Август 2026)','до 30.09'),('X','до 30.09'),('X (Январь 2027)','с 21.12 по 04.01')]:
            with self.assertRaises(ValueError):
                promotion_dates(period,title,'2026-09-22')
    def test_invalid_dates(self):
        with self.assertRaises(ValueError):
            promotion_dates('с 31.09 по 40.09','X (Сентябрь 2026)','2026-09-22')
    def test_future_period(self):
        with self.assertRaisesRegex(ValueError,'promotional_period_not_started'):
            promotion_dates('с 24.09 по 30.09','X (Сентябрь 2026)','2026-09-22')
    def test_deadline_is_inclusive(self):
        self.assertEqual(promotion_dates('до 22.09','X (Сентябрь 2026)','2026-09-22'),(None,'2026-09-22'))
