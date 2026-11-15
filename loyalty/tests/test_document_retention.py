"""Retain real public PDF metadata through the actual Sheets publisher.

Only Google HTTP is replaced. The UniCredit source PDF, its extraction,
publication scope and the document-catalogue reader all run unchanged.
"""
import copy
import io
import json
import os
from pathlib import Path
import re
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch
from urllib.parse import unquote

import requests

sys.path.insert(0, str(Path(__file__).parents[1]))
import sheets_normalized as publication
from document_catalogue import build_documents, read_archived_documents
from document_text import document_records, extract_pdf
from rzd_external import BANK, bank_pdf_records
from unified_inputs import HEADERS as INPUT_HEADERS

ARCHIVE = 'parser_documents_archive'
ARCHIVE_HEADERS = INPUT_HEADERS['parser_offers'] + [
    'Исходная строка parser_offers', 'Архивировано UTC']
SHA = 'c9db3bc59fea0645579888f4d1a453c1b5089a7accf601878c66ebfc155f2610'
URL = 'https://www.unicreditbank.ru/content/dam/cee2020-pws-ru/banking/primeclub/CashBackRules.pdf'
NOW = '2026-11-15T12:00:00+00:00'
RGO_SHA = '905bb3b03f3b98709054b14c5ae08974a6f7be775857819cf8cd2cb688be683b'
RGO_URL = ('https://rgo.ru/upload/medialibrary/2ed/jm89ty2fg8j8an3g362l5uq6lij95owe/'
           'Moya_Kompaniya_RGO_belaya_20.01.26.pdf')


class HttpResponse:
    status_code = 200

    def __init__(self, value):
        self.value = value

    def json(self):
        return copy.deepcopy(self.value)


class WorkbookHTTP:
    """A small native-values HTTP boundary, including atomic append semantics."""
    def __init__(self):
        self.tabs = {}
        self.writes = []
        self.add('parser_offers', 10, 26, [INPUT_HEADERS['parser_offers']])
        self.add('parser_coverage', 11, 15,
                 [publication.SCHEMAS['parser_coverage'] + ['Ручной комментарий']])
        self.add('_ui_catalog', 12, 26, [])
        self.add(ARCHIVE, 13, 28, [ARCHIVE_HEADERS], hidden=True)

    def add(self, title, ident, width, rows, *, hidden=False):
        self.tabs[title] = {'properties': {'title': title, 'sheetId': ident,
            'hidden': hidden, 'gridProperties': {'rowCount': 5000, 'columnCount': width}},
            'values': copy.deepcopy(rows)}

    @staticmethod
    def column(value):
        result = 0
        for char in value:
            result = result * 26 + ord(char) - 64
        return result - 1

    def request(self, method, url, **kwargs):
        suffix = url.split('/spreadsheets/fixture-sheet', 1)[1]
        if method == 'GET' and not suffix:
            rows = []
            fields = kwargs.get('params', {}).get('fields', '')
            for table in self.tabs.values():
                props = copy.deepcopy(table['properties'])
                if 'hidden' not in fields:
                    props.pop('hidden')
                rows.append({'properties': props})
            return HttpResponse({'sheets': rows})
        if method == 'GET' and suffix.startswith('/values/'):
            a1 = unquote(suffix[len('/values/'):])
            match = re.fullmatch(r"'([^']+)'!([A-Z]+)(\d+):([A-Z]+)(\d+)", a1)
            if not match:
                raise AssertionError('Unexpected values range: ' + a1)
            title, left, top, right, bottom = match.groups()
            start, end = self.column(left), self.column(right) + 1
            values = []
            for row in self.tabs[title]['values'][int(top)-1:int(bottom)]:
                value = copy.deepcopy(row[start:end])
                while value and value[-1] == '':
                    value.pop()
                values.append(value)
            while values and not values[-1]:
                values.pop()
            return HttpResponse({'values': values})
        if method != 'POST' or suffix != ':batchUpdate':
            raise AssertionError('Unexpected Sheets HTTP operation')
        for operation in kwargs['json']['requests']:
            if 'setBasicFilter' in operation:
                continue
            kind = next(iter(operation))
            value = operation[kind]
            position = value.get('range') or value.get('start') or value
            table = next(table for table in self.tabs.values()
                         if table['properties']['sheetId'] == position['sheetId'])
            title = table['properties']['title']
            if not title.startswith('parser_'):
                raise AssertionError('Write escaped parser sheets')
            self.writes.append((title, kind))
            if kind == 'appendDimension':
                table['properties']['gridProperties']['rowCount'] += value['length']
                continue
            if kind == 'appendCells':
                start = len(table['values'])
                column = 0
            elif kind == 'updateCells':
                start = position.get('startRowIndex', position.get('rowIndex', 0))
                column = position.get('startColumnIndex', position.get('columnIndex', 0))
            else:
                raise AssertionError('Unexpected Sheets mutation: ' + kind)
            for offset, row in enumerate(value['rows']):
                index = start + offset
                while len(table['values']) <= index:
                    table['values'].append([])
                cells = [cell.get('userEnteredValue', {}).get('stringValue', '')
                         for cell in row['values']]
                target = table['values'][index]
                target.extend([''] * max(0, column + len(cells) - len(target)))
                target[column:column+len(cells)] = cells
        return HttpResponse({})


class DocumentRetentionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        data = (Path(__file__).parents[2] / 'source-documents' / (SHA + '.pdf')).read_bytes()
        cls.records = bank_pdf_records(data, {'url': URL, 'label': 'Правила Программы лояльности'},
            {'id': 'public-parent-reference', 'content_sha256': None}, NOW)
        cls.bundle = {'schema_version': 2, 'run_id': 'retention-review:1',
            'observed_at': NOW, 'records': cls.records, 'sources': [{
                'source_id': 'rzd_unicredit_rules',
                'name': 'РЖД Бонус — связанные правила ЮниКредита', 'root': BANK,
                'status': 'ok', 'discovered': len(cls.records), 'normalized': len(cls.records),
                'failed': 0, 'errors': [], 'coverage': 'public document retention test',
                'region': None, 'observed_at': NOW}]}
        cls.prepared = publication.prepare(cls.bundle)['parser_offers']
        data = (Path(__file__).parents[2] / 'source-documents' / (RGO_SHA + '.pdf')).read_bytes()
        rgo = document_records('rgo', 'pdf:source-retention', 'Программа лояльности членов РГО',
            None, RGO_URL, NOW, extract_pdf(data, allow_ocr=False),
            parent_source='https://rgo.ru/membership/loyalty-program/',
            label='Специальные тарифные условия для членов РГО со скидкой до 35%')
        cls.practical_bundle = {'schema_version': 2, 'run_id': 'retention-rgo:1',
            'observed_at': NOW, 'records': rgo, 'sources': [{
                'source_id': 'rgo', 'name': 'Программа лояльности членов РГО',
                'root': 'https://rgo.ru/membership/loyalty-program/',
                'status': 'partial', 'discovered': len(rgo), 'normalized': len(rgo),
                'failed': 1, 'errors': [{'reason': 'document_text_partial'}],
                'coverage': 'public document retention test', 'region': None, 'observed_at': NOW}]}

    def publish(self, memory, payload=None):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'normalized.json'
            path.write_text(json.dumps(payload or self.bundle), encoding='utf-8')
            def request(_session, method, url, **kwargs):
                return memory.request(method, url, **kwargs)
            with patch.object(requests.sessions.Session, 'request', request), \
                 patch.dict(os.environ, {'DISCOUNTS_SPREADSHEET_ID': 'fixture-sheet',
                                         'GOOGLE_ACCESS_TOKEN': 'fixture-token'}), \
                 patch.object(sys, 'argv', ['sheets_normalized.py', '--input', str(path), '--publish']), \
                 redirect_stdout(io.StringIO()):
                publication.main()
                reader = publication.NormalizedSheets('fixture-sheet', 'fixture-token')
                return build_documents(read_archived_documents(reader))

    def test_real_bulk_pdf_remains_in_document_catalogue_after_offer_scope_filters_it(self):
        memory = WorkbookHTTP()
        manual = [''] * 25 + ['Архивная заметка владельца']
        memory.tabs[ARCHIVE]['values'].append(manual.copy())
        documents = self.publish(memory)
        self.assertEqual(len(documents), 1)
        self.assertEqual(documents[0][0], 'ЮниКредит Банк')
        self.assertEqual(documents[0][8], SHA)
        self.assertEqual(documents[0][4], URL)
        self.assertEqual(memory.tabs['parser_offers']['values'], [INPUT_HEADERS['parser_offers']])
        self.assertEqual(memory.tabs[ARCHIVE]['values'][1], manual)
        retained = memory.tabs[ARCHIVE]['values'][2:]
        self.assertEqual(len(retained), 4)
        for row in retained:
            self.assertTrue(all(not row[index] for index in (7, 8, 9, 10, 11, 25)))
            details = json.loads(row[20])
            self.assertEqual(details['document_sha256'], SHA)
            self.assertNotIn('pages', details)
        before = copy.deepcopy(memory.tabs[ARCHIVE])
        self.publish(memory)
        self.assertEqual(memory.tabs[ARCHIVE], before)

    def test_previous_pdf_version_is_retained_before_the_same_offer_id_is_updated(self):
        memory = WorkbookHTTP()
        current = publication.prepare(self.practical_bundle)['parser_offers'][0]
        previous = copy.deepcopy(current)
        details = json.loads(previous[20])
        # Both digests name real originals. Their association with one row ID is
        # a storage-state transition, not a claim about successive source terms.
        details['document_sha256'] = SHA
        previous[20] = json.dumps(details)
        previous[22] = '2026-09-14T13:52:41.717848+00:00'
        memory.tabs['parser_offers']['values'].append(previous + ['Личная заметка'])
        documents = self.publish(memory, self.practical_bundle)
        self.assertEqual({row[8] for row in documents}, {SHA, RGO_SHA})
        actual = memory.tabs['parser_offers']['values'][1]
        self.assertEqual(actual[:25], current)
        self.assertEqual(actual[25], 'Личная заметка')
        retained = memory.tabs[ARCHIVE]['values'][1:]
        old = next(row for row in retained if json.loads(row[20])['document_sha256'] == SHA)
        self.assertEqual(old[22], previous[22])
        self.assertEqual(old[26], '2')
        archive_write = next(i for i, entry in enumerate(memory.writes) if entry[0] == ARCHIVE)
        offer_write = next(i for i, entry in enumerate(memory.writes) if entry[0] == 'parser_offers')
        self.assertLess(archive_write, offer_write)

    def test_reobserved_bulk_pdf_refreshes_metadata_without_growing_or_rewriting_legacy(self):
        memory = WorkbookHTTP()
        legacy = self.prepared[0] + ['Архивная заметка владельца', '2', NOW]
        memory.tabs[ARCHIVE]['values'].append(copy.deepcopy(legacy))
        self.publish(memory)
        first = copy.deepcopy(memory.tabs[ARCHIVE]['values'])
        newest = '2026-11-16T12:00:00+00:00'
        incoming = copy.deepcopy(self.bundle)
        incoming['observed_at'] = newest
        incoming['run_id'] = 'retention-review:2'
        for record in incoming['records']:
            record['observed_at'] = newest
        for report in incoming['sources']:
            report['observed_at'] = newest
        memory.tabs[ARCHIVE]['values'][-1][25] = 'Комментарий к сохранённой копии'
        documents = self.publish(memory, incoming)
        after = copy.deepcopy(memory.tabs[ARCHIVE]['values'])
        self.assertEqual(documents[0][6], newest)
        self.assertEqual(after[1], legacy)
        self.assertEqual(len(after), len(first))
        self.assertEqual(after[-1][25], 'Комментарий к сохранённой копии')
        self.assertEqual([row[27] for row in after[2:]], [row[27] for row in first[2:]])
        self.publish(memory, incoming)
        self.assertEqual(memory.tabs[ARCHIVE]['values'], after)
        # A delayed older run cannot roll the last successful observation back.
        self.publish(memory)
        self.assertEqual(memory.tabs[ARCHIVE]['values'], after)


if __name__ == '__main__':
    unittest.main()
