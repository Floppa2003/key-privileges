"""Both native merch coupon components share one explicit redemption end."""
import json
import unittest
from pathlib import Path

from document_text import document_records
from test_observed_campaign_periods import AS_OF, retained_without_dates
from unified_normalization import normalize_record


CAPTURE = json.loads(Path(__file__).with_name('fixtures_live').joinpath(
    'observed-utair-merch-expiry-20261114.json').read_text())


def merch_record():
    return document_records(
        'utair_rule_documents', 'document:pNnqOk', 'Utair Status', 'Utair',
        CAPTURE['url'], CAPTURE['observed_at'], CAPTURE['document'],
        parent_source=CAPTURE['parent_source'], label=CAPTURE['label'],
        parent_sha256=CAPTURE['parent_response_sha256'])[0]


class ObservedUtairMerchExpiry(unittest.TestCase):
    def test_fresh_shared_end_does_not_guess_the_damaged_start(self):
        row = merch_record()
        self.assertEqual((row['valid_from'], row['valid_until']),
                         (None, '2026-12-31'))
        self.assertIn('01.03.202 6г.', row['conditions_text'])
        self.assertIn('5 000 рублей', row['conditions_text'])
        self.assertIn('предоставляется 5% скидка', row['conditions_text'])

    def test_retained_shared_end_expires_both_components_without_rewriting_raw(self):
        raw = retained_without_dates(merch_record())
        n = normalize_record(raw, as_of=AS_OF)
        self.assertEqual((n['validity']['from'], n['validity']['until']),
                         (None, '2026-12-31'))
        self.assertEqual(n['validity']['status'], 'within_stated_period')
        self.assertEqual(n['raw'], raw)
        expired = normalize_record(raw, as_of='2027-01-01')
        self.assertEqual(expired['validity']['status'], 'expired')
        self.assertEqual(expired['raw'], raw)


if __name__ == '__main__':
    unittest.main()
