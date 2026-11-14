"""A sole public EKP prize ends with its explicitly owned redemption code."""
import copy
import json
import unittest
from pathlib import Path

from catalogue_view import record_row
from ekp_catalog import make_record
from test_observed_campaign_periods import AS_OF, retained_without_dates
from unified_normalization import normalize_record


CAPTURE = json.loads(Path(__file__).with_name('fixtures_live').joinpath(
    'observed-ekp-prize-expiry-20261114.json').read_text())
ENDS = {
    '3434': '2026-11-30', '3416': '2026-12-31', '3419': '2026-11-30',
    '3421': '2026-12-30', '3420': '2026-11-30', '3432': '2026-12-31',
    '3433': '2026-11-30', '3435': '2026-11-04', '3413': '2026-12-31',
    '3436': '2026-11-30', '3438': '2026-11-30', '3422': '2026-12-30',
    '3414': '2026-12-31', '3439': '2026-11-30', '3411': '2026-09-30',
    '3442': '2026-11-30', '3449': '2026-11-30', '3441': '2026-11-04',
}


def source_record(source):
    return make_record(source['row'], source['observed_at'], request=source['request'],
                       response_sha=source['response_sha'], observed_total=source['observed_total'],
                       completed_at=source['completed_at'])


class ObservedEKPPrizeExpiry(unittest.TestCase):
    def test_native_sole_prize_redemption_deadlines_own_the_offer_end(self):
        self.assertEqual({s['row']['id'] for s in CAPTURE['sole_prize']}, set(ENDS))
        for source in CAPTURE['sole_prize']:
            with self.subTest(partner_id=source['row']['id']):
                row = source_record(source)
                self.assertEqual((row['valid_from'], row['valid_until']),
                                 (None, ENDS[source['row']['id']]))

    def test_retained_prize_deadlines_reach_validity_and_expired_reader_filter(self):
        for source in CAPTURE['sole_prize']:
            with self.subTest(partner_id=source['row']['id']):
                raw = retained_without_dates(source_record(source))
                before = copy.deepcopy(raw)
                n = normalize_record(raw, as_of=AS_OF)
                end = ENDS[source['row']['id']]
                expected_status = 'expired' if end < AS_OF else 'within_stated_period'
                self.assertEqual(n['validity'], {
                    'from': None, 'until': end, 'as_of': AS_OF, 'status': expected_status,
                })
                if expected_status == 'expired':
                    self.assertEqual(record_row(n, AS_OF), (None, 'истёкший срок'))
                self.assertEqual(raw, before)
                self.assertEqual(n['raw'], before)

    def test_distinct_acquisition_and_redemption_windows_remain_unresolved(self):
        for source in CAPTURE['separate_acquisition_controls']:
            with self.subTest(partner_id=source['row']['id']):
                row = source_record(source)
                self.assertEqual((row['valid_from'], row['valid_until']), (None, None))
                self.assertTrue(row['redemption_text'].startswith('До '))
                self.assertIn('Промокод действует до ', row['redemption_text'])
                raw = retained_without_dates(row)
                n = normalize_record(raw, as_of=AS_OF)
                self.assertEqual(n['validity']['status'], 'unknown')
                self.assertIsNone(n['validity']['until'])


if __name__ == '__main__':
    unittest.main()
