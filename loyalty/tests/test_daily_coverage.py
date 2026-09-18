"""Daily coverage must outlive the old 5,000-row diagnostic window."""
import copy
import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).parents[1]))
import sheets_normalized as publication
from sheets_sync import Sheets
from test_sync import FakeSheets

class DailyCoverageTests(unittest.TestCase):
    def history(self):
        return [[str(i)] + ['old'] * 13 + ['manual ' + str(i)] for i in range(4999)]

    def client(self, cls):
        client = cls('fixture-sheet', 'fixture-token')
        memory = FakeSheets()
        memory.tabs['parser_coverage'] = {
            'properties': {'title':'parser_coverage', 'sheetId':20,
                'gridProperties':{'rowCount':5000, 'columnCount':15}},
            'values':[publication.SCHEMAS['parser_coverage'] + ['Ручной комментарий']] + self.history()}
        client.request = memory.request
        return client, memory

    def test_real_upsert_crosses_old_bound_preserving_history_and_manual_cells(self):
        cls = getattr(publication, 'CoverageSheets', publication.NormalizedSheets)
        client, memory = self.client(cls)
        before = copy.deepcopy(memory.tabs)
        incoming = ['new-run:ekp'] + ['new'] * 13
        self.assertEqual(client.upsert('parser_coverage', [incoming]), 1)
        actual = memory.tabs['parser_coverage']['values']
        self.assertEqual(actual[:-1], before['parser_coverage']['values'])
        self.assertEqual(actual[-1], incoming)
        self.assertEqual(memory.tabs['loyalty_partner_benefits'], before['loyalty_partner_benefits'])
        self.assertEqual(client.upsert('parser_coverage', [incoming]), 0)

    def test_normalized_offer_and_legacy_bounds_do_not_expand(self):
        self.assertEqual(Sheets.max_rows, 5000)
        self.assertEqual(publication.NormalizedSheets.max_rows, 5000)

    def test_coverage_writer_is_restricted_to_its_own_tab(self):
        cls = getattr(publication, 'CoverageSheets', None)
        self.assertIsNotNone(cls)
        client, memory = self.client(cls)
        for name in ('parser_offers', 'parser_inbox', 'loyalty_partner_benefits'):
            with self.subTest(name=name), self.assertRaises(ValueError):
                client.upsert(name, [])
        memory.tabs['parser_coverage']['properties']['gridProperties']['rowCount'] = cls.max_rows + 1
        with self.assertRaises(ValueError):
            client.upsert('parser_coverage', [])

    def test_real_readback_corruption_still_fails(self):
        cls = getattr(publication, 'CoverageSheets', None)
        self.assertIsNotNone(cls)
        client, memory = self.client(cls)
        original = memory.request
        def request(method, suffix='', **kwargs):
            result = original(method, suffix, **kwargs)
            if method == 'POST' and any('updateCells' in r for r in kwargs['json']['requests']):
                memory.tabs['parser_coverage']['values'][-1][1] = 'CORRUPTED'
            return result
        client.request = request
        with self.assertRaises(ValueError):
            client.upsert('parser_coverage', [['new-run:ekp'] + ['new'] * 13])

    def test_main_routes_reports_to_dedicated_writer(self):
        from test_normalized_sync import bundle
        payload=bundle();rows=publication.prepare(payload)
        with patch.object(publication.Path, 'stat') as stat, \
             patch.object(publication.Path, 'read_text', return_value=json.dumps(payload)), \
             patch.object(publication, 'NormalizedSheets') as offers, \
             patch.object(publication, 'CoverageSheets', create=True) as coverage, \
             patch.object(sys, 'argv', ['sheets_normalized.py', '--publish']):
            stat.return_value.st_size = 2000
            offers.return_value.upsert.return_value = 1
            coverage.return_value.upsert.return_value = 1
            publication.main()
            offers.return_value.upsert.assert_called_once_with('parser_offers', rows['parser_offers'])
            coverage.return_value.upsert.assert_called_once_with('parser_coverage', rows['parser_coverage'])

if __name__ == '__main__':
    unittest.main()
