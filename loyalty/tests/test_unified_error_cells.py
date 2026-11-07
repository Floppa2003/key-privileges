"""Native error results must not disappear as blank or unmapped source cells."""
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
from unified_views import SCHEMAS
from test_unified_live import FakeUnified


def source_tables():
    return {name: [[] for _ in range(header - 1)] + [
        [{'value': field} for field in HEADERS[name]]]
        for name, (header, _) in INPUT_TABS.items()}


def native_error():
    # Calculated output cells can have an effective error without an entered
    # value or formula in that cell. Keep the real CellData conversion here.
    return {'effectiveValue': {'errorValue': {
        'type': 'N_A', 'message': 'Synthetic calculated output error'}}}


class ErrorCellInputTests(unittest.TestCase):
    def test_error_only_row_is_not_an_empty_source(self):
        for name in INPUT_TABS:
            with self.subTest(source=name):
                tables = source_tables()
                tables[name].append([atom_from_cell(native_error())])
                with self.assertRaisesRegex(ValueError, 'Source error cell requires review'):
                    inputs_from_tables(tables)

    def test_error_only_middle_row_is_not_skipped_between_records(self):
        tables = source_tables()
        tables['yandex_discounts_complete_all'].extend([
            [{'value': 'First merchant'}],
            [atom_from_cell(native_error())],
            [{'value': 'Second merchant'}],
        ])
        with self.assertRaisesRegex(ValueError, 'Source error cell requires review'):
            inputs_from_tables(tables)

    def test_trailing_error_survives_removal_of_styled_empty_rows(self):
        tables = source_tables()
        tables['yandex_discounts_complete_all'].extend([
            [{'value': 'Synthetic merchant'}],
            [atom_from_cell(native_error())],
            [{'format': '0%'}], [],
        ])
        with self.assertRaisesRegex(ValueError, 'Source error cell requires review'):
            inputs_from_tables(tables)

    def test_unmapped_error_next_to_valid_values_is_not_discarded(self):
        tables = source_tables()
        width = INPUT_TABS['yandex_discounts_complete_all'][1]
        tables['yandex_discounts_complete_all'].append(
            [{'value': 'Synthetic merchant'}] + [{}] * (width - 1) +
            [atom_from_cell(native_error())])
        with self.assertRaisesRegex(ValueError, 'Unmapped populated source column'):
            inputs_from_tables(tables)

    def test_unmapped_error_only_trailing_row_is_not_trimmed(self):
        tables = source_tables()
        width = INPUT_TABS['yandex_discounts_complete_all'][1]
        tables['yandex_discounts_complete_all'].extend([
            [{'value': 'Synthetic merchant'}],
            [{}] * width + [atom_from_cell(native_error())],
            [{'format': 'General'}],
        ])
        with self.assertRaisesRegex(ValueError, 'Unmapped populated source column'):
            inputs_from_tables(tables)

    def test_formatting_and_false_error_flag_still_leave_empty_rows_empty(self):
        tables = source_tables()
        tables['yandex_discounts_complete_all'].append([{'value': 'Synthetic merchant'}])
        padded = copy.deepcopy(tables)
        for rows in padded.values():
            rows.extend([[{'format': '0%'}], [{'error': False}], []])
        self.assertEqual(inputs_from_tables(padded), inputs_from_tables(tables))

    def test_formula_error_still_rejects_the_source(self):
        tables = source_tables()
        cell = native_error()
        cell['userEnteredValue'] = {'formulaValue': '=NA()'}
        tables['yandex_discounts_complete_all'].append([atom_from_cell(cell)])
        with self.assertRaisesRegex(ValueError, 'Source error cell requires review'):
            inputs_from_tables(tables)


class ErrorResultClient(FakeUnified):
    """Use the complete in-memory publisher with native errors at its HTTP edge."""
    def __init__(self, *, unmapped=False):
        super().__init__()
        self.unmapped = unmapped
        if unmapped:
            self.tabs['yandex_discounts_complete_all']['properties']['gridProperties']['columnCount'] += 1

    def request(self, method, suffix='', **kwargs):
        result = super().request(method, suffix, **kwargs)
        source_range = kwargs.get('params', {}).get('ranges', '')
        if method == 'GET' and source_range.startswith("'yandex_discounts_complete_all'!"):
            cells = [{}] * INPUT_TABS['yandex_discounts_complete_all'][1] if self.unmapped else []
            result['sheets'][0]['data'][0]['rowData'].append({'values': cells + [native_error()]})
        return result


class ErrorCellPublicationTests(unittest.TestCase):
    def test_error_result_stops_publication_before_any_destination_change(self):
        for unmapped in (False, True):
            with self.subTest(unmapped=unmapped):
                client = ErrorResultClient(unmapped=unmapped)
                before = copy.deepcopy(client.tabs)
                with self.assertRaises(ValueError), contextlib.redirect_stdout(io.StringIO()):
                    publish_all(as_of='2026-11-07', client=client)
                self.assertEqual(client.tabs, before)
                self.assertFalse(set(client.tabs) & set(SCHEMAS))
                self.assertTrue(all(method == 'GET' for method, _ in client.calls))


if __name__ == '__main__':
    unittest.main()
