"""Private normalization stage: Sheets -> common views in the SAME spreadsheet.

Never upload this stage's source rows or outputs as public Actions artifacts.
Only counts/digests are printed. Source tabs are read-only, destination allowlist
is disjoint, and each publication is read back. No Google permissions are changed.
"""
from __future__ import annotations
import argparse
import json
import os
import time
from datetime import datetime,timezone
from pathlib import Path
from sheets_sync import Sheets
from model import verify_rows
from unified_inputs import read_tables,inputs_from_tables
from unified_normalization import normalize_inputs,digest,dump
from unified_views import SCHEMAS,prepare_views,retire_missing
from practical_scope import select_inputs,VERSION as SCOPE_VERSION

class UnifiedSheets(Sheets):
    schemas=SCHEMAS
    max_rows=30000

    def request(self,method,suffix='',**kwargs):
        # One request per 1.1 seconds stays below the per-user read/write quotas.
        # Only explicit quota rejections retry; ambiguous write/network failures
        # stop publication and leave its manifest unverified.
        for attempt in range(3):
            wait=getattr(self,'_next_request_at',0)-time.monotonic()
            if wait>0:time.sleep(wait)
            self._next_request_at=time.monotonic()+1.1
            try:return super().request(method,suffix,**kwargs)
            except RuntimeError as exc:
                if str(exc)!='Google Sheets HTTP 429' or attempt==2:raise
                time.sleep(30*(attempt+1))


def _values_fingerprint(tables):
    # Blank styled trailing rows and UI-rendered strings are not source facts.
    inputs,_=inputs_from_tables(tables)
    return digest(inputs)


def publish_all(*,as_of=None,client=None):
    as_of=as_of or datetime.now(timezone.utc).date().isoformat()
    client=client or UnifiedSheets(os.environ.get('DISCOUNTS_SPREADSHEET_ID',''),os.environ.get('GOOGLE_ACCESS_TOKEN',''))
    tables=read_tables(client)
    inputs,inventory=inputs_from_tables(tables)
    if not inputs:raise ValueError('No source records; refusing empty publication')
    practical,excluded=select_inputs(inputs)
    result=normalize_inputs(practical,as_of=as_of)
    result['audit'].update(publication_scope=SCOPE_VERSION,excluded_bulk_records=excluded,
        input_records_before_scope=len(inputs),source_snapshot_sha256=digest(inputs))
    result['audit']['input_inventory']=inventory
    views=prepare_views(result)
    # Inspect all proposed rows before the first write, including formula safety
    # and the bounded literal-cell constraints inherited from the existing writer.
    from model import plan_rows
    for name,rows in views.items():plan_rows([SCHEMAS[name]],rows,len(SCHEMAS[name]))
    if _values_fingerprint(read_tables(client))!=digest(inputs):raise ValueError('Source changed before publication')
    audit=[row.copy() for row in views['normalization_audit']]
    for row in audit:
        if row[0]=='manifest':row[4]='publishing'
    client.upsert('normalization_audit',audit)
    counts={};expected={}
    for name,rows in views.items():
        if name=='normalization_audit':continue
        props=client.ensure_tab(name);old=client.values(name,props)
        incoming=retire_missing(old,rows,len(SCHEMAS[name]))
        counts[name]=client.upsert(name,incoming)
        props=client.metadata()[name];actual=client.values(name,props)
        positions={r[0]:i for i,r in enumerate(actual) if r}
        expected[name]=[(positions[r[0]],r) for r in incoming]
        verify_rows(actual,expected[name],len(SCHEMAS[name]))
        # Show only current components; retired ones are retained, not mixed with
        # the current output or mistaken for an expired source offer.
        w=len(SCHEMAS[name]);end=max(1,len(actual))
        client.request('POST',':batchUpdate',json={'requests':[{'setBasicFilter':{'filter':{
            'range':{'sheetId':props['sheetId'],'startRowIndex':0,'endRowIndex':end,'startColumnIndex':0,'endColumnIndex':w+1},
            'criteria':{str(w-2):{'condition':{'type':'TEXT_EQ','values':[{'userEnteredValue':'current'}]}}}
        }}}]})
    if _values_fingerprint(read_tables(client))!=digest(inputs):raise ValueError('Source changed during publication; manifest remains unverified')
    for row in views['normalization_audit']:
        if row[0]=='manifest':row[4]='verified'
    client.upsert('normalization_audit',views['normalization_audit'])
    # Final readback after the last write. Includes all current output rows, not
    # just a random example, and audit completion is not a scrape-freshness claim.
    meta=client.metadata()
    for name,checks in expected.items():verify_rows(client.values(name,meta[name]),checks,len(SCHEMAS[name]))
    actual=client.values('normalization_audit',meta['normalization_audit']);pos={r[0]:i for i,r in enumerate(actual) if r}
    verify_rows(actual,[(pos[r[0]],r) for r in views['normalization_audit']],len(SCHEMAS['normalization_audit']))
    print(dump({'mode':'unified_views_published_and_readback_verified','records':len(inputs),
                'rows':{k:len(v) for k,v in views.items()},'source_snapshot_sha256':digest(inputs)}))
    return result


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--publish',action='store_true')
    p.add_argument('--as-of')
    p.add_argument('--offline-input',help='Local canonical source tables; may contain private data')
    p.add_argument('--out',help='Local output directory; forbidden with --publish')
    args=p.parse_args()
    if args.publish:
        if args.out or args.offline_input:p.error('Live publication never writes local/export artifacts')
        publish_all(as_of=args.as_of);return
    if not args.offline_input:p.error('Use --publish or --offline-input')
    path=Path(args.offline_input)
    if path.stat().st_size>50000000:raise ValueError('Offline input bound exceeded')
    tables=json.loads(path.read_text(encoding='utf8'))['sheets'];inputs,inventory=inputs_from_tables(tables)
    result=normalize_inputs(inputs,as_of=args.as_of or datetime.now(timezone.utc).date().isoformat())
    result['audit']['input_inventory']=inventory
    views=prepare_views(result)
    if args.out:
        target=Path(args.out);target.mkdir(parents=True,exist_ok=True)
        (target/'normalized.json').write_text(dump(result),encoding='utf8')
        (target/'records.jsonl').write_text(''.join(dump(r)+'\n' for r in result['records']),encoding='utf8')
        for group in ('benefits','conditions','costs','codes'):
            (target/(group+'.jsonl')).write_text(''.join(dump(x)+'\n' for r in result['records'] for x in r[group]),encoding='utf8')
        (target/'audit.json').write_text(dump(result['audit']),encoding='utf8')
        (target/'views.json').write_text(dump(views),encoding='utf8')
    print(dump({'mode':'offline_unified_verified','records':len(inputs),'views':{k:len(v) for k,v in views.items()}}))

if __name__=='__main__':
    try:main()
    except Exception as exc:
        # Error details can contain a private cell or credential. Fail closed,
        # print only class name. Local tests remain the detailed diagnosis path.
        print(f'Unified normalization failed ({type(exc).__name__}); publication is not certified.')
        raise SystemExit(1)
