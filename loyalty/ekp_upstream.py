"""Use complete EKP collection evidence independently of the Sheets publisher."""
import argparse
from datetime import datetime, timezone
import hashlib
import io
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
import zipfile

MAX_AGE_SECONDS = 7 * 24 * 60 * 60
MAX_CANDIDATES = 5
MAX_ARCHIVE_BYTES = 25_000_000
MAX_UNPACKED_BYTES = 50_000_000
MAX_ARCHIVE_FILES = 13  # report + normalized + at most eleven source pages


def recent(stamp, clock):
    if not isinstance(stamp, str):
        return False
    try:
        instant = datetime.fromisoformat(stamp.replace('Z', '+00:00'))
    except ValueError:
        return False
    return instant.tzinfo is not None and 0 <= (clock - instant).total_seconds() <= MAX_AGE_SECONDS


def select_upstream(fetch, repository, clock, *, report=None):
    rejected = []
    checked = 0
    def reject(run, reason, artifact=None, snapshot=None):
        entry = {'run_id': run['id'], 'reason': reason}
        if artifact:
            entry['artifact_id'] = artifact['id']
        entry.update(snapshot or {})
        rejected.append(entry)
        if report:
            report({'status': 'rejected', **entry})

    data = fetch('actions/workflows/ekp-api.yml/runs?branch=main&status=completed&per_page=30')
    for run in data['workflow_runs'][:30]:
        if (run.get('path') != '.github/workflows/ekp-api.yml' or run.get('head_branch') != 'main'
                or run.get('head_repository', {}).get('full_name') != repository
                or run.get('status') != 'completed'):
            continue
        if not recent(run.get('updated_at'), clock):
            reject(run, 'ekp_run_not_fresh')
            continue
        rid, attempt, commit = run['id'], run['run_attempt'], run['head_sha']
        jobs = fetch(f'actions/runs/{rid}/attempts/{attempt}/jobs?per_page=100')['jobs']
        collectors = [j for j in jobs if j.get('name') == 'collect']
        if len(collectors) != 1:
            reject(run, 'ekp_collect_missing_or_ambiguous')
            continue
        job = collectors[0]
        if (job.get('run_id') != rid or job.get('run_attempt') != attempt or job.get('head_sha') != commit
                or job.get('status') != 'completed' or job.get('conclusion') != 'success'
                or not recent(job.get('completed_at'), clock)):
            reject(run, 'ekp_collect_not_verified')
            continue
        name = f'ekp-public-{rid}-{attempt}'
        artifacts = fetch(f'actions/runs/{rid}/artifacts?per_page=100')['artifacts']
        matches = [a for a in artifacts if a.get('name') == name and a.get('expired') is False
                   and a.get('workflow_run', {}).get('id') == rid
                   and a['workflow_run'].get('head_branch') == 'main'
                   and a['workflow_run'].get('head_sha') == commit
                   and re.fullmatch(r'sha256:[a-f0-9]{64}', a.get('digest') or '')]
        if len(matches) != 1:
            reject(run, 'ekp_artifact_not_available')
            continue
        artifact = matches[0]
        if checked == MAX_CANDIDATES:
            reject(run, 'ekp_candidate_validation_limit', artifact)
            break
        checked += 1
        size = artifact.get('size_in_bytes')
        if type(size) is not int or not 0 < size <= MAX_ARCHIVE_BYTES:
            reject(run, 'ekp_upstream_archive_size_bound', artifact)
            continue
        selected = {'run_id': rid, 'run_attempt': attempt, 'name': name, 'commit': commit,
                    'artifact_id': artifact['id'], 'artifact_digest': artifact['digest'],
                    'artifact_size_bytes': size, 'collect_job_id': job['id'],
                    'workflow_conclusion': run['conclusion']}
        try:
            raw = fetch(f"actions/artifacts/{artifact['id']}/zip")
            bundle = validate_archive(raw, selected, clock)
        except (ValueError, KeyError, TypeError, OSError, RuntimeError, zipfile.BadZipFile,
                subprocess.SubprocessError) as exc:
            reason = str(exc) if re.fullmatch(r'[a-z_0-9]{1,100}', str(exc)) else type(exc).__name__
            reject(run, reason, artifact, getattr(exc, 'snapshot', None))
            continue
        return {**selected, **snapshot_summary(bundle), 'rejected_candidates': rejected}
    raise ValueError('ekp_recent_complete_collection_not_found')


def snapshot_summary(bundle):
    source = bundle['sources'][0]
    coverage = json.loads(source['coverage'])
    return {'source_status': source['status'], 'accepted_records': len(bundle['records']),
            'reported_total': coverage['reported_total'], 'parent_observed_at': bundle['observed_at']}


class IncompleteUpstreamError(ValueError):
    def __init__(self, bundle):
        super().__init__('ekp_upstream_incomplete')
        self.snapshot = snapshot_summary(bundle)


def validate_archive(raw, selection, clock):
    if not isinstance(raw, bytes) or not 0 < len(raw) <= MAX_ARCHIVE_BYTES:
        raise ValueError('ekp_upstream_archive_size_bound')
    if len(raw) != selection['artifact_size_bytes']:
        raise ValueError('ekp_upstream_archive_size_mismatch')
    if 'sha256:' + hashlib.sha256(raw).hexdigest() != selection['artifact_digest']:
        raise ValueError('ekp_upstream_archive_digest_mismatch')
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        files = archive.infolist()
        names = [f.filename for f in files]
        if (not 2 <= len(files) <= MAX_ARCHIVE_FILES or len(names) != len(set(names))
                or not {'normalized.json', 'report.json'}.issubset(names)
                or any(not re.fullmatch(r'(?:normalized|report|page-[0-9]{4})\.json', name) for name in names)):
            raise ValueError('ekp_upstream_archive_scope')
        if sum(f.file_size for f in files) > MAX_UNPACKED_BYTES:
            raise ValueError('ekp_upstream_archive_unpacked_bound')
        with tempfile.TemporaryDirectory() as folder:
            for file in files:
                Path(folder, file.filename).write_bytes(archive.read(file))
            return validate_upstream(folder, selection, clock)


def validate_upstream(folder, selection, clock):
    from ekp_session_collect import validate_session_bundle
    bundle = validate_session_bundle(
        folder, run_id=f"{selection['run_id']}:{selection['run_attempt']}",
        commit=selection['commit'], clock=clock, max_age_seconds=MAX_AGE_SECONDS,
    )
    source = bundle['sources'][0]
    coverage = json.loads(source['coverage'])
    if (source['status'] != 'ok' or source['failed'] != 0 or source['errors']
            or coverage.get('catalogue_pagination_complete') is not True
            or coverage.get('all_source_rows_mapped') is not True):
        raise IncompleteUpstreamError(bundle)
    return bundle


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('command', choices=('select', 'validate'))
    parser.add_argument('--selection', default='ekp-upstream-selection.json')
    parser.add_argument('--folder', default='ekp-upstream')
    args = parser.parse_args()
    clock = datetime.now(timezone.utc)
    if args.command == 'select':
        repository = os.environ['GITHUB_REPOSITORY']
        def fetch(path):
            raw = subprocess.check_output(['gh', 'api', f'repos/{repository}/{path}'], timeout=60)
            return raw if path.endswith('/zip') else json.loads(raw)
        selected = select_upstream(fetch, repository, clock, report=lambda entry: print(json.dumps(entry)))
        Path(args.selection).write_text(json.dumps(selected, indent=2) + '\n')
        with open(os.environ['GITHUB_OUTPUT'], 'a') as output:
            output.write(f"run_id={selected['run_id']}\nname={selected['name']}\nartifact_id={selected['artifact_id']}\n")
        print(json.dumps(selected))
    else:
        selected = json.loads(Path(args.selection).read_text())
        bundle = validate_upstream(args.folder, selected, clock)
        print(json.dumps({'run_id': bundle['run_id'], 'records': len(bundle['records']),
                          'parent_observed_at': bundle['observed_at'], 'status': 'complete_upstream_reconstructed'}))


if __name__ == '__main__':
    main()
