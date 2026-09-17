"""Supplementary public EKP rules, never account-only terms or extra discounts."""
from __future__ import annotations
import argparse, hashlib, json, os, re, time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit, urljoin
import requests
from bs4 import BeautifulSoup
from protego import Protego
from normalized import make_offer, text, content_hash
from document_text import extract_pdf, document_records
from free_access_probe import FreeReader, free_plan, LOCATION_JS
from sheets_normalized import prepare

SID='ekp_linked_rules'
METHOD='ekp_source_linked_rules_v1'
ROOT='https://ekp.spb.ru/capabilities/loyalty/'
HOSTS=('ekp.spb.ru','xn--b1abfnwkklk1gdn5a.xn--p1ai','mpclinic.ru','vamprivet.ru')
MAX_FILES=12
MAX_BYTES=6_000_000
MAX_CREDITS=400
MAX_SECONDS=720
BOT='LoyaltyCatalogResearchBot'
RULE_LABEL=re.compile(r'правил|подробн|услов|прейскурант|приложен',re.I)
DENIAL=re.compile(r'access denied|just a moment|проверка безопасности|доступ к сайту временно ограничен',re.I)

def now():return datetime.now(timezone.utc).isoformat()
def sha(data):return hashlib.sha256(data).hexdigest()
def instant(value):
    result=datetime.fromisoformat(value.replace('Z','+00:00'))
    if result.tzinfo is None:raise ValueError('el_timezone')
    return result

def checked_url(value):
    if not isinstance(value,str) or len(value)>1200:raise ValueError('el_url')
    u=urlsplit(value)
    if u.scheme!='https' or u.username or u.password or u.port not in (None,443) or u.query or u.fragment or '..' in u.path or '\\' in value:
        raise ValueError('el_url')
    host=u.hostname.encode('idna').decode() if u.hostname else ''
    if host not in HOSTS:raise ValueError('el_unreviewed_host')
    path=u.path or '/'
    if '%' in path or any(c.isspace() or ord(c)<32 for c in value):raise ValueError('el_url')
    if path!='/robots.txt':
        allowed=(host=='ekp.spb.ru' and path.rstrip('/')=='/silverage' or
            host==HOSTS[1] and re.fullmatch(r'/img/dogovori/[A-Za-z0-9_.-]+\.pdf',path,re.I) or
            host=='mpclinic.ru' and re.fullmatch(r'/upload/[A-Za-z0-9_.-]+\.pdf',path,re.I) or
            host=='vamprivet.ru' and path.rstrip('/')=='/supreme-restaurants')
        if not allowed:raise ValueError('el_unreviewed_path')
    return urlunsplit(('https',host,path,'',''))

def discover(base,clock):
    prepare(base)
    if not 0<=(clock-instant(base['observed_at'])).total_seconds()<=604800:raise ValueError('el_parent_snapshot_age')
    targets={};inventory={};gated=0
    for r in base['records']:
        if r['source_id']!='ekp':raise ValueError('el_foreign_parent')
        row=r['details']['public_partner']
        if row['description_authorized']:
            gated+=1;continue
        if not row['active']:continue
        for field in ('loyaltyDescription','discountScheme'):
            for a in BeautifulSoup(row.get(field,''),'html.parser').select('a[href]'):
                original=a['href'];label=a.get_text(' ',strip=True)
                entry=inventory.setdefault(original,{'url':original,'labels':[],'classification':'merchant_or_redemption_reference'})
                if label not in entry['labels']:entry['labels'].append(label)
                if not (urlsplit(original).path.lower().endswith('.pdf') or RULE_LABEL.search(label)):continue
                try:url=checked_url(original)
                except ValueError as exc:
                    entry['classification']=str(exc);continue
                entry['classification']='selected_public_rules'
                item=targets.setdefault(url,{'url':url,'parents':[]})
                parent={'record_id':r['id'],'source_url':r['source_url'],'content_sha256':r['content_sha256'],
                    'observed_at':r['observed_at'],'partner':r['partner_name'],'field':field,'label':label,'original_link':original}
                if parent not in item['parents']:item['parents'].append(parent)
    return [targets[u] for u in sorted(targets)],{'links':list(inventory.values()),'gated_parent_count':gated,
        'parent_run':base['run_id'],'parent_observed_at':base['observed_at'],'parent_is_not_a_new_source_observation':True}

def clean_html(data):
    soup=BeautifulSoup(data,'html.parser')
    if not soup.html:raise ValueError('el_not_html')
    title=soup.title.get_text(' ',strip=True) if soup.title else ''
    if DENIAL.search(title) or soup.select('input[type=password]'):raise ValueError('el_access_boundary')
    for n in soup.select('script,style,noscript,form,input,textarea,button,iframe,svg,nav,header,footer,[hidden],[aria-hidden="true"]'):n.decompose()
    for n in soup.find_all(True):
        n.attrs={k:v for k,v in n.attrs.items() if k in ('id','class','href','colspan','rowspan')}
        if n.has_attr('href') and urlsplit(n['href']).scheme not in ('https','http'):del n.attrs['href']
    return str(soup)

def html_fields(data):
    soup=BeautifulSoup(data,'html.parser');body=soup.find('main') or soup.body
    if body is None:raise ValueError('el_no_content')
    headings=[text(h.get_text(' ',strip=True)) for h in body.select('h1') if h.get_text(strip=True)]
    if len(set(headings))!=1:raise ValueError('el_html_needs_render_or_scope_review')
    value=text(body.get_text('\n',strip=True))
    if not 120<=len(value)<=35000 or DENIAL.search(value[:500]):raise ValueError('el_html_needs_render_or_scope_review')
    return headings[0],value

class Reader:
    def __init__(self,key='',*,session=None,sleep=time.sleep):
        self.session=session or requests.Session();self.session.trust_env=False
        self.key=key;self.sleep=sleep;self.started=time.monotonic();self.reserved=0;self.charged=0
        self.receipts=[];self.policies={};self.next_at={};self.stopped=set();self.free_checked=False;self.provider_halted=False;self.delays={}
    def limit(self,host):
        delay=max(0,self.next_at.get(host,0)-time.monotonic())
        if host in self.stopped or len(self.receipts)>=40 or time.monotonic()+delay-self.started>MAX_SECONDS-80:
            raise ValueError('el_budget_or_stopped')
        self.sleep(delay)
    def raw(self,url,*,provider=None,browser=False):
        url=checked_url(url);host=urlsplit(url).hostname;self.limit(host)
        item={'url':url,'transport':provider or 'direct_https','requested_at':now()};self.receipts.append(item)
        try:
            kwargs={'timeout':(5,20),'allow_redirects':False,'stream':True,'headers':{'User-Agent':BOT+'/1.0'}}
            target=url
            if provider:
                if self.provider_halted:raise ValueError('el_provider_stopped')
                if not self.key:raise ValueError('el_free_key_not_available')
                if not self.free_checked:
                    guard=FreeReader(self.key,[{'url':url}]);usage,_=guard._request('usage',{})
                    if free_plan(usage)<MAX_CREDITS:raise ValueError('el_insufficient_free_credits')
                    self.free_checked=True
                cost=(125 if browser else 25) if provider=='residential' else (10 if browser else 1)
                if self.reserved+cost>MAX_CREDITS:raise ValueError('el_credit_budget')
                self.reserved+=cost;item['reserved_credits']=cost
                target='https://api.scrapingant.com/v2/general'
                kwargs['timeout']=(10,75)
                kwargs['params']={'url':url,'x-api-key':self.key,'browser':str(browser).lower(),
                    'proxy_country':'RU','proxy_type':provider,'timeout':'60'}
                if browser:kwargs['params'].update(js_snippet=LOCATION_JS,block_resource=['image','media','font'])
            with self.session.get(target,**kwargs) as response:
                status=response.status_code;item['status']=status
                if response.headers.get('Retry-After') or status==429:
                    self.stopped.add(host);raise ValueError('el_rate_limit')
                if provider:
                    if status in (401,402,403,409,429):raise ValueError('el_provider_auth_quota')
                    if status!=200:raise ValueError('el_provider_unavailable')
                    charge=str(response.headers.get('Ant-credits-cost',''))
                    if not charge.isdigit() or int(charge)>cost:raise ValueError('el_unknown_credit_cost')
                    item['charged_credits']=int(charge);self.charged+=int(charge)
                    status=int(response.headers.get('Ant-page-status-code','0'));item['origin_status']=status
                    if status==429 or response.headers.get('ant-original-header-retry-after'):
                        self.stopped.add(host);raise ValueError('el_rate_limit')
                if status in (301,302,307,308) and not provider:
                    redirect=checked_url(urljoin(url,response.headers.get('Location','')))
                    if urlsplit(redirect).hostname!=host:raise ValueError('el_foreign_redirect')
                    item['redirect']=redirect;return b'',item
                if status!=200:raise ValueError('el_http_'+str(status))
                data=bytearray()
                for block in response.iter_content(65536):
                    data.extend(block)
                    if len(data)>MAX_BYTES:raise ValueError('el_response_size')
                if self.key and self.key.encode() in data:raise ValueError('el_credential_echo')
                item.update(bytes=len(data),sha256=sha(data),mime=response.headers.get('Content-Type','').split(';')[0])
                if browser:
                    dom=BeautifulSoup(bytes(data),'html.parser');actual=dom.html.get('data-loyalty-probe-location','') if dom.html else ''
                    if checked_url(actual).rstrip('/')!=url.rstrip('/'):raise ValueError('el_browser_destination')
                return bytes(data),item
        except Exception as exc:
            code=str(exc) if isinstance(exc,ValueError) and str(exc).startswith('el_') else 'el_transport_error'
            if provider and code in ('el_provider_auth_quota','el_unknown_credit_cost','el_credential_echo','el_rate_limit'):
                self.provider_halted=True
            item['error']=code;raise ValueError(code) from None
        finally:item['finished_at']=now();self.next_at[host]=time.monotonic()+self.delays.get(host,3)
    def read_policy(self,url):
        host=urlsplit(url).hostname
        if host in self.policies:return self.policies[host]
        policy_url='https://'+host+'/robots.txt'
        last='el_policy_unavailable'
        for mode in (None,'datacenter','residential'):
            try:
                raw,receipt=self.raw(policy_url,provider=mode)
                if receipt.get('redirect'):raise ValueError('el_policy_redirect')
                from public_transport import robots_document
                try:body,_=robots_document(200,raw.decode('utf8'))
                except (RuntimeError,UnicodeError):raise ValueError('el_policy_unreadable') from None
                if not re.search(r'^\s*User-agent:',body,re.M|re.I):raise ValueError('el_policy_unreadable')
                rules=Protego.parse(body);self.policies[host]=rules;return rules
            except ValueError as exc:
                last=str(exc)
                if last in ('el_http_404','el_http_410'):
                    self.policies[host]=Protego.parse('User-agent: *\nAllow: /');return self.policies[host]
                if last not in ('el_transport_error','el_provider_unavailable'):break
        raise ValueError(last)
    def read(self,url):
        rules=self.read_policy(url)
        delay=max(3,rules.crawl_delay(BOT) or 0)
        rate=rules.request_rate(BOT)
        if rate:delay=max(delay,rate.seconds/rate.requests)
        if delay>30:raise ValueError('el_policy_delay_bound')
        host=urlsplit(url).hostname;self.delays[host]=delay
        self.next_at[host]=max(self.next_at.get(host,0),time.monotonic()+delay)
        if not rules.can_fetch(url,BOT):raise ValueError('el_source_policy')
        last='el_unread'
        for mode in (None,'datacenter','residential'):
            try:
                current=url
                for _ in range(3):
                    raw,receipt=self.raw(current,provider=mode,browser=bool(mode and not url.lower().endswith('.pdf')))
                    if receipt.get('redirect'):
                        current=receipt['redirect']
                        if not rules.can_fetch(current,BOT):raise ValueError('el_source_policy')
                        continue
                    break
                else:raise ValueError('el_redirect_limit')
                if url.lower().endswith('.pdf'):
                    if not raw.startswith(b'%PDF-') or receipt['mime']!='application/pdf':raise ValueError('el_not_pdf')
                    return raw,receipt
                raw=clean_html(raw).encode();html_fields(raw)
                return raw,receipt
            except ValueError as exc:
                last=str(exc)
                if last not in ('el_transport_error','el_provider_unavailable','el_html_needs_render_or_scope_review','el_no_content'):break
        raise ValueError(last)

def rows_for(data,entry,receipt,observed_at):
    names=sorted({p['partner'] for p in entry['parents']});partner=names[0] if len(names)==1 else None
    detail={'retrieval_method':METHOD,'parent_references':entry['parents'],'download_receipt':receipt,
        'source_account_used':False,'eligibility_verified':False,'recursive_links_read':False}
    if data.startswith(b'%PDF-'):
        doc=extract_pdf(data)
        rows=document_records(SID,'pdf:'+sha(entry['url'].encode()),'ЕКП — связанные публичные условия',partner,
            entry['url'],observed_at,doc,parent_source=entry['parents'][0]['source_url'],
            parent_sha256=entry['parents'][0]['content_sha256'],label=entry['parents'][0]['label'],extra_details=detail)
    else:
        title,value=html_fields(data)
        rows=[make_offer(SID,'html:'+sha(entry['url'].encode()),'ЕКП — связанные публичные условия',partner,'',
            entry['url'],observed_at,title=title,conditions=value,record_kind='program_rules',source_status='public_linked_rules_text',
            details={**detail,'public_rule_text':value},warnings=['linked_rules_not_additional_discounts','user_eligibility_not_verified'])]
    for r in rows:
        r['warnings'].append('parent_snapshot_time_separate_from_document_read')
        r['content_sha256']=content_hash(r)
    return rows

def assemble(base,audit,folder):
    entries,inventory=discover(base,instant(audit['started_at']))
    if inventory!=audit['inventory'] or [e['url'] for e in entries]!=[r['url'] for r in audit['results']]:raise ValueError('el_inventory_mismatch')
    rows=[];errors=[];downloaded=0
    for i,(entry,result) in enumerate(zip(entries,audit['results'])):
        if result.get('error'):
            if not re.fullmatch(r'el_[a-z0-9_]+',result['error']):raise ValueError('el_error_shape')
            errors.append({'url':entry['url'],'reason':result['error']});continue
        if i>=MAX_FILES or result['file']!=sha(entry['url'].encode())+('.pdf' if entry['url'].lower().endswith('.pdf') else '.html'):
            raise ValueError('el_file_identity')
        target=entry['url'];visited=set()
        for _ in range(3):
            if target==result['receipt'].get('url'):break
            if target in visited:raise ValueError('el_redirect_loop')
            visited.add(target)
            hops=[r['redirect'] for r in audit['requests'] if r['url']==target and r.get('redirect')]
            if len(set(hops))!=1:raise ValueError('el_unbound_receipt')
            target=checked_url(hops[0])
            if urlsplit(target).hostname!=urlsplit(entry['url']).hostname:raise ValueError('el_foreign_redirect')
        else:raise ValueError('el_unbound_receipt')
        data=(Path(folder)/'objects'/result['file']).read_bytes()
        if sha(data)!=result['sha256'] or len(data)>MAX_BYTES:raise ValueError('el_object_hash')
        receipt=result['receipt']
        if receipt not in audit['requests'] or receipt.get('origin_status',receipt['status'])!=200 or receipt.get('error'):
            raise ValueError('el_receipt')
        if not entry['url'].lower().endswith('.pdf') and data!=clean_html(data).encode():raise ValueError('el_unsanitized_html')
        if data.startswith(b'%PDF-'):
            # OCR was already executed once during collection; validate its saved
            # page identities and exact parts, never perform it again on publish.
            doc=result['document']
            if doc['document_sha256']!=sha(data):raise ValueError('el_pdf_hash')
            import io
            from pypdf import PdfReader
            count=len(PdfReader(io.BytesIO(data),strict=True).pages)
            if doc['page_count']!=count or [p['number'] for p in doc['pages']]!=list(range(1,count+1)):
                raise ValueError('el_pdf_page_identity')
            if doc['ocr_pages']!=sum(p['method']=='ocr_unverified' for p in doc['pages']):
                raise ValueError('el_ocr_page_count')
            if any(p['sha256']!=sha(p['text'].encode()) for p in doc['pages']):raise ValueError('el_pdf_page_hash')
            names=sorted({p['partner'] for p in entry['parents']})
            partrows=document_records(SID,'pdf:'+sha(entry['url'].encode()),'ЕКП — связанные публичные условия',names[0] if len(names)==1 else None,
                entry['url'],audit['started_at'],doc,parent_source=entry['parents'][0]['source_url'],parent_sha256=entry['parents'][0]['content_sha256'],
                label=entry['parents'][0]['label'],extra_details={'retrieval_method':METHOD,'parent_references':entry['parents'],
                'download_receipt':receipt,'source_account_used':False,'eligibility_verified':False,'recursive_links_read':False})
            for r in partrows:r['warnings'].append('parent_snapshot_time_separate_from_document_read');r['content_sha256']=content_hash(r)
            if doc['errors']:errors.append({'url':entry['url'],'reason':'el_document_text_partial'})
        else:partrows=rows_for(data,entry,receipt,audit['started_at'])
        rows.extend(partrows);downloaded+=1
    report={'source_id':SID,'name':'ЕКП — связанные публичные условия','root':ROOT,
        'status':('partial' if errors else 'ok') if rows else 'failed','discovered':max(len(entries),len(rows)),
        'normalized':len(rows),'failed':len(errors),'errors':errors,'region':None,'observed_at':audit['started_at'],
        'coverage':json.dumps({'method':METHOD,'discovered_documents':len(entries),'downloaded_documents':downloaded,
            'parent_run':base['run_id'],'parent_observed_at':base['observed_at'],'gated_parent_count':inventory['gated_parent_count'],
            'public_reference_urls':len(inventory['links']),'output_parts':len(rows),'provider_reserved':audit['reserved'],
            'provider_charged':sum(r.get('charged_credits',0) for r in audit['requests']),
            'account_used':False,'all_external_sites_exhausted':False},ensure_ascii=False)}
    result={'schema_version':2,'run_id':audit['run_id'],'observed_at':audit['started_at'],'records':rows,'sources':[report]}
    prepare(result);return result

def validate_bundle(folder,run_id,commit,clock):
    folder=Path(folder);audit=json.loads((folder/'audit.json').read_text());base=json.loads((folder/'parents.json').read_text())
    if audit['run_id']!=run_id or audit['commit']!=commit or not instant(audit['started_at'])<=instant(audit['finished_at'])<=clock:
        raise ValueError('el_run_identity')
    if (clock-instant(audit['started_at'])).total_seconds()>7200 or not 0<=audit['reserved']<=MAX_CREDITS:
        raise ValueError('el_freshness_or_budget')
    if audit.get('source_account_used') is not False or len(audit['requests'])>40:
        raise ValueError('el_privacy_or_request_budget')
    if sum(r.get('reserved_credits',0) for r in audit['requests'])!=audit['reserved']:
        raise ValueError('el_reservation_mismatch')
    for receipt in audit['requests']:
        checked_url(receipt['url'])
        if not instant(audit['started_at'])<=instant(receipt['requested_at'])<=instant(receipt['finished_at'])<=instant(audit['finished_at']):
            raise ValueError('el_receipt_time')
        if not 0<=receipt.get('charged_credits',0)<=receipt.get('reserved_credits',0):
            raise ValueError('el_charge_mismatch')
    result=assemble(base,audit,folder)
    if result!=json.loads((folder/'normalized.json').read_text()):raise ValueError('el_replay_mismatch')
    return result


def validate_record(r):
    d=r['details'];url=checked_url(r['source_url']);parents=d.get('parent_references',[])
    if (r['source_id']!=SID or d.get('retrieval_method')!=METHOD or not parents or len(parents)>200
        or r['record_kind'] not in ('program_rules','source_observation') or r['rates'] or r['tables']
        or r['valid_from'] is not None or r['valid_until'] is not None
        or any(d.get(k) is not False for k in ('source_account_used','eligibility_verified','recursive_links_read'))):
        raise ValueError('el_record_scope')
    for parent in parents:
        if (parent.get('source_url')!='https://ekp.spb.ru/api/portal/loyalty/partners'
            or checked_url(parent.get('original_link'))!=url
            or not re.fullmatch('[a-f0-9]{64}',parent.get('record_id',''))
            or not re.fullmatch('[a-f0-9]{64}',parent.get('content_sha256',''))
            or parent.get('field') not in ('loyaltyDescription','discountScheme')
            or instant(parent['observed_at'])>instant(r['observed_at'])):
            raise ValueError('el_parent_binding')
    names=sorted({p['partner'] for p in parents})
    if r['partner_name']!=(names[0] if len(names)==1 else None):raise ValueError('el_partner_binding')
    if not d.get('live_document_text'):
        if (r['native_id']!='html:'+sha(url.encode()) or r['conditions_text']!=d.get('public_rule_text')
            or r['benefit_text'] or r['source_status']!='public_linked_rules_text'):
            raise ValueError('el_html_binding')
    elif not r['native_id'].startswith('pdf:'+sha(url.encode())):
        raise ValueError('el_pdf_binding')

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--input',default='ekp-upstream/normalized.json');parser.add_argument('--out',default='ekp-linked-output')
    args=parser.parse_args();base=json.loads(Path(args.input).read_text());started=now();entries,inventory=discover(base,instant(started))
    folder=Path(args.out);folder.mkdir(parents=True,exist_ok=True);(folder/'objects').mkdir(exist_ok=True)
    (folder/'parents.json').write_text(json.dumps(base,ensure_ascii=False))
    reader=Reader(os.getenv('SCRAPINGANT_API_KEY',''))
    audit={'run_id':os.environ['GITHUB_RUN_ID']+':'+os.environ['GITHUB_RUN_ATTEMPT'],'commit':os.environ['GITHUB_SHA'],
        'started_at':started,'inventory':inventory,'results':[],'requests':reader.receipts,'reserved':0,'source_account_used':False}
    for i,entry in enumerate(entries):
        result={'url':entry['url']};audit['results'].append(result)
        try:
            if i>=MAX_FILES:raise ValueError('el_file_bound')
            data,receipt=reader.read(entry['url']);pdf=data.startswith(b'%PDF-')
            name=sha(entry['url'].encode())+('.pdf' if pdf else '.html');(folder/'objects'/name).write_bytes(data)
            result.update(file=name,sha256=sha(data),receipt=receipt)
            if pdf:result['document']=extract_pdf(data)
        except Exception as exc:
            code=str(exc) if isinstance(exc,ValueError) and str(exc).startswith('el_') else 'el_collection_error'
            result.clear();result.update(url=entry['url'],error=code)
    audit.update(finished_at=now(),reserved=reader.reserved)
    (folder/'audit.json').write_text(json.dumps(audit,ensure_ascii=False,indent=2))
    bundle=assemble(base,audit,folder);(folder/'normalized.json').write_text(json.dumps(bundle,ensure_ascii=False))
    validate_bundle(folder,audit['run_id'],audit['commit'],datetime.now(timezone.utc))
    print(json.dumps({'records':len(bundle['records']),'status':bundle['sources'][0]['status'],'charged_credits':reader.charged}))

if __name__=='__main__':main()
