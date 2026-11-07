"""Native clock/expiry offsets must not be silently normalized on ingestion."""
import copy
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1]))
from announcements import parse_feed
from t2_source import catalog_records
from test_announcements import CFG, NOW, card, post


BAD_OFFSETS = (
    '+03:60', '-03:60', '+03:00:60', '-03:00:60',
    '+0360', '-0360', '+030060', '-030060',
    '+03:00:60.5', '-03:00:60.5', '+24:00', '-24:00',
)
PAGINATION = '<a class="tme_messages_more" href="/s/ekpcard?before=70" data-before="70">more</a>'
FIXTURE = Path(__file__).with_name('fixtures_live') / 't2-catalog.json'


class AnnouncementNativeTimestampTests(unittest.TestCase):
    def test_overflowing_native_clock_is_rejected(self):
        for offset in BAD_OFFSETS:
            with self.subTest(offset=offset):
                markup = post('ekpcard/70', 'Держателям ЕКП скидка 10% ' + card(),
                              when='2026-09-10T13:00:00' + offset)
                result = parse_feed(markup, CFG, NOW)
                self.assertEqual(len(result['records']), 0)
                self.assertEqual(result['errors'], [{
                    'phase': 'post', 'native_id': 'ekpcard/70',
                    'reason': 'missing_publication_time',
                }])

    def test_valid_native_clocks_keep_local_date_offset_cards_and_pagination(self):
        cases = (
            ('2026-09-10T13:00:00Z', '2026-09-10T13:00:00+00:00'),
            ('2026-09-10T13:00:00.123456789Z', '2026-09-10T13:00:00.123456+00:00'),
            ('2026-09-10T13:00:00,5+03:30', '2026-09-10T13:00:00.500000+03:30'),
            ('2026-09-10T00:15:00+14:00', '2026-09-10T00:15:00+14:00'),
            ('2026-09-10T23:45:00-12:00', '2026-09-10T23:45:00-12:00'),
            ('2026-09-10T13:00:00+03:30:15.5', '2026-09-10T13:00:00+03:30:15.500000'),
            ('20260910T130000+0330', '2026-09-10T13:00:00+03:30'),
            ('2026-W37-4T13:00:00+03:00', '2026-09-10T13:00:00+03:00'),
        )
        for value, expected in cases:
            with self.subTest(value=value):
                markup = post('ekpcard/70', 'Держателям ЕКП скидка 10% ' + card(),
                              when=value) + PAGINATION
                result = parse_feed(markup, CFG, NOW)
                self.assertEqual(result['errors'], [])
                self.assertEqual(len(result['records']), 1)
                record = result['records'][0]
                self.assertEqual(record['native_id'], 'ekpcard/70')
                self.assertEqual(record['details']['published_at'], expected)
                self.assertEqual(record['details']['linked_cards'], [{
                    'label': 'Studio',
                    'url': 'https://ekp.spb.ru/capabilities/loyalty/tiles/123?region=78',
                }])
                self.assertEqual(result['next_url'], 'https://t.me/s/ekpcard?before=70')

    def test_bad_clock_does_not_hide_the_next_valid_post_or_cursor(self):
        markup = (
            post('ekpcard/70', 'Держателям ЕКП скидка 10% ' + card(),
                 when='2026-09-10T13:00:00+03:60')
            + post('ekpcard/71', 'Держателям ЕКП скидка 15% ' + card(),
                   when='2026-09-10T13:00:00+03:00')
            + PAGINATION
        )
        result = parse_feed(markup, CFG, NOW)
        self.assertEqual([r['native_id'] for r in result['records']], ['ekpcard/71'])
        self.assertEqual(result['scanned'], 2)
        self.assertEqual(result['next_url'], 'https://t.me/s/ekpcard?before=70')
        self.assertEqual(result['errors'], [{
            'phase': 'post', 'native_id': 'ekpcard/70',
            'reason': 'missing_publication_time',
        }])

    def test_announcement_clock_still_requires_timezone(self):
        result = parse_feed(
            post('ekpcard/70', 'Держателям ЕКП скидка 10% ' + card(),
                 when='2026-09-10T13:00:00'), CFG, NOW)
        self.assertEqual(result['records'], [])
        self.assertEqual(result['errors'][0]['reason'], 'missing_publication_time')


class T2NativeTimestampTests(unittest.TestCase):
    def test_overflowing_native_expiry_is_rejected_without_mutating_payload(self):
        for offset in BAD_OFFSETS:
            with self.subTest(offset=offset):
                data = json.loads(FIXTURE.read_text())
                data['data']['offers'][0]['dateTo'] = '2026-12-31T13:00:00' + offset
                before = copy.deepcopy(data)
                with self.assertRaises(ValueError):
                    catalog_records(data, NOW)
                self.assertEqual(data, before)

    def test_valid_native_expiry_keeps_local_date_and_original_timestamp(self):
        cases = (
            ('2026-09-15T23:59:00.000+03:00', '2026-09-15'),
            ('2026-12-31', '2026-12-31'),
            ('2026-12-31 23:59:59', '2026-12-31'),
            ('2026-12-31T23:59:59.123456789Z', '2026-12-31'),
            ('2026-12-31T23:59:59,5+03:30', '2026-12-31'),
            ('2026-12-31T00:15:00+14:00', '2026-12-31'),
            ('2026-12-31T23:45:00-12:00', '2026-12-31'),
            ('2026-12-31T23:59:59+03:30:15.5', '2026-12-31'),
            ('20261231T234500-1200', '2026-12-31'),
            ('2026-W53-4T23:59:59+03:00', '2026-12-31'),
        )
        for value, expected in cases:
            with self.subTest(value=value):
                data = json.loads(FIXTURE.read_text())
                data['data']['offers'][0]['dateTo'] = value
                before = copy.deepcopy(data)
                records = catalog_records(data, NOW)
                self.assertEqual(len(records), 4)
                record = records[0]
                self.assertEqual(record['native_id'], '5871FFCF1EE82EACE0630D06F60A6869')
                self.assertEqual(record['valid_until'], expected)
                self.assertEqual(record['details']['source_date_to'], value)
                self.assertEqual(data, before)

    def test_absent_native_expiry_remains_unknown(self):
        for value in (None, ''):
            with self.subTest(value=value):
                data = json.loads(FIXTURE.read_text())
                data['data']['offers'][0]['dateTo'] = value
                record = catalog_records(data, NOW)[0]
                self.assertIsNone(record['valid_until'])
                self.assertEqual(record['details']['source_date_to'], value)


if __name__ == '__main__':
    unittest.main()
