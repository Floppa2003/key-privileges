"""Bounded anonymous EKP catalogue in one browser network context.

The browser sends only the observed read-only public API query, never credentials.
Protected terms are dropped inside the browser and again before persistence. The
public mapper and Google publisher contracts are shared with the direct reader.
"""
from __future__ import annotations
import argparse
import base64
import hashlib
import json
import os
import re
import time
from datetime import datetime,timezone
from pathlib import Path
from urllib.parse import urlsplit,parse_qsl
import requests
from bs4 import BeautifulSoup
from free_access_probe import FreeReader,ProbeError,free_plan,now
from ekp_catalog import ROOT,API,POLICY,query,page,public_row,make_record,validate_bundle

MAX_CREDITS=175  # Policy25, optional policy retry25, one browser125.
MAX_REQUESTS=3
MAX_PAGES=11
SCRIPT=Path(__file__).with_name('ekp_session_ui.js')


def root_identity(value):
    u=urlsplit(value)
    if (u.scheme!='https' or u.netloc!='ekp.spb.ru' or u.fragment or
        u.path not in ('/capabilities/loyalty/','/capabilities/loyalty/tiles','/capabilities/loyalty/tiles/') or
        parse_qsl(u.query,keep_blank_values=True) not in ([],[('region','98')])):
        raise ValueError('ekp_session_root_changed')


def instant(value):
    d=datetime.fromisoformat(value.replace('Z','+00:00'))
    if d.tzinfo is None:raise ValueError('ekp_missing_source_timezone')
    return d


class Reader:
    def __init__(self,key,*,get=requests.get,sleep=time.sleep):
        self.http=FreeReader(key,[{'url':ROOT}],get=get,max_credits=MAX_CREDITS,max_requests=MAX_REQUESTS)
        self.sleep=sleep;self.calls=0;self.reserved=0;self.charged=0;self.balance=None;self.ready=False
        self.browser_used=False;self.last=0;self.deadline=time.monotonic()+260

    def preflight(self):
        payload,_=self.http._request('usage',{});self.balance=free_plan(payload)
        if self.balance<MAX_CREDITS:raise ProbeError('insufficient_weekly_free_credits')
        self.ready=True

    def read(self,url):
        if not self.ready or self.http.halted or url not in (POLICY,ROOT):raise ProbeError('ekp_reader_not_ready')
        browser=url==ROOT;cost=125 if browser else 25
        if browser and self.browser_used:raise ProbeError('ekp_browser_already_requested')
        if self.calls>=MAX_REQUESTS or self.reserved+cost>MAX_CREDITS:raise ProbeError('ekp_session_budget_bound')
        delay=max(0,1.1-(time.monotonic()-self.last))
        if time.monotonic()+delay+80>self.deadline:raise ProbeError('ekp_session_time_bound')
        self.sleep(delay);self.calls+=1;self.reserved+=cost
        self.browser_used=self.browser_used or browser
        params={'url':url,'browser':str(browser).lower(),'proxy_country':'RU','proxy_type':'residential','timeout':'60'}
        if browser:params.update(js_snippet=base64.b64encode(SCRIPT.read_bytes()).decode(),block_resource=['image','media','font'])
        try:raw,meta=self.http._request('general',params)
        finally:self.last=time.monotonic()
        charge=str(meta.get('Ant-credits-cost',''));status=str(meta.get('Ant-page-status-code',''))
        if not charge.isdigit() or int(charge)>cost:self.http.halted=True;raise ProbeError('ekp_cost_contract_changed')
        self.charged+=int(charge)
        if status=='429' or meta.get('ant-original-header-retry-after'):self.http.halted=True;raise ProbeError('ekp_source_rate_limit')
        if status!='200':raise ProbeError('ekp_origin_http_refusal')
        from public_transport import check_response
        check_response(200,raw)
        return raw

    def closing_balance(self):
        if self.http.halted:return None
        try:usage,_=self.http._request('usage',{});return free_plan(usage)
        except ProbeError:return None


def policy_document(reader,audit):
    for number in range(2):
        item={'number':number+1,'started_at':now()};audit.setdefault('policy_attempts',[]).append(item)
        try:
            raw=reader.read(POLICY);item.update(result='source_document_received',finished_at=now());return raw
        except ProbeError as exc:
            item.update(error=str(exc),finished_at=now())
            if number or str(exc)!='provider_http_404' or getattr(reader.http,'halted',False):raise
            item['retry_delay_seconds']=10;reader.sleep(10)
    raise ProbeError('ekp_policy_retry_exhausted')


def accept_session(obj,out,audit,records,seen,errors):
    """Verify page identities and preserve prior valid pages after a later failure."""
    if not isinstance(obj,dict) or not isinstance(obj.get('pages'),list) or len(obj['pages'])>MAX_PAGES:
        raise ValueError('ekp_session_contract_changed')
    root_identity(obj['initialUrl']);root_identity(obj['finalUrl'])
    start,end=instant(obj['startedAt']),instant(obj['finishedAt'])
    if not instant(audit['started_at'])<=start<=end<=datetime.now(timezone.utc):
        raise ValueError('ekp_session_time_invalid')
    if (end-start).total_seconds()>65:raise ValueError('ekp_session_duration_invalid')
    source_errors=obj.get('errors')
    if (not isinstance(source_errors,list) or len(source_errors)>10 or
        any(not isinstance(x,str) or not re.fullmatch('[a-zA-Z_]{1,100}',x) for x in source_errors)):
        raise ValueError('ekp_session_error_contract_changed')
    audit['session']={'started_at':obj['startedAt'],'finished_at':obj['finishedAt'],
                      'initial_url':obj['initialUrl'],'final_url':obj['finalUrl'],'errors':source_errors}
    offset=0;total=None;previous=start
    for src in obj['pages']:
        if (src.get('request')!=query(offset) or src.get('status')!=200 or src.get('url')!=API
            or not re.fullmatch('[a-f0-9]{64}',src.get('sourceSha',''))):raise ValueError('ekp_page_identity_invalid')
        completed=instant(src['completedAt'])
        if not previous<=completed<=end:raise ValueError('ekp_page_time_invalid')
        previous=completed;ids=page(src,offset)
        if total is None:total=src['total']
        if src['total']!=total or seen.intersection(ids) or len(ids)!=min(120,total-offset):
            raise ValueError('ekp_page_count_changed')
        public=[]
        for original in src['partners']:
            try:
                projected=public_row(original)
                row=make_record(projected,audit['started_at'],request=src['request'],response_sha=src['sourceSha'],
                                observed_total=total,completed_at=src['completedAt'])
                public.append(projected);records.append(row)
            except (ValueError,TypeError,KeyError):
                errors.append({'phase':'record','native_id':original['id'],'reason':'ekp_source_fields_not_accepted'})
        seen.update(ids);file=f'page-{offset:04d}.json'
        (out/file).write_text(json.dumps({'total':total,'offset':offset,'partners':public},ensure_ascii=False,indent=2))
        audit['pages'].append({'file':file,'request':src['request'],'source_count':len(ids),'accepted':len(public),
            'origin_status':200,'completed_at':src['completedAt'],'source_response_sha256':src['sourceSha'],
            'public_projection_sha256':hashlib.sha256((out/file).read_bytes()).hexdigest()})
        offset+=len(ids);audit['reported_total']=total
    if type(obj.get('complete')) is not bool:raise ValueError('ekp_completion_flag_invalid')
    finished=bool(obj['complete'] and total is not None and len(seen)==total and not source_errors)
    if obj['complete'] and not finished:raise ValueError('ekp_completion_count_mismatch')
    errors.extend({'phase':'session','reason':code} for code in source_errors)
    if not finished and not source_errors:errors.append({'phase':'coverage','reason':'ekp_session_partial'})
    return finished


def collect(reader,out,*,run_id,observed_at,commit):
    from public_transport import robots_document
    from protego import Protego
    from sheets_normalized import prepare
    out=Path(out);out.mkdir(parents=True,exist_ok=True);records=[];seen=set();errors=[];complete=False
    audit={'run_id':run_id,'commit':commit,'started_at':observed_at,'source_account_used':False,'publication':False,
        'mode':'one_anonymous_browser_public_api','script_sha256':hashlib.sha256(SCRIPT.read_bytes()).hexdigest(),'pages':[],'errors':errors}
    robots={}
    try:
        reader.preflight();audit['opening_balance']=reader.balance
        raw=policy_document(reader,audit);rules,state=robots_document(200,raw);policy=Protego.parse(rules)
        if not all(policy.can_fetch(u,'LoyaltyCatalogResearchBot') for u in (ROOT,API)):raise ProbeError('robots_disallow')
        # Current source publishes no pacing rule. A future rule requires a
        # separately tested script interval, not silently violating it.
        if policy.crawl_delay('LoyaltyCatalogResearchBot') or policy.request_rate('LoyaltyCatalogResearchBot'):
            raise ProbeError('ekp_source_pacing_requires_review')
        (out/'robots.txt').write_text(rules)
        robots={'state':state,'http_status':200,'sha256':hashlib.sha256(raw.encode()).hexdigest()}
        raw=reader.read(ROOT);soup=BeautifulSoup(raw,'html.parser');nodes=soup.select('#loyalty-session-api')
        if len(nodes)!=1:raise ProbeError('ekp_session_marker_missing')
        obj=json.loads(nodes[0].get_text())
        complete=accept_session(obj,out,audit,records,seen,errors)
    except Exception as exc:
        reason=str(exc)
        errors.append({'phase':'collection','reason':reason if isinstance(exc,(ValueError,RuntimeError)) and re.fullmatch('[a-z_0-9]{1,100}',reason) else type(exc).__name__})
    audit.update(provider_requests=reader.calls,reserved_credits=reader.reserved,known_charged_credits=reader.charged,
        closing_balance=reader.closing_balance(),accepted_records=len(records),observed_ids=len(seen),
        pagination_complete=complete,finished_at=now())
    (out/'report.json').write_text(json.dumps(audit,ensure_ascii=False,indent=2))
    meta={'method':'anonymous_source_catalogue_api','transport':'one_anonymous_browser_context',
        'reported_total':audit.get('reported_total'),'distinct_ids_observed':len(seen),'records_accepted':len(records),
        'catalogue_pagination_complete':complete,'all_source_rows_mapped':complete and not errors,
        'page_size':120,'source_region_parameter':'98','source_ui_filter_label_observed':'Все регионы',
        'public_terms_records':sum(r['record_kind']=='partner_offer' for r in records),
        'login_gated_records':sum(r['details']['public_partner']['description_authorized'] for r in records),
        'full_program_terms_verified':False,'private_terms_collected':False,'linked_terms_read':False}
    report={'source_id':'ekp','name':'ЕКП — публичный каталог','root':ROOT,'status':'ok' if complete and not errors else 'partial' if records else 'failed',
        'discovered':len(seen),'normalized':len(records),'failed':len(errors),'coverage':json.dumps(meta,ensure_ascii=False),
        'region':None,'errors':errors,'observed_at':observed_at,'robots':robots}
    bundle={'schema_version':2,'run_id':run_id,'observed_at':observed_at,'records':records,'sources':[report]}
    prepare(bundle);(out/'normalized.json').write_text(json.dumps(bundle,ensure_ascii=False,indent=2))
    return bundle


def validate_session_bundle(folder,*,run_id,commit,clock):
    bundle=validate_bundle(folder,run_id=run_id,commit=commit,clock=clock)
    audit=json.loads((Path(folder)/'report.json').read_text());meta=json.loads(bundle['sources'][0]['coverage'])
    if (audit.get('mode')!='one_anonymous_browser_public_api' or
        audit.get('script_sha256')!=hashlib.sha256(SCRIPT.read_bytes()).hexdigest() or
        type(audit.get('reserved_credits')) is not int or not 0<=audit['reserved_credits']<=MAX_CREDITS or
        type(audit.get('provider_requests')) is not int or not 0<=audit['provider_requests']<=MAX_REQUESTS):
        raise ValueError('ekp_session_audit_mismatch')
    count=sum(x['source_count'] for x in audit['pages'])
    if (count!=audit['observed_ids'] or count!=meta['distinct_ids_observed'] or
        audit['pagination_complete']!=meta['catalogue_pagination_complete'] or
        audit['errors']!=bundle['sources'][0]['errors'] or
        (meta['catalogue_pagination_complete'] and count!=meta['reported_total'])):
        raise ValueError('ekp_session_coverage_mismatch')
    return bundle


def main():
    p=argparse.ArgumentParser();p.add_argument('--out',default='ekp-api-output');args=p.parse_args()
    out=Path(args.out);out.mkdir(parents=True,exist_ok=True);(out/'normalized.json').unlink(missing_ok=True)
    run_id=os.environ['GITHUB_RUN_ID']+':'+os.environ['GITHUB_RUN_ATTEMPT']
    bundle=collect(Reader(os.getenv('SCRAPINGANT_API_KEY','')),out,run_id=run_id,observed_at=now(),commit=os.environ['GITHUB_SHA'])
    if os.getenv('GITHUB_OUTPUT'):
        with open(os.environ['GITHUB_OUTPUT'],'a') as f:f.write('has_payload=true\nhas_records='+str(bool(bundle['records'])).lower()+'\n')
    print(json.dumps({'accepted':len(bundle['records']),'status':bundle['sources'][0]['status'],'published':False}))

if __name__=='__main__':
    try:main()
    except Exception:
        print('EKP session collection failed; no publication authorized.');raise SystemExit(1)
