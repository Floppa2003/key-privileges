"""GitHub-controlled, public-only Google IMPORT transport for RZD.

No provider key or source account. A separate allowlisted workspace receives
constant public-URL formulas, is read back, and is cleared after every request.
No private discount-sheet cell is read by this collection module.
"""
from __future__ import annotations
import argparse
import json
import os
import re
import time
from datetime import datetime,timezone
from pathlib import Path
from urllib.parse import urljoin,urlsplit
from sheets_sync import Sheets
from sheets_normalized import prepare
from rzd_import_catalog import (HOME,ROOT,ROBOTS,ORIGINAL,METHOD,formula,digest,
    instant,cell_atom,checked_observation,catalog,detail,RESTRICTION)

STAGING_ID='1nIH7seMlDR_3Hw1iOMQ0bnrD-iWspj73zvqCVT4dxW8'
SHEET_ID=1350472954
SHEET='public_fetch'
MARKER='PUBLIC_SOURCE_IMPORT_WORKSPACE_V1'
ROWS=2048
MAX_PAGES=32
MAX_DETAILS=100
MAX_READS=135
MAX_SECONDS=3300
OUT=Path('rzd-import-output')


def now():return datetime.now(timezone.utc).isoformat()

def reason(exc):
    s=str(exc)
    return s if re.fullmatch(r'rzd_[a-z_]{1,100}',s) else type(exc).__name__

def save(path,obj):
    tmp=path.with_suffix('.tmp');tmp.write_text(json.dumps(obj,ensure_ascii=False,indent=2));tmp.replace(path)


def policy_from(obs):
    from protego import Protego
    checked_observation(obs)
    if obs['kind']!='robots' or any(c['kind']!='string' for c in obs['cells']):raise ValueError('rzd_policy_representation')
    rules='\n'.join(c['text'] for c in obs['cells'])
    if not re.search(r'^User-agent\s*:',rules,re.I|re.M) or '<html' in rules.lower() or RESTRICTION.search(rules):
        raise ValueError('rzd_policy_not_readable')
    return Protego.parse(rules)


class ImportReader:
    def __init__(self,token,run_id,*,client=None,clock=time.monotonic,sleep=time.sleep):
        self.client=client or Sheets(STAGING_ID,token)
        self.clock=clock;self.sleep=sleep;self.run_id=run_id
        self.started=self.clock();self.next_at=0;self.delay=20;self.calls=0
        self.observations=[];self.cleanup_verified=False
        meta=self.client.request('GET',params={'fields':'spreadsheetId,properties(importFunctionsExternalUrlAccessAllowed),sheets.properties(sheetId,title,gridProperties)'})
        targets=[x['properties'] for x in meta.get('sheets',[]) if x['properties']['sheetId']==SHEET_ID]
        if (meta.get('spreadsheetId')!=STAGING_ID or meta.get('properties',{}).get('importFunctionsExternalUrlAccessAllowed') is not True
            or len(targets)!=1 or targets[0]['title']!=SHEET or targets[0]['gridProperties']['rowCount']!=ROWS
            or targets[0]['gridProperties']['columnCount']!=4):raise ValueError('rzd_workspace_identity')
        self.snapshot()

    def snapshot(self):
        data=self.client.request('GET',params={'ranges':f"'{SHEET}'!A1:D{ROWS}",'includeGridData':'true',
            'fields':'spreadsheetId,sheets(properties(sheetId,title),data(startRow,startColumn,rowData.values(userEnteredValue,effectiveValue,formattedValue,effectiveFormat.numberFormat)))'})
        sheets=data.get('sheets',[])
        if (data.get('spreadsheetId')!=STAGING_ID or len(sheets)!=1 or sheets[0]['properties']['sheetId']!=SHEET_ID
            or sheets[0]['properties']['title']!=SHEET):raise ValueError('rzd_workspace_response_identity')
        rows=[]
        for block in sheets[0].get('data',[]):
            if block.get('startRow',0)!=0 or block.get('startColumn',0)!=0 or rows:raise ValueError('rzd_workspace_grid_offset')
            rows=[r.get('values',[]) for r in block.get('rowData',[])]
        if not rows or rows[0][0].get('userEnteredValue',{}).get('stringValue')!=MARKER:raise ValueError('rzd_workspace_marker')
        return rows

    def clear(self,generation):
        self.cleanup_verified=False
        self.client.request('POST',':batchUpdate',json={'requests':[
            {'updateCells':{'range':{'sheetId':SHEET_ID,'startRowIndex':1,'endRowIndex':ROWS,'startColumnIndex':0,'endColumnIndex':4},
                            'rows':[],'fields':'userEnteredValue,userEnteredFormat.numberFormat'}},
            {'updateCells':{'start':{'sheetId':SHEET_ID,'rowIndex':0,'columnIndex':2},
                            'rows':[{'values':[{'userEnteredValue':{'stringValue':generation}}]}],'fields':'userEnteredValue'}}]})
        for _ in range(5):
            rows=self.snapshot()
            if len(rows[0])<3 or rows[0][2].get('userEnteredValue',{}).get('stringValue')!=generation:raise ValueError('rzd_workspace_generation')
            if not any(c.get('effectiveValue') or c.get('userEnteredValue') for row in rows[1:] for c in row):
                self.cleanup_verified=True;return
            self.sleep(1)
        raise ValueError('rzd_workspace_not_cleared')

    def read(self,url,kind):
        f=formula(url,kind)
        if self.calls>=MAX_READS or self.clock()-self.started>MAX_SECONDS-80:raise ValueError('rzd_collection_bound')
        generation=f'{self.run_id}:{self.calls+1}'
        self.clear(generation)
        self.sleep(max(0,self.next_at-self.clock()))
        requested=now();self.calls+=1;self.cleanup_verified=False
        self.client.request('POST',':batchUpdate',json={'requests':[{'updateCells':{
            'start':{'sheetId':SHEET_ID,'rowIndex':1,'columnIndex':0},
            'rows':[{'values':[{'userEnteredValue':{'formulaValue':f}}]}],'fields':'userEnteredValue'}}]})
        self.next_at=self.clock()+self.delay
        previous=None;until=self.clock()+65;last_error=None
        try:
            while self.clock()<until:
                rows=self.snapshot()
                if len(rows[0])<3 or rows[0][2].get('userEnteredValue',{}).get('stringValue')!=generation:raise ValueError('rzd_workspace_generation')
                if len(rows)<2 or not rows[1]:self.sleep(2);continue
                if rows[1][0].get('userEnteredValue',{}).get('formulaValue')!=f:raise ValueError('rzd_formula_readback')
                atoms=[]
                try:
                    for i,row in enumerate(rows[1:],1):
                        if any(c.get('effectiveValue') or c.get('userEnteredValue') for c in row[1:]):raise ValueError('rzd_wide_import_result')
                        c=row[0] if row else {}
                        if i!=1 and c.get('userEnteredValue'):raise ValueError('rzd_unexpected_staging_input')
                        value=cell_atom(c)
                        if value is not None:atoms.append(value)
                    if not atoms:raise ValueError('rzd_empty_import_result')
                    if len(atoms)>=2000 or len(json.dumps(atoms,ensure_ascii=False))>700000:raise ValueError('rzd_import_size_bound')
                except ValueError as exc:
                    if str(exc)!='rzd_import_error_cell':raise
                    last_error=str(exc);self.sleep(3);continue
                current=digest(atoms)
                if previous==current:
                    if kind=='catalog_cards':
                        from rzd_catalogue_cards import sanitize
                        if any(a['kind']!='string' for a in atoms):raise ValueError('rzd_catalogue_coercion')
                        atoms=[{'kind':'string','text':sanitize('\n'.join(a['text'] for a in atoms))}];current=digest(atoms)
                    obs={'url':url,'kind':kind,'requested_at':requested,'calculated_at':now(),
                         'cells':atoms,'cells_sha256':current,'formula_sha256':digest(f)}
                    checked_observation(obs);self.observations.append(obs);return obs
                previous=current;self.sleep(2)
            raise ValueError(last_error or 'rzd_import_calculation_timeout')
        finally:
            self.clear('idle:'+self.run_id)

    def close(self):self.clear('idle:'+self.run_id)


def walk(reader,run_id,commit,observed_at,*,checkpoint=lambda:None,include_previews=False):
    from rzd_catalogue_cards import previews,merge_previews,make_preview
    preview_index={};preview_count=0
    records=[];errors=[];details=[];pages=[];pending=[];external=0;combined=0
    rules=None;catalogue_complete=False
    try:
        rules=policy_from(reader.read(ROBOTS,'robots'));checkpoint()
        rate=rules.request_rate('LoyaltyCatalogResearchBot')
        reader.delay=max(20,rules.crawl_delay('LoyaltyCatalogResearchBot') or 0,rate.seconds/rate.requests if rate else 0)
        if reader.delay>60:raise ValueError('rzd_source_delay_bound')
        if not rules.can_fetch(HOME,'LoyaltyCatalogResearchBot'):raise ValueError('rzd_policy_disallow')
        home=reader.read(HOME,'home');checkpoint();cells=checked_observation(home)
        if (not re.search('РЖД.*Бонус',cells[0]['text'],re.I) or ROOT not in {urljoin(HOME,c['text'].strip()) for c in cells[1:]}):
            raise ValueError('rzd_home_catalogue_link_missing')
        pending=[ROOT];known={ROOT}
        while pending and len(pages)<MAX_PAGES:
            url=pending.pop(0);pages.append(url)
            try:
                if not rules.can_fetch(url,'LoyaltyCatalogResearchBot'):raise ValueError('rzd_policy_disallow')
                observation=reader.read(url,'catalog_cards' if include_previews else 'catalog');checkpoint()
                parsed=catalog(observation)
                if include_previews:merge_previews(preview_index,previews(observation))
                external+=parsed['external_links'];combined+=parsed['combined_pagination_links']
                for target in parsed['details']:
                    if target not in details:details.append(target)
                for target in parsed['pages']:
                    if target not in known:known.add(target);pending.append(target)
            except Exception as exc:errors.append({'phase':'catalogue','url':url,'reason':reason(exc)})
        if pending:errors.append({'phase':'catalogue','reason':'rzd_catalogue_page_bound'})
        catalogue_complete=not pending and not any(e['phase']=='catalogue' for e in errors)
        selected=details
        if len(details)>MAX_DETAILS:
            week=int(instant(observed_at).timestamp()//604800);start=week*MAX_DETAILS%len(details)
            selected=(details[start:]+details[:start])[:MAX_DETAILS]
            errors.append({'phase':'detail','reason':'rzd_rotating_detail_bound'})
        for url in selected:
            try:
                if not rules.can_fetch(url,'LoyaltyCatalogResearchBot'):raise ValueError('rzd_policy_disallow')
                obs=reader.read(url,'detail');checkpoint()
                records.append(detail(obs,observed_at))
            except Exception as exc:
                failure=reason(exc);errors.append({'phase':'detail','url':url,'reason':failure})
                if include_previews and url in preview_index and failure!='rzd_policy_disallow':
                    records.append(make_preview(preview_index[url],observed_at,failure));preview_count+=1
                if failure=='rzd_collection_bound':break
    except Exception as exc:errors.append({'phase':'setup','reason':reason(exc)})
    meta={'method':METHOD,'catalogue_root':ROOT,'catalogue_pages_attempted':len(pages),
          'catalogue_pagination_exhausted':catalogue_complete,'pagination_scope':'source_single_PAGEN_category_states',
          'combined_category_states_not_repeated':combined,'external_card_links_not_fetched':external,
          'discovered_owned_detail_urls':len(details),'accepted_detail_records':len(records)-preview_count,
          'all_discovered_details_read':len(records)-preview_count==len(details) and bool(details),
          'origin_http_status_exposed':False,'origin_cache_age_verified':False,'source_account_used':False,
          'full_program_and_eligibility_verified':False,'linked_rules_read':False}
    if include_previews:meta.update(accepted_catalogue_previews=preview_count,preview_records_are_not_full_conditions=True)
    report={'source_id':'rzd','name':'РЖД Бонус — публичный каталог','root':ORIGINAL,
            'status':('ok' if catalogue_complete and len(records)==len(details) and not errors else 'partial') if records else 'failed',
            'discovered':len(details),'normalized':len(records),'failed':len(errors),'coverage':json.dumps(meta,ensure_ascii=False),
            'region':None,'errors':errors,'observed_at':observed_at}
    return {'schema_version':2,'run_id':run_id,'observed_at':observed_at,'records':records,'sources':[report]}


def validate_bundle(folder,*,run_id,commit,clock):
    folder=Path(folder)
    for name in ('normalized.json','evidence.json'):
        if (folder/name).stat().st_size>25000000:raise ValueError('rzd_bundle_size_bound')
    bundle=json.loads((folder/'normalized.json').read_text());audit=json.loads((folder/'evidence.json').read_text())
    if (audit.get('run_id')!=run_id or audit.get('commit')!=commit or audit.get('cleanup_verified') is not True
        or bundle.get('run_id')!=run_id or audit.get('started_at')!=bundle.get('observed_at')
        or audit.get('source_accounts_used') is not False or audit.get('scrapingant_credits')!=0):raise ValueError('rzd_bundle_identity')
    start,end=instant(audit['started_at']),instant(audit['finished_at'])
    if not start<=end<=clock or (clock-end).total_seconds()>900 or (end-start).total_seconds()>3600:raise ValueError('rzd_bundle_time')
    observations=audit.get('observations',[])
    if len(observations)>MAX_READS:raise ValueError('rzd_bundle_observation_bound')
    from rzd_catalogue_cards import previews,merge_previews,make_preview
    include_previews=audit.get('include_previews',False)
    if type(include_previews) is not bool:raise ValueError('rzd_preview_mode')
    preview_index={};discovery_order=[]
    expected=[];discovered=set();known_pages={ROOT};seen=set();rules=None;last=start;home_verified=False
    for obs in observations:
        checked_observation(obs)
        a,b=instant(obs['requested_at']),instant(obs['calculated_at'])
        if not last<=a<=b<=end or (obs['kind'],obs['url']) in seen:raise ValueError('rzd_bundle_observation_order')
        last=b;seen.add((obs['kind'],obs['url']))
        if obs['kind']=='robots':rules=policy_from(obs);continue
        if rules is None or not rules.can_fetch(obs['url'],'LoyaltyCatalogResearchBot'):raise ValueError('rzd_bundle_source_policy')
        if obs['kind']=='home':
            cells=checked_observation(obs)
            if not re.search('РЖД.*Бонус',cells[0]['text'],re.I) or ROOT not in {urljoin(HOME,c['text'].strip()) for c in cells[1:]}:
                raise ValueError('rzd_home_catalogue_link_missing')
            home_verified=True
        if obs['kind'] in ('catalog','catalog_cards'):
            if not home_verified or obs['url'] not in known_pages:raise ValueError('rzd_undiscovered_pagination')
            try:p=catalog(obs)
            except ValueError:continue
            if obs['kind']=='catalog_cards':
                if not include_previews:raise ValueError('rzd_unexpected_preview_mode')
                merge_previews(preview_index,previews(obs))
            discovery_order.extend(u for u in p['details'] if u not in discovered)
            discovered.update(p['details']);known_pages.update(p['pages'])
        elif obs['kind']=='detail':
            if obs['url'] not in discovered:raise ValueError('rzd_undiscovered_detail')
            try:expected.append(detail(obs,bundle['observed_at']))
            except ValueError:continue
    detail_count=len(expected);preview_count=0
    if include_previews:
        detail_rows={r['source_url']:r for r in expected};failures={}
        for e in bundle['sources'][0]['errors']:
            if e.get('phase')=='detail' and e.get('url'):
                if e['url'] not in discovered or e['url'] in failures:raise ValueError('rzd_preview_failure_source')
                failures[e['url']]=e['reason']
        expected=[]
        selected=discovery_order
        if len(selected)>MAX_DETAILS:
            week=int(instant(bundle['observed_at']).timestamp()//604800);offset=week*MAX_DETAILS%len(selected)
            selected=(selected[offset:]+selected[:offset])[:MAX_DETAILS]
        for url in selected:
            if url in detail_rows:expected.append(detail_rows[url])
            elif url in failures and url in preview_index and failures[url]!='rzd_policy_disallow':
                expected.append(make_preview(preview_index[url],bundle['observed_at'],failures[url]));preview_count+=1
    if expected!=bundle['records'] or len(bundle.get('sources',[]))!=1:raise ValueError('rzd_bundle_reconstruction')
    report=bundle['sources'][0]
    if report.get('source_id')!='rzd' or report.get('root')!=ORIGINAL or report.get('discovered')!=len(discovered):raise ValueError('rzd_bundle_coverage')
    meta=json.loads(report['coverage'])
    if (meta.get('accepted_detail_records')!=detail_count or meta.get('discovered_owned_detail_urls')!=len(discovered)
        or meta.get('origin_http_status_exposed') is not False or meta.get('origin_cache_age_verified') is not False
        or meta.get('source_account_used') is not False or meta.get('full_program_and_eligibility_verified') is not False
        or meta.get('all_discovered_details_read')!=(detail_count==len(discovered) and bool(discovered))):
        raise ValueError('rzd_bundle_coverage_mismatch')
    if include_previews and (meta.get('accepted_catalogue_previews')!=preview_count or meta.get('preview_records_are_not_full_conditions') is not True):raise ValueError('rzd_preview_coverage')
    completed=home_verified and known_pages<={u for k,u in seen if k in ('catalog','catalog_cards')} and not any(e['phase']=='catalogue' for e in report['errors'])
    if meta['catalogue_pagination_exhausted']!=completed:raise ValueError('rzd_bundle_pagination_claim')
    status=('ok' if completed and len(expected)==len(discovered) and not report['errors'] else 'partial') if expected else 'failed'
    if report['status']!=status:raise ValueError('rzd_bundle_status')
    prepare(bundle)
    return bundle


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--out',default=str(OUT));args=parser.parse_args()
    out=Path(args.out);out.mkdir(exist_ok=True,parents=True)
    run_id=os.environ['GITHUB_RUN_ID']+':'+os.environ['GITHUB_RUN_ATTEMPT'];commit=os.environ['GITHUB_SHA']
    started=now();reader=None
    audit={'run_id':run_id,'commit':commit,'started_at':started,'source_accounts_used':False,
           'scrapingant_credits':0,'staging_contains_only_public_source_data':True,'observations':[],
           'origin_response_and_cache_age_not_exposed':True,'cleanup_verified':False,'include_previews':True}
    def checkpoint():
        if reader:audit['observations']=reader.observations
        save(out/'evidence.json',audit)
    try:
        reader=ImportReader(os.environ.get('GOOGLE_ACCESS_TOKEN',''),run_id)
        bundle=walk(reader,run_id,commit,started,checkpoint=checkpoint,include_previews=True)
        reader.close();audit['cleanup_verified']=reader.cleanup_verified
        audit['import_requests']=reader.calls;audit['finished_at']=now();checkpoint()
        prepare(bundle);save(out/'normalized.json',bundle)
        validate_bundle(out,run_id=run_id,commit=commit,clock=datetime.now(timezone.utc))
        if os.getenv('GITHUB_OUTPUT'):
            with open(os.environ['GITHUB_OUTPUT'],'a') as f:f.write('has_payload=true\n')
        print(json.dumps({'records':len(bundle['records']),'source_status':bundle['sources'][0]['status'],
                          'import_requests':reader.calls,'scrapingant_credits':0,'workspace_cleared':True}))
    except Exception as exc:
        audit['error']=reason(exc);audit['finished_at']=now();checkpoint()
        (out/'normalized.json').unlink(missing_ok=True)
        print('RZD import failed ('+reason(exc)+'); publication not verified.')
        raise SystemExit(1)

if __name__=='__main__':main()
