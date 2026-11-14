"""Anonymized reproductions of encountered Mir period and disclaimer wording.

The conflicting start, agreeing offer and separate acquisition/redemption
deadlines come from actual retained rows. No date variants are synthesized.
"""
import copy
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).parents[1]))
from adapters import mir_detail
from catalogue_view import record_row
from normalized import validate_offer
from test_observed_promo_actions import LOGIN
from test_source_availability_dates import stored_input
from unified_normalization import make_input, normalize_record


NOW = '2026-11-14T12:00:00+00:00'
AS_OF = '2026-11-14'
URL = 'https://vamprivet.ru/promo/observed-period-fixture/'
PERIOD = 'с 22 сентября по 31 декабря 2026'
DISCLAIMER = ('Предложение действует с 23 сентября 2026 г. по 31 декабря 2026 г. '
              'Скидка 25% предоставляется при сумме заказа от 4 000 ₽. '
              'Акция действует только при оформлении заказа на сайте и не '
              'распространяется на покупки в розничных магазинах и мобильном приложении.')


def source_offer(start='22.09.2026', end='31.12.2026', period=PERIOD,
                 disclaimer=DISCLAIMER, conditions=LOGIN):
    promo = {
        'xml_id': 'observed-period-fixture', 'url': '/promo/observed-period-fixture/',
        'name': 'Предложение магазина', 'owner': {'name': 'Пример'},
        'desc': {'number': {'PREFIX': 'Скидка', 'AMOUNT': '25%'},
                 'text': 'на оплату от 4 000 ₽ на сайте по промокоду'},
        'startDate': start, 'endDate': end, 'status': 'active',
        'promoIsStarted': True, 'prizeIsSuspended': False,
        'templates': [
            {'templateName': 'period', 'templateTitle': 'Срок проведения',
             'templateText': period},
            {'templateName': 'conditions', 'templateTitle': 'Условия акции',
             'templateText': conditions},
            {'templateName': 'site', 'templateTitle': '', 'templateText': 'Сайт партнёра'},
            {'templateName': 'disclamer', 'templateTitle': '', 'templateText': disclaimer},
        ],
    }
    before = copy.deepcopy(promo)
    row, = mir_detail({'data': {'content': {'promoDetail': {'promo': {'promoAction': promo}}}}},
                      URL, NOW)
    if promo != before:
        raise AssertionError('The adapter changed its original source object')
    return row


def stored(row):
    return stored_input({
        'schema_version': 2, 'run_id': 'fixture:1', 'observed_at': NOW,
        'records': [row], 'sources': [{
            'source_id': 'mir', 'name': 'Мир', 'root': 'https://vamprivet.ru/',
            'status': 'ok', 'normalized': 1, 'discovered': 1, 'failed': 0,
            'coverage': 'owned observed period', 'region': None, 'errors': [],
            'observed_at': NOW,
        }],
    })


class ObservedMirStartConflict(unittest.TestCase):
    def assert_common_conflict(self, raw):
        before = copy.deepcopy(raw)
        n = normalize_record(raw, as_of=AS_OF)
        self.assertIsNone(n['validity']['from'])
        self.assertEqual(n['validity']['until'], '2026-12-31')
        self.assertEqual(n['validity']['status'], 'source_date_conflict')
        self.assertTrue(any('conflict' in issue for issue in n['quality']['issues']))
        self.assertEqual(raw, before)
        self.assertEqual(n['raw'], before)
        row, reason = record_row(n, AS_OF)
        self.assertIsNone(reason)
        self.assertEqual(row[6], 'до 2026-12-31')
        self.assertEqual(row[12], 'Проверь срок')
        self.assertIn(PERIOD, row[5])
        self.assertIn('с 23 сентября 2026 г. по 31 декабря 2026 г.', row[5])

    def test_fresh_conflicting_start_is_withheld_and_source_text_preserved(self):
        row = source_offer()
        validate_offer(row)
        self.assertIsNone(row['valid_from'])
        self.assertEqual(row['valid_until'], '2026-12-31')
        self.assertTrue(any('conflict' in issue for issue in row['warnings']))
        self.assertEqual(row['details']['templates'][0]['text'], PERIOD)
        self.assertEqual(row['details']['templates'][3]['text'], DISCLAIMER)

    def test_fresh_stored_row_keeps_conflict_even_with_start_already_blank(self):
        self.assert_common_conflict(make_input(stored(source_offer())))

    def test_retained_old_start_is_withheld_without_rewriting_snapshot(self):
        source = stored(source_offer())
        # This is the actual old persisted projection, before conflict handling.
        source['fields']['Начало']['value'] = '2026-09-22'
        source['fields']['Ограничения JSON']['value'] = '[]'
        self.assert_common_conflict(make_input(source))

    def test_uncontested_end_still_excludes_the_offer_after_its_last_day(self):
        n = normalize_record(make_input(stored(source_offer())), as_of='2027-01-01')
        self.assertIsNone(n['validity']['from'])
        self.assertEqual(n['validity']['until'], '2026-12-31')
        self.assertEqual(n['validity']['status'], 'expired')
        self.assertTrue(any('conflict' in issue for issue in n['quality']['issues']))
        row, reason = record_row(n, '2027-01-01')
        self.assertIsNone(row)
        self.assertEqual(reason, 'истёкший срок')

    def test_agreeing_owned_start_remains_available(self):
        row = source_offer('18.09.2026', '31.12.2026',
                           'с 18 сентября по 31 декабря 2026',
                           'Предложение действует с 18 сентября 2026 г. по 31 декабря 2026 г.')
        n = normalize_record(make_input(stored(row)), as_of=AS_OF)
        self.assertEqual((row['valid_from'], row['valid_until']), ('2026-09-18', '2026-12-31'))
        self.assertEqual(n['validity'], {'from': '2026-09-18', 'until': '2026-12-31',
                                        'as_of': AS_OF, 'status': 'within_stated_period'})
        self.assertFalse(any('conflict' in issue for issue in n['quality']['issues']))

    def test_encountered_acquisition_end_is_not_conflated_with_redemption_end(self):
        controls = [
            ('22.07.2026', '22.09.2026', 'с 22 июля по 22 сентября 2026',
             'Акция действует с 22 июля 2026г. по 06 октября 2026 г.',
             'Успейте получить его до 22 сентября 2026, а активировать до 6 октября 2026',
             '2026-07-22', '2026-09-22'),
            ('07.04.2026', '31.10.2026', 'с 7 апреля по 31 октября 2026',
             'Акция действует с 07 апреля 2026 г. по 15 ноября 2026 г.',
             'Успейте получить штрихкод до 31 октября 2026, а активировать до 15 ноября 2026',
             '2026-04-07', '2026-10-31'),
        ]
        for start, end, period, disclaimer, conditions, want_start, want_end in controls:
            with self.subTest(period=period):
                row = source_offer(start, end, period, disclaimer, conditions)
                n = normalize_record(make_input(stored(row)), as_of=AS_OF)
                self.assertEqual((row['valid_from'], row['valid_until']), (want_start, want_end))
                self.assertEqual((n['validity']['from'], n['validity']['until']), (want_start, want_end))
                self.assertEqual(n['validity']['status'], 'expired')
                self.assertFalse(any('conflict' in issue for issue in n['quality']['issues']))


if __name__ == '__main__':
    unittest.main()
