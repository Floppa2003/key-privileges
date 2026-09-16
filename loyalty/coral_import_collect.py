"""Coral Google-import supplement, reusing released mapping and publication.

Sitemap membership is not a complete live category listing. Failures retain old
rows; no source login, coupon issue, account session or paid provider is used.
"""
from __future__ import annotations
import argparse,json,os,re,time
from datetime import datetime,timezone
from pathlib import Path
from sheets_sync import Sheets
from sheets_normalized import prepare
import coral_import_catalog as m
import coral_catalog as coral

STAGING_ID='1nIH7seMlDR_3Hw1iOMQ0bnrD-iWspj73zvqCVT4dxW8'
SHEET_ID=2026091604
SHEET='coral_public_fetch'
MARKER='CORAL_PUBLIC_IMPORT_V1'
ROWS=4096
MAX_DETAILS=180
MAX_READS=184
MAX_SECONDS=2600
OUT=Path('coral-import-output')


def now():return datetime.now(timezone.utc).isoformat()


def reason(exc):
    s=str(exc)
    return s if re.fullmatch(r'(?:coral|coral_import)_[a-z_]{1,100}|access_challenge|canonical_identity_unconfirmed',s) else type(exc).__name__


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
            or targets[0]['gridProperties']['columnCount']!=4):raise ValueError('coral_import_workspace_identity')
        self.snapshot()

    def snapshot(self):
        data=self.client.request('GET',params={'ranges':f"'{SHEET}'!A1:D{ROWS}",'includeGridData':'true',
            'fields':'spreadsheetId,sheets(properties(sheetId,title),data(startRow,startColumn,rowData.values(userEnteredValue,effectiveValue)))'})
        sheets=data.get('sheets',[])
        if (data.get('spreadsheetId')!=STAGING_ID or len(sheets)!=1 or sheets[0]['properties']['sheetId']!=SHEET_ID
            or sheets[0]['properties']['title']!=SHEET):raise ValueError('coral_import_workspace_response_identity')
        rows=[]
        for block in sheets[0].get('data',[]):
            if block.get('startRow',0)!=0 or block.get('startColumn',0)!=0 or rows:raise ValueError('coral_import_workspace_grid_offset')
            rows=[r.get('values',[]) for r in block.get('rowData',[])]
        if not rows or not rows[0] or rows[0][0].get('userEnteredValue',{}).get('stringValue')!=MARKER:raise ValueError('coral_import_workspace_marker')
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
            if len(rows[0])<3 or rows[0][2].get('userEnteredValue',{}).get('stringValue')!=generation:raise ValueError('coral_import_workspace_generation')
            if not any(c.get('effectiveValue') or c.get('userEnteredValue') for row in rows[1:] for c in row):
                self.cleanup_verified=True;return
            self.sleep(1)
        raise ValueError('coral_import_workspace_not_cleared')

    def read(self,url,kind):
        f=m.formula(url,kind)
        if self.calls>=MAX_READS or self.clock()-self.started>MAX_SECONDS-80:
            t=now();self.observations.append({'url':url,'kind':kind,'requested_at':t,'calculated_at':t,'error':'coral_import_collection_bound'})
            raise ValueError('coral_import_collection_bound')
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
                if len(rows[0])<3 or rows[0][2].get('userEnteredValue',{}).get('stringValue')!=generation:raise ValueError('coral_import_workspace_generation')
                if len(rows)<2 or not rows[1]:self.sleep(2);continue
                if rows[1][0].get('userEnteredValue',{}).get('formulaValue')!=f:raise ValueError('coral_import_formula_readback')
                atoms=[]
                try:
                    for i,row in enumerate(rows[1:]):
                        if any(c.get('effectiveValue') or c.get('userEnteredValue') for c in row[1:]):raise ValueError('coral_import_wide_import_result')
                        cell=row[0] if row else {}
                        if i and cell.get('userEnteredValue'):raise ValueError('coral_import_unexpected_staging_input')
                        a=m.atom(cell,i,kind)
                        if a is not None:atoms.append(a)
                    if not atoms:raise ValueError('coral_import_empty_import_result')
                    if len(atoms)>m.MAX_CELLS or len(json.dumps(atoms,ensure_ascii=False))>m.MAX_JSON+100000:raise ValueError('coral_import_import_size_bound')
                except ValueError as exc:
                    if str(exc)!='coral_import_error_cell':raise
                    last_error=str(exc);self.sleep(3);continue
                current=m.digest(atoms)
                if previous==current:
                    obs={'url':url,'kind':kind,'requested_at':requested,'calculated_at':now(),
                         'cells':atoms,'cells_sha256':current,'formula_sha256':m.digest(f)}
                    m.checked_observation(obs);public=m.public_observation(obs);self.observations.append(public);return public
                previous=current;self.sleep(2)
            raise ValueError(last_error or 'coral_import_import_calculation_timeout')
        except Exception as exc:
            self.observations.append({'url':url,'kind':kind,'requested_at':requested,'calculated_at':now(),'error':reason(exc)})
            raise
        finally:self.clear('idle:'+self.run_id)

    def close(self):self.clear('idle:'+self.run_id)


def walk(reader,run_id,observed_at,*,checkpoint=lambda:None):
    states={sid:{'records':[],'errors':[],'entries':[],'excluded':[],'attempted':0} for sid in ('coral','coral_promo')}
    categories={};sitemap_count=0;pol=None;common_error=None
    def read(url,kind):
        if pol is not None and not pol.can_fetch(url,'LoyaltyCatalogResearchBot'):raise ValueError('coral_import_policy_disallow')
        try:return reader.read(url,kind)
        finally:checkpoint()
    try:
        pobs=read(m.ROBOTS,'robots');pol=m.policy(pobs)
        rate=pol.request_rate('LoyaltyCatalogResearchBot')
        delay=max(5,pol.crawl_delay('LoyaltyCatalogResearchBot') or 0,rate.seconds/rate.requests if rate else 0)
        if delay>30:raise ValueError('coral_import_policy_delay_bound')
        reader.delay=delay
    except Exception as exc:common_error=reason(exc)
    if pol is not None and common_error is None:
        try:
            index=read(coral.CLUB,'club_index');categories={x['url']:x['title'] for x in coral.listing(index['content'],'coral')}
            states['coral']['entries'],sitemap_count=m.sitemap(read(m.SITEMAP,'sitemap'),categories)
        except Exception as exc:states['coral']['errors'].append({'phase':'discovery','reason':reason(exc)})
        try:
            index=read(coral.PROMO,'promo_index');states['coral_promo']['entries']=coral.listing(index['content'],'coral_promo')
        except Exception as exc:states['coral_promo']['errors'].append({'phase':'discovery','reason':reason(exc)})
    for sid,state in states.items():
        if common_error:state['errors'].append({'phase':'policy','reason':common_error})
        entries=state['entries'];selected=entries
        # Future growth is an explicit rotating bounded subset, never silent loss.
        if len(entries)>MAX_DETAILS:
            start=(int(m.instant(observed_at).timestamp())//604800*MAX_DETAILS)%len(entries)
            selected=(entries[start:]+entries[:start])[:MAX_DETAILS]
            state['errors'].append({'phase':'selection','reason':'coral_import_rotating_bound'})
        consecutive=0
        for entry in selected:
            if sum(x['attempted'] for x in states.values())>=MAX_DETAILS:
                state['errors'].append({'phase':'selection','reason':'coral_import_total_detail_bound'});break
            try:
                state['attempted']+=1
                obs=read(entry['url'],'club_detail' if sid=='coral' else 'promo_detail')
                if sid=='coral' and m.physical_product(obs):
                    state['excluded'].append(entry['url']);consecutive=0;continue
                state['records'].append(m.detail(obs,sid,entry,observed_at));consecutive=0
            except Exception as exc:
                code=reason(exc);state['errors'].append({'phase':'detail','url':entry['url'],'reason':code});consecutive+=1
                if (not getattr(reader,'cleanup_verified',True) or code=='coral_import_collection_bound'
                    or consecutive>=3):
                    state['errors'].append({'phase':'details','reason':'coral_import_consecutive_failure_or_bound'});break
    reports=[];rows=[]
    for sid,state in states.items():
        rows.extend(state['records'])
        meta={'method':m.METHOD,'scope':'sitemap_children_under_current_club_categories' if sid=='coral' else 'current_promo_index',
            'sitemap_urls':sitemap_count if sid=='coral' else None,'current_club_categories':len(categories) if sid=='coral' else None,
            'discovered_detail_urls':len(state['entries']),'details_attempted':state['attempted'],
            'accepted_details':len(state['records']),'excluded_physical_merchandise_urls':state['excluded'],
            'all_discovered_details_accounted':len(state['records'])+len(state['excluded'])==len(state['entries']) and not state['errors'],
            'full_program_catalog':False,'javascript_category_membership_verified':False,'source_account_used':False,
            'origin_http_status_exposed':False,'origin_cache_age_verified':False,'linked_rules_read':False,
            'raw_form_script_templates_persisted':False,'sanitized_source_projection_not_original_html':True}
        reports.append({'source_id':sid,'name':'CoralBonus — '+('Клуб' if sid=='coral' else 'Акции'),
            'root':coral.CLUB if sid=='coral' else coral.PROMO,
            'status':'partial' if state['records'] and (state['errors'] or sid=='coral') else 'ok' if state['records'] else 'failed',
            'discovered':len(state['entries']),'normalized':len(state['records']),'failed':len(state['errors']),
            'errors':state['errors'],'coverage':json.dumps(meta,ensure_ascii=False),'region':None,'observed_at':observed_at})
    return {'schema_version':2,'run_id':run_id,'observed_at':observed_at,'records':rows,'sources':reports}


class ReplayReader:
    cleanup_verified=True
    def __init__(self,events):self.events=list(events);self.used=0
    def read(self,url,kind):
        if self.used>=len(self.events):raise ValueError('coral_import_replay_missing')
        o=self.events[self.used]
        if (o.get('url'),o.get('kind'))!=(url,kind):raise ValueError('coral_import_replay_order')
        self.used+=1
        if 'error' in o:raise ValueError(o['error'])
        return m.validate_public(o)


def validate_bundle(folder,*,run_id,commit,clock):
    folder=Path(folder)
    for name in ('normalized.json','evidence.json'):
        if (folder/name).stat().st_size>25000000:raise ValueError('coral_import_bundle_bound')
    b=json.loads((folder/'normalized.json').read_text());a=json.loads((folder/'evidence.json').read_text())
    if (a.get('run_id')!=run_id or a.get('commit')!=commit or b.get('run_id')!=run_id
        or a.get('started_at')!=b.get('observed_at') or a.get('cleanup_verified') is not True
        or a.get('source_accounts_used') is not False or a.get('scrapingant_credits')!=0):raise ValueError('coral_import_bundle_identity')
    start,end=m.instant(a['started_at']),m.instant(a['finished_at'])
    if not start<=end<=clock or (clock-end).total_seconds()>900 or (end-start).total_seconds()>2900:raise ValueError('coral_import_bundle_time')
    events=a.get('observations',[])
    if not isinstance(events,list) or not len(events)<=MAX_READS:raise ValueError('coral_import_bundle_reads')
    last=start
    for o in events:
        m.checked_url(o['url'],o['kind']);t,u=m.instant(o['requested_at']),m.instant(o['calculated_at'])
        if not last<=t<=u<=end or (u-t).total_seconds()>180:raise ValueError('coral_import_event_time')
        last=u
        if 'error' in o:
            if set(o)!={'url','kind','requested_at','calculated_at','error'} or reason(ValueError(o['error']))!=o['error']:raise ValueError('coral_import_error_shape')
        else:m.validate_public(o)
    replay=ReplayReader(events);expected=walk(replay,run_id,b['observed_at'])
    if expected!=b or replay.used!=len(events):raise ValueError('coral_import_bundle_reconstruction')
    prepare(b);return b


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--out',default=str(OUT));args=parser.parse_args()
    out=Path(args.out);out.mkdir(exist_ok=True,parents=True)
    run=os.environ['GITHUB_RUN_ID']+':'+os.environ['GITHUB_RUN_ATTEMPT'];commit=os.environ['GITHUB_SHA'];started=now();reader=None
    audit={'run_id':run,'commit':commit,'started_at':started,'source_accounts_used':False,'scrapingant_credits':0,
           'observations':[],'cleanup_verified':False,'source_projection':'sanitized_after_typed_google_import'}
    def checkpoint():
        if reader:audit['observations']=reader.observations
        save(out/'evidence.json',audit)
    try:
        reader=ImportReader(os.environ.get('GOOGLE_ACCESS_TOKEN',''),run)
        bundle=walk(reader,run,started,checkpoint=checkpoint)
        reader.close();audit['cleanup_verified']=reader.cleanup_verified;audit['import_requests']=reader.calls;audit['finished_at']=now();checkpoint()
        prepare(bundle);save(out/'normalized.json',bundle)
        validate_bundle(out,run_id=run,commit=commit,clock=datetime.now(timezone.utc))
        if os.getenv('GITHUB_OUTPUT'):
            with open(os.environ['GITHUB_OUTPUT'],'a') as f:f.write('has_payload=true\n')
        print(json.dumps({'records':len(bundle['records']),'statuses':{s['source_id']:s['status'] for s in bundle['sources']},
                          'import_requests':reader.calls,'scrapingant_credits':0,'workspace_cleared':True}))
    except Exception as exc:
        if reader:
            try:reader.close();audit['cleanup_verified']=reader.cleanup_verified
            except Exception:audit['cleanup_verified']=False
        audit['error']=reason(exc);audit['finished_at']=now();checkpoint();(out/'normalized.json').unlink(missing_ok=True)
        print('Coral import failed ('+reason(exc)+'); publication not verified.');raise SystemExit(1)

if __name__=='__main__':main()
