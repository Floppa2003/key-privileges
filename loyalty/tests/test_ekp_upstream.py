"""An unrelated publish failure must not hide successfully collected evidence."""
import copy
import contextlib
from datetime import datetime, timezone, timedelta
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parents[1]))
from ekp_upstream import main, select_upstream, validate_upstream
from test_ekp_session import Fake, run, session
from ekp_session_collect import validate_session_bundle

REPOSITORY = 'Floppa2003/key-privileges'
CLOCK = datetime(2026, 11, 3, 15, 28, 55, tzinfo=timezone.utc)
SHA = '92afe0223a4f44df58aa28c93100e5ec6d794f14'


def recent_run():
    return {
        'id': 41487463433, 'run_attempt': 1, 'head_sha': SHA,
        'head_branch': 'main', 'path': '.github/workflows/ekp-api.yml',
        'status': 'completed', 'conclusion': 'failure',
        'created_at': '2026-11-02T17:03:37Z', 'updated_at': '2026-11-02T17:06:57Z',
        'head_repository': {'full_name': REPOSITORY},
    }


class GithubReplies:
    def __init__(self):
        self.run = recent_run()
        self.old = {**recent_run(), 'id': 100, 'conclusion': 'success',
                    'created_at': '2026-10-20T17:03:37Z', 'updated_at': '2026-10-20T17:06:57Z'}
        self.jobs = [{
            'id': 125422335917, 'name': 'collect', 'run_id': 41487463433,
            'run_attempt': 1, 'head_sha': SHA, 'status': 'completed', 'conclusion': 'success',
            'completed_at': '2026-11-02T17:05:55Z',
        }]
        self.artifacts = [{
            'id': 13163046259, 'name': 'ekp-public-41487463433-1', 'expired': False,
            'digest': 'sha256:4c9cde8dcba991674374aaff68b2fa3c8ba783455f4aa9651bfd4b2e3b5a3024',
            'workflow_run': {'id': 41487463433, 'head_branch': 'main', 'head_sha': SHA},
        }]
        self.paths = []

    def __call__(self, path):
        self.paths.append(path)
        if path.startswith('actions/workflows/ekp-api.yml/runs?'):
            runs = [self.run, self.old]
            if 'status=success' in path:
                runs = [r for r in runs if r['conclusion'] == 'success']
            return {'workflow_runs': copy.deepcopy(runs)}
        if path == 'actions/runs/41487463433/attempts/1/jobs?per_page=100':
            return {'jobs': copy.deepcopy(self.jobs)}
        if path == 'actions/runs/41487463433/artifacts?per_page=100':
            return {'artifacts': copy.deepcopy(self.artifacts)}
        raise AssertionError('Unexpected external request: ' + path)


class EkpUpstreamSelection(unittest.TestCase):
    def test_select_cli_exports_exact_artifact_identity_for_download(self):
        api = GithubReplies()
        class Clock(datetime):
            @classmethod
            def now(cls, tz=None):
                return CLOCK
        def gh(command, *, timeout):
            self.assertEqual(command[:2], ['gh', 'api'])
            prefix = f'repos/{REPOSITORY}/'
            self.assertTrue(command[2].startswith(prefix))
            return json.dumps(api(command[2][len(prefix):])).encode()
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder) / 'outputs'
            selection = Path(folder) / 'selection.json'
            with patch.dict(os.environ, GITHUB_REPOSITORY=REPOSITORY, GITHUB_OUTPUT=str(output)), \
                    patch.object(sys, 'argv', ['ekp_upstream.py', 'select', '--selection', str(selection)]), \
                    patch('ekp_upstream.datetime', Clock), \
                    patch('ekp_upstream.subprocess.check_output', side_effect=gh), \
                    contextlib.redirect_stdout(io.StringIO()):
                main()
            values = dict(line.split('=', 1) for line in output.read_text().splitlines())
            self.assertEqual(values['run_id'], '41487463433')
            self.assertEqual(values.get('artifact_id'), '13163046259')
            self.assertEqual(json.loads(selection.read_text())['artifact_id'], 13163046259)

    def test_successful_collection_is_usable_after_publish_failure(self):
        selected = select_upstream(GithubReplies(), REPOSITORY, CLOCK)
        self.assertEqual(selected['run_id'], 41487463433)
        self.assertEqual(selected['run_attempt'], 1)
        self.assertEqual(selected['name'], 'ekp-public-41487463433-1')
        self.assertEqual(selected['commit'], SHA)
        self.assertEqual(selected['artifact_id'], 13163046259)

    def test_failed_or_unfinished_collection_is_not_selected(self):
        for state in ('failure', 'cancelled', 'skipped', 'in_progress'):
            api = GithubReplies()
            api.jobs[0]['conclusion'] = state
            if state == 'in_progress':
                api.jobs[0]['status'] = state
            with self.subTest(state=state), self.assertRaisesRegex(ValueError, 'collection_not_found'):
                select_upstream(api, REPOSITORY, CLOCK)

    def test_missing_or_expired_collection_artifact_is_not_selected(self):
        for change in ('missing', 'expired', 'wrong_attempt', 'wrong_sha', 'missing_digest'):
            api = GithubReplies()
            if change == 'missing':
                api.artifacts.clear()
            elif change == 'expired':
                api.artifacts[0]['expired'] = True
            elif change == 'wrong_attempt':
                api.artifacts[0]['name'] = 'ekp-public-41487463433-2'
            elif change == 'wrong_sha':
                api.artifacts[0]['workflow_run']['head_sha'] = '0' * 40
            else:
                api.artifacts[0].pop('digest')
            with self.subTest(change=change), self.assertRaisesRegex(ValueError, 'collection_not_found'):
                select_upstream(api, REPOSITORY, CLOCK)

    def test_wrong_repository_branch_workflow_or_attempt_is_not_selected(self):
        for change in ('repository', 'branch', 'workflow', 'attempt', 'job_sha'):
            api = GithubReplies()
            if change == 'repository':
                api.run['head_repository']['full_name'] = 'another/repository'
            elif change == 'branch':
                api.run['head_branch'] = 'feature'
            elif change == 'workflow':
                api.run['path'] = '.github/workflows/unrelated.yml'
            elif change == 'attempt':
                api.jobs[0]['run_attempt'] = 2
            else:
                api.jobs[0]['head_sha'] = '0' * 40
            with self.subTest(change=change), self.assertRaisesRegex(ValueError, 'collection_not_found'):
                select_upstream(api, REPOSITORY, CLOCK)

    def test_stale_and_future_collection_are_not_selected(self):
        for stamp in ('2026-10-20T17:05:55Z', '2026-11-04T17:05:55Z'):
            api = GithubReplies()
            api.jobs[0]['completed_at'] = stamp
            with self.subTest(stamp=stamp), self.assertRaisesRegex(ValueError, 'collection_not_found'):
                select_upstream(api, REPOSITORY, CLOCK)


class EkpUpstreamValidation(unittest.TestCase):
    selection = {'run_id': 'fixture', 'run_attempt': 1, 'commit': 'test'}

    def test_fresh_previous_snapshot_keeps_dates_and_default_publish_window(self):
        with tempfile.TemporaryDirectory() as folder:
            bundle = run(Fake(session(2)), folder)
            clock = datetime.now(timezone.utc) + timedelta(days=2)
            accepted = validate_upstream(folder, self.selection, clock)
            self.assertEqual(accepted['run_id'], 'fixture:1')
            self.assertEqual(accepted['observed_at'], bundle['observed_at'])
            self.assertEqual(accepted['records'][1]['rates'][0]['value'], '17')
            with self.assertRaisesRegex(ValueError, 'ekp_artifact_not_fresh'):
                validate_session_bundle(folder, run_id='fixture:1', commit='test', clock=clock)

    def test_partial_successful_job_is_not_usable_as_complete_catalogue(self):
        obj = session(245)
        obj['pages'] = obj['pages'][:1]
        obj['complete'] = False
        obj['errors'] = ['source_http_refusal']
        with tempfile.TemporaryDirectory() as folder:
            bundle = run(Fake(obj), folder)
            self.assertEqual(bundle['sources'][0]['status'], 'partial')
            with self.assertRaisesRegex(ValueError, 'ekp_upstream_incomplete'):
                validate_upstream(folder, self.selection, datetime.now(timezone.utc))

    def test_old_or_future_source_observation_is_not_refreshed(self):
        with tempfile.TemporaryDirectory() as folder:
            run(Fake(session(2)), folder)
            for delta in (timedelta(days=8), -timedelta(days=1)):
                with self.subTest(delta=delta), self.assertRaisesRegex(ValueError, 'ekp_artifact_not_fresh'):
                    validate_upstream(folder, self.selection, datetime.now(timezone.utc) + delta)

    def test_source_run_commit_and_page_digest_are_revalidated(self):
        with tempfile.TemporaryDirectory() as folder:
            run(Fake(session(2)), folder)
            clock = datetime.now(timezone.utc)
            for change in ({'run_attempt': 2}, {'commit': 'wrong'}):
                with self.subTest(change=change), self.assertRaisesRegex(ValueError, 'identity_mismatch'):
                    validate_upstream(folder, {**self.selection, **change}, clock)
            page = Path(folder) / 'page-0000.json'
            page.write_text(page.read_text() + ' ')
            with self.assertRaisesRegex(ValueError, 'ekp_page_digest_mismatch'):
                validate_upstream(folder, self.selection, clock)


if __name__ == '__main__':
    unittest.main()
