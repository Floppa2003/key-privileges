"""Additional public clauses found during the complete 2026-11-14 date audit."""
import copy
import json
import unittest
from pathlib import Path

from catalogue_view import build_catalogue
from public_reward_projection import make_record
from test_observed_campaign_periods import AS_OF, coral_record, retained_without_dates
from unified_normalization import normalize_record


CAPTURE = json.loads(Path(__file__).with_name('fixtures_live').joinpath(
    'observed-additional-periods-20261114.json').read_text())


class ObservedAdditionalPeriods(unittest.TestCase):
    def test_coral_offer_dates_are_distinct_from_code_activation_dates(self):
        row = coral_record(CAPTURE['coral'])
        self.assertEqual((row['valid_from'], row['valid_until']),
                         ('2026-10-26', '2027-10-31'))
        raw = retained_without_dates(row)
        n = normalize_record(raw, as_of=AS_OF)
        self.assertEqual((n['validity']['from'], n['validity']['until']),
                         ('2026-10-26', '2027-10-31'))
        self.assertEqual(n['raw'], raw)
        self.assertIn('Даты активации промокодов: 26.10.2026-31.10.2027', raw['conditions'])

    def test_magnit_labelled_written_ranges_reach_fresh_and_retained_dates(self):
        for native, start in (('1754', '2026-08-12'), ('1757', '2026-07-22')):
            with self.subTest(native=native):
                source = CAPTURE['magnit'][native]
                row = make_record('magnit_partners_public', source['evidence'], source['observed_at'])
                self.assertEqual((row['valid_from'], row['valid_until']), (start, '2026-12-31'))
                raw = retained_without_dates(row)
                n = normalize_record(raw, as_of=AS_OF)
                self.assertEqual((n['validity']['from'], n['validity']['until']),
                                 (start, '2026-12-31'))
                self.assertEqual(n['raw'], raw)

    def test_magnit_extra_code_discount_does_not_expire_ongoing_bonus_offer(self):
        source = CAPTURE['magnit']['1761']
        row = make_record('magnit_partners_public', source['evidence'], source['observed_at'])
        self.assertEqual((row['valid_from'], row['valid_until']), (None, None))
        raw = retained_without_dates(row)
        n = normalize_record(raw, as_of=AS_OF)
        self.assertEqual((n['validity']['from'], n['validity']['until']), (None, None))
        self.assertEqual(n['raw'], raw)
        self.assertEqual(len(build_catalogue([n], as_of=AS_OF)['rows']), 1)

    def test_magnit_explicit_early_completion_is_a_fresh_source_status(self):
        source = CAPTURE['magnit']['1838']
        row = make_record('magnit_partners_public', source['evidence'], source['observed_at'])
        self.assertEqual(row['source_status'], 'finished')
        # The source's scheduled end survives, without inventing a year for
        # the separate early-completion announcement.
        self.assertEqual(row['valid_until'], '2026-12-31')

    def test_retained_magnit_completion_excludes_offer_without_rewriting_source(self):
        source = CAPTURE['magnit']['1838']
        row = make_record('magnit_partners_public', source['evidence'], source['observed_at'])
        raw = retained_without_dates(row)
        raw['source_status'] = 'published'
        raw['original']['fields']['Статус источника']['value'] = 'published'
        before = copy.deepcopy(raw)
        n = normalize_record(raw, as_of=AS_OF)
        self.assertIs(n['availability'].get('source_enabled'), False)
        catalogue = build_catalogue([n], as_of=AS_OF)
        self.assertEqual(catalogue['rows'], [])
        self.assertEqual(catalogue['removed'][0]['reason'], 'неактивное предложение источника')
        self.assertEqual(n['raw'], before)
        self.assertEqual(raw, before)


if __name__ == '__main__':
    unittest.main()
