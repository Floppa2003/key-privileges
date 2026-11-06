"""Sheets percent semantics at the native-cell/common-input boundary."""
import copy
import sys
import unittest
from decimal import InvalidOperation
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1]))
from unified_inputs import atom_from_cell, clean_atom, HEADERS, inputs_from_tables, read_tables
from unified_normalization import INPUT_TABS, make_input, normalize_record


def input_from_cell(cell):
    return make_input({'id': 'synthetic-format', 'origin': 'VG_community_offers',
                       'row': 5, 'fields': {
                           'Service Name': {'value': 'Synthetic merchant'},
                           'Discount': clean_atom(atom_from_cell(cell)),
                       }})


def numeric_cell(value, pattern, *, kind='NUMBER'):
    return {'userEnteredValue': {'numberValue': value},
            'userEnteredFormat': {'numberFormat': {'type': kind, 'pattern': pattern}}}


class NumberFormatTests(unittest.TestCase):
    def test_literal_percent_does_not_scale_native_number(self):
        for pattern in ('0"%"', r'0\%', '0_%', '"Discount % "0.0'):
            with self.subTest(pattern=pattern):
                raw = input_from_cell(numeric_cell(.2, pattern))
                self.assertEqual(raw['benefit'], '0.2')
                self.assertEqual(raw['original']['fields']['Discount']['value'], .2)
                self.assertEqual(normalize_record(raw, as_of='2026-11-06')['benefits'], [])

    def test_effective_format_supplies_formula_percent_semantics(self):
        cell = {'userEnteredValue': {'formulaValue': '=1/5'},
                'effectiveValue': {'numberValue': .2}, 'formattedValue': '90%',
                'effectiveFormat': {'numberFormat': {'type': 'PERCENT', 'pattern': '0%'}}}
        before = copy.deepcopy(cell)
        raw = input_from_cell(cell)
        self.assertEqual(raw['benefit'], 'Discount 20%')
        self.assertEqual(raw['original']['fields']['Discount'],
                         {'value': .2, 'formula': '=1/5', 'format': '%'})
        self.assertEqual(cell, before)
        benefits = normalize_record(raw, as_of='2026-11-06')['benefits']
        self.assertEqual([(b['kind'], b['value'], b['unit']) for b in benefits],
                         [('discount', '20', 'percent')])

    def test_percent_type_without_pattern_uses_its_default(self):
        for field in ('userEnteredFormat', 'effectiveFormat'):
            with self.subTest(field=field):
                cell = {'userEnteredValue': {'numberValue': .2},
                        field: {'numberFormat': {'type': 'PERCENT'}}}
                self.assertEqual(input_from_cell(cell)['benefit'], 'Discount 20%')

    def test_effective_format_overrides_entered_format(self):
        cases = [
            ({'type': 'PERCENT', 'pattern': '0%'},
             {'type': 'NUMBER', 'pattern': '0.0'}, '0.2'),
            ({'type': 'NUMBER', 'pattern': '0.0'},
             {'type': 'PERCENT', 'pattern': '0%'}, 'Discount 20%'),
            ({'type': 'PERCENT', 'pattern': '0%'},
             {'type': 'NUMBER'}, '0.2'),
        ]
        for entered, effective, expected in cases:
            with self.subTest(entered=entered, effective=effective):
                cell = {'userEnteredValue': {'numberValue': .2},
                        'userEnteredFormat': {'numberFormat': entered},
                        'effectiveFormat': {'numberFormat': effective}}
                self.assertEqual(input_from_cell(cell)['benefit'], expected)

    def test_boolean_is_preserved_without_percentage_conversion(self):
        for value in (True, False):
            with self.subTest(value=value):
                cell = {'userEnteredValue': {'boolValue': value},
                        'userEnteredFormat': {'numberFormat': {'type': 'PERCENT', 'pattern': '0%'}}}
                try:
                    raw = input_from_cell(cell)
                except InvalidOperation:
                    self.fail('Boolean reached Decimal percentage conversion')
                self.assertIs(raw['original']['fields']['Discount']['value'], value)
                self.assertEqual(raw['benefit'], str(value))
                self.assertEqual(normalize_record(raw, as_of='2026-11-06')['benefits'], [])

    def test_direct_input_does_not_treat_boolean_as_numeric(self):
        for value in (True, False):
            with self.subTest(value=value):
                row = {'id': 'boolean', 'origin': 'VG_community_offers', 'row': 5,
                       'fields': {'Discount': {'value': value, 'format': '%'}}}
                try:
                    raw = make_input(row)
                except InvalidOperation:
                    self.fail('Direct boolean input reached Decimal percentage conversion')
                self.assertEqual(raw['benefit'], str(value))
                self.assertEqual(raw['original'], row)

    def test_percent_in_other_numeric_section_does_not_scale_value(self):
        cases = [
            (.2, '0.00;0%', '0.2'),
            (0, '0.00;0%', '0'),
            (0, '0%;0.00', 'Discount 0%'),
            (0, '0;0%;@', '0'),
            (0, '0%;0;@', 'Discount 0%'),
            (-.2, '0%;0.00;0%', '-0.2'),
            (0, '0%;0%;0', '0'),
            (.2, '0%;0.00;0', 'Discount 20%'),
        ]
        for value, pattern, expected in cases:
            with self.subTest(value=value, pattern=pattern):
                self.assertEqual(input_from_cell(numeric_cell(value, pattern))['benefit'], expected)

    def test_date_and_time_literal_percent_is_not_numeric_percentage(self):
        for kind, pattern in (('DATE', 'yyyy%'), ('TIME', 'hh:mm%'),
                              ('DATE_TIME', 'yyyy-mm-dd hh:mm%')):
            with self.subTest(kind=kind):
                raw = input_from_cell(numeric_cell(.2, pattern, kind=kind))
                self.assertEqual(raw['benefit'], '0.2')
                self.assertEqual(raw['original']['fields']['Discount']['value'], .2)
                self.assertEqual(normalize_record(raw, as_of='2026-11-06')['benefits'], [])

    def test_text_section_percent_does_not_scale_numeric_value(self):
        for pattern in ('0.0;0.0;0.0;"Rate %: "@', '0.0;"Rate %: "@'):
            with self.subTest(pattern=pattern):
                self.assertEqual(input_from_cell(numeric_cell(.2, pattern))['benefit'], '0.2')

    def test_literal_semicolon_does_not_change_active_section(self):
        cases = [
            ('0.0";"%', 'Discount 20%'),
            (r'0.0\;%', 'Discount 20%'),
            (r'0.0\;;0%', '0.2'),
            ('0.0";%";0%', '0.2'),
        ]
        for pattern, expected in cases:
            with self.subTest(pattern=pattern):
                self.assertEqual(input_from_cell(numeric_cell(.2, pattern))['benefit'], expected)

    def test_fill_character_percent_is_literal(self):
        cases = [('0*%', '0.2'), ('0*%%', 'Discount 20%'),
                 ('0*;% ', 'Discount 20%'), ('0*;;0%', '0.2')]
        for pattern, expected in cases:
            with self.subTest(pattern=pattern):
                self.assertEqual(input_from_cell(numeric_cell(.2, pattern))['benefit'], expected)

    def test_color_and_uniform_conditional_formats_keep_percent(self):
        for pattern in ('[Red]0%;[Blue]0%;0%',
                        '[>1]0%;[<=1]0%;0%', '[>1]0%;0%'):
            with self.subTest(pattern=pattern):
                self.assertEqual(input_from_cell(numeric_cell(.2, pattern))['benefit'], 'Discount 20%')

    def test_conditional_sections_use_first_match_then_fallback(self):
        cases = [
            (.2, '[>1]0%;[<0]0%;0.0', '0.2'),
            (.2, '[>0]0%;[<0]0.0;0.0', 'Discount 20%'),
            (.2, '[>0]0.0;[<1]0%;0.0', '0.2'),
            (.2, '[>1]0%;[<-1]0%', '0.2'),
            (0, '[>0]0.0;[<0]0.0;0%', 'Discount 0%'),
            (.2, '[>=0.2]0.0;[<0.2]0%;0%', '0.2'),
            (.2, '[=0.20]0.0;[<>0.20]0%;0%', '0.2'),
            (.2, '[=0.1]0.0;[<>0.1]0%;0.0', 'Discount 20%'),
        ]
        for value, pattern, expected in cases:
            with self.subTest(value=value, pattern=pattern):
                self.assertEqual(input_from_cell(numeric_cell(value, pattern))['benefit'], expected)

    def test_offline_canonical_percent_atoms_remain_compatible(self):
        for pattern in ('%', '0%', '0.00%'):
            with self.subTest(pattern=pattern):
                self.assertEqual(clean_atom({'value': .2, 'format': pattern}),
                                 {'value': .2, 'format': '%'})
        cell = {'userEnteredValue': {'stringValue': '20%'},
                'userEnteredFormat': {'numberFormat': {'type': 'PERCENT', 'pattern': '0%'}}}
        self.assertEqual(input_from_cell(cell)['benefit'], '20%')


class NativeFormatReadTests(unittest.TestCase):
    def test_read_tables_requests_effective_format_for_formula_cell(self):
        class CellsClient:
            def metadata(self):
                return {name: {'gridProperties': {'rowCount': header + 1, 'columnCount': width}}
                        for name, (header, width) in INPUT_TABS.items()}

            def request(self, method, *, params):
                self_test.assertEqual(method, 'GET')
                name = params['ranges'].split('!')[0].strip("'")
                header = INPUT_TABS[name][0]
                rows = [[] for _ in range(header - 1)] + [[
                    {'userEnteredValue': {'stringValue': text}} for text in HEADERS[name]]]
                if name == 'VG_community_offers':
                    row = [{} for _ in HEADERS[name]]
                    row[1] = {'userEnteredValue': {'stringValue': 'Synthetic merchant'}}
                    row[4] = {'userEnteredValue': {'formulaValue': '=1/5'},
                              'effectiveValue': {'numberValue': .2}}
                    # Emulate the API's fields projection at the HTTP boundary.
                    if 'effectiveFormat.numberFormat' in params['fields']:
                        row[4]['effectiveFormat'] = {
                            'numberFormat': {'type': 'PERCENT', 'pattern': '0%'}}
                    rows.append(row)
                return {'sheets': [{'properties': {'title': name}, 'data': [
                    {'startRow': 0, 'startColumn': 0,
                     'rowData': [{'values': row} for row in rows]}]}]}

        self_test = self
        inputs, _ = inputs_from_tables(read_tables(CellsClient()))
        self.assertEqual(len(inputs), 1)
        self.assertEqual(inputs[0]['benefit'], 'Discount 20%')
        self.assertEqual(inputs[0]['original']['fields']['Discount']['formula'], '=1/5')


if __name__ == '__main__':
    unittest.main()
