"""Citydrive's uniquely attached native offer footnote owns its expiry."""
import html
import json
import unittest
from pathlib import Path

from coral_catalog import detail
from test_observed_campaign_periods import AS_OF, retained_without_dates
from unified_normalization import normalize_record


CAPTURE = json.loads(Path(__file__).with_name('fixtures_live').joinpath(
    'observed-citydrive-expiry-20261114.json').read_text())


def source_record():
    body = ('<section><div class="order-lg-2"><h1>' + html.escape(CAPTURE['title']) + '</h1>'
            + ''.join('<p>' + html.escape(line) + '</p>' for line in CAPTURE['excerpt'].splitlines())
            + '</div><div class="product-purchase-box referal"></div></section>')
    return detail(body, 'coral', {'url': CAPTURE['url'], 'category': CAPTURE['category']},
                  CAPTURE['observed_at'], {})


class ObservedCitydriveExpiry(unittest.TestCase):
    def test_native_attached_discount_footnote_sets_the_offer_end(self):
        row = source_record()
        self.assertEqual((row['valid_from'], row['valid_until']), (None, '2026-12-31'))
        self.assertIn('Действует до 31.12.2026 г. при аренде по поминутному и Фикс тарифу.',
                      row['conditions_text'])

    def test_retained_body_keeps_owned_expiry_without_changing_raw(self):
        raw = retained_without_dates(source_record())
        n = normalize_record(raw, as_of=AS_OF)
        self.assertEqual(n['validity'], {'from': None, 'until': '2026-12-31',
                                        'as_of': AS_OF, 'status': 'within_stated_period'})
        self.assertEqual(n['raw'], raw)


if __name__ == '__main__':
    unittest.main()
