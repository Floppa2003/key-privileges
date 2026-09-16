"""GitHub -> isolated public Google import -> existing verified Sheet publisher.

The owner reports Aeroflot approved this catalogue read. Only the fixed public
catalogue/API scope is excepted; other source policy and account rules are intact.
"""
from __future__ import annotations
import argparse
import json
import os
import re
import time
from datetime import datetime,timezone
from pathlib import Path
from urllib.parse import parse_qsl,urlsplit
from sheets_sync import Sheets
from sheets_normalized import prepare
import aeroflot_import_catalog as m
import aeroflot_airlines as airlines

STAGING_ID='1nIH7seMlDR_3Hw1iOMQ0bnrD-iWspj73zvqCVT4dxW8'
SHEET_ID=2026091602
SHEET='af_public_fetch'
MARKER='AEROFLOT_PUBLIC_IMPORT_V1'
ROWS=4096
MAX_DETAILS=260
MAX_READS=324
MAX_SECONDS=3000
OUT=Path('aeroflot-import-output')


def now():return datetime.now(timezone.utc).isoformat()

def reason(exc):
    s=str(exc)
    return s if re.fullmatch('af_[a-z_]{1,100}',s) else type(exc).__name__

def save(path,obj):
    tmp=path.with_suffix('.tmp');tmp.write_text(json.dumps(obj,ensure_ascii=False,indent=2));tmp.replace(path)


class ImportReader:
    """Same clear/generation/stable-read contract as the existing RZD reader."""
    def __init__(self,token,run_id,*,client=None,clock=time.monotonic,sleep=time.sleep):
        self.client=client or Sheets(STAGING_ID,token)
        self.clock=clock;self.sleep=sleep;self.run_id=run_id
        self.started=clock();self.next_at=0;self.delay=5;self.calls=0
        self.observations=[];self.cleanup_verified=False
        meta=self.client.request('GET',params={'fields':'spreadsheetId,properties(importFunctionsExternalUrlAccessAllowed),sheets.properties(sheetId,title,gridProperties)'})
        targets=[x['properties'] for x in meta.get('sheets',[]) if x['properties']['sheetId']==SHEET_ID]
        if (meta.get('spreadsheetId')!=STAGING_ID or meta.get('properties',{}).get('importFunctionsExternalUrlAccessAllowed') is not True
            or len(targets)!=1 or targets[0]['title']!=SHEET or targets[0]['gridProperties']['rowCount']!=ROWS
            or targets[0]['gridProperties']['columnCount']!=4):raise ValueError('af_workspace_identity')
        self.snapshot()

    def snapshot(self):
        data=self.client.request('GET',params={'ranges':f"'{SHEET}'!A1:D{ROWS}",'includeGridData':'true',
            'fields':'spreadsheetId,sheets(properties(sheetId,title),data(startRow,startColumn,rowData.values(userEnteredValue,effectiveValue)))'})
        sheets=data.get('sheets',[])
        if (data.get('spreadsheetId')!=STAGING_ID or len(sheets)!=1 or sheets[0]['properties']['sheetId']!=SHEET_ID
            or sheets[0]['properties']['title']!=SHEET):raise ValueError('af_workspace_response_identity')
        rows=[]
        for block in sheets[0].get('data',[]):
            if block.get('startRow',0)!=0 or block.get('startColumn',0)!=0 or rows:raise ValueError('af_workspace_grid_offset')
            rows=[r.get('values',[]) for r in block.get('rowData',[])]
        if not rows or not rows[0] or rows[0][0].get('userEnteredValue',{}).get('stringValue')!=MARKER:raise ValueError('af_workspace_marker')
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
            if len(rows[0])<3 or rows[0][2].get('userEnteredValue',{}).get('stringValue')!=generation:raise ValueError('af_workspace_generation')
            if not any(c.get('effectiveValue') or c.get('userEnteredValue') for row in rows[1:] for c in row):
                self.cleanup_verified=True;return
            self.sleep(1)
        raise ValueError('af_workspace_not_cleared')

    def read(self,url,kind):
        f=m.formula(url,kind)
        if self.calls>=MAX_READS or self.clock()-self.started>MAX_SECONDS-80:raise ValueError('af_collection_bound')
        generation=f'{self.run_id}:{self.calls+1}'
        self.clear(generation);self.sleep(max(0,self.next_at-self.clock()))
        requested=now();self.calls+=1;self.cleanup_verified=False
        previous=None;until=self.clock()+65;last_error=None
        try:
            self.client.request('POST',':batchUpdate',json={'requests':[{'updateCells':{
                'start':{'sheetId':SHEET_ID,'rowIndex':1,'columnIndex':0},
                'rows':[{'values':[{'userEnteredValue':{'formulaValue':f}}]}],'fields':'userEnteredValue'}}]})
            self.next_at=self.clock()+self.delay
            while self.clock()<until:
                rows=self.snapshot()
                if len(rows[0])<3 or rows[0][2].get('userEnteredValue',{}).get('stringValue')!=generation:raise ValueError('af_workspace_generation')
                if len(rows)<2 or not rows[1]:self.sleep(2);continue
                if rows[1][0].get('userEnteredValue',{}).get('formulaValue')!=f:raise ValueError('af_formula_readback')
                atoms=[]
                try:
                    for i,row in enumerate(rows[1:]):
                        if any(c.get('effectiveValue') or c.get('userEnteredValue') for c in row[1:]):raise ValueError('af_wide_import_result')
                        cell=row[0] if row else {}
                        if i and cell.get('userEnteredValue'):raise ValueError('af_unexpected_staging_input')
                        a=m.atom(cell,i,kind)
                        if a is not None:atoms.append(a)
                    if not atoms:raise ValueError('af_empty_import_result')
                    if len(atoms)>m.MAX_CELLS or len(json.dumps(atoms,ensure_ascii=False))>m.MAX_JSON+100000:raise ValueError('af_import_size_bound')
                except ValueError as exc:
                    if str(exc)!='af_import_error_cell':raise
                    last_error=str(exc);self.sleep(3);continue
                current=m.digest(atoms)
                if previous==current:
                    obs={'url':url,'kind':kind,'requested_at':requested,'calculated_at':now(),
                         'cells':atoms,'cells_sha256':current,'formula_sha256':m.digest(f)}
                    m.checked_observation(obs);self.observations.append(obs);return obs
                previous=current;self.sleep(2)
            raise ValueError(last_error or 'af_import_calculation_timeout')
        finally:self.clear('idle:'+self.run_id)

    def close(self):self.clear('idle:'+self.run_id)


def policy(obs):
    cells=m.checked_observation(obs)
    if obs['kind']!='robots' or any(c['type']!='string' for c in cells):raise ValueError('af_policy_representation')
    text='\n'.join(c['value'] for c in cells)
    if not re.search('^User-agent:',text,re.I|re.M) or '<html' in text.lower() or m.BLOCKED.search(text):raise ValueError('af_policy_unreadable')
    return {'method':'google_import_policy_projection','sha256':m.digest(cells),'default_rules_not_overridden_globally':True,
            'catalogue_read_basis':m.PERMISSION}


def discovery(obs,scope='companies'):
    cells=m.checked_observation(obs)
    if obs['kind']!='discovery' or any(c['type']!='string' for c in cells):raise ValueError('af_discovery_shape')
    if not re.search('Партн[её]ры.*Аэрофлот',cells[0]['value'],re.I):raise ValueError('af_discovery_identity')
    allowed={'www.aeroflot.ru','aeroflot.ru'}
    links=[urlsplit(c['value'].strip()) for c in cells[1:]]
    if not any(u.scheme in ('https','http') and u.netloc in allowed and u.path.rstrip('/') in ('/partners/partners','/ru-ru/partners') for u in links):
        raise ValueError('af_company_catalogue_link_not_observed')
    if scope in ('airlines','all') and not any(u.scheme=='https' and u.netloc in allowed and u.path.rstrip('/')=='/partners/airlines' for u in links):
        raise ValueError('af_airline_catalogue_link_not_observed')
    return True


def report(observed_at,rows,partners,errors,pol=None,*,scope='companies',air_partners=None,air_roots=None):
    count=len(partners)
    coverage={'method':m.METHOD,'catalogue_root':m.ROOT,'catalogue_api':m.CATALOG,
      'scope':'all_partners_in_current_russian_company_category_response',
      'discovered_company_partners':count,'accepted_detail_records':len(rows),
      'category_response_parsed':bool(partners),'all_category_partners_read':bool(count) and len(rows)==count and not errors,
      'airline_catalogue_read':False,'linked_rules_read':False,'source_account_used':False,
      'origin_http_status_exposed':False,'origin_cache_age_verified':False,'full_program_and_eligibility_verified':False,
      'permission_basis':m.PERMISSION,'permission_email_independently_read':False}
    name='Аэрофлот Бонус — компании-партнёры'
    if scope!='companies':
        air_partners=air_partners or {};air_roots=air_roots or set()
        air_count=sum(r['native_id'].startswith('airline:') for r in rows)
        company_count=len(rows)-air_count
        coverage.update(scope=scope,discovered_company_partners=len(partners),accepted_company_details=company_count,
            all_category_partners_read=bool(partners) and company_count==len(partners),
            airline_catalogue_read=bool(air_roots),airline_catalogue_api=airlines.CATALOG,
            discovered_root_airlines=len(air_roots),discovered_airlines_including_children=len(air_partners),
            accepted_airline_details=air_count,all_discovered_airlines_read=bool(air_roots) and air_count==len(air_partners),
            airline_table_coefficients_are_not_cash_discounts=True)
        count=len(partners)+len(air_partners);name='Аэрофлот Бонус — '+('авиакомпании' if scope=='airlines' else 'компании и авиакомпании')
    return {'source_id':'aeroflot','name':name,'root':m.ROOT,
      'status':('partial' if errors or len(rows)!=count else 'ok') if rows else 'failed',
      'discovered':count,'normalized':len(rows),'failed':len(errors),'errors':errors,
      'coverage':json.dumps(coverage,ensure_ascii=False),'region':'Источник: lang=ru; география применимости не проверена',
      'observed_at':observed_at,'robots':pol}


def walk(reader,run_id,observed_at,*,checkpoint=lambda:None,scope='companies'):
    if scope not in ('companies','airlines','all'):raise ValueError('af_scope_invalid')
    records=[];errors=[];partners={};pol=None;root_seen=False;air_partners={};air_roots=set()
    try:
        pol=policy(reader.read(m.ROBOTS,'robots'));checkpoint()
        root_seen=discovery(reader.read(m.ROOT,'discovery'),scope);checkpoint()
        if scope in ('companies','all'):
            partners=m.catalog(reader.read(m.CATALOG,'catalog'));checkpoint()
            selected=list(partners)
            if len(selected)>MAX_DETAILS:
                start=(int(m.instant(observed_at).timestamp())//604800*MAX_DETAILS)%len(selected)
                selected=(selected[start:]+selected[:start])[:MAX_DETAILS]
                errors.append({'phase':'details','reason':'af_rotating_detail_bound'})
            consecutive=0
            for pid in selected:
                try:
                    obs=reader.read(m.detail_url(pid),'detail');checkpoint()
                    records.append(m.detail(obs,partners[pid],observed_at));consecutive=0
                except Exception as exc:
                    errors.append({'phase':'detail','url':m.detail_url(pid),'reason':reason(exc)});consecutive+=1
                    if not getattr(reader,'cleanup_verified',True) or consecutive>=3 or reason(exc)=='af_collection_bound':
                        errors.append({'phase':'details','reason':'af_consecutive_failure_or_budget_stop'});break
    except Exception as exc:errors.append({'phase':'discovery','reason':reason(exc)})
    if root_seen and scope in ('airlines','all') and getattr(reader,'cleanup_verified',True):
        try:
            air_partners=airlines.catalog(reader.read(airlines.CATALOG,'airline_catalog'));air_roots=set(air_partners);checkpoint()
            pending=list(air_partners);attempted=set();consecutive=0
            while pending and len(attempted)<airlines.MAX_AIRLINES:
                pid=pending.pop(0)
                if pid in attempted:continue
                attempted.add(pid)
                try:
                    obs=reader.read(airlines.detail_url(pid),'airline_detail');checkpoint()
                    row=airlines.detail(obs,air_partners[pid],observed_at)
                    airlines.add_children(air_partners,row['details']['public_airline'])
                    records.append(row);consecutive=0
                    pending.extend(i for i in air_partners if i not in attempted and i not in pending)
                except Exception as exc:
                    errors.append({'phase':'airline_detail','url':airlines.detail_url(pid),'reason':reason(exc)});consecutive+=1
                    if not getattr(reader,'cleanup_verified',True) or consecutive>=3 or reason(exc)=='af_collection_bound':
                        errors.append({'phase':'airline_details','reason':'af_consecutive_failure_or_budget_stop'});break
            if pending and len(attempted)>=airlines.MAX_AIRLINES:errors.append({'phase':'airline_details','reason':'af_airline_detail_bound'})
        except Exception as exc:errors.append({'phase':'airline_catalogue','reason':reason(exc)})
    return {'schema_version':2,'run_id':run_id,'observed_at':observed_at,'records':records,
            'sources':[report(observed_at,records,partners,errors,pol,scope=scope,air_partners=air_partners,air_roots=air_roots)]}


def validate_bundle(folder,*,run_id,commit,clock):
    folder=Path(folder)
    for name in ('normalized.json','evidence.json'):
        if (folder/name).stat().st_size>25000000:raise ValueError('af_bundle_size_bound')
    bundle=json.loads((folder/'normalized.json').read_text());audit=json.loads((folder/'evidence.json').read_text())
    if (audit.get('run_id')!=run_id or audit.get('commit')!=commit or audit.get('cleanup_verified') is not True
        or bundle.get('run_id')!=run_id or audit.get('started_at')!=bundle.get('observed_at')
        or audit.get('source_accounts_used') is not False or audit.get('scrapingant_credits')!=0
        or audit.get('permission_basis')!=m.PERMISSION or audit.get('permission_email_independently_read') is not False):raise ValueError('af_bundle_identity')
    start,end=m.instant(audit['started_at']),m.instant(audit['finished_at'])
    if not start<=end<=clock or (clock-end).total_seconds()>900 or (end-start).total_seconds()>3300:raise ValueError('af_bundle_time')
    observations=audit.get('observations',[])
    if len(observations)>MAX_READS:raise ValueError('af_bundle_observation_bound')
    scope=audit.get('scope','companies')
    if scope not in ('companies','airlines','all'):raise ValueError('af_scope_invalid')
    partners={};air_partners={};air_roots=set();expected=[];pol=None;root_seen=False;last=start;seen=set()
    for obs in observations:
        m.checked_observation(obs)
        a,b=m.instant(obs['requested_at']),m.instant(obs['calculated_at'])
        if not last<=a<=b<=end or obs['url'] in seen:raise ValueError('af_bundle_observation_order')
        last=b;seen.add(obs['url']);kind=obs['kind']
        if kind=='robots':pol=policy(obs);continue
        if pol is None:raise ValueError('af_bundle_policy_not_recorded')
        if kind=='discovery':root_seen=discovery(obs,scope)
        elif kind=='catalog':
            if not root_seen or scope=='airlines':raise ValueError('af_bundle_catalogue_not_discovered')
            try:partners=m.catalog(obs)
            except ValueError:continue
        elif kind=='detail':
            pid=int(dict(parse_qsl(urlsplit(obs['url']).query))['id'])
            if pid not in partners:raise ValueError('af_bundle_undiscovered_partner')
            try:expected.append(m.detail(obs,partners[pid],bundle['observed_at']))
            except ValueError:continue
        elif kind=='airline_catalog':
            if not root_seen or scope=='companies':raise ValueError('af_bundle_airlines_not_discovered')
            try:air_partners=airlines.catalog(obs);air_roots=set(air_partners)
            except ValueError:continue
        elif kind=='airline_detail':
            pid=int(dict(parse_qsl(urlsplit(obs['url']).query))['id'])
            if pid not in air_partners:raise ValueError('af_bundle_undiscovered_airline')
            try:
                row=airlines.detail(obs,air_partners[pid],bundle['observed_at'])
                airlines.add_children(air_partners,row['details']['public_airline']);expected.append(row)
            except ValueError:continue
    if expected!=bundle['records'] or len(bundle.get('sources',[]))!=1:raise ValueError('af_bundle_reconstruction')
    supplied=bundle['sources'][0]
    if supplied!=report(bundle['observed_at'],expected,partners,supplied['errors'],pol,scope=scope,air_partners=air_partners,air_roots=air_roots):raise ValueError('af_bundle_coverage')
    if sum(r['native_id'].startswith('partner:') for r in expected)>MAX_DETAILS or sum(r['native_id'].startswith('airline:') for r in expected)>airlines.MAX_AIRLINES:raise ValueError('af_bundle_detail_bound')
    prepare(bundle)
    return bundle


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--out',default=str(OUT));parser.add_argument('--scope',choices=('companies','airlines','all'),default='companies');args=parser.parse_args()
    out=Path(args.out);out.mkdir(exist_ok=True,parents=True)
    run_id=os.environ['GITHUB_RUN_ID']+':'+os.environ['GITHUB_RUN_ATTEMPT'];commit=os.environ['GITHUB_SHA']
    started=now();reader=None
    audit={'run_id':run_id,'commit':commit,'started_at':started,'source_accounts_used':False,
      'scrapingant_credits':0,'permission_basis':m.PERMISSION,'permission_email_independently_read':False,
      'staging_contains_only_public_source_data':True,'observations':[], 'cleanup_verified':False,
      'origin_response_and_cache_age_not_exposed':True,'scope':args.scope}
    def checkpoint():
        if reader:audit['observations']=reader.observations
        save(out/'evidence.json',audit)
    try:
        reader=ImportReader(os.environ.get('GOOGLE_ACCESS_TOKEN',''),run_id)
        bundle=walk(reader,run_id,started,checkpoint=checkpoint,scope=args.scope)
        reader.close();audit['cleanup_verified']=reader.cleanup_verified
        audit['import_requests']=reader.calls;audit['finished_at']=now();checkpoint()
        prepare(bundle);save(out/'normalized.json',bundle)
        validate_bundle(out,run_id=run_id,commit=commit,clock=datetime.now(timezone.utc))
        if os.getenv('GITHUB_OUTPUT'):
            with open(os.environ['GITHUB_OUTPUT'],'a') as f:f.write('has_payload=true\n')
        print(json.dumps({'records':len(bundle['records']),'source_status':bundle['sources'][0]['status'],
                          'import_requests':reader.calls,'scrapingant_credits':0,'workspace_cleared':True}))
    except Exception as exc:
        if reader:
            try:reader.close();audit['cleanup_verified']=reader.cleanup_verified
            except Exception:audit['cleanup_verified']=False
        audit['error']=reason(exc);audit['finished_at']=now();checkpoint()
        (out/'normalized.json').unlink(missing_ok=True)
        print('Aeroflot import failed ('+reason(exc)+'); publication not verified.')
        raise SystemExit(1)

if __name__=='__main__':main()
