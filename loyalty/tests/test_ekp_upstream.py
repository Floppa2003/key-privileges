"""An unrelated publish failure must not hide successfully collected evidence."""
import copy
import contextlib
from datetime import datetime, timezone, timedelta
import hashlib
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile

sys.path.insert(0, str(Path(__file__).parents[1]))
from ekp_upstream import main, select_upstream, validate_upstream
from test_ekp_session import Fake, fail_after, run, session
from ekp_session_collect import collect, validate_session_bundle

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


def source_archive(run_id, commit, *, partial=False, observed='2026-11-02T17:05:19+00:00'):
    """Real collector/projection; only source responses and the clock are fakes."""
    start = datetime.fromisoformat(observed)
    obj = session(121 if partial else 2, started_at=start + timedelta(seconds=1))
    if partial:
        fail_after(obj, reason='source_body_error')
    with tempfile.TemporaryDirectory() as folder:
        with patch('ekp_session_collect.now', return_value=(start + timedelta(seconds=4)).isoformat()):
            collect(Fake(obj), folder, run_id=f'{run_id}:1', observed_at=observed, commit=commit)
        data = io.BytesIO()
        with zipfile.ZipFile(data, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
            for file in sorted(Path(folder).iterdir()):
                archive.writestr(file.name, file.read_bytes())
        return data.getvalue()


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
        self.snapshots = [{'run': self.run, 'jobs': self.jobs, 'artifacts': self.artifacts}]
        self.payloads = {}
        self.set_archive(self.artifacts[0], source_archive(self.run['id'], SHA))
        self.paths = []

    def set_archive(self, artifact, data):
        self.payloads[artifact['id']] = data
        artifact['digest'] = 'sha256:' + hashlib.sha256(data).hexdigest()
        artifact['size_in_bytes'] = len(data)

    def add_newer(self, *, run_id=500, artifact_id=600, partial=True,
                  observed='2026-11-03T12:00:00+00:00'):
        candidate = {**recent_run(), 'id': run_id, 'conclusion': 'success',
                     'created_at': '2026-11-03T12:00:00Z', 'updated_at': '2026-11-03T12:10:00Z'}
        job = {**self.jobs[0], 'id': run_id + 1, 'run_id': run_id,
               'completed_at': '2026-11-03T12:05:00Z'}
        artifact = {**self.artifacts[0], 'id': artifact_id, 'name': f'ekp-public-{run_id}-1',
                    'workflow_run': {'id': run_id, 'head_branch': 'main', 'head_sha': SHA}}
        self.set_archive(artifact, source_archive(run_id, SHA, partial=partial, observed=observed))
        self.snapshots.insert(0, {'run': candidate, 'jobs': [job], 'artifacts': [artifact]})
        return artifact

    def __call__(self, path):
        self.paths.append(path)
        if path.startswith('actions/workflows/ekp-api.yml/runs?'):
            runs = [s['run'] for s in self.snapshots] + [self.old]
            if 'status=success' in path:
                runs = [r for r in runs if r['conclusion'] == 'success']
            return {'workflow_runs': copy.deepcopy(runs)}
        for snapshot in self.snapshots:
            rid = snapshot['run']['id']
            attempt = snapshot['run']['run_attempt']
            if path == f'actions/runs/{rid}/attempts/{attempt}/jobs?per_page=100':
                return {'jobs': copy.deepcopy(snapshot['jobs'])}
            if path == f'actions/runs/{rid}/artifacts?per_page=100':
                return {'artifacts': copy.deepcopy(snapshot['artifacts'])}
        for aid, payload in self.payloads.items():
            if path == f'actions/artifacts/{aid}/zip':
                return payload
        raise AssertionError('Unexpected external request: ' + path)


class EkpUpstreamSelection(unittest.TestCase):
    def test_newer_partial_is_rejected_before_selecting_complete_snapshot(self):
        api = GithubReplies()
        api.add_newer()
        selected = select_upstream(api, REPOSITORY, CLOCK)
        self.assertEqual(selected['run_id'], 41487463433)
        self.assertEqual(selected['artifact_id'], 13163046259)
        self.assertEqual(selected['parent_observed_at'], '2026-11-02T17:05:19+00:00')
        self.assertEqual(selected['accepted_records'], 2)
        self.assertEqual(selected['reported_total'], 2)
        rejected = selected['rejected_candidates'][0]
        self.assertEqual(rejected['run_id'], 500)
        self.assertEqual(rejected['artifact_id'], 600)
        self.assertEqual(rejected['reason'], 'ekp_upstream_incomplete')
        self.assertEqual(rejected['accepted_records'], 120)
        self.assertEqual(rejected['reported_total'], 121)
        self.assertEqual(rejected['parent_observed_at'], '2026-11-03T12:00:00+00:00')

    def test_newest_complete_snapshot_is_preferred(self):
        api = GithubReplies()
        api.add_newer(partial=False)
        selected = select_upstream(api, REPOSITORY, CLOCK)
        self.assertEqual(selected['run_id'], 500)
        self.assertEqual(selected['artifact_id'], 600)
        self.assertEqual(selected['parent_observed_at'], '2026-11-03T12:00:00+00:00')
        self.assertEqual(selected['rejected_candidates'], [])

    def test_old_source_time_cannot_be_refreshed_by_a_new_run(self):
        api = GithubReplies()
        api.add_newer(partial=False, observed='2026-10-20T12:00:00+00:00')
        selected = select_upstream(api, REPOSITORY, CLOCK)
        self.assertEqual(selected['run_id'], 41487463433)
        self.assertEqual(selected['rejected_candidates'][0]['reason'], 'ekp_artifact_not_fresh')

    def test_archive_digest_failure_is_reported_before_fallback(self):
        api = GithubReplies()
        api.add_newer(partial=False)
        data = api.payloads[600]
        api.payloads[600] = data[:10] + bytes([data[10] ^ 1]) + data[11:]
        selected = select_upstream(api, REPOSITORY, CLOCK)
        self.assertEqual(selected['run_id'], 41487463433)
        self.assertEqual(selected['rejected_candidates'][0]['reason'], 'ekp_upstream_archive_digest_mismatch')

    def test_archive_with_foreign_paths_is_rejected(self):
        api = GithubReplies()
        artifact = api.add_newer(partial=False)
        data = io.BytesIO(api.payloads[600])
        with zipfile.ZipFile(data, 'a') as archive:
            archive.writestr('../outside.json', '{}')
        api.set_archive(artifact, data.getvalue())
        selected = select_upstream(api, REPOSITORY, CLOCK)
        self.assertEqual(selected['run_id'], 41487463433)
        self.assertEqual(selected['rejected_candidates'][0]['reason'], 'ekp_upstream_archive_scope')

    def test_large_archive_is_not_downloaded(self):
        api = GithubReplies()
        artifact = api.add_newer(partial=False)
        artifact['size_in_bytes'] = 25_000_001
        selected = select_upstream(api, REPOSITORY, CLOCK)
        self.assertEqual(selected['run_id'], 41487463433)
        self.assertNotIn('actions/artifacts/600/zip', api.paths)
        self.assertEqual(selected['rejected_candidates'][0]['reason'], 'ekp_upstream_archive_size_bound')

    def test_candidate_validation_stops_after_five_downloads(self):
        api = GithubReplies()
        for i in range(6):
            api.add_newer(run_id=500 + i, artifact_id=600 + i)
        journal = []
        with self.assertRaisesRegex(ValueError, 'collection_not_found'):
            select_upstream(api, REPOSITORY, CLOCK, report=journal.append)
        self.assertEqual(len([p for p in api.paths if p.endswith('/zip')]), 5)
        self.assertEqual(journal[-1]['reason'], 'ekp_candidate_validation_limit')
        self.assertNotIn('actions/artifacts/13163046259/zip', api.paths)

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
            response = api(command[2][len(prefix):])
            return response if isinstance(response, bytes) else json.dumps(response).encode()
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
        obj = fail_after(session(245))
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
