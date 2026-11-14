"""The actual Taivas offer states two separate periods across New Year."""
import copy
import html
import json
import unittest
from pathlib import Path

from bs4 import BeautifulSoup
from partner_pages import extract_partner_page
from test_observed_campaign_periods import retained_without_dates
from unified_normalization import normalize_record


CAPTURE = json.loads(Path(__file__).with_name('fixtures_live').joinpath(
    'observed-taivas-periods-20261114.json').read_text())


def source_record():
    # The selector is native; only its HTML scaffold is supplied by the test.
    body = '<section id="rec1240645516">' + ''.join(
        '<p>' + html.escape(line) + '</p>' for line in CAPTURE['excerpt'].splitlines()) + '</section>'
    return extract_partner_page('rzd_taivas', BeautifulSoup(body, 'html.parser'),
                                CAPTURE['source_url'], CAPTURE['observed_at'])[0]


def retained_record():
    raw = retained_without_dates(source_record())
    # Replay the actually retained first interval and its truncated evidence.
    for field, label, value in (
            ('valid_from', 'Начало', CAPTURE['stored_from']),
            ('valid_until', 'Окончание', CAPTURE['stored_until'])):
        raw[field] = value
        raw['original']['fields'][label]['value'] = value
    raw['details']['validity_evidence'] = CAPTURE['stored_validity_evidence']
    raw['original']['fields']['Детали JSON']['value'] = json.dumps(raw['details'], ensure_ascii=False)
    return raw


class ObservedTaivasPeriods(unittest.TestCase):
    def test_fresh_source_keeps_both_intervals_in_literal_evidence(self):
        row = source_record()
        self.assertEqual((row['valid_from'], row['valid_until']),
                         ('2026-09-15', '2026-12-30'))
        self.assertEqual(row['details']['validity_evidence'],
                         'Срок действия акции: 15.09 - 30.12.2026, 09.01-14.05.2027')

    def test_retained_source_selects_the_current_or_next_interval_without_filling_gap(self):
        for day, start, end, status in (
                ('2026-11-14', '2026-09-15', '2026-12-30', 'within_stated_period'),
                ('2027-01-01', '2027-01-09', '2027-05-14', 'not_started'),
                ('2027-01-09', '2027-01-09', '2027-05-14', 'within_stated_period'),
                ('2027-05-15', '2027-01-09', '2027-05-14', 'expired')):
            with self.subTest(day=day):
                raw = retained_record()
                before = copy.deepcopy(raw)
                n = normalize_record(raw, as_of=day)
                self.assertEqual(n['validity'], {
                    'from': start, 'until': end, 'as_of': day, 'status': status,
                })
                self.assertEqual(raw, before)
                self.assertEqual(n['raw'], before)


if __name__ == '__main__':
    unittest.main()
