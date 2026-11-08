"""ID-bearing source rows must not silently acquire legacy row identities."""
import contextlib
import copy
import io
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1]))
from unified_inputs import HEADERS, atom_from_cell, inputs_from_tables
from unified_normalization import INPUT_TABS
from unified_publish import publish_all
from test_unified_live import FakeUnified


PARSER_TABS = ('parser_offers', 'parser_inbox')
INVALID_CELLS = (
    {},
    {'userEnteredValue': {'stringValue': ''}},
    {'userEnteredValue': {'stringValue': ' \t\r\n'}},
    {'userEnteredValue': {'numberValue': 0}},
    {'userEnteredValue': {'numberValue': 42}},
    {'userEnteredValue': {'boolValue': False}},
    {'userEnteredValue': {'boolValue': True}},
    {'userEnteredValue': {'formulaValue': '=A1'}},
)


def source_values(name, ident='source:published-id'):
    values = {'ID': ident, 'Программа': 'Synthetic program',
              'Партнёр': 'Synthetic partner', 'Заголовок': 'Synthetic offer',
              'Тип записи': 'partner_offer', 'Выгода': 'Скидка 10%',
              'Источник': 'Synthetic source', 'Заголовок страницы': 'Synthetic page',
              'Текст страницы — требует разбора': 'Скидка 10%'}
    return [values.get(key, '') for key in HEADERS[name]]


def source_tables(name, id_cell):
    tables = {tab: [[] for _ in range(header - 1)] + [
        [{'value': key} for key in HEADERS[tab]]]
        for tab, (header, _) in INPUT_TABS.items()}
    row = [{'value': value} for value in source_values(name)]
    row[0] = atom_from_cell(id_cell)
    tables[name].append(row)
    return tables


class NativeIdClient(FakeUnified):
    def __init__(self, source, id_cell):
        super().__init__()
        self.source = source
        self.id_cell = copy.deepcopy(id_cell)
        self.tabs[source]['values'].append(source_values(source))

    def request(self, method, suffix='', **kwargs):
        result = super().request(method, suffix, **kwargs)
        if (method == 'GET' and kwargs.get('params', {}).get('ranges', '').startswith(
                "'" + self.source + "'!")):
            result['sheets'][0]['data'][0]['rowData'][-1]['values'][0] = copy.deepcopy(self.id_cell)
        return result


class ExplicitSourceIdTests(unittest.TestCase):
    def test_populated_parser_rows_require_nonblank_string_ids(self):
        for name in PARSER_TABS:
            for cell in INVALID_CELLS:
                with self.subTest(source=name, cell=cell):
                    tables = source_tables(name, cell)
                    before = copy.deepcopy(tables)
                    with self.assertRaisesRegex(ValueError, 'Invalid explicit source ID'):
                        inputs_from_tables(tables)
                    self.assertEqual(tables, before)

    def test_valid_literal_id_is_preserved_verbatim(self):
        for name in PARSER_TABS:
            with self.subTest(source=name):
                tables = source_tables(name, {'userEnteredValue': {'stringValue': 'Native:ID-Case'}})
                before = copy.deepcopy(tables)
                records, _ = inputs_from_tables(tables)
                self.assertEqual([record['id'] for record in records], ['Native:ID-Case'])
                self.assertEqual(records[0]['original']['fields']['ID'], {'value': 'Native:ID-Case'})
                self.assertEqual(tables, before)

    def test_cached_formula_id_retains_both_value_and_formula(self):
        cell = {'userEnteredValue': {'formulaValue': '=A1'},
                'effectiveValue': {'stringValue': 'Native:formula-id'}}
        for name in PARSER_TABS:
            with self.subTest(source=name):
                records, _ = inputs_from_tables(source_tables(name, cell))
                self.assertEqual(records[0]['id'], 'Native:formula-id')
                self.assertEqual(records[0]['original']['fields']['ID'],
                                 {'value': 'Native:formula-id', 'formula': '=A1'})

    def test_empty_and_styled_parser_rows_still_leave_no_record(self):
        for name in PARSER_TABS:
            with self.subTest(source=name):
                tables = source_tables(name, {'userEnteredValue': {'stringValue': 'valid-id'}})
                tables[name][-1] = []
                tables[name].extend([[{'format': '0%'}], [], [{'value': ''}]])
                records, _ = inputs_from_tables(tables)
                self.assertEqual(records, [])

    def test_legacy_rows_keep_their_declared_row_locator(self):
        expected = {
            'loyalty_partner_benefits': 'afa26d00e55b4f014625bbea55ab122714a41ba9ee7fac0f6eee22bf78ba7fd5',
            'yandex_discounts_complete_all': '9db9273312773b34207700ebaa3148440dd8bef013014e2108b13214fb3676ff',
            'VG_community_offers': 'da4766d0f21c871ecf0c86c6a005ea70c4946b0bae46e761a60126e0cffe592f',
        }
        tables = {tab: [[] for _ in range(header - 1)] + [
            [{'value': key} for key in HEADERS[tab]]]
            for tab, (header, _) in INPUT_TABS.items()}
        for name in expected:
            row = [{} for _ in HEADERS[name]]
            label = 'Партнёр / сервис' if name == 'loyalty_partner_benefits' else 'Service Name'
            row[HEADERS[name].index(label)] = {'value': 'Synthetic legacy offer'}
            tables[name].append(row)
        records, _ = inputs_from_tables(tables)
        self.assertEqual({record['origin']: record['id'] for record in records}, expected)


class SourceIdPublicationTests(unittest.TestCase):
    def test_invalid_native_id_stops_the_real_pipeline_before_any_write(self):
        for name in PARSER_TABS:
            for cell in INVALID_CELLS:
                with self.subTest(source=name, cell=cell):
                    client = NativeIdClient(name, cell)
                    before = copy.deepcopy(client.tabs)
                    with self.assertRaisesRegex(ValueError, 'Invalid explicit source ID'), contextlib.redirect_stdout(io.StringIO()):
                        publish_all(as_of='2026-11-08', client=client)
                    self.assertEqual(client.tabs, before)
                    self.assertTrue(all(method == 'GET' for method, _ in client.calls))

    def test_bad_id_cannot_retire_previously_published_terms(self):
        for name in PARSER_TABS:
            with self.subTest(source=name):
                client = NativeIdClient(name, {'userEnteredValue': {'stringValue': 'Native:existing-id'}})
                with contextlib.redirect_stdout(io.StringIO()):
                    publish_all(as_of='2026-11-08', client=client)
                client.id_cell = {}
                client.calls.clear()
                before = copy.deepcopy(client.tabs)
                with self.assertRaisesRegex(ValueError, 'Invalid explicit source ID'), contextlib.redirect_stdout(io.StringIO()):
                    publish_all(as_of='2026-11-08', client=client)
                self.assertEqual(client.tabs, before)
                self.assertTrue(all(method == 'GET' for method, _ in client.calls))


if __name__ == '__main__':
    unittest.main()
