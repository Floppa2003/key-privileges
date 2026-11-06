"""The published record schema accepts real deterministic source projections."""
import copy
import json
import sys
import unittest
from pathlib import Path

from bs4 import BeautifulSoup
from jsonschema import Draft202012Validator, FormatChecker

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import test_hse_alumni as hse_fixture
import test_konsierge_catalog as konsierge_fixture
import test_recovered_vtb_summary_projection as vtb_fixture
from recovered_sources import parse_bank_page
from sheets_normalized import prepare, SCHEMAS
from tsum_alfa import extract_tsum, SOURCE_ID as TSUM, URL as TSUM_URL
from unified_normalization import make_input, normalize_inputs, validate_normalized

ROOT = Path(__file__).resolve().parents[1]
NOW = '2026-11-06T00:00:00+00:00'


class UnifiedSchemaContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        schema = json.loads((ROOT / 'unified.schema.json').read_text())
        Draft202012Validator.check_schema(schema)
        cls.validator = Draft202012Validator(schema, format_checker=FormatChecker())

    def project_bundle(self, bundle):
        before = copy.deepcopy(bundle)
        rows = prepare(bundle)['parser_offers']
        inputs = [make_input({
            'id': row[0], 'origin': 'parser_offers', 'row': index,
            'fields': {header: {'value': value}
                       for header, value in zip(SCHEMAS['parser_offers'], row)},
        }) for index, row in enumerate(rows, 2)]
        originals = copy.deepcopy(inputs)
        records = normalize_inputs(inputs, as_of='2026-11-06')['records']
        self.assertEqual(inputs, originals)
        self.assertEqual(bundle, before)
        for source, record in zip(originals, records):
            self.assertEqual(record['raw'], source)
            validate_normalized(record)
        return records

    def project_rows(self, rows):
        source = rows[0]['source_id']
        self.assertTrue(all(row['source_id'] == source for row in rows))
        return self.project_bundle({
            'schema_version': 2, 'run_id': 'fixture:schema', 'observed_at': NOW,
            'records': rows, 'sources': [{
                'source_id': source, 'name': source, 'root': rows[0]['source_url'],
                'status': 'ok', 'discovered': len(rows), 'normalized': len(rows),
                'failed': 0, 'errors': [], 'region': None,
                'coverage': 'public fixture', 'observed_at': NOW,
            }],
        })

    def assert_schema(self, record):
        errors = [f'{list(error.absolute_path)}: {error.message}'
                  for error in self.validator.iter_errors(record)]
        self.assertEqual(errors, [])

    def hse_records(self):
        return self.project_rows(hse_fixture.parse_catalog(hse_fixture.page(), NOW))

    def konsierge_records(self):
        fixture = konsierge_fixture.KonsiergeTests()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        return self.project_bundle(fixture.bundle())

    def test_owned_catalog_clauses_match_published_schema(self):
        for record in self.hse_records():
            with self.subTest(partner=record['partner']['name']):
                self.assertTrue(record['benefits'])
                self.assertEqual(record['benefits'][0]['method'], 'owned_source_clause')
                self.assert_schema(record)

    def test_owned_merchant_clauses_match_published_schema(self):
        html = (ROOT / 'tests/fixtures_live/tsum-alfa.html').read_text()
        rows = extract_tsum(TSUM, BeautifulSoup(html, 'html.parser'), TSUM_URL, NOW, {})
        records = self.project_rows(rows)
        self.assertTrue(any(record['benefits'] for record in records))
        for record in records:
            with self.subTest(title=record['title']):
                for benefit in record['benefits']:
                    self.assertEqual(benefit['method'], 'owned_source_clause')
                self.assert_schema(record)

    def test_owned_bank_clauses_match_published_schema(self):
        row = parse_bank_page('af_vtb_rules', vtb_fixture.page(), NOW)
        record, = self.project_rows([row])
        cashback, = [term for term in record['benefits'] if term['kind'] == 'cashback']
        self.assertEqual(cashback['method'], 'owned_source_clause')
        self.assert_schema(record)

    def test_conflicting_source_dates_match_published_schema(self):
        matches = [record for record in self.konsierge_records()
                   if record['validity']['status'] == 'source_date_conflict']
        self.assertTrue(matches)
        for record in matches:
            self.assertIsNone(record['validity']['until'])
            self.assert_schema(record)

    def test_source_expiry_with_unknown_customer_period_matches_schema(self):
        matches = [record for record in self.konsierge_records()
                   if record['validity']['status'] == 'source_expiry_elapsed_customer_period_unknown']
        self.assertTrue(matches)
        for record in matches:
            self.assertIsNone(record['validity']['until'])
            self.assert_schema(record)

    def test_unknown_method_remains_rejected(self):
        record = self.hse_records()[0]
        record['benefits'][0]['method'] = 'invented_projection'
        errors = list(self.validator.iter_errors(record))
        self.assertTrue(any(list(error.absolute_path) == ['benefits', 0, 'method']
                            for error in errors))

    def test_unknown_validity_status_remains_rejected(self):
        record = self.hse_records()[0]
        record['validity']['status'] = 'invented_verified_eligibility'
        errors = list(self.validator.iter_errors(record))
        self.assertTrue(any(list(error.absolute_path) == ['validity', 'status']
                            for error in errors))
