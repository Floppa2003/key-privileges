"""Queued publication must use current PDF bytes without changing tested code."""
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parents[1]))
import unified_publish
from document_catalogue import build_documents, document_sources
from test_document_catalogue import SHA, source

ORIGINAL = Path(__file__).parents[2] / 'source-documents' / (SHA + '.pdf')
COPY = 'https://raw.githubusercontent.com/Floppa2003/key-privileges/main/source-documents/' + SHA + '.pdf'


class CurrentArchivePublicationTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        root = Path(self.temporary.name)
        self.origin = root / 'origin'
        self.checkout = root / 'queued-publisher'
        self.origin.mkdir()
        self.git(self.origin, 'init', '-b', 'main')
        self.git(self.origin, 'config', 'user.name', 'Archive regression')
        self.git(self.origin, 'config', 'user.email', 'archive-test@example.invalid')
        (self.origin / 'code.py').write_text('tested revision\n')
        self.commit('tested code')
        self.git(root, 'clone', str(self.origin), str(self.checkout))
        self.tested = self.git(self.checkout, 'rev-parse', 'HEAD')
        (self.origin / 'source-documents').mkdir()
        shutil.copyfile(ORIGINAL, self.origin / 'source-documents' / (SHA + '.pdf'))
        (self.origin / 'code.py').write_text('later unreviewed code\n')
        self.commit('later PDF and code')

    @staticmethod
    def git(root, *args):
        return subprocess.run(['git', '-C', str(root), *args], check=True,
                              capture_output=True, text=True).stdout.strip()

    def commit(self, message):
        self.git(self.origin, 'add', '.')
        self.git(self.origin, 'commit', '-m', message)

    def publish(self, rows):
        # Replace the Google publication boundary; use the actual document
        # projection and verified-file link builder inside that boundary.
        def project(**kwargs):
            rows.extend(build_documents(document_sources([source(), source(visual=True)])))
        with patch('unified_publish.publish_all', project), \
             patch('pdf_archive.DEFAULT_ARCHIVE_DIR', self.checkout / 'source-documents'), \
             patch.dict(os.environ, {'PDF_ARCHIVE_DIR': str(self.checkout / 'source-documents')}), \
             patch.object(sys, 'argv', ['unified_publish.py', '--publish']):
            unified_publish.main()
            self.assertEqual(os.environ['PDF_ARCHIVE_DIR'], str(self.checkout / 'source-documents'))

    def test_queued_code_uses_current_pdf_and_repeat_keeps_identical_links(self):
        first = []
        self.publish(first)
        self.assertEqual(first[0][5], COPY)
        self.assertNotIn('Копия не сохранена', first[0][3])
        again = []
        self.publish(again)
        self.assertEqual(again, first)
        self.assertEqual(self.git(self.checkout, 'rev-parse', 'HEAD'), self.tested)
        self.assertEqual((self.checkout / 'code.py').read_text(), 'tested revision\n')
        self.assertEqual(self.git(self.checkout, 'status', '--porcelain'), '')

    def test_failed_refresh_stops_before_publication_instead_of_using_stale_bytes(self):
        self.git(self.checkout, 'remote', 'set-url', 'origin', str(self.origin / 'missing'))
        rows = []
        with self.assertRaises(subprocess.CalledProcessError):
            self.publish(rows)
        self.assertEqual(rows, [])

    def test_corrupt_current_pdf_stops_before_publication(self):
        (self.origin / 'source-documents' / (SHA + '.pdf')).write_bytes(b'not the archived PDF')
        self.commit('damaged archived copy')
        rows = []
        with self.assertRaises(ValueError):
            self.publish(rows)
        self.assertEqual(rows, [])

    def test_archive_symlink_is_not_followed_or_published(self):
        target = self.origin / 'source-documents' / (SHA + '.pdf')
        target.unlink()
        target.symlink_to('../code.py')
        self.commit('invalid archive symlink')
        rows = []
        with self.assertRaises(ValueError):
            self.publish(rows)
        self.assertEqual(rows, [])


if __name__ == '__main__':
    unittest.main()
