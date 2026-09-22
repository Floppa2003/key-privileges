"""Reversible source holds, justified by a complete same-source inventory.

Last successful offer text/time stay intact. Failed reads never retire records.
These policies apply only to the three reviewed public reward integrations.
"""
from __future__ import annotations
import copy
import hashlib
import json
from datetime import date, datetime

LIMITS = {'backit_public': 2000, 'club_avolta_public': 80}
FRESHNESS_DAYS = {'backit_public': 7, 'club_avolta_public': 7, 'mantera_moments': 7}
HOLD_REASONS = {
    'source_disclosed_temporarily_disabled', 'financial_or_acquisition_ad',
    'dated_promotional_rate_requires_current_confirmation', 'promotional_period_expired',
    'promotional_period_not_started', 'no_positive_tariff',
    'detail_page_replaced_by_catalogue', 'source_conflict_lounge_admission_price',
    'no_concrete_partner_benefit', 'not_in_complete_inventory',
}

def _stamp(value):
    dt = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if dt.tzinfo is None:
        raise ValueError('lifecycle_timestamp_without_timezone')
    return dt

def _url(sid, url):
    if sid == 'backit_public':
        from backit_source import card_url
        return card_url(url)
    if sid == 'club_avolta_public':
        from avolta_source import reviewed_url
        return reviewed_url(url)
    raise ValueError('unsupported_lifecycle_source')

def attach_inventory(report, urls, excluded, *, source_id=None):
    """Record the observed universe, not just successfully parsed rows."""
    sid = source_id or report.get('source_id')
    if sid not in LIMITS or not 1 <= len(urls) <= LIMITS[sid]:
        raise ValueError('inventory_source_or_bound')
    urls = [_url(sid, u) for u in urls]
    if len(set(urls)) != len(urls):
        raise ValueError('duplicate_inventory_identity')
    by_url = {}
    for item in excluded:
        u = _url(sid, item['url'])
        reason = item['reason']
        if u not in urls or u in by_url or reason not in HOLD_REASONS:
            raise ValueError('invalid_inventory_exclusion')
        by_url[u] = reason
    report['inventory_v1'] = {'source_id': sid, 'urls': sorted(urls), 'excluded': by_url}

def validate_inventories(bundle):
    """Only complete successful reads authorize reconciliation; fail on drift."""
    result = {}
    for report in bundle['sources']:
        if report['source_id'] == 'mantera_moments':
            # Named hotels share one source URL, so use their validated IDs.
            from mantera_lifecycle import snapshot
            records = [r for r in bundle['records'] if r['source_id'] == 'mantera_moments']
            current = snapshot(report, records, bundle['observed_at'])
            if current is not None:
                result['mantera_moments'] = current
            continue
        snap = report.get('inventory_v1')
        if snap is None:
            continue
        sid = report['source_id']
        check = {}
        attach_inventory(check, snap['urls'],
                         [{'url': u, 'reason': r} for u, r in snap['excluded'].items()],
                         source_id=sid)
        if check['inventory_v1'] != snap:
            raise ValueError('inventory_identity_mismatch')
        if report['status'] not in ('ok', 'no_normalized_records') or report['errors']:
            continue
        if report['observed_at'] != bundle['observed_at']:
            raise ValueError('inventory_observation_mismatch')
        accepted = [r['source_url'] for r in bundle['records'] if r['source_id'] == sid]
        urls, excluded = set(snap['urls']), set(snap['excluded'])
        if (len(accepted) != report['normalized'] or len(set(accepted)) != len(accepted)
                or set(accepted) & excluded or set(accepted) | excluded != urls):
            raise ValueError('inventory_not_fully_accounted')
        result[sid] = snap
    return result

def reconcile_rows(bundle, existing, incoming):
    """Return upserts with reversible metadata; never clear, delete or shift rows."""
    snapshots = validate_inventories(bundle)
    now = _stamp(bundle['observed_at'])
    existing_by_id = {r[0]: r for r in existing[1:] if r and r[0]}
    output, accepted = [], set()
    for row in incoming:
        prev = existing_by_id.get(row[0])
        if prev:
            d = json.loads(prev[20] or '{}')
            if d.get('public_reward_source') in FRESHNESS_DAYS:
                last = max(_stamp(prev[22]), _stamp(d.get('_lifecycle', {}).get('checked_at', prev[22])))
                if last > now:
                    continue
        output.append(row)
        accepted.add(row[0])
    for original in existing[1:]:
        if not original or not original[0] or original[0] in accepted:
            continue
        row = (original[:25] + [''] * 25)[:25]
        d = json.loads(row[20] or '{}')
        sid = d.get('public_reward_source')
        if sid not in snapshots:
            continue
        snap = snapshots[sid]
        if sid == 'mantera_moments':
            from mantera_lifecycle import hold_reason
            reason = hold_reason(row, d, snap)
        else:
            u = _url(sid, row[17])
            native = u.rsplit('/', 1)[-1] if sid == 'backit_public' else u.split('/nashi-partnery/', 1)[1]
            if row[0] != hashlib.sha256((sid + '\n' + native).encode()).hexdigest():
                raise ValueError('lifecycle_stored_identity_mismatch')
            if d.get('public_reward_evidence', {}).get('url') != u:
                raise ValueError('lifecycle_stored_url_mismatch')
            reason = snap['excluded'].get(u)
            if u not in snap['urls']:
                reason = 'not_in_complete_inventory'
        last = max(_stamp(row[22]), _stamp(d.get('_lifecycle', {}).get('checked_at', row[22])))
        if last > now:
            continue
        if reason is None:
            continue
        d = copy.deepcopy(d)
        d['_lifecycle'] = {'version': 1, 'state': 'withheld', 'source_id': sid,
                           'reason': reason, 'checked_at': bundle['observed_at'],
                           'run_id': bundle['run_id'], 'last_offer_observed_at': row[22]}
        row[20] = json.dumps(d, ensure_ascii=False, sort_keys=True, separators=(',', ':'))
        output.append(row)
    return output

def reader_hold(raw, as_of):
    d = raw.get('details', {})
    sid = d.get('public_reward_source')
    if sid not in FRESHNESS_DAYS:
        return None
    state = d.get('_lifecycle')
    if state:
        if (state.get('version') != 1 or state.get('source_id') != sid
                or state.get('state') != 'withheld' or state.get('reason') not in HOLD_REASONS
                or _stamp(state['checked_at']) < _stamp(raw['observed_at'])):
            raise ValueError('invalid_stored_lifecycle_metadata')
        return 'источник отключил или не подтвердил предложение'
    observed = _stamp(raw['observed_at']).date()
    age = (date.fromisoformat(as_of) - observed).days
    if age < 0:
        return 'дата наблюдения в будущем'
    if age > FRESHNESS_DAYS[sid]:
        return 'наблюдение старше 7 дней'
    return None

def health_summary(bundle, *, expected_sources=None):
    """Separate source health from the publication of other successful sources."""
    report_ids = [r['source_id'] for r in bundle['sources']]
    if len(report_ids) != len(set(report_ids)):
        raise ValueError('duplicate_source_health_report')
    snapshots = validate_inventories(bundle)
    health = []
    for r in bundle['sources']:
        sid = r['source_id']
        if sid not in FRESHNESS_DAYS:
            continue
        complete = sid in snapshots
        health.append({'source_id': sid, 'healthy': complete, 'status': r['status'],
                       'records': r['normalized'], 'errors': len(r['errors'])})
    if expected_sources is not None:
        if not set(expected_sources) <= set(FRESHNESS_DAYS):
            raise ValueError('unsupported_expected_health_source')
        for sid in sorted(set(expected_sources) - set(report_ids)):
            health.append({'source_id':sid, 'healthy':False, 'status':'missing_source_report',
                           'records':0, 'errors':1})
    return health

if __name__ == '__main__':
    import argparse
    from pathlib import Path
    p = argparse.ArgumentParser()
    p.add_argument('--input', default='loyalty-output/normalized.json')
    p.add_argument('--sources', default='', help='Same registered source selection as the collector')
    args = p.parse_args()
    from source_selection import select_sources
    configs = json.loads(Path(__file__).with_name('sources_normalized.json').read_text())
    selected = select_sources(configs, args.sources)
    expected = [c['id'] for c in selected if c['id'] in FRESHNESS_DAYS]
    bundle = json.loads(Path(args.input).read_text())
    health = health_summary(bundle, expected_sources=expected)
    from collection_runtime import execution_health
    execution = execution_health(bundle, [c['id'] for c in selected])
    print(json.dumps({'collection_execution': execution, 'source_health': health}, ensure_ascii=False))
    import os
    if os.getenv('GITHUB_STEP_SUMMARY'):
        lines=['## Collection execution and public reward source health', '',
               f"Execution complete: {execution['healthy']}; state: {execution['state']}; reports: {execution['reported_sources']}/{execution['expected_sources']}.", '', '| Source | Healthy | Records | Errors |', '|---|---|---:|---:|']
        lines.extend(f"| {r['source_id']} | {r['healthy']} | {r['records']} | {r['errors']} |" for r in health)
        with open(os.environ['GITHUB_STEP_SUMMARY'],'a') as f:
            f.write('\n'.join(lines)+'\n')
    raise SystemExit(0 if execution['healthy'] and all(r['healthy'] for r in health) else 1)
