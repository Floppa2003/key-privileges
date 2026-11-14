"""Explicit whole-campaign rule periods must not inherit another stage's dates."""
import html
import json
import unittest
from pathlib import Path

from document_text import document_records, sha
from ekp_linked_rules import rows_for
from test_observed_campaign_periods import AS_OF, retained_without_dates
from unified_normalization import normalize_record


CAPTURE = json.loads(Path(__file__).with_name('fixtures_live').joinpath(
    'observed-rule-periods-20261114.json').read_text())


def vtb_record():
    source = CAPTURE['vtb']
    return document_records(
        'af_vtb_rules', 'linked-pdf:' + sha(source['url'].encode())[:32],
        'Аэрофлот Бонус', 'ВТБ', source['url'], source['observed_at'], source['document'],
        parent_source=source['parent_source'], label=source['label'],
        parent_sha256=source['parent_response_sha256'],
        extra_details={'transport': source['transport']})[0]


def mir_record():
    source = CAPTURE['mir']
    raw = ('<html><body><main><h1>' + html.escape(source['title']) + '</h1>'
           + ''.join('<p>' + html.escape(line) + '</p>' for line in source['excerpt'].splitlines()[1:])
           + '</main></body></html>').encode()
    entry = {'url': source['url'], 'parents': [source['parent']]}
    return rows_for(raw, entry, source['receipt'], source['observed_at'])[0]


class ObservedRulePeriods(unittest.TestCase):
    def test_vtb_native_campaign_period_ignores_earning_and_crediting_windows(self):
        row = vtb_record()
        self.assertEqual((row['valid_from'], row['valid_until']),
                         ('2026-04-27', '2026-11-20'))
        self.assertIn('01.05.2026 по 31.10.2026', row['conditions_text'])
        self.assertIn('с 01.11.2026 по 20.11.2026', row['conditions_text'])

    def test_linked_mir_campaign_period_ignores_later_bank_participation_start(self):
        row = mir_record()
        self.assertEqual((row['valid_from'], row['valid_until']),
                         ('2026-01-01', '2026-12-31'))
        self.assertIn('с 01.10.2026', row['conditions_text'])

    def test_retained_owned_rule_periods_reach_normalized_dates(self):
        for row, wanted in (
                (vtb_record(), ('2026-04-27', '2026-11-20')),
                (mir_record(), ('2026-01-01', '2026-12-31'))):
            with self.subTest(url=row['source_url']):
                raw = retained_without_dates(row)
                n = normalize_record(raw, as_of=AS_OF)
                self.assertEqual((n['validity']['from'], n['validity']['until']), wanted)
                self.assertEqual(n['raw'], raw)


if __name__ == '__main__':
    unittest.main()
