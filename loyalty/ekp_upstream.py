"""Use complete EKP collection evidence independently of the Sheets publisher."""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import subprocess

MAX_AGE_SECONDS = 7 * 24 * 60 * 60


def recent(stamp, clock):
    if not isinstance(stamp, str):
        return False
    try:
        instant = datetime.fromisoformat(stamp.replace('Z', '+00:00'))
    except ValueError:
        return False
    return instant.tzinfo is not None and 0 <= (clock - instant).total_seconds() <= MAX_AGE_SECONDS


def select_upstream(fetch, repository, clock):
    data = fetch('actions/workflows/ekp-api.yml/runs?branch=main&status=completed&per_page=30')
    for run in data['workflow_runs']:
        if (run.get('path') != '.github/workflows/ekp-api.yml' or run.get('head_branch') != 'main'
                or run.get('head_repository', {}).get('full_name') != repository
                or run.get('status') != 'completed' or not recent(run.get('updated_at'), clock)):
            continue
        rid, attempt, commit = run['id'], run['run_attempt'], run['head_sha']
        jobs = fetch(f'actions/runs/{rid}/attempts/{attempt}/jobs?per_page=100')['jobs']
        collectors = [j for j in jobs if j.get('name') == 'collect']
        if len(collectors) != 1:
            continue
        job = collectors[0]
        if (job.get('run_id') != rid or job.get('run_attempt') != attempt or job.get('head_sha') != commit
                or job.get('status') != 'completed' or job.get('conclusion') != 'success'
                or not recent(job.get('completed_at'), clock)):
            continue
        name = f'ekp-public-{rid}-{attempt}'
        artifacts = fetch(f'actions/runs/{rid}/artifacts?per_page=100')['artifacts']
        matches = [a for a in artifacts if a.get('name') == name and a.get('expired') is False
                   and a.get('workflow_run', {}).get('id') == rid
                   and a['workflow_run'].get('head_branch') == 'main'
                   and a['workflow_run'].get('head_sha') == commit
                   and re.fullmatch(r'sha256:[a-f0-9]{64}', a.get('digest', ''))]
        if len(matches) != 1:
            continue
        artifact = matches[0]
        return {'run_id': rid, 'run_attempt': attempt, 'name': name, 'commit': commit,
                'artifact_id': artifact['id'], 'artifact_digest': artifact['digest'],
                'collect_job_id': job['id'], 'workflow_conclusion': run['conclusion']}
    raise ValueError('ekp_recent_successful_collection_not_found')


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
        raise ValueError('ekp_upstream_incomplete')
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
            return json.loads(subprocess.check_output(['gh', 'api', f'repos/{repository}/{path}'], timeout=60))
        selected = select_upstream(fetch, repository, clock)
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
