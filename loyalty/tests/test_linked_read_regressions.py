"""Transport-buffer and literal TSV regressions; no live requests or OCR calls."""
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch
sys.path.insert(0, str(Path(__file__).parents[1]))
import document_text as d
import ekp_linked_rules as e
from test_rzd_external import Response
from test_ekp_linked_rules import HTML, NOW, URL, html
from test_document_text import pdf


class BrowserBufferTests(unittest.TestCase):
    def test_provider_html_buffer_keeps_destination_marker(self):
        for suffix in ('', '/'):
            raw = html().replace(b'<html>', ('<html data-loyalty-probe-location="'+HTML+suffix+'">').encode())
            session = Mock()
            session.get.return_value = Response(raw, headers={
                'Ant-credits-cost':'10', 'Ant-page-status-code':'200'})
            reader = e.Reader('synthetic-key', session=session, sleep=lambda _: None)
            reader.free_checked = True
            value, receipt = reader.raw(HTML, provider='datacenter', browser=True)
            self.assertEqual(value, raw)
            self.assertEqual(receipt['origin_status'], 200)
            self.assertNotIn('error', receipt)
            self.assertEqual(reader.charged, 10)

    def test_foreign_browser_destination_still_rejected(self):
        raw = html().replace(b'<html>', b'<html data-loyalty-probe-location="https://private.example/">')
        session = Mock()
        session.get.return_value = Response(raw, headers={
            'Ant-credits-cost':'10', 'Ant-page-status-code':'200'})
        reader = e.Reader('synthetic-key', session=session, sleep=lambda _: None)
        reader.free_checked = True
        with self.assertRaises(ValueError):
            reader.raw(HTML, provider='datacenter', browser=True)


class TsvLiteralTests(unittest.TestCase):
    def test_quotes_are_words_not_multiline_csv_escape(self):
        header = 'level\tpage_num\tblock_num\tpar_num\tline_num\tword_num\tleft\ttop\twidth\theight\tconf\ttext\n'
        lines = [header]
        for page, words in [(1, ['"', '13%', '"']), (2, ['"Курс', '900'])]:
            lines.append(f'1\t{page}\t0\t0\t0\t0\t0\t0\t1\t1\t-1\t\n')
            for index, word in enumerate(words, 1):
                lines.append(f'5\t{page}\t1\t1\t1\t{index}\t0\t0\t1\t1\t95\t{word}\n')
        tsv = ''.join(lines).encode()
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)
            def fake_run(args, **kwargs):
                if args[0] == 'pdftoppm':
                    for n in (1, 2): (path/f'ocr-{n}.png').write_bytes(b'synthetic image')
                    return subprocess.CompletedProcess(args, 0, b'', b'')
                return subprocess.CompletedProcess(args, 0, tsv, b'')
            with patch('document_text.shutil.which', return_value='/synthetic'), patch('document_text.subprocess.run', side_effect=fake_run):
                result = d.ocr_pages(path/'input.pdf', [1, 2], folder)
            self.assertEqual(result[1][0], '" 13% "')
            self.assertEqual(result[2][0], '"Курс 900')
            self.assertEqual(result[1][1]['words'], 3)
            self.assertEqual(result[2][1]['words'], 2)
            self.assertNotIn('\t', result[1][0])

    def test_numeric_pdf_metadata_uses_source_label(self):
        doc = d.extract_pdf(pdf(['Meaningful conditions']))
        doc['title'] = '7'
        records = d.document_records('rgo', 'pdf:example', 'Example', 'Partner', 'https://rgo.ru/new-rules.pdf', NOW, doc,
                                     parent_source=HTML, label='Appendix to offer')
        self.assertEqual(records[0]['title'], 'Appendix to offer')

if __name__ == '__main__':
    unittest.main()
