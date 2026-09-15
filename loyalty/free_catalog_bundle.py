"""Map fresh same-attempt provider evidence to the existing publication contract.

No network, secrets or account sessions. Saved diagnostics from previous runs are
not accepted as fresh observations. Unimplemented roots never become offers.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from free_access_probe import SOURCE_IDS, configured_roots, run
from nordwind_catalog import parse_catalog
from normalized import validate_offer
from sheets_normalized import prepare


def build(report, roots, folder, *, run_id, attempt, commit, clock):
    if (report.get('run_id') != run_id or report.get('run_attempt') != attempt
        or report.get('commit') != commit or not run_id or not attempt or not commit
        or report.get('mode') != 'free_access_probe' or report.get('account_sessions_used') is not False
        or report.get('free_plan_confirmed') is not True
        or report.get('source_ids') != list(SOURCE_IDS)):
        raise ValueError('untrusted_or_wrong_attempt_report')
    observed = report['started_at']; started = datetime.fromisoformat(observed)
    finished = datetime.fromisoformat(report['finished_at'])
    if (started.tzinfo is None or finished.tzinfo is None
        or not started <= finished <= clock or not 0 <= (clock-started).total_seconds() <= 1200):
        raise ValueError('provider_report_not_fresh')
    observations = report.get('sources', [])
    by_id = {x['source_id']: x for x in observations}
    if len(by_id) != len(observations) or set(by_id)-set(SOURCE_IDS):
        raise ValueError('provider_report_identity')
    records = []; reports = []
    for cfg in roots:
        sid = cfg['id']; obs = by_id.get(sid, {})
        errors = []; rows = []; coverage = 'not_collected'
        if sid == 'nordwind' and obs.get('status') == 'candidate_requires_review':
            path = Path(folder)/'nordwind.html'
            if (obs.get('origin_http_status') != 200 or obs.get('final_url') != cfg['url']
                or path.stat().st_size > 6_000_000):
                raise ValueError('provider_source_identity')
            raw = path.read_bytes()
            if hashlib.sha256(raw).hexdigest() != obs.get('sanitized_dom_sha256'):
                raise ValueError('provider_document_hash_mismatch')
            try:
                rows = parse_catalog(raw.decode(), observed)
                coverage = json.dumps({'scope': 'all_accordions_in_observed_partnerlist',
                    'cards': len(rows), 'source_document_sha256': obs['sanitized_dom_sha256'],
                    'provider_run': run_id+':'+attempt, 'source_request_completed_at': obs['finished_at'],
                    'provider_origin_status': 200, 'full_program_catalog': False,
                    'linked_partner_sites_read': False}, ensure_ascii=False)
            except (ValueError, KeyError, TypeError):
                errors.append({'phase': 'extraction', 'reason': 'nordwind_structure_not_accepted'})
        elif obs.get('status') == 'candidate_requires_review':
            coverage = 'public_root_read_no_offer_adapter'
            errors.append({'phase': 'extraction', 'reason': 'no_reviewed_offer_adapter'})
        else:
            errors.append({'phase': 'provider', 'reason': obs.get('error', 'not_read')})
        for row in rows:
            validate_offer(row)
        records.extend(rows)
        reports.append({'source_id': sid, 'name': cfg['name'], 'root': cfg['url'],
            'status': 'ok' if rows and not errors else 'partial' if rows else 'failed',
            'discovered': len(rows), 'normalized': len(rows), 'failed': len(errors),
            'coverage': coverage, 'region': None, 'errors': errors, 'observed_at': observed})
    bundle = {'schema_version': 2, 'run_id': run_id+':'+attempt, 'observed_at': observed,
              'records': records, 'sources': reports}
    prepare(bundle)
    return bundle


def main():
    p = argparse.ArgumentParser(); p.add_argument('--input', default='free-access-output')
    p.add_argument('--out', default='free-catalog-output'); p.add_argument('--collect', action='store_true'); args = p.parse_args()
    output = Path(args.out); output.mkdir(exist_ok=True)
    (output/'normalized.json').unlink(missing_ok=True)
    if args.collect:
        roots = configured_roots(Path(__file__).with_name('sources_normalized.json'))
        report = run(roots, os.environ.get('SCRAPINGANT_API_KEY', ''), args.input)
        # Bind the freshly returned in-process observation, never a prior disk report.
        report['run_attempt'] = os.getenv('GITHUB_RUN_ATTEMPT')
        (Path(args.input)/'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        report = json.loads((Path(args.input)/'report.json').read_text())
    if report.get('status') == 'not_configured' or not report.get('free_plan_confirmed'):
        count = 0
    else:
        bundle = build(report, configured_roots(Path(__file__).with_name('sources_normalized.json')),
                       args.input, run_id=os.getenv('GITHUB_RUN_ID'), attempt=os.getenv('GITHUB_RUN_ATTEMPT'),
                       commit=os.getenv('GITHUB_SHA'), clock=datetime.now(timezone.utc))
        if args.collect:
            from coral_catalog import collect as collect_coral
            additional = collect_coral(report, args.input, os.environ.get('SCRAPINGANT_API_KEY', ''), bundle['observed_at'])
            for source in bundle['sources']:
                result = additional.get(source['source_id'])
                if result is None:
                    continue
                rows = result['records']; errors = result['errors']; meta = result['meta']
                bundle['records'].extend(rows)
                source.update(normalized=len(rows), discovered=max(len(rows), meta.get('discovered_details', 0)),
                    failed=len(errors), errors=errors, coverage=json.dumps(meta, ensure_ascii=False),
                    status=('ok' if meta.get('all_observed_promo_details_read') else 'partial') if rows else 'failed')
            prepare(bundle)
        count = len(bundle['records'])
        if count:
            (output/'normalized.json').write_text(json.dumps(bundle, ensure_ascii=False, indent=2))
    if os.getenv('GITHUB_OUTPUT'):
        with open(os.environ['GITHUB_OUTPUT'], 'a') as f:
            f.write('has_records='+('true' if count else 'false')+'\n')
    print(json.dumps({'normalized_records': count, 'published': False}))


if __name__ == '__main__':
    try:
        main()
    except Exception:
        print('Free catalogue validation failed; no publication authorized.')
        raise SystemExit(1)
