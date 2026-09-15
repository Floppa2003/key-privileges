"""Live candidate acceptance only: no Sheets access or publication."""
import asyncio
import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from collect_normalized import one
from sheets_normalized import prepare

OUT = Path('ekp-live-output')


async def main():
    OUT.mkdir(exist_ok=True)
    now = datetime.now(timezone.utc).isoformat()
    cfg = next(c for c in json.loads(Path('loyalty/sources_normalized.json').read_text()) if c['id'] == 'ekp')
    manifest = {'commit': os.environ['GITHUB_SHA'], 'replica': os.environ.get('REPLICA'),
                'started_at': now, 'production_dispatcher': True,
                'publication_performed': False, 'google_access': False,
                'live_preview_verified': False, 'live_pagination_verified': False,
                'hashes': {str(p): hashlib.sha256(p.read_bytes()).hexdigest()
                           for p in sorted(Path('loyalty').rglob('*')) if p.is_file() and p.suffix in ('.py','.json')
                           and '__pycache__' not in p.parts}}
    def save():
        (OUT/'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2))
    save()
    try:
        report, rows = await asyncio.wait_for(one(None, cfg, now, 60), 360)
        bundle = {'schema_version': 2, 'run_id': os.environ['GITHUB_RUN_ID'] + ':' + os.environ.get('REPLICA','1'),
                  'observed_at': now, 'sources': [report], 'records': rows}
        (OUT/'normalized.json').write_text(json.dumps(bundle, ensure_ascii=False, indent=2))
        prepared = prepare(bundle)
        manifest['prepared_rows'] = {k: len(v) for k,v in prepared.items()}
        manifest['source_status'] = report['status']
        coverage = json.loads(report['coverage']) if report['coverage'].startswith('{') else {}
        fatal = [e for e in report['errors'] if e['phase'] != 'coverage']
        manifest['live_preview_verified'] = bool(rows) and not fatal
        manifest['live_pagination_verified'] = bool(coverage.get('snapshots_read',0) >= 2 and not fatal)
        manifest['full_catalog_complete'] = False
        if not (manifest['live_preview_verified'] and manifest['live_pagination_verified']):
            raise RuntimeError('live_EKP_preview_and_pagination_not_verified')
    except Exception as exc:
        manifest['error_class'] = type(exc).__name__
        raise
    finally:
        manifest['finished_at'] = datetime.now(timezone.utc).isoformat()
        save()


if __name__ == '__main__':
    asyncio.run(main())
