"""Exercise archive publication with real downloaded PDF bytes and Git state.

The in-memory remote supplies Git operations and concurrent-head failures;
no PDF wording or offer semantics are manufactured by these storage tests.
"""
import copy
import hashlib
from pathlib import Path
import sys
import tempfile
import unittest
import requests

sys.path.insert(0, str(Path(__file__).parents[1]))
from archive_publish import ApiError, GitHub, git_blob_sha, publish_archive

SHA = '905bb3b03f3b98709054b14c5ae08974a6f7be775857819cf8cd2cb688be683b'
NAME = SHA + '.pdf'
ORIGINAL = Path(__file__).parents[2] / 'source-documents' / NAME


class Remote:
    def __init__(self):
        self.current = '0' * 40
        self.commits = {self.current: {}}
        self.parents = {}
        self.blobs = {}
        self.created = 0
        self.updates = 0
        self.conflicts = 0
        self.always_conflict = False
        self.corrupt_readback = False
        self.reads = []

    def head(self):
        return self.current

    def archive_entries(self, commit):
        return copy.deepcopy(self.commits[commit])

    def create_blob(self, data):
        sha = git_blob_sha(data)
        self.blobs[sha] = data
        return sha

    def create_commit(self, parent, additions):
        self.created += 1
        commit = hashlib.sha1((parent + str(self.created)).encode()).hexdigest()
        self.parents[commit] = parent
        self.commits[commit] = {**self.commits[parent], **copy.deepcopy(additions)}
        return commit

    def advance(self, commit):
        self.updates += 1
        if self.conflicts or self.always_conflict:
            self.conflicts = max(0, self.conflicts - 1)
            concurrent = hashlib.sha1(('concurrent' + str(self.updates)).encode()).hexdigest()
            self.commits[concurrent] = {**self.commits[self.current], 'README.md': {
                'type': 'blob', 'mode': '100644', 'sha': 'c' * 40}}
            self.current = concurrent
            raise ApiError(422)
        if self.parents[commit] != self.current:
            raise ApiError(422)
        self.current = commit

    def read_blob(self, sha):
        self.reads.append((self.current, sha))
        data = self.blobs[sha]
        return data[:-100] if self.corrupt_readback else data


class ArchivePublicationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = ORIGINAL.read_bytes()
        assert hashlib.sha256(cls.data).hexdigest() == SHA

    def captured(self, directory):
        (Path(directory) / NAME).write_bytes(self.data)

    def test_exact_original_is_committed_and_read_back_without_rewriting_on_repeat(self):
        remote = Remote()
        with tempfile.TemporaryDirectory() as folder:
            self.captured(folder)
            first = publish_archive(folder, remote)
            self.assertEqual(first['added'], 1)
            self.assertEqual(first['verified'], 1)
            self.assertEqual(first['commit_sha'], remote.current)
            self.assertEqual(remote.reads[-1][0], remote.current)
            oid = remote.commits[remote.current][NAME]['sha']
            self.assertEqual(remote.blobs[oid], self.data)
            second = publish_archive(folder, remote)
            self.assertEqual(second['added'], 0)
            self.assertEqual(second['commit_sha'], first['commit_sha'])
            self.assertEqual(remote.updates, 1)
            self.assertEqual(remote.reads[-1], (remote.current, oid))

    def test_concurrent_main_update_is_preserved_and_retried_on_new_head(self):
        remote = Remote()
        remote.conflicts = 1
        with tempfile.TemporaryDirectory() as folder:
            self.captured(folder)
            result = publish_archive(folder, remote)
        self.assertEqual(result['added'], 1)
        self.assertEqual(remote.updates, 2)
        self.assertIn('README.md', remote.commits[remote.current])
        self.assertEqual(remote.blobs[remote.commits[remote.current][NAME]['sha']], self.data)

    def test_conflict_retries_are_bounded(self):
        remote = Remote()
        remote.always_conflict = True
        with tempfile.TemporaryDirectory() as folder:
            self.captured(folder)
            with self.assertRaisesRegex(RuntimeError, 'concurrent_updates_exhausted'):
                publish_archive(folder, remote)
        self.assertEqual(remote.updates, 3)
        self.assertNotIn(NAME, remote.commits[remote.current])

    def test_permission_denial_or_unchanged_head_rejection_is_not_retried(self):
        for status in (403, 422):
            with self.subTest(status=status), tempfile.TemporaryDirectory() as folder:
                remote = Remote()
                def reject(_commit):
                    remote.updates += 1
                    raise ApiError(status)
                remote.advance = reject
                self.captured(folder)
                with self.assertRaises(ApiError):
                    publish_archive(folder, remote)
                self.assertEqual(remote.updates, 1)
                self.assertNotIn(NAME, remote.commits[remote.current])

    def test_ambiguous_http_write_failure_stops_without_retry(self):
        class TimeoutSession:
            calls = 0
            def request(self, *_args, **_kwargs):
                self.calls += 1
                raise requests.Timeout('transport test')
        session = TimeoutSession()
        api = GitHub('test-token', session=session)
        with self.assertRaisesRegex(RuntimeError, '^archive_github_transport_failed$'):
            api.advance('b' * 40)
        self.assertEqual(session.calls, 1)

    def test_existing_immutable_filename_cannot_be_overwritten(self):
        remote = Remote()
        remote.commits[remote.current][NAME] = {
            'type': 'blob', 'mode': '100644', 'sha': 'd' * 40}
        with tempfile.TemporaryDirectory() as folder:
            self.captured(folder)
            with self.assertRaisesRegex(ValueError, 'immutable_copy_mismatch'):
                publish_archive(folder, remote)
        self.assertEqual(remote.updates, 0)

    def test_remote_corruption_after_commit_blocks_success(self):
        remote = Remote()
        remote.corrupt_readback = True
        with tempfile.TemporaryDirectory() as folder:
            self.captured(folder)
            with self.assertRaises(ValueError):
                publish_archive(folder, remote)
        self.assertEqual(remote.updates, 1)
        self.assertTrue(remote.reads)

    def test_wrong_names_symlinks_and_invalid_bytes_stop_before_any_mutation(self):
        for mode in ('wrong-name', 'symlink', 'truncated'):
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as folder:
                remote = Remote()
                path = Path(folder) / NAME
                if mode == 'symlink':
                    path.symlink_to(ORIGINAL)
                else:
                    path.write_bytes(self.data if mode == 'wrong-name' else self.data[:1000])
                    if mode == 'wrong-name':
                        path.rename(Path(folder) / ('a' * 64 + '.pdf'))
                with self.assertRaises(ValueError):
                    publish_archive(folder, remote)
                self.assertEqual(remote.created, 0)
                self.assertEqual(remote.updates, 0)

    def test_no_document_run_is_a_noop_with_a_pinned_main_commit(self):
        remote = Remote()
        with tempfile.TemporaryDirectory() as folder:
            result = publish_archive(Path(folder) / 'not-created', remote)
        self.assertEqual(result, {'commit_sha': '0' * 40, 'captured': 0, 'added': 0, 'verified': 0})
        self.assertEqual(remote.created, 0)


if __name__ == '__main__':
    unittest.main()
