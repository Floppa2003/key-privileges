"""Original-file retention uses the actual public RGO/Beeline PDF bytes.

The failure injections exercise storage and parser boundaries, not invented
source wording or synthetic discount examples.
"""
import hashlib
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parents[1]))
from pdf_archive import capture_pdf, archive_url

SHA = '905bb3b03f3b98709054b14c5ae08974a6f7be775857819cf8cd2cb688be683b'
SOURCE = ('https://rgo.ru/upload/medialibrary/2ed/'
          'jm89ty2fg8j8an3g362l5uq6lij95owe/Moya_Kompaniya_RGO_belaya_20.01.26.pdf')
ORIGINAL = Path(__file__).parents[2] / 'source-documents' / (SHA + '.pdf')
NOW = '2026-11-15T12:00:00+00:00'


class OriginalPdfArchiveTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = ORIGINAL.read_bytes()
        assert hashlib.sha256(cls.data).hexdigest() == SHA

    def test_exact_bytes_are_deduplicated_and_url_requires_verified_file(self):
        with tempfile.TemporaryDirectory() as directory:
            self.assertEqual(archive_url(SHA, directory=directory), '')
            self.assertEqual(capture_pdf(self.data, directory=directory), SHA)
            target = Path(directory) / (SHA + '.pdf')
            first = target.stat()
            self.assertEqual(capture_pdf(self.data, directory=directory), SHA)
            self.assertEqual(target.read_bytes(), self.data)
            self.assertEqual(target.stat().st_mtime_ns, first.st_mtime_ns)
            self.assertEqual([p.name for p in Path(directory).iterdir()], [SHA + '.pdf'])
            self.assertEqual(archive_url(SHA, directory=directory),
                'https://raw.githubusercontent.com/Floppa2003/key-privileges/main/source-documents/' + SHA + '.pdf')

    def test_bad_digest_or_corrupt_existing_copy_never_becomes_a_link(self):
        with tempfile.TemporaryDirectory() as directory:
            for value in ('../' + SHA, 'A' * 64, None):
                self.assertEqual(archive_url(value, directory=directory), '')
            target = Path(directory) / (SHA + '.pdf')
            target.write_bytes(b'<html>download failed</html>')
            with self.assertRaises(ValueError):
                archive_url(SHA, directory=directory)
            with self.assertRaises(ValueError):
                capture_pdf(self.data, directory=directory)
            self.assertEqual(target.read_bytes(), b'<html>download failed</html>')

    def test_truncated_real_pdf_with_preserved_header_and_trailer_is_rejected(self):
        damaged = self.data[:128] + self.data[-512:]
        self.assertTrue(damaged.startswith(b'%PDF-'))
        self.assertIn(b'%%EOF', damaged[-1024:])
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(ValueError):
                capture_pdf(damaged, directory=directory)
            self.assertEqual(list(Path(directory).iterdir()), [])

    def test_symlink_cannot_substitute_for_an_archived_file(self):
        with tempfile.TemporaryDirectory() as directory:
            (Path(directory) / (SHA + '.pdf')).symlink_to(ORIGINAL)
            with self.assertRaises(ValueError):
                archive_url(SHA, directory=directory)
            with self.assertRaises(ValueError):
                capture_pdf(self.data, directory=directory)

    def test_capture_is_opt_in_and_invalid_downloads_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {}, clear=True):
            with patch('pdf_archive.DEFAULT_ARCHIVE_DIR', Path(directory)):
                self.assertEqual(capture_pdf(self.data), SHA)
                self.assertEqual(list(Path(directory).iterdir()), [])
            for invalid in (b'<html>not PDF</html>', self.data[:1000]):
                with self.assertRaises(ValueError):
                    capture_pdf(invalid, directory=directory)
            self.assertEqual(list(Path(directory).iterdir()), [])

    def test_original_survives_hard_text_parser_failure(self):
        from document_text import extract_pdf
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {'PDF_CAPTURE_DIR':directory}):
            with patch('pypdf.PdfReader', side_effect=ValueError('parser_failure')):
                with self.assertRaisesRegex(ValueError, 'parser_failure'):
                    extract_pdf(self.data)
            self.assertEqual((Path(directory) / (SHA + '.pdf')).read_bytes(), self.data)

    def test_native_only_parsers_capture_before_rejecting_the_document(self):
        import alfa_public_rules
        import alfa_partner_rules
        import known_pdf
        import tsvetnoy_source
        for parse in (known_pdf.pdf_pages, alfa_public_rules.pdf_text,
                      alfa_partner_rules.pdf_text,
                      lambda data:tsvetnoy_source.matrix(data, ['Старт','Стандарт','Плюс'])):
            with self.subTest(parse=parse), tempfile.TemporaryDirectory() as directory:
                with patch.dict(os.environ, {'PDF_CAPTURE_DIR':directory}):
                    with self.assertRaises(Exception):
                        parse(self.data)
                self.assertEqual((Path(directory) / (SHA + '.pdf')).read_bytes(), self.data)

    def test_rgo_parser_failure_retains_a_searchable_non_offer(self):
        from normalized import validate_offer, content_hash
        from reviewed_pdf import extract_rgo_pdf
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {'PDF_CAPTURE_DIR':directory}):
            with patch('reviewed_pdf.extract_pdf', side_effect=ValueError('parser_failure')):
                rows = extract_rgo_pdf(self.data, SOURCE, NOW,
                    label='Специальные тарифные условия для членов РГО со скидкой до 35%')
            self.assertEqual(len(rows), 1)
            row = rows[0]
            self.assertEqual(row['record_kind'], 'source_observation')
            self.assertEqual(row['details']['document_sha256'], SHA)
            self.assertEqual(row['details']['extraction_method'], 'source_pdf_original_only')
            self.assertEqual(row['partner_name'], None)
            self.assertEqual(row['source_url'], SOURCE)
            self.assertEqual(row['benefit_text'], '')
            self.assertEqual(row['rates'], [])
            self.assertEqual(row['promo_codes'], [])
            self.assertEqual(row['valid_until'], None)
            self.assertNotIn('page_count', row['details'])
            validate_offer(row)
            row['benefit_text'] = row['details']['discovery_label']
            row['content_sha256'] = content_hash(row)
            with self.assertRaises(ValueError):
                validate_offer(row)
            self.assertEqual((Path(directory) / (SHA + '.pdf')).read_bytes(), self.data)

    def test_live_rgo_card_label_stays_bound_to_its_pdf_without_guessing_a_merchant(self):
        from collect_normalized import rgo_catalogue_entries
        raw=(Path(__file__).with_name('fixtures_live') / 'rgo-beeline-card.html').read_text()
        entries=rgo_catalogue_entries(raw,'https://rgo.ru/membership/loyalty-program/')
        self.assertEqual(entries,[{'url':SOURCE,
            'label':'Специальные тарифные условия для членов РГО со скидкой до 35%'}])


if __name__ == '__main__':
    unittest.main()
