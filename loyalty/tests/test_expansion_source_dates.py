"""Source timestamps must be valid before their calendar date reaches the reader."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1]))
from expansion_common import iso
from sheets_normalized import SCHEMAS, prepare
from test_catalogue_expansion import OLD, bundle, coupon, x5
from test_lifecycle_pipeline import reader


def project_to_reader(source, evidence):
    payload = bundle(source, [evidence])
    row = prepare(payload)['parser_offers'][0]
    view, reason = reader(row, OLD[:10])
    return payload['records'][0], row, view, reason


class ExpansionSourceDateTests(unittest.TestCase):
    def test_existing_x5_and_gorod_timestamp_fixtures_reach_the_reader(self):
        for source, evidence in [('x5_partners_public', x5()),
                                 ('gorod_public', coupon())]:
            with self.subTest(source=source):
                record, row, view, reason = project_to_reader(source, evidence)
                self.assertEqual(record['valid_until'], '2026-12-31')
                self.assertEqual(row[SCHEMAS['parser_offers'].index('Окончание')], '2026-12-31')
                self.assertIsNotNone(view)
                self.assertIsNone(reason)

    def test_supported_complete_dates_keep_the_source_calendar_date(self):
        dates = [
            '2026-12-31',
            '31.12.2026',
            '2026-12-31 23:59:59',
            '2026-12-31T23:59:59',
            '2026-12-31T23:59:59.123456789',
            '2026-12-31T23:59:59,5',
            '2026-12-31T23:59:59Z',
            '2026-12-31T23:59:59.123Z',
            '2026-12-31T23:59:59.5+03:30',
            '2026-12-31 23:59:59+00:00',
            # Converting either of these to UTC would change its calendar date.
            '2026-12-31T00:15:00+14:00',
            '2026-12-31T23:45:00-12:00',
        ]
        for value in dates:
            for source, evidence in [('x5_partners_public', x5()),
                                     ('gorod_public', coupon())]:
                with self.subTest(source=source, value=value):
                    if source == 'x5_partners_public':
                        evidence['card']['endDate'] = value
                    else:
                        evidence['data']['endAt'] = value
                        evidence['data']['couponEndAt'] = value
                    record, row, view, reason = project_to_reader(source, evidence)
                    self.assertEqual(record['valid_until'], '2026-12-31')
                    self.assertEqual(row[SCHEMAS['parser_offers'].index('Окончание')], '2026-12-31')
                    self.assertIsNotNone(view)
                    self.assertIsNone(reason)

    def test_x5_rejects_malformed_card_timestamps_before_publication(self):
        suffixes = ['garbage', 'T25:00:00', 'T12:60:00', 'T12:00:60',
                    'T12:00:00+25:00', 'T12:00:00+03:60',
                    'T12:00:00-03:60', 'T12:00:00Zgarbage']
        for field, day in [('startDate', '2026-06-04'), ('endDate', '2026-12-31')]:
            for suffix in suffixes:
                with self.subTest(field=field, value=day + suffix):
                    evidence = x5()
                    evidence['card'][field] = day + suffix
                    with self.assertRaises(ValueError):
                        project_to_reader('x5_partners_public', evidence)

    def test_gorod_rejects_malformed_expiry_fields_before_publication(self):
        values = ['2026-12-31garbage', '2026-12-31T25:00:00',
                  '2026-12-31T12:00:00+25:00', '2026-12-31T12:00:00+03:60',
                  '2026-12-31T12:00:00-03:60']
        for field in ('endAt', 'couponEndAt', 'countdown'):
            for value in values:
                with self.subTest(field=field, value=value):
                    evidence = coupon()
                    evidence['data'][field] = value
                    with self.assertRaises(ValueError):
                        project_to_reader('gorod_public', evidence)

    def test_missing_coupon_dates_remain_unknown_and_readable(self):
        for value in (None, ''):
            with self.subTest(value=value):
                self.assertIsNone(iso(value))
                evidence = coupon()
                evidence['data']['endAt'] = value
                evidence['data']['couponEndAt'] = value
                record, _, view, reason = project_to_reader('gorod_public', evidence)
                self.assertIsNone(record['valid_until'])
                self.assertIsNotNone(view)
                self.assertIsNone(reason)
        evidence = coupon()
        del evidence['data']['endAt'], evidence['data']['couponEndAt']
        record, _, view, reason = project_to_reader('gorod_public', evidence)
        self.assertIsNone(record['valid_until'])
        self.assertIsNotNone(view)
        self.assertIsNone(reason)

    def test_calendar_validation_still_applies_to_dates_and_timestamps(self):
        for value in ('2028-02-29', '29.02.2028', '2028-02-29T12:00:00Z'):
            with self.subTest(valid=value):
                self.assertEqual(iso(value), '2028-02-29')
        for value in ('2026-02-29', '31.04.2026', '2026-02-29T12:00:00+03:00'):
            with self.subTest(invalid=value):
                with self.assertRaises(ValueError):
                    iso(value)


if __name__ == '__main__':
    unittest.main()
