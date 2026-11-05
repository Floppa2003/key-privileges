"""Same live PDF aliases can have different recoverable OCR outcomes."""
import asyncio
import hashlib
import io
import json
import subprocess
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

from pypdf import PdfReader, PdfWriter

sys.path.insert(0, str(Path(__file__).parents[1]))
import utair_documents as m
from document_text import extract_pdf
from normalized import validate_offer
from test_document_images import image_pdf
from test_document_text import NOW
from test_utair_direct_discovery import Response

SHORT = 'https://ut0.ru/ExistingLink'
DOWNLOAD = 'https://eu-s3.beelinecloud.ru/utair-log/original.pdf'
DIRECT = 'https://eu-s3.beelinecloud.ru/utair-log/alias.pdf?X-Amz-Signature=TEMP_SECRET'
THIRD = 'https://eu-s3.beelinecloud.ru/utair-log/third.pdf'
HTML = ('<div>Bronze <a href="' + SHORT + '">Hotel rules</a></div>'
        '<div>Gold <a href="' + DIRECT + '">Transfer rules</a></div>')
FOOTER = 'This is only a long native footer without image terms. ' * 6


def scanned_pdf(pages=1):
    data = image_pdf(image_count=0, inline_count=10, native_text=FOOTER)
    if pages == 1:
        return data
    reader = PdfReader(io.BytesIO(data))
    writer = PdfWriter()
    for _ in range(pages):
        writer.add_page(reader.pages[0])
    output = io.BytesIO()
    writer.write(output)
    return output.getvalue()


def ocr_result(pages=1, text='Complete terms page '):
    return {n: (text + str(n) + '.', {'minimum_numeric_confidence': 90})
            for n in range(1, pages + 1)}


class Client:
    def __init__(self, raw=HTML):
        self.raw = raw

    async def read(self, *args, **kwargs):
        return self.raw


class DocumentMergeQualityTests(unittest.IsolatedAsyncioTestCase):
    async def collect(self, data, outcomes, raw=HTML):
        def download(url, **kwargs):
            if url == SHORT:
                response = Response(b'', 302)
                response.headers['Location'] = DOWNLOAD
                return response
            if url in (DOWNLOAD, DIRECT, THIRD):
                return Response(data)
            raise AssertionError('Unexpected source request: ' + url)

        report = {'errors': []}
        with patch.object(m.requests, 'get', side_effect=download), \
             patch('document_text.ocr_pages', side_effect=outcomes):
            rows = await m.collect_documents(Client(raw), {'id': 'utair_rule_documents', 'url': m.ROOT},
                                             report, NOW, 500)
        for row in rows:
            validate_offer(row)
        return rows, report

    def assert_merged_provenance(self, row):
        self.assertEqual(row['source_url'], SHORT)
        self.assertEqual(row['benefit_url'], SHORT)
        self.assertEqual(row['link_kind'], 'detail_page')
        self.assertEqual(row['observed_at'], NOW)
        self.assertEqual(row['details']['public_aliases'], [SHORT])
        self.assertEqual(row['details']['discovery_label'], 'Hotel rules')
        self.assertEqual(row['details']['discovery_labels'], ['Hotel rules', 'Transfer rules'])
        self.assertEqual(row['details']['discovery_contexts'], ['Bronze Hotel rules', 'Gold Transfer rules'])
        self.assertEqual(len(row['details']['direct_document_resources']), 1)
        self.assertNotIn('TEMP_SECRET', json.dumps(row))
        self.assertNotIn('X-Amz-', json.dumps(row))

    async def test_complete_ocr_wins_over_partial_in_either_alias_order(self):
        data = await asyncio.to_thread(scanned_pdf)
        for complete_first in (False, True):
            with self.subTest(complete_first=complete_first):
                incomplete = subprocess.TimeoutExpired('tesseract', 180)
                outcomes = [ocr_result(), incomplete] if complete_first else [incomplete, ocr_result()]
                try:
                    rows, report = await self.collect(data, outcomes)
                except ValueError as exc:
                    self.fail('A recoverable alias OCR error discarded the complete PDF: ' + str(exc))
                self.assertEqual(len(rows), 1)
                row = rows[0]
                self.assertEqual(row['native_id'], 'document:ExistingLink')
                self.assertEqual(row['id'], hashlib.sha256(b'utair_rule_documents\ndocument:ExistingLink').hexdigest())
                self.assertIn('Complete terms page 1.', row['conditions_text'])
                self.assertNotIn('long native footer', row['conditions_text'])
                self.assertEqual(row['details']['document_errors'], [])
                self.assertEqual(row['details']['ocr_pages'], 1)
                self.assertEqual(row['source_status'], 'public_rules_ocr_unverified')
                self.assertIn('ocr_text_unverified_no_manual_corrections', row['warnings'])
                self.assert_merged_provenance(row)
                self.assertEqual(report['errors'][0]['errors'], [{'page': 1, 'reason': 'TimeoutExpired'}])

    async def test_complete_shorter_extraction_replaces_all_partial_parts(self):
        data = await asyncio.to_thread(scanned_pdf, 48)
        partial = await asyncio.to_thread(extract_pdf, data, allow_ocr=False)
        partial_rows = m.document_records('utair_rule_documents', 'document:ExistingLink', 'Utair Status',
                                          'Utair', SHORT, NOW, partial, parent_source=m.ROOT)
        self.assertEqual(len(partial_rows), 2)
        try:
            rows, report = await self.collect(data, [subprocess.TimeoutExpired('tesseract', 180), ocr_result(48)])
        except ValueError as exc:
            self.fail('Different extraction part boundaries discarded the completed PDF: ' + str(exc))
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row['native_id'], 'document:ExistingLink')
        self.assertEqual(row['details']['document_part'], {'number': 1, 'total': 1})
        self.assertEqual([p['number'] for p in row['details']['pages']], list(range(1, 49)))
        self.assertEqual([p['text'] for p in row['details']['pages']],
                         ['Complete terms page ' + str(n) + '.' for n in range(1, 49)])
        self.assertEqual(row['details']['document_errors'], [])
        self.assertEqual(row['details']['ocr_pages'], 48)
        self.assertNotIn('long native footer', row['conditions_text'])
        self.assert_merged_provenance(row)

    async def test_conflicting_complete_ocr_results_still_fail_closed(self):
        data = await asyncio.to_thread(scanned_pdf)
        with self.assertRaisesRegex(ValueError, '^same_document_digest_different_text$'):
            await self.collect(data, [ocr_result(text='First complete result '),
                                      ocr_result(text='A longer conflicting complete result ')])

    async def test_later_complete_alias_resolves_earlier_partial_disagreement(self):
        data = await asyncio.to_thread(scanned_pdf, 2)
        first, second = ocr_result(2, text='First partial page '), ocr_result(2, text='Second partial page ')
        first[2] = ('', {})
        second[1] = ('', {})
        raw = HTML + '<div>Platinum <a href="' + THIRD + '">Complete rules</a></div>'
        try:
            rows, report = await self.collect(data, [first, second, ocr_result(2)], raw)
        except ValueError as exc:
            self.fail('An earlier partial conflict hid the later complete extraction: ' + str(exc))
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['native_id'], 'document:ExistingLink')
        self.assertEqual([p['text'] for p in rows[0]['details']['pages']],
                         ['Complete terms page 1.', 'Complete terms page 2.'])
        self.assertEqual(rows[0]['details']['document_errors'], [])
        self.assertEqual(rows[0]['details']['discovery_labels'],
                         ['Hotel rules', 'Transfer rules', 'Complete rules'])


if __name__ == '__main__':
    unittest.main()
