"""The source's complete year belongs to both abbreviated campaign bounds."""
import html
import json
import unittest
from pathlib import Path
from urllib.parse import urlsplit

from adapters import extract
from test_observed_campaign_periods import AS_OF, retained_without_dates
from unified_normalization import normalize_record


CAPTURE = json.loads(Path(__file__).with_name('fixtures_live').joinpath(
    'observed-promomiles-periods-20261114.json').read_text())
WANT = {
    '/act/june2026': ('2026-06-01', '2026-07-31'),
    '/act/april2026': ('2026-04-01', '2026-04-30'),
    '/act/march2026': ('2026-03-01', '2026-03-31'),
    '/act/december2025': ('2025-12-01', '2025-12-31'),
    '/act/oct26': ('2026-10-01', '2026-11-30'),
}


def campaign_record(source):
    path = urlsplit(source['detail_url']).path
    card = ('<a class="promotion-mini" href="' + path + '">'
            '<div class="promotion-mini__title">' + html.escape(source['title']) + '</div>'
            '<div class="promotion-mini__text">' + html.escape(source['benefit']) + '</div>'
            '<div class="promotion-mini__info">' + html.escape(source['conditions']) + '</div></a>')
    return extract('promomiles', card, 'https://promomiles.aeroflot.ru/', source['observed_at'])[0]


class ObservedPromoMilesPeriods(unittest.TestCase):
    def test_native_campaign_cards_have_both_explicit_calendar_bounds(self):
        for source in CAPTURE:
            with self.subTest(url=source['detail_url']):
                row = campaign_record(source)
                self.assertEqual((row['valid_from'], row['valid_until']),
                                 WANT[urlsplit(source['detail_url']).path])
                self.assertEqual(row['conditions_text'], source['conditions'])

    def test_retained_campaign_cards_gain_period_without_changing_evidence(self):
        for source in CAPTURE:
            with self.subTest(url=source['detail_url']):
                raw = retained_without_dates(campaign_record(source))
                n = normalize_record(raw, as_of=AS_OF)
                self.assertEqual((n['validity']['from'], n['validity']['until']),
                                 WANT[urlsplit(source['detail_url']).path])
                self.assertEqual(n['raw'], raw)


if __name__ == '__main__':
    unittest.main()
