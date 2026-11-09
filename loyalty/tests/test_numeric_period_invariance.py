"""A changed explicit promotion length is not an ambiguous inferred year."""
import sys
import unittest
from pathlib import Path

from bs4 import BeautifulSoup

sys.path.insert(0, str(Path(__file__).parents[1]))
from promotion_period import promotion_dates
from test_public_reward_sources import common, html, kuper


class NumericPromotionPeriods(unittest.TestCase):
    def accepted(self, parse, *args):
        try:
            return parse(*args)
        except ValueError as exc:
            self.fail("A complete valid interval was rejected: " + str(exc))

    def test_explicit_long_periods_preserve_source_dates(self):
        for end, expected in (("31.12.2026", "2026-12-31"),
                              ("31.01.2027", "2027-01-31")):
            with self.subTest(end=end):
                document = BeautifulSoup(html("backit-kuper.html"), "html.parser")
                period = "Повышение с 01.09.2026 по " + end
                label = document.new_tag("p", attrs={"class": "info"})
                label.string = period
                document.select_one(".shop-rates").append(label)
                row = self.accepted(kuper, str(document))
                self.assertEqual((row["valid_from"], row["valid_until"]),
                                 ("2026-09-01", expected))
                self.assertIn(period, row["conditions_text"])
                normalized = common(row)
                self.assertEqual(normalized["validity"]["from"], "2026-09-01")
                self.assertEqual(normalized["validity"]["until"], expected)
                self.assertEqual([b["value"] for b in normalized["benefits"]],
                                 ["388", "24", "388"])

    def test_explicit_93_and_94_days_have_the_same_semantics(self):
        for end, expected in (("03.12.2026", "2026-12-03"),
                              ("04.12.2026", "2026-12-04")):
            with self.subTest(end=end):
                self.assertEqual(
                    self.accepted(promotion_dates, "с 01.09.2026 по " + end, "", "2026-09-22"),
                    ("2026-09-01", expected))

    def test_missing_years_keep_the_conservative_length_bound(self):
        for period in ("с 01.09 по 31.12", "с 01.09.2026 по 31.12",
                       "с 01.09 по 31.12.2026", "с 01.09 по 31.01.2027"):
            with self.subTest(period=period):
                with self.assertRaisesRegex(ValueError, "requires_current_confirmation"):
                    promotion_dates(period, "Купер (сентябрь 2026)", "2026-09-22")

    def test_short_inferred_period_still_requires_current_page_month(self):
        self.assertEqual(promotion_dates("с 01.09 по 30.09", "Купер (сентябрь 2026)",
                                         "2026-09-22"), ("2026-09-01", "2026-09-30"))
        with self.assertRaisesRegex(ValueError, "requires_current_confirmation"):
            promotion_dates("с 01.09 по 30.09", "Купер (август 2026)", "2026-09-22")

    def test_explicit_period_must_include_observation(self):
        for period, reason in (("с 01.01.2026 по 31.08.2026", "promotional_period_expired"),
                               ("с 01.10.2026 по 31.03.2027", "promotional_period_not_started")):
            with self.subTest(period=period):
                with self.assertRaisesRegex(ValueError, reason):
                    promotion_dates(period, "", "2026-09-22")

    def test_invalid_or_reversed_dates_do_not_become_periods(self):
        for period in ("с 01.10.2026 по 01.09.2026", "с 31.09.2026 по 31.01.2027",
                       "с 01.09.2026 по 31.02.2027", "с 01.09.2026 по 31.12.20261"):
            with self.subTest(period=period), self.assertRaises(ValueError):
                promotion_dates(period, "", "2026-09-22")

    def test_explicit_end_day_is_inclusive(self):
        self.assertEqual(self.accepted(promotion_dates, "с 01.01.2026 по 22.09.2026", "", "2026-09-22"),
                         ("2026-01-01", "2026-09-22"))
        with self.assertRaisesRegex(ValueError, "promotional_period_expired"):
            promotion_dates("с 01.01.2026 по 22.09.2026", "", "2026-09-23")
