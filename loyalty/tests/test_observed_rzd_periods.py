"""Owned RZD labels are dates; publication cells and scoped ends are not."""
import json
import unittest
from pathlib import Path

from rzd_import_catalog import detail
from test_observed_campaign_periods import AS_OF, retained_without_dates
from unified_normalization import normalize_record


CAPTURE = json.loads(Path(__file__).with_name('fixtures_live').joinpath(
    'observed-rzd-periods-20261114.json').read_text())
WANT = (
    ('2026-06-01', None),
    ('2026-04-09', '2026-12-31'),
    (None, None),  # Radisson's overall and hotel-specific ends differ.
    (None, '2026-11-30'),
    (None, '2026-12-31'),
    ('2026-01-01', None),
    ('2026-01-01', None),
    (None, '2026-11-30'),
    (None, '2026-12-31'),
    ('2026-04-01', None),
    ('2026-01-01', None),
    (None, None),  # The native Google date cell is a publication date.
)


class ObservedRzdPeriods(unittest.TestCase):
    def test_native_import_reads_labels_with_original_string_dates(self):
        for source, wanted in zip(CAPTURE, WANT):
            with self.subTest(url=source['observation']['url'], wanted=wanted):
                row = detail(source['observation'], source['observed_at'])
                self.assertEqual((row['valid_from'], row['valid_until']), wanted)

    def test_retained_owned_import_gains_same_dates_without_mutation(self):
        for source, wanted in zip(CAPTURE, WANT):
            with self.subTest(url=source['observation']['url'], wanted=wanted):
                row = detail(source['observation'], source['observed_at'])
                raw = retained_without_dates(row)
                n = normalize_record(raw, as_of=AS_OF)
                self.assertEqual((n['validity']['from'], n['validity']['until']), wanted)
                self.assertEqual(n['raw'], raw)


if __name__ == '__main__':
    unittest.main()
