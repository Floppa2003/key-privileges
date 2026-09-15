"""Read-only integration check. No Google data, credentials or publication."""
import asyncio
import hashlib
import json
import os
from datetime import datetime,timezone
from pathlib import Path
from collect_normalized import one
from sheets_normalized import prepare

OUT=Path('utair-support-output')

async def main():
    OUT.mkdir(exist_ok=True)
    cfg=next(c for c in json.loads(Path('loyalty/sources_normalized.json').read_text()) if c['id']=='utair')
    now=datetime.now(timezone.utc).isoformat()
    manifest={'commit':os.getenv('GITHUB_SHA'),'replica':os.getenv('REPLICA'),'started_at':now,
        'script_hashes':{str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in Path('loyalty').glob('*.py')},
        'production_dispatcher':True,'google_access':False,'publication_performed':False}
    (OUT/'manifest.json').write_text(json.dumps(manifest,indent=2))
    report,rows=await asyncio.wait_for(one(None,cfg,now,100),200)
    bundle={'schema_version':2,'run_id':os.environ['GITHUB_RUN_ID']+':'+os.environ.get('REPLICA','1'),
        'observed_at':now,'sources':[report],'records':rows}
    (OUT/'normalized.json').write_text(json.dumps(bundle,ensure_ascii=False,indent=2))
    prepared=prepare(bundle)
    manifest.update(finished_at=datetime.now(timezone.utc).isoformat(),
                    prepared_rows={k:len(v) for k,v in prepared.items()},source_status=report['status'])
    (OUT/'manifest.json').write_text(json.dumps(manifest,indent=2))
    if report['status']!='ok' or not rows:raise RuntimeError('utair_live_dispatch_not_successful')
    print(json.dumps({'status':'live_dispatch_and_preparation_verified','rows':len(rows)}))

if __name__=='__main__':asyncio.run(main())
