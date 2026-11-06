"""Reviewed exact partner rates reject changed ranges instead of taking a bound."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1]))
import alfa_partner_rules
from sheets_normalized import SCHEMAS, prepare
from unified_normalization import make_input, normalize_record
from test_alfa_partner_clauses import NOW, record, source_text


def common_input(row):
    report = dict(source_id=alfa_partner_rules.SOURCE_ID, name='Alfa',
                  root='https://alfabank.servicecdn.ru/', status='ok', discovered=1,
                  normalized=1, failed=0, coverage='fixture', region=None,
                  errors=[], observed_at=NOW)
    bundle = dict(schema_version=2, run_id='fixture:numeric', observed_at=NOW,
                  records=[row], sources=[report])
    values = prepare(bundle)['parser_offers'][0]
    return make_input(dict(id=row['id'], origin='parser_offers', row=2,
                           fields={h: {'value': v}
                                   for h, v in zip(SCHEMAS['parser_offers'], values)}))


class AlfaPartnerNumericBoundaryTests(unittest.TestCase):
    def test_changed_or_reversed_range_cannot_become_reviewed_exact_rate(self):
        for rate in ('10%–5%', '10%–15%', '10% - 15%'):
            with self.subTest(rate=rate):
                body = source_text().replace('по ставке 10 %', 'по ставке ' + rate)
                with self.assertRaisesRegex(ValueError, 'alfa_partner_pdf_rate_invalid_or_changed'):
                    record(body)

    def test_stored_common_input_cannot_resurrect_the_first_bound(self):
        raw = common_input(record())
        for rate in ('10%–5%', '10%–15%'):
            with self.subTest(rate=rate):
                changed = {**raw, 'benefit': raw['benefit'].replace('по ставке 10 %',
                                                                  'по ставке ' + rate)}
                self.assertNotEqual(changed['benefit'], raw['benefit'])
                with self.assertRaisesRegex(ValueError, 'alfa_partner_pdf_rate_invalid_or_changed'):
                    normalize_record(changed, as_of='2026-11-06')

    def test_reviewed_exact_rate_and_owned_conditions_survive_source_to_common(self):
        row = record()
        raw = common_input(row)
        result = normalize_record(raw, as_of='2026-11-06')
        self.assertEqual(result['raw'], raw)
        self.assertEqual([(term['kind'], term['value'], term['value_min'],
                           term['qualifier']) for term in result['benefits']],
                         [('earn_rewards', '10', None, 'exact')])
        self.assertTrue(all(term['evidence']['text'] in row['benefit_text']
                            for term in result['benefits']))
        self.assertTrue(all(term['condition_ids'] for term in result['benefits']))


if __name__ == '__main__':
    unittest.main()
