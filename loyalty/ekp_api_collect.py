"""Weekly EKP public catalogue, bounded to 300 Free credits and 12 requests.

Read-only POST uses the query observed from the normal anonymous UI. Responses
are projected before persistence. No browser session, coupon issuance, private
source headers or third-party destination is used. The separate existing Google
publisher consumes only this validated same-run bundle.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
import re
import time
from pathlib import Path
import requests
from free_access_probe import FreeReader,ProbeError,free_plan,now
from ekp_catalog import ROOT,API,POLICY,PAGE_SIZE,query,page,public_row,make_record

MAX_CREDITS=300
MAX_REQUESTS=12


class Reader:
    def __init__(self,key,*,get=requests.get,post=requests.post,sleep=time.sleep):
        self.body=None;self.sleep=sleep;self.calls=0;self.reserved=0;self.charged=0
        self.deadline=time.monotonic()+1000;self.last=0;self.interval=1.1;self.balance=None;self.ready=False
        def transport(url,**kwargs):
            if url.endswith('/general') and kwargs.get('params',{}).get('url')==API:
                kwargs['headers']={**kwargs['headers'],'Ant-Content-Type':'application/json'}
                return post(url,data=json.dumps(self.body,separators=(',',':')),**kwargs)
            return get(url,**kwargs)
        self.http=FreeReader(key,[{'url':ROOT}],get=transport)

    def preflight(self):
        payload,_=self.http._request('usage',{});self.balance=free_plan(payload)
        if self.balance<MAX_CREDITS:raise ProbeError('insufficient_weekly_free_credits')
        self.ready=True

    def read(self,url,body=None):
        if not self.ready or self.http.halted or url not in (API,POLICY):raise ProbeError('ekp_reader_not_ready')
        if url==API and body!=query(body.get('pagination',{}).get('offset')):raise ProbeError('ekp_unreviewed_query')
        if self.calls>=MAX_REQUESTS or self.reserved+25>MAX_CREDITS:raise ProbeError('ekp_weekly_budget_bound')
        delay=max(0,self.interval-(time.monotonic()-self.last))
        if delay>60 or time.monotonic()+delay+80>self.deadline:raise ProbeError('ekp_time_or_pacing_bound')
        self.sleep(delay);self.body=body;self.calls+=1;self.reserved+=25
        try:
            raw,meta=self.http._request('general',{'url':url,'browser':'false','proxy_country':'RU','proxy_type':'residential','timeout':'60'})
        finally:self.last=time.monotonic()
        c=str(meta.get('Ant-credits-cost',''));s=str(meta.get('Ant-page-status-code',''))
        if not c.isdigit() or int(c)>25:self.http.halted=True;raise ProbeError('ekp_cost_contract_changed')
        self.charged+=int(c)
        if meta.get('ant-original-header-retry-after') or s=='429':self.http.halted=True;raise ProbeError('ekp_source_rate_limit')
        if s!='200':raise ProbeError('ekp_origin_http_refusal')
        from public_transport import check_response
        check_response(200,raw)
        return raw

    def closing_balance(self):
        if self.http.halted:return None
        try:payload,_=self.http._request('usage',{});return free_plan(payload)
        except ProbeError:return None



def read_policy(reader, audit):
    """One paced retry only for the provider's documented unreachable-route404.

    No target refusal, authentication, quota, challenge or malformed source
    response is retried. Both attempts consume the same original per-run budget.
    """
    attempts=audit.setdefault('policy_attempts',[])
    for number in range(2):
        entry={'number':number+1,'started_at':now()};attempts.append(entry)
        try:
            raw=reader.read(POLICY)
            entry.update(result='source_document_received',finished_at=now())
            return raw
        except ProbeError as exc:
            entry.update(error=str(exc),finished_at=now())
            if number or str(exc)!='provider_http_404' or getattr(getattr(reader,'http',None),'halted',False):
                raise
            entry['retry_delay_seconds']=10
            reader.sleep(10)
    raise ProbeError('ekp_policy_retry_exhausted')



def read_page(reader, request, audit):
    """Retry a known read-only query once on provider route404, at most twice/run.

    A source refusal, challenge, auth/rate/quota or schema error is never retried.
    The same 300-credit/12-request cap accounts for unsuccessful requests too.
    """
    attempts=audit.setdefault('page_attempts',[])
    for number in range(2):
        item={'offset':request['pagination']['offset'],'number':number+1,'started_at':now()}
        attempts.append(item)
        try:
            raw=reader.read(API,request)
            item.update(result='source_document_received',finished_at=now())
            return raw
        except ProbeError as exc:
            item.update(error=str(exc),finished_at=now())
            if (number or str(exc)!='provider_http_404' or audit.get('page_retries',0)>=2
                or getattr(getattr(reader,'http',None),'halted',False)):
                raise
            audit['page_retries']=audit.get('page_retries',0)+1
            item['retry_delay_seconds']=10
            reader.sleep(10)
    raise ProbeError('ekp_page_retry_exhausted')


def collect(reader,out,*,run_id,observed_at,commit):
    from public_transport import robots_document
    from protego import Protego
    from sheets_normalized import prepare
    out=Path(out);out.mkdir(parents=True,exist_ok=True)
    records=[];seen=set();total=None;offset=0;pages=[];errors=[];completed=False
    report={'source_id':'ekp','name':'ЕКП — публичный каталог','root':ROOT,'status':'failed','discovered':0,
        'normalized':0,'failed':0,'coverage':'not_collected','region':None,'errors':errors,'observed_at':observed_at}
    audit={'run_id':run_id,'commit':commit,'started_at':observed_at,'pages':pages,'source_account_used':False,'publication':False}
    def save():
        audit.update(requests=reader.calls,reserved_credits=reader.reserved,known_charged_credits=reader.charged,
                     accepted_records=len(records),errors=errors)
        (out/'report.json').write_text(json.dumps(audit,ensure_ascii=False,indent=2))
    try:
        reader.preflight();audit['opening_balance']=reader.balance;save()
        raw=read_policy(reader,audit);rules,state=robots_document(200,raw);policy=Protego.parse(rules)
        if not policy.can_fetch(API,'LoyaltyCatalogResearchBot') or not policy.can_fetch(ROOT,'LoyaltyCatalogResearchBot'):
            raise ProbeError('robots_disallow')
        rate=policy.request_rate('LoyaltyCatalogResearchBot')
        reader.interval=max(1.1,policy.crawl_delay('LoyaltyCatalogResearchBot') or 0,rate.seconds/rate.requests if rate else 0)
        (out/'robots.txt').write_text(rules)
        report['robots']={'state':state,'http_status':200,'sha256':hashlib.sha256(raw.encode()).hexdigest()}
        while reader.calls<MAX_REQUESTS:
            request=query(offset)
            try:
                raw=read_page(reader,request,audit)
            except ProbeError as exc:
                if str(exc)!='provider_http_404' or total is None:raise
                # The source total from an earlier successful current page bounds
                # the remaining read-only offsets. A missing page remains a gap;
                # it does not discard later pages or become an empty result.
                errors.append({'phase':'page','offset':offset,'reason':'provider_http_404'})
                audit.setdefault('missing_page_offsets',[]).append(offset)
                offset+=min(PAGE_SIZE,total-offset);save()
                if offset==total:break
                continue
            finished=now();payload=json.loads(raw)
            ids=page(payload,offset)
            if total is None:total=payload['total']
            if payload['total']!=total or seen.intersection(ids):raise ProbeError('ekp_catalogue_changed_during_scan')
            if not ids and offset<total:raise ProbeError('ekp_premature_empty_page')
            if len(ids)!=min(PAGE_SIZE,total-offset):raise ProbeError('ekp_short_nonfinal_page')
            seen.update(ids);digest=hashlib.sha256(raw.encode()).hexdigest();public=[];page_errors=[]
            for source in payload['partners']:
                try:
                    projected=public_row(source)
                    record=make_record(projected,observed_at,request=request,response_sha=digest,observed_total=total,completed_at=finished)
                    public.append(projected);records.append(record)
                except (ValueError,TypeError,KeyError):
                    page_errors.append({'phase':'record','native_id':source['id'],'reason':'ekp_source_fields_not_accepted'})
            errors.extend(page_errors)
            filename=f'page-{offset:04d}.json'
            (out/filename).write_text(json.dumps({'total':total,'offset':offset,'partners':public},ensure_ascii=False,indent=2))
            pages.append({'file':filename,'request':request,'source_count':len(ids),'accepted':len(public),
                'source_response_sha256':digest,'public_projection_sha256':hashlib.sha256((out/filename).read_bytes()).hexdigest(),
                'completed_at':finished,'origin_status':200})
            save();offset+=len(ids)
            if offset==total:
                completed=len(seen)==total
                break
        if not completed and (total is None or offset<total):
            errors.append({'phase':'coverage','reason':'ekp_weekly_budget_bound'})
    except Exception as exc:
        code=str(exc);reason=code if isinstance(exc,(ProbeError,RuntimeError,ValueError)) and re.fullmatch(r'[a-z_0-9]{1,100}',code) else type(exc).__name__
        errors.append({'phase':'collection','reason':reason})
    report.update(discovered=len(seen),normalized=len(records),failed=len(errors),status='ok' if completed and not errors else 'partial' if records else 'failed',
        coverage=json.dumps({'method':'anonymous_source_catalogue_api','reported_total':total,'distinct_ids_observed':len(seen),
            'records_accepted':len(records),'catalogue_pagination_complete':completed,'all_source_rows_mapped':completed and not errors,
            'page_size':PAGE_SIZE,'source_region_parameter':'98','source_ui_filter_label_observed':'Все регионы',
            'public_terms_records':sum(x['record_kind']=='partner_offer' for x in records),
            'login_gated_records':sum(x['details']['public_partner']['description_authorized'] for x in records),
            'full_program_terms_verified':False,'private_terms_collected':False,'linked_terms_read':False},ensure_ascii=False))
    audit['closing_balance']=reader.closing_balance();audit['finished_at']=now();save()
    bundle={'schema_version':2,'run_id':run_id,'observed_at':observed_at,'records':records,'sources':[report]}
    prepare(bundle)
    (out/'normalized.json').write_text(json.dumps(bundle,ensure_ascii=False,indent=2))
    return bundle


def main():
    p=argparse.ArgumentParser();p.add_argument('--out',default='ekp-api-output');args=p.parse_args()
    out=Path(args.out);out.mkdir(parents=True,exist_ok=True);(out/'normalized.json').unlink(missing_ok=True)
    key=os.getenv('SCRAPINGANT_API_KEY','')
    if not key:raise ProbeError('missing_api_key')
    run_id=os.environ['GITHUB_RUN_ID']+':'+os.environ['GITHUB_RUN_ATTEMPT'];commit=os.environ['GITHUB_SHA']
    bundle=collect(Reader(key),out,run_id=run_id,observed_at=now(),commit=commit)
    if os.getenv('GITHUB_OUTPUT'):
        with open(os.environ['GITHUB_OUTPUT'],'a') as f:f.write('has_payload=true\nhas_records='+str(bool(bundle['records'])).lower()+'\n')
    print(json.dumps({'accepted':len(bundle['records']),'status':bundle['sources'][0]['status'],'published':False}))

if __name__=='__main__':
    try:main()
    except Exception:
        print('EKP collection failed; publication not authorized.');raise SystemExit(1)
