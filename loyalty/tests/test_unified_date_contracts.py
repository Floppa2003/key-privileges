"""Explicit source intervals and normalization dates must have valid contracts."""
import contextlib
import copy
import io
import json
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parents[1]))
from unified_inputs import HEADERS, read_tables
from unified_normalization import make_input, normalize_inputs, normalize_record
from unified_publish import main, publish_all
from unified_views import SCHEMAS
from test_unified_live import FakeUnified


def legacy_row(validity, origin='yandex_discounts_complete_all'):
    return {
        'id': 'synthetic:date-contract', 'origin': origin, 'row': 2,
        'fields': {
            'Service Name': {'value': 'Synthetic date offer'},
            'Discount': {'value': 'Discount 10%'},
            'Validity': {'value': validity},
        },
    }


def parser_row():
    values = {
        'ID': 'synthetic:parser-date-contract',
        'Программа': 'Synthetic program', 'Партнёр': 'Synthetic partner',
        'Заголовок': 'Synthetic offer', 'Тип записи': 'partner_offer',
        'Выгода': 'Скидка 10%', 'Начало': '2024-02-01', 'Окончание': '2024-03-31',
    }
    return {
        'id': 'synthetic:parser-date-contract', 'origin': 'parser_offers', 'row': 2,
        'fields': {name: {'value': value} for name, value in values.items()},
    }


class LegacyIntervalContractTests(unittest.TestCase):
    def test_invalid_explicit_endpoint_is_not_an_open_interval(self):
        for origin in ('yandex_discounts_complete_all', 'VG_community_offers'):
            for validity in (
                '2026-02-30 to 2026-12-31',
                '2026-01-01 to 2026-02-30',
                '2026-13-01 – 2026-12-31',
                '2026-01-01 — 0000-12-31',
            ):
                with self.subTest(origin=origin, validity=validity):
                    with self.assertRaises(ValueError):
                        make_input(legacy_row(validity, origin))

    def test_valid_explicit_interval_preserves_bounds_and_source(self):
        for origin in ('yandex_discounts_complete_all', 'VG_community_offers'):
            for separator in ('to', '–', '—'):
                with self.subTest(origin=origin, separator=separator):
                    validity = f'2024-02-29 {separator} 2024-03-01'
                    source = legacy_row(validity, origin)
                    before = copy.deepcopy(source)
                    result = make_input(source)
                    self.assertEqual(result['valid_from'], '2024-02-29')
                    self.assertEqual(result['valid_until'], '2024-03-01')
                    self.assertEqual(result['validity_raw'], validity)
                    self.assertEqual(result['original'], before)
                    self.assertEqual(source, before)

    def test_free_form_and_absent_validity_remain_unknown(self):
        for validity in (None, '', 'Дата будет объявлена', '2026-02-30'):
            with self.subTest(validity=validity):
                source = make_input(legacy_row(validity))
                result = normalize_record(source, as_of='2026-11-07')
                self.assertIsNone(source['valid_from'])
                self.assertIsNone(source['valid_until'])
                self.assertEqual(source['validity_raw'], validity)
                self.assertEqual(result['validity']['status'], 'unknown')

    def test_malformed_interval_stops_publication_before_any_write(self):
        for validity in (
            '2026-02-30 to 2026-12-31',
            '2026-01-01 to 2026-02-30',
        ):
            with self.subTest(validity=validity):
                client = FakeUnified()
                name = 'yandex_discounts_complete_all'
                client.tabs[name]['values'][-1][HEADERS[name].index('Validity')] = validity
                before = copy.deepcopy(client.tabs)
                with self.assertRaises(ValueError), contextlib.redirect_stdout(io.StringIO()):
                    publish_all(as_of='2026-11-07', client=client)
                self.assertEqual(client.tabs, before)
                self.assertFalse(set(client.tabs) & set(SCHEMAS))
                self.assertTrue(all(method == 'GET' for method, _ in client.calls))


class StructuredDateContractTests(unittest.TestCase):
    def test_invalid_structured_date_is_not_discarded(self):
        for column in ('Начало', 'Окончание'):
            for value in ('2026-02-30', '2026-11-07T25:00:00', 'not a date', False, 0, {}, []):
                with self.subTest(column=column, value=value):
                    source = parser_row()
                    source['fields'][column] = {'value': value}
                    before = copy.deepcopy(source)
                    with self.assertRaises(ValueError):
                        make_input(source)
                    self.assertEqual(source, before)

    def test_missing_and_blank_structured_dates_remain_absent(self):
        for column, field in (('Начало', 'valid_from'), ('Окончание', 'valid_until')):
            for atom in (None, {}, {'value': None}, {'value': ''}, {'value': ' \t\r\n'}):
                with self.subTest(column=column, atom=atom):
                    source = parser_row()
                    if atom is None:
                        del source['fields'][column]
                    else:
                        source['fields'][column] = copy.deepcopy(atom)
                    before = copy.deepcopy(source)
                    result = make_input(source)
                    self.assertIsNone(result[field])
                    self.assertEqual(result['original'], before)
                    self.assertEqual(source, before)

    def test_supported_structured_dates_preserve_raw_evidence(self):
        for column, field in (('Начало', 'valid_from'), ('Окончание', 'valid_until')):
            for value in (
                '2024-02-29', '29.02.2024', '29 Feb 2024',
                '2024-02-29 08:30:00', '2024-02-29T23:59:59Z',
                '2024-02-29T08:30:00.125+03:00', ' \t2024-02-29\n',
                45351, 45351.75,
            ):
                with self.subTest(column=column, value=value):
                    source = parser_row()
                    source['fields'][column] = {'value': value}
                    before = copy.deepcopy(source)
                    result = make_input(source)
                    self.assertEqual(result[field], '2024-02-29')
                    self.assertEqual(result['original'], before)
                    self.assertEqual(source, before)
                    normalized = normalize_record(result, as_of='2024-02-29')
                    self.assertEqual(normalized['validity']['status'], 'within_stated_period')

    def test_bad_structured_date_stops_publication_before_any_write(self):
        for column in ('Начало', 'Окончание'):
            with self.subTest(column=column):
                source = parser_row()
                source['fields'][column] = {'value': '2026-02-30'}
                client = FakeUnified()
                client.tabs['parser_offers']['values'].append([
                    source['fields'].get(name, {}).get('value', '')
                    for name in HEADERS['parser_offers']])
                before = copy.deepcopy(client.tabs)
                with self.assertRaises(ValueError), contextlib.redirect_stdout(io.StringIO()):
                    publish_all(as_of='2024-02-29', client=client)
                self.assertEqual(client.tabs, before)
                self.assertFalse(set(client.tabs) & set(SCHEMAS))
                self.assertTrue(all(method == 'GET' for method, _ in client.calls))


class TimestampOffsetContractTests(unittest.TestCase):
    invalid_offsets = (
        '+03:60', '-03:60', '+03:00:60', '+0360',
        '-030060', '+03:60.5', '+030060,5', '+24:00',
    )

    def test_legacy_offset_overflow_remains_unknown(self):
        for offset in self.invalid_offsets:
            with self.subTest(offset=offset):
                value = '2026-12-31T12:00:00' + offset
                source = legacy_row(value)
                before = copy.deepcopy(source)
                result = make_input(source)
                self.assertIsNone(result['valid_until'])
                self.assertEqual(result['validity_raw'], value)
                self.assertEqual(result['original'], before)
                self.assertEqual(source, before)
                normalized = normalize_record(result, as_of='2027-01-01')
                self.assertEqual(normalized['validity']['status'], 'unknown')

    def test_structured_offset_overflow_is_rejected(self):
        for column in ('Начало', 'Окончание'):
            for offset in self.invalid_offsets:
                with self.subTest(column=column, offset=offset):
                    source = parser_row()
                    source['fields'][column] = {'value': '2026-12-31T12:00:00' + offset}
                    before = copy.deepcopy(source)
                    with self.assertRaises(ValueError):
                        make_input(source)
                    self.assertEqual(source, before)

    def test_valid_timestamp_forms_keep_the_source_calendar_date(self):
        for value in (
            '2026-12-31T00:15:00+14:00',
            '2026-12-31T23:45:00-12:00',
            '2026-12-31T001500+1400',
            '2026-12-31T234500-1200',
            '2026-12-31T12+03',
            '2026-12-31T1200+0300',
            '2026-12-31T120000.125+030015.5',
            '2026-12-31T12:00:00,125+03:00:15,5',
            '2026-12-31T12:00:00+03.5',
            '2026-12-31T12:00:00+0300.5',
            '2026-12-31T12:00:00-235959.999999',
            '2026-12-31T120000Z',
            '2026-12-31T12:00:00',
        ):
            with self.subTest(value=value):
                source = legacy_row(value)
                before = copy.deepcopy(source)
                result = make_input(source)
                self.assertEqual(result['valid_until'], '2026-12-31')
                self.assertEqual(result['original'], before)
                self.assertEqual(source, before)
                normalized = normalize_record(result, as_of='2027-01-01')
                self.assertEqual(normalized['validity']['status'], 'expired')
                for column, field, status in (
                    ('Начало', 'valid_from', 'within_stated_period'),
                    ('Окончание', 'valid_until', 'expired'),
                ):
                    structured = parser_row()
                    structured['fields']['Начало'] = {'value': '2026-12-01'}
                    structured['fields']['Окончание'] = {'value': '2027-01-31'}
                    structured['fields'][column] = {'value': value}
                    original = copy.deepcopy(structured)
                    mapped = make_input(structured)
                    self.assertEqual(mapped[field], '2026-12-31')
                    self.assertEqual(mapped['original'], original)
                    self.assertEqual(structured, original)
                    normalized = normalize_record(mapped, as_of='2027-01-01')
                    self.assertEqual(normalized['validity']['status'], status)


class AsOfContractTests(unittest.TestCase):
    def test_record_rejects_noncanonical_or_invalid_as_of(self):
        source = make_input(legacy_row('2026-01-01 to 2026-12-31'))
        for as_of in (
            '20261107', '2026-W45-6', '', '2026-11-7',
            '2026-11-07T00:00:00', ' 2026-11-07', '2026-11-07\n',
            '2026-02-29', '2026-13-07', '0000-01-01',
        ):
            with self.subTest(as_of=as_of):
                with self.assertRaises(ValueError):
                    normalize_record(source, as_of=as_of)

    def test_empty_bundle_still_rejects_bad_as_of(self):
        for as_of in ('20261107', '2026-W45-6', '2026-02-29', ''):
            with self.subTest(as_of=as_of):
                with self.assertRaises(ValueError):
                    normalize_inputs([], as_of=as_of)

    def test_public_filter_cannot_bypass_as_of_validation(self):
        source = make_input(legacy_row('2026-01-01 to 2026-12-31'))
        with self.assertRaises(ValueError):
            normalize_inputs([source], as_of='20261107', public_only=True)

    def test_canonical_as_of_keeps_inclusive_interval_boundaries(self):
        source = make_input(legacy_row('2024-02-29 to 2024-03-01'))
        for as_of, status in (
            ('2024-02-28', 'not_started'),
            ('2024-02-29', 'within_stated_period'),
            ('2024-03-01', 'within_stated_period'),
            ('2024-03-02', 'expired'),
        ):
            with self.subTest(as_of=as_of):
                result = normalize_inputs([source], as_of=as_of)
                self.assertEqual(result['as_of'], as_of)
                self.assertEqual(result['records'][0]['validity'], {
                    'from': '2024-02-29', 'until': '2024-03-01',
                    'as_of': as_of, 'status': status,
                })

    def test_empty_bundle_keeps_valid_canonical_as_of(self):
        result = normalize_inputs([], as_of='2024-02-29')
        self.assertEqual(result['as_of'], '2024-02-29')
        self.assertEqual(result['records'], [])


class AsOfCallerContractTests(unittest.TestCase):
    def test_explicit_bad_publication_date_stops_before_any_write(self):
        for as_of in ('', False, '20261107', '2026-W45-6'):
            with self.subTest(as_of=as_of):
                client = FakeUnified()
                before = copy.deepcopy(client.tabs)
                with self.assertRaises(ValueError), contextlib.redirect_stdout(io.StringIO()):
                    publish_all(as_of=as_of, client=client)
                self.assertEqual(client.tabs, before)
                self.assertFalse(set(client.tabs) & set(SCHEMAS))
                self.assertTrue(all(method == 'GET' for method, _ in client.calls))

    def test_omitted_or_none_publication_date_defaults_to_today(self):
        for arguments in ({}, {'as_of': None}):
            with self.subTest(arguments=arguments):
                client = FakeUnified()
                with patch('unified_publish.datetime') as clock, contextlib.redirect_stdout(io.StringIO()):
                    clock.now.return_value = datetime(2026, 11, 7, 12, tzinfo=timezone.utc)
                    result = publish_all(client=client, **arguments)
                self.assertEqual(result['as_of'], '2026-11-07')
                self.assertEqual(result['records'][0]['validity']['as_of'], '2026-11-07')
                manifest = next(row for row in client.tabs['normalization_audit']['values']
                                if row and row[0] == 'manifest')
                self.assertEqual(manifest[4], 'verified')

    def test_offline_cli_explicit_bad_date_creates_no_output(self):
        for as_of in ('', '20261107', '2026-W45-6'):
            with self.subTest(as_of=as_of), tempfile.TemporaryDirectory() as folder:
                source = Path(folder) / 'source.json'
                source.write_text(json.dumps({'sheets': read_tables(FakeUnified())}), encoding='utf8')
                before = source.read_bytes()
                output = Path(folder) / 'output'
                arguments = ['unified_publish.py', '--offline-input', str(source),
                             '--out', str(output), '--as-of', as_of]
                with patch('sys.argv', arguments), self.assertRaises(ValueError), contextlib.redirect_stdout(io.StringIO()):
                    main()
                self.assertFalse(output.exists())
                self.assertEqual(source.read_bytes(), before)

    def test_offline_cli_omitted_date_defaults_to_today(self):
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / 'source.json'
            source.write_text(json.dumps({'sheets': read_tables(FakeUnified())}), encoding='utf8')
            before = source.read_bytes()
            output = Path(folder) / 'output'
            arguments = ['unified_publish.py', '--offline-input', str(source), '--out', str(output)]
            with patch('sys.argv', arguments), patch('unified_publish.datetime') as clock, contextlib.redirect_stdout(io.StringIO()):
                clock.now.return_value = datetime(2026, 11, 7, 12, tzinfo=timezone.utc)
                main()
            result = json.loads((output / 'normalized.json').read_text(encoding='utf8'))
            self.assertEqual(result['as_of'], '2026-11-07')
            self.assertEqual(result['records'][0]['validity']['as_of'], '2026-11-07')
            self.assertEqual(source.read_bytes(), before)


if __name__ == '__main__':
    unittest.main()
