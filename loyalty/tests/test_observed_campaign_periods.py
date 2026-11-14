"""Actual Coral and Magnit clauses that previously lost both calendar bounds."""
import copy
import html
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1]))
from coral_catalog import detail
from public_reward_projection import make_record
from test_source_availability_dates import stored_input
from unified_normalization import make_input, normalize_record


CAPTURE = json.loads(Path(__file__).with_name('fixtures_live').joinpath(
    'observed-campaign-periods-20261114.json').read_text())
AS_OF = '2026-11-14'


def coral_record(source):
    # Only the surrounding owned-column structure is supplied by the test;
    # the heading and both date-bearing paragraphs are unchanged excerpts.
    raw = ('<section><div class="order-lg-2"><h1>'
           + html.escape(source['title']) + '</h1>'
           + ''.join('<p>' + html.escape(line) + '</p>'
                     for line in source['excerpt'].splitlines())
           + '</div><div class="product-purchase-box referal"></div></section>')
    return detail(raw, 'coral', {'url': source['url'], 'category': 'Недвижимость'},
                  source['observed_at'], {})


def retained_without_dates(row):
    observed = row['observed_at']
    source = stored_input({
        'schema_version': 2, 'run_id': '43612232710:1', 'observed_at': observed,
        'records': [row], 'sources': [{
            'source_id': row['source_id'], 'name': row['program'],
            'root': row['source_url'], 'status': 'ok', 'normalized': 1,
            'discovered': 1, 'failed': 0, 'coverage': 'public_source_excerpt',
            'region': None, 'errors': [], 'observed_at': observed,
        }],
    })
    for label in ('Начало', 'Окончание'):
        source['fields'][label]['value'] = ''
    details = json.loads(source['fields']['Детали JSON']['value'])
    if 'public_coral_block' in details:
        details['public_coral_block']['valid_until'] = None
    source['fields']['Детали JSON']['value'] = json.dumps(details, ensure_ascii=False)
    return make_input(source)


class ObservedCampaignPeriods(unittest.TestCase):
    def test_coral_do_separator_reaches_fresh_source_bounds(self):
        for source, start, end in zip(CAPTURE['coral'],
                                      ('2026-04-13', '2026-06-08'),
                                      ('2026-12-21', '2027-06-07')):
            with self.subTest(url=source['url']):
                row = coral_record(source)
                self.assertEqual((row['valid_from'], row['valid_until']), (start, end))
                self.assertIn(source['excerpt'], row['conditions_text'])

    def test_retained_coral_do_ranges_reach_reader_validity(self):
        for source, start, end in zip(CAPTURE['coral'],
                                      ('2026-04-13', '2026-06-08'),
                                      ('2026-12-21', '2027-06-07')):
            with self.subTest(url=source['url']):
                raw = retained_without_dates(coral_record(source))
                before = copy.deepcopy(raw)
                n = normalize_record(raw, as_of=AS_OF)
                self.assertEqual(n['validity'], {
                    'from': start, 'until': end, 'as_of': AS_OF,
                    'status': 'within_stated_period',
                })
                self.assertEqual(raw, before)
                self.assertEqual(n['raw'], before)

    def test_magnit_latin_c_reaches_fresh_source_bounds(self):
        source = CAPTURE['magnit']
        row = make_record('magnit_partners_public', source['evidence'], source['observed_at'])
        self.assertEqual((row['valid_from'], row['valid_until']),
                         ('2026-11-02', '2027-11-30'))
        self.assertIn('Срок проведения акции: c 02.11.2026 по 30.11.2027',
                      row['conditions_text'])

    def test_retained_magnit_latin_c_reaches_reader_validity(self):
        source = CAPTURE['magnit']
        row = make_record('magnit_partners_public', source['evidence'], source['observed_at'])
        raw = retained_without_dates(row)
        before = copy.deepcopy(raw)
        n = normalize_record(raw, as_of=AS_OF)
        self.assertEqual(n['validity'], {
            'from': '2026-11-02', 'until': '2027-11-30', 'as_of': AS_OF,
            'status': 'within_stated_period',
        })
        self.assertEqual(raw, before)
        self.assertEqual(n['raw'], before)


if __name__ == '__main__':
    unittest.main()
