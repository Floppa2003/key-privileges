"""Read PDF links from this run's Coral rules, then reuse the literal publisher.

Only public /media/*.pdf URLs from validated parents are eligible. The existing
free provider key is scoped to this step; no Google token or account is needed.
"""
from __future__ import annotations
import argparse, copy, hashlib, json, os, re, time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit, unquote
import requests
import coral_import as coral
from document_text import extract_pdf, document_records
from free_access_probe import FreeReader, free_plan, ProbeError
from normalized import content_hash
from sheets_normalized import prepare

SOURCE_ID='coral_pdf_documents'
MAX_FILES=8;MAX_CREDITS=52;MAX_BYTES=6_000_000;MAX_SECONDS=480


def now():return datetime.now(timezone.utc).isoformat()
def sha(data):return hashlib.sha256(data).hexdigest()
def is_pdf(url):
    if not isinstance(url,str) or len(url)>1200:return False
    u=urlsplit(url);path=unquote(u.path)
    return (u.scheme=='https' and u.netloc=='coralbonus.ru' and not u.query and not u.fragment
            and re.fullmatch(r'/media/[A-Za-z0-9_-]+/[^/\\\x00-\x1f]+\.pdf',path,re.I) is not None
            and '..' not in path and not re.search(r'%2f|%5c|%00|%25',u.path,re.I))


def discover(records):
    found={}
    for r in records:
        if r['source_id']!='coral_rule_documents':continue
        for link in r['details']['public_rule']['unread_links']:
            url=link['url']
            if not is_pdf(url):continue
            item=found.setdefault(url,{'url':url,'parents':[]})
            parent={'record_id':r['id'],'source_url':r['source_url'],'content_sha256':r['content_sha256'],
                    'title':r['title'],'label':link['label']}
            if parent not in item['parents']:item['parents'].append(parent)
    return [found[u] for u in sorted(found)]


class Reader:
    def __init__(self,key,*,get=requests.get,clock=time.monotonic,sleep=time.sleep):
        self.key=key;self.get=get;self.clock=clock;self.sleep=sleep;self.deadline=clock()+MAX_SECONDS
        self.requests=[];self.reserved=0;self.charged=0;self.stopped=False;self.next_at=0
        self.guard=FreeReader(key,[{'url':'https://coralbonus.ru/'}],get=get,max_credits=MAX_CREDITS,max_requests=16)
        usage,_=self.guard._request('usage',{});self.opening_balance=free_plan(usage)
        if self.opening_balance<MAX_CREDITS:raise ProbeError('insufficient_free_credits')

    def read(self,url,delay=5):
        if not is_pdf(url):raise ValueError('cp_pdf_scope')
        failure='cp_no_pdf'
        for proxy,cost in (('datacenter',1),('residential',25)):
            wait=max(0,self.next_at-self.clock())
            if self.stopped or self.reserved+cost>MAX_CREDITS or len(self.requests)>=16 or self.clock()+wait+60>self.deadline:
                raise ValueError('cp_budget_or_stopped')
            self.sleep(wait);self.reserved+=cost
            item={'url':url,'proxy':proxy,'reserved':cost,'requested_at':now()};self.requests.append(item)
            try:
                with self.get('https://api.scrapingant.com/v2/general',params={'url':url,'x-api-key':self.key,
                    'browser':'false','proxy_country':'RU','proxy_type':proxy,'timeout':'40'},
                    timeout=(10,55),allow_redirects=False,stream=True) as response:
                    item['provider_status']=response.status_code
                    if response.status_code in (401,402,403,409,429) or response.headers.get('Retry-After'):
                        self.stopped=True;raise ValueError('cp_provider_auth_quota_or_rate_limit')
                    if response.status_code!=200:raise ValueError('cp_provider_non_success')
                    charge=str(response.headers.get('Ant-credits-cost',''))
                    if not charge.isdigit() or int(charge)>cost:self.stopped=True;raise ValueError('cp_cost_contract')
                    item['charged']=int(charge);self.charged+=int(charge)
                    status=response.headers.get('Ant-page-status-code','');item['origin_status']=status
                    if status=='429' or response.headers.get('ant-original-header-retry-after'):
                        self.stopped=True;raise ValueError('cp_source_rate_limit')
                    if status!='200':raise ValueError('cp_origin_refusal')
                    mime=response.headers.get('Content-Type','').split(';')[0].strip().lower()
                    item['content_type']=mime
                    if mime!='application/pdf':raise ValueError('cp_non_pdf_content_type')
                    data=bytearray()
                    for block in response.iter_content(65536):
                        data.extend(block)
                        if len(data)>MAX_BYTES:self.stopped=True;raise ValueError('cp_pdf_size_bound')
                    if self.key.encode() in data:self.stopped=True;raise ValueError('cp_credential_echo')
                    if not data.startswith(b'%PDF-'):raise ValueError('cp_non_pdf_magic')
                    item.update(result='pdf',bytes=len(data),sha256=sha(data));return bytes(data),len(self.requests)-1
            except Exception as exc:
                failure=str(exc) if isinstance(exc,ValueError) and str(exc).startswith('cp_') else 'cp_transport_error'
                item['error']=failure
                if failure not in ('cp_provider_non_success','cp_origin_refusal','cp_transport_error'):raise ValueError(failure) from None
            finally:item['finished_at']=now();self.next_at=self.clock()+delay
        raise ValueError(failure)


def rows_for(data,entry,result,observed_at):
    doc=extract_pdf(data,allow_ocr=False)
    rows=document_records(SOURCE_ID,'pdf:'+sha(entry['url'].encode()),'CoralBonus — PDF-правила',None,
        entry['url'],observed_at,doc,parent_source=entry['parents'][0]['source_url'],
        parent_sha256=entry['parents'][0]['content_sha256'],label=entry['parents'][0]['label'],
        extra_details={'retrieval_method':'coral_source_linked_pdf_free_api_v1','parent_references':entry['parents'],
                       'download_receipt':result,'source_account_used':False,'linked_further_documents_read':False})
    for row in rows:
        row['warnings']+=['parent_html_and_pdf_equivalence_not_assumed','source_link_is_not_current_eligibility']
        row['content_sha256']=content_hash(row)
    return rows


def assemble(base,audit,folder):
    entries=discover(base['records'])
    if [x['url'] for x in audit['results']]!=[e['url'] for e in entries]:raise ValueError('cp_discovery_mismatch')
    output=[];errors=[];downloaded=0;partial=0
    for index,(entry,result) in enumerate(zip(entries,audit['results'])):
        if set(result)-{'url','file','sha256','receipt','error'}:raise ValueError('cp_result_shape')
        if 'error' in result:
            if set(result)!={'url','error'} or not re.fullmatch(r'cp_[a-z_]+',result['error']):raise ValueError('cp_error_shape')
            errors.append({'url':entry['url'],'reason':result['error']});continue
        if index>=MAX_FILES or result['file']!=sha(entry['url'].encode())+'.pdf':raise ValueError('cp_file_identity')
        path=folder/'pdf'/result['file']
        if path.stat().st_size>MAX_BYTES:raise ValueError('cp_file_bound')
        data=path.read_bytes()
        if sha(data)!=result['sha256']:raise ValueError('cp_file_hash')
        n=result['receipt']
        if type(n) is not int or not 0<=n<len(audit['requests']):raise ValueError('cp_receipt_index')
        receipt=audit['requests'][n]
        if (receipt.get('url')!=entry['url'] or receipt.get('result')!='pdf' or receipt.get('provider_status')!=200
            or receipt.get('origin_status')!='200' or receipt.get('sha256')!=sha(data)
            or receipt.get('bytes')!=len(data) or receipt.get('content_type')!='application/pdf'):
            raise ValueError('cp_receipt_mismatch')
        rows=rows_for(data,entry,receipt,base['observed_at']);output+=rows;downloaded+=1
        if rows[0]['details']['document_errors']:
            partial+=1;errors.append({'url':entry['url'],'reason':'cp_native_text_partial'})
    combined=copy.deepcopy(base)
    if entries:
        meta={'method':'source_linked_pdf_free_api_v1','discovered_files':len(entries),'downloaded_files':downloaded,
              'native_text_partial_files':partial,'output_parts':len(output),'account_used':False,'ocr_used':False,
              'source_links_discovered_from_current_rules':True,'pdf_html_equivalence_verified':False,
              'scrapingant_reserved':audit['reserved'],'scrapingant_confirmed_cost':sum(r.get('charged',0) for r in audit['requests'])}
        combined['sources'].append({'source_id':SOURCE_ID,'name':'CoralBonus — связанные PDF-правила','root':coral.c.CLUB,
            'status':('partial' if errors else 'ok') if output else 'failed',
            'discovered':len(output)+len(entries)-downloaded,'normalized':len(output),'failed':len(errors),
            'errors':errors,'coverage':json.dumps(meta,ensure_ascii=False),'region':None,'observed_at':base['observed_at']})
        combined['records']+=output
    prepare(combined);return combined


def validate_bundle(folder,run_id,commit,clock):
    folder=Path(folder);base=coral.validate_bundle(folder,run_id,commit,clock)
    audit=json.loads((folder/'pdf-report.json').read_text())
    if (audit.get('run_id')!=run_id or audit.get('commit')!=commit or audit.get('base_sha256')!=sha((folder/'normalized.json').read_bytes())
        or audit.get('source_account_used') is not False or audit.get('free_only') is not True):raise ValueError('cp_bundle_identity')
    start,end=map(coral.instant,(audit['started_at'],audit['finished_at']))
    original=json.loads((folder/'evidence.json').read_text())
    if not coral.instant(original['finished_at'])<=start<=end<=clock or (end-start).total_seconds()>MAX_SECONDS+70:raise ValueError('cp_bundle_time')
    requests_=audit['requests']
    if not isinstance(requests_,list) or len(requests_)>MAX_FILES*2 or sum(x['reserved'] for x in requests_)!=audit['reserved'] or not 0<=audit['reserved']<=MAX_CREDITS:
        raise ValueError('cp_budget_evidence')
    entries={e['url'] for e in discover(base['records'])};seen={};last=start
    observations={o['url']:o for o in original['observations']}
    policy=coral.policy(coral.checked(observations[coral.ROBOTS])) if entries else None
    for item in requests_:
        a,b=map(coral.instant,(item['requested_at'],item['finished_at']))
        if not last<=a<=b<=end or item['url'] not in entries or not policy.can_fetch(item['url'],'LoyaltyCatalogResearchBot'):raise ValueError('cp_request_binding')
        seq=seen.setdefault(item['url'],[]);seq.append(item['proxy'])
        if seq not in (['datacenter'],['datacenter','residential']):raise ValueError('cp_request_repetition')
        if item['reserved']!={'datacenter':1,'residential':25}[item['proxy']] or not 0<=item.get('charged',0)<=item['reserved']:raise ValueError('cp_cost_binding')
        last=b
    combined=assemble(base,audit,folder)
    if json.loads((folder/'combined.json').read_text())!=combined:raise ValueError('cp_output_reconstruction')
    return combined


def collect(folder,key,run_id,commit,*,reader_factory=Reader):
    folder=Path(folder);base=coral.validate_bundle(folder,run_id,commit,datetime.now(timezone.utc));entries=discover(base['records'])
    audit={'run_id':run_id,'commit':commit,'base_sha256':sha((folder/'normalized.json').read_bytes()),'started_at':now(),
           'source_account_used':False,'free_only':True,'reserved':0,'requests':[],'results':[]}
    (folder/'pdf').mkdir(exist_ok=True);reader=None;initial=None
    try:
        if entries:
            if not key:raise ValueError('cp_key_not_configured')
            reader=reader_factory(key)
            audit['opening_balance']=reader.opening_balance
    except Exception:initial='cp_free_provider_unavailable' if key else 'cp_key_not_configured'
    original=json.loads((folder/'evidence.json').read_text());obs={o['url']:o for o in original['observations']}
    policy=coral.policy(coral.checked(obs[coral.ROBOTS])) if entries else None
    rate=policy.request_rate('LoyaltyCatalogResearchBot') if policy else None
    delay=max(5,policy.crawl_delay('LoyaltyCatalogResearchBot') or 0,rate.seconds/rate.requests if rate else 0) if policy else 5
    if delay>60:initial='cp_source_delay_bound'
    for index,entry in enumerate(entries):
        result={'url':entry['url']};audit['results'].append(result)
        try:
            if initial:raise ValueError(initial)
            if index>=MAX_FILES:raise ValueError('cp_file_limit')
            if not policy.can_fetch(entry['url'],'LoyaltyCatalogResearchBot'):raise ValueError('cp_robots_disallow')
            data,receipt=reader.read(entry['url'],delay)
            # Extraction is required before recording a successful publication candidate.
            extract_pdf(data,allow_ocr=False)
            name=sha(entry['url'].encode())+'.pdf';(folder/'pdf'/name).write_bytes(data)
            result.update(file=name,sha256=sha(data),receipt=receipt)
        except Exception as exc:
            reason=str(exc) if isinstance(exc,ValueError) and re.fullmatch('cp_[a-z_]+',str(exc)) else 'cp_download_or_extraction_failed'
            result['error']=reason
    if reader:audit.update(requests=reader.requests,reserved=reader.reserved)
    audit['finished_at']=now();combined=assemble(base,audit,folder)
    (folder/'pdf-report.json').write_text(json.dumps(audit,ensure_ascii=False,indent=2))
    (folder/'combined.json').write_text(json.dumps(combined,ensure_ascii=False))
    validate_bundle(folder,run_id,commit,datetime.now(timezone.utc))
    return combined


def main():
    p=argparse.ArgumentParser();p.add_argument('--input',default='coral-import-output');args=p.parse_args()
    try:
        b=collect(args.input,os.environ.get('SCRAPINGANT_API_KEY',''),os.environ['GITHUB_RUN_ID']+':'+os.environ['GITHUB_RUN_ATTEMPT'],os.environ['GITHUB_SHA'])
        print(json.dumps({'combined_records':len(b['records']),'pdf_parts':sum(r['source_id']==SOURCE_ID for r in b['records'])}))
    except Exception as exc:
        print('Coral PDF stage failed: '+(str(exc) if isinstance(exc,ValueError) and re.fullmatch('cp_[a-z_]+',str(exc)) else type(exc).__name__))
        raise SystemExit(1)
if __name__=='__main__':main()
