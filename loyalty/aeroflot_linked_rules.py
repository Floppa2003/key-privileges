"""Public rules linked by Aeroflot; direct HTTPS, bounded pagination, no accounts.

The root catalogue is a recent discovery parent, not a new observation. Only
reviewed external rule routes and their public redirects are followed. Product
exclusion membership and PDF clauses remain conditions, not additional benefits.
"""
from __future__ import annotations
import argparse, hashlib, json, os, re, time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin, urlsplit, urlunsplit, parse_qsl
import requests
from bs4 import BeautifulSoup
from protego import Protego
from normalized import make_offer, text, content_hash
from sheets_normalized import prepare
from document_text import extract_pdf, document_records

SID='aeroflot_linked_rules'
METHOD='aeroflot_source_linked_rules_v1'
PROGRAM='Аэрофлот Бонус — связанные публичные условия'
ROOT='https://www.aeroflot.ru/ru-ru/afl_bonus/partners'
STOLETOV='/catalog/extra/spiski-tovarov/tovary-bez-skidok/'
PARK='/vazhno-znat/pravila-ispolzovaniya.html'
HOSTS=('stoletov.ru','parkingsvo.ru','parking.svo.aero','parking.svo.su')
BOT='LoyaltyCatalogResearchBot'
MAX_PAGES=40; MAX_FILES=8; MAX_READS=100; MAX_SECONDS=1500; MAX_BYTES=6_000_000
REDIRECTS=(301,302,303,307,308)
DENIAL=re.compile(r'access denied|just a moment|captcha|проверка безопасности|доступ.{0,30}(?:ограничен|запрещ)',re.I)
INJECTION=re.compile(r'ignore (?:all |previous )?instructions|system prompt|игнорируй.{0,30}инструкц',re.I)
RULE_LABEL=re.compile(r'правил|услов|исключени',re.I)

def now():return datetime.now(timezone.utc).isoformat()
def sha(value):return hashlib.sha256(value).hexdigest()
def instant(value):
    value=datetime.fromisoformat(value.replace('Z','+00:00'))
    if value.tzinfo is None:raise ValueError('al_timezone')
    return value

def checked_url(value):
    if not isinstance(value,str) or len(value)>1200:raise ValueError('al_url_scope')
    u=urlsplit(value)
    if u.scheme!='https' or u.netloc not in HOSTS or u.fragment or '%' in u.path or '..' in u.path or '\\' in value or any(c.isspace() for c in value):
        raise ValueError('al_url_scope')
    path=u.path;query=parse_qsl(u.query,keep_blank_values=True)
    if path=='/robots.txt' and not query:return value
    if u.netloc=='stoletov.ru' and path in ('/catalog/groups/',STOLETOV,STOLETOV.rstrip('/')):
        if not query:return value
        if path==STOLETOV and len(query)==1 and query[0][0]=='page' and re.fullmatch('[1-9][0-9]?',query[0][1]):return value
    if u.netloc=='parkingsvo.ru' and path==PARK and not query:return value
    if u.netloc in ('parking.svo.aero','parking.svo.su') and re.fullmatch(r'/storage/[A-Za-z0-9_./-]+\.pdf',path,re.I) and not query:return value
    raise ValueError('al_url_scope')

def redirect_allowed(original,target,policy=False):
    checked_url(target);a,b=urlsplit(original),urlsplit(target)
    if (a.netloc=='stoletov.ru')!=(b.netloc=='stoletov.ru'):raise ValueError('al_cross_partner_redirect')
    if policy and b.path!='/robots.txt':raise ValueError('al_policy_redirect')
    if not policy and b.path=='/robots.txt':raise ValueError('al_target_is_policy')
    return target

def discover(base,clock):
    prepare(base)
    if not 0<=(clock-instant(base['observed_at'])).total_seconds()<=604800:raise ValueError('al_parent_age')
    entries={};inventory=[]
    for record in base['records']:
        if record['source_id']!='aeroflot':raise ValueError('al_foreign_parent')
        if record['native_id'].startswith('airline:'):continue
        for link in record['details']['public_partner']['outgoing_links']:
            if link['field']=='partner_url' or not RULE_LABEL.search(link['label']):continue
            item={'url':link['url'],'label':link['label'],'classification':'outside_reviewed_rule_scope'};inventory.append(item)
            try:
                url=checked_url(link['url'])
                if urlsplit(url).path=='/robots.txt':continue
            except ValueError:continue
            item['classification']='selected_public_rules'
            parent={'record_id':record['id'],'source_url':record['source_url'],'content_sha256':record['content_sha256'],
                'observed_at':record['observed_at'],'partner':record['partner_name'],'field':link['field'],
                'label':link['label'],'original_link':url}
            target=entries.setdefault(url,{'url':url,'parents':[]})
            if parent not in target['parents']:target['parents'].append(parent)
    return [entries[k] for k in sorted(entries)],inventory

def clean_html(data,url):
    soup=BeautifulSoup(data,'html.parser')
    if not soup.html or soup.select('input[type=password]'):raise ValueError('al_html_access_boundary')
    title=soup.title.get_text(' ',strip=True) if soup.title else ''
    if DENIAL.search(title) or INJECTION.search(soup.get_text(' ',strip=True)):raise ValueError('al_html_access_boundary')
    for node in soup.select('script,style,noscript,form,input,textarea,button,iframe,svg,img,nav,header,footer,[hidden],[aria-hidden="true"]'):node.decompose()
    for node in soup.find_all(True):
        node.attrs={k:v for k,v in node.attrs.items() if k in ('id','class','href','colspan','rowspan')}
        if node.has_attr('href'):
            target=urljoin(url,node['href']);u=urlsplit(target)
            # Keep public product references as data, never fetch product cards.
            if u.scheme!='https' or u.netloc!='stoletov.ru' or u.fragment or u.username or u.password or (u.query and not re.fullmatch(r'page=[1-9][0-9]?',u.query)):
                del node.attrs['href']
            else:node['href']=target
    return str(BeautifulSoup(str(soup.html),'html.parser').html)

def catalog_fields(raw,url):
    checked_url(url);dom=BeautifulSoup(raw,'html.parser');main=dom.find('main')
    if main is None:raise ValueError('al_catalog_structure')
    titles=[text(h.get_text(' ',strip=True)) for h in main.select('h1')]
    counts=main.select('.app-main-title_count');notes=main.select('[class*="CatalogSlugsPage_headerSubText"]')
    if len(titles)!=1 or not re.search(r'товар.*исключен',titles[0],re.I) or len(counts)!=1 or len(notes)!=1:raise ValueError('al_catalog_structure')
    count=re.fullmatch(r'([0-9 ]+)\s+товар\w*',text(counts[0].get_text(' ',strip=True)))
    if not count:raise ValueError('al_catalog_count')
    total=int(count[1].replace(' ',''))
    products={}
    for a in main.select('a.product-name'):
        name=text(a.get_text(' ',strip=True));link=a.get('href','');u=urlsplit(link)
        if not name or u.scheme!='https' or u.netloc!='stoletov.ru' or not u.path.startswith('/catalog/') or u.query:raise ValueError('al_product_identity')
        if link in products and products[link]!=name:raise ValueError('al_product_conflict')
        products[link]=name
    if not 0<len(products)<=total<=5000:raise ValueError('al_product_count')
    next_links=[]
    for a in main.select('.pagination-microservices a[href]'):
        link=checked_url(urljoin(url,a['href']))
        if urlsplit(link).netloc!='stoletov.ru' or urlsplit(link).path!=STOLETOV:raise ValueError('al_pagination_scope')
        if link not in next_links:next_links.append(link)
    page=int(dict(parse_qsl(urlsplit(url).query)).get('page','1'))
    return {'title':titles[0],'total':total,'note':text(notes[0].get_text(' ',strip=True)),
            'products':[{'url':k,'name':v} for k,v in products.items()],'next_links':next_links,'page':page}

class Reader:
    def __init__(self,folder,*,get=requests.get,sleep=time.sleep,wall=now):
        self.folder=Path(folder);(self.folder/'objects').mkdir(exist_ok=True,parents=True)
        self.get=get;self.sleep=sleep;self.wall=wall;self.started=time.monotonic()
        self.receipts=[];self.policies={};self.next_at={};self.delay={};self.stopped=set()
    def raw(self,url):
        checked_url(url);host=urlsplit(url).netloc
        wait=max(0,self.next_at.get(host,0)-time.monotonic())
        if host in self.stopped or len(self.receipts)>=MAX_READS or time.monotonic()+wait-self.started>MAX_SECONDS-90:raise ValueError('al_request_bound')
        self.sleep(wait);item={'url':url,'requested_at':self.wall()};index=len(self.receipts);self.receipts.append(item)
        try:
            with self.get(url,headers={'User-Agent':BOT+'/1.0'},timeout=(8,25),stream=True,allow_redirects=False) as response:
                item.update(status=response.status_code,mime=response.headers.get('Content-Type','').split(';')[0].lower())
                if response.status_code==429 or response.headers.get('Retry-After'):
                    self.stopped.add(host);raise ValueError('al_rate_limit')
                if response.status_code in REDIRECTS:
                    item['redirect']=redirect_allowed(url,urljoin(url,response.headers.get('Location','')),url.endswith('/robots.txt'))
                    return index
                if response.status_code in (404,410) and url.endswith('/robots.txt'):return index
                if response.status_code!=200:raise ValueError('al_http_'+str(response.status_code))
                buf=bytearray();deadline=time.monotonic()+60
                for chunk in response.iter_content(65536):
                    buf.extend(chunk)
                    if len(buf)>MAX_BYTES or time.monotonic()>deadline:raise ValueError('al_response_bound')
                raw=bytes(buf);item['origin_sha256']=sha(raw);item['origin_bytes']=len(raw)
                if url.endswith('/robots.txt'):data=raw;ext='txt'
                elif raw.startswith(b'%PDF-'):
                    if item['mime']!='application/pdf':raise ValueError('al_pdf_mime')
                    data=raw;ext='pdf'
                else:
                    if urlsplit(url).netloc!='stoletov.ru':raise ValueError('al_expected_parking_pdf')
                    data=clean_html(raw,url).encode();ext='html'
                filename=f'objects/{index}-{sha(data)}.{ext}'
                (self.folder/filename).write_bytes(data);item.update(file=filename,saved_sha256=sha(data),saved_bytes=len(data))
                return index
        except Exception as exc:
            item['error']=str(exc) if isinstance(exc,ValueError) and str(exc).startswith('al_') else 'al_transport_error'
            raise ValueError(item['error']) from None
        finally:
            item['finished_at']=self.wall();self.next_at[host]=time.monotonic()+self.delay.get(host,3)
    def policy(self,host):
        if host in self.policies:return self.policies[host][0]
        current='https://'+host+'/robots.txt';chain=[];seen=set()
        for _ in range(5):
            if current in seen:raise ValueError('al_policy_loop')
            seen.add(current);idx=self.raw(current);chain.append(idx);item=self.receipts[idx]
            if item.get('redirect'):current=item['redirect'];continue
            rules=policy_from_receipt(item,self.folder)
            delay=source_delay(rules)
            self.delay[host]=delay;self.next_at[host]=time.monotonic()+delay
            self.policies[host]=(rules,chain);return rules
        raise ValueError('al_policy_redirect_bound')
    def fetch(self,url):
        current=checked_url(url);chain=[];seen=set()
        for _ in range(5):
            if current in seen:raise ValueError('al_redirect_loop')
            seen.add(current);rules=self.policy(urlsplit(current).netloc)
            if not rules.can_fetch(current,BOT):raise ValueError('al_source_policy')
            idx=self.raw(current);chain.append(idx);item=self.receipts[idx]
            if item.get('redirect'):current=item['redirect'];continue
            return {'chain':chain,'final_url':current,'file':item['file']}
        raise ValueError('al_redirect_bound')

def object_bytes(receipt,folder):
    name=receipt.get('file','')
    if not re.fullmatch(r'objects/[0-9]+-[a-f0-9]{64}\.(html|pdf|txt)',name):raise ValueError('al_object_path')
    data=(Path(folder)/name).read_bytes()
    if len(data)>MAX_BYTES or len(data)!=receipt['saved_bytes'] or sha(data)!=receipt['saved_sha256']:raise ValueError('al_object_digest')
    return data

def policy_from_receipt(item,folder):
    if item.get('status') in (404,410):return Protego.parse('User-agent: *\nAllow: /')
    raw=object_bytes(item,folder).decode('utf8')
    if '<html' in raw.lower() or not re.search(r'^\s*User-agent:',raw,re.I|re.M):raise ValueError('al_policy_unreadable')
    return Protego.parse(raw)

def source_delay(rules):
    rate=rules.request_rate(BOT)
    delay=max(3,rules.crawl_delay(BOT) or 0,rate.seconds/rate.requests if rate else 0)
    if delay>30:raise ValueError('al_policy_delay_bound')
    return delay

def checked_fetch(start,fetch,audit,folder):
    current=start;seen=set();requests_=audit['requests']
    if not 1<=len(fetch['chain'])<=5:raise ValueError('al_chain_bound')
    for step,idx in enumerate(fetch['chain']):
        if type(idx) is not int or not 0<=idx<len(requests_) or current in seen:raise ValueError('al_chain')
        seen.add(current);item=requests_[idx]
        if item['url']!=current or item.get('error'):raise ValueError('al_chain')
        chain=audit['policies'].get(urlsplit(current).netloc)
        if not chain:raise ValueError('al_missing_policy')
        policy_url='https://'+urlsplit(current).netloc+'/robots.txt'
        for pi in chain:
            if type(pi) is not int or not 0<=pi<idx:raise ValueError('al_policy_order')
            p=requests_[pi]
            if p['url']!=policy_url or p.get('error'):raise ValueError('al_policy_chain')
            if p.get('redirect'):policy_url=redirect_allowed(policy_url,p['redirect'],True)
        rules=policy_from_receipt(p,folder);source_delay(rules)
        if not rules.can_fetch(current,BOT):raise ValueError('al_source_policy')
        if item.get('redirect'):current=redirect_allowed(current,item['redirect']);continue
        if step!=len(fetch['chain'])-1 or item['status']!=200 or current!=fetch['final_url'] or item['file']!=fetch['file']:raise ValueError('al_final_response')
        data=object_bytes(item,folder)
        if not data.startswith(b'%PDF-') and data!=clean_html(data,current).encode():raise ValueError('al_unsanitized_html')
        return data,item
    raise ValueError('al_unfinished_chain')

def make_rows(entry,fetch,data,observed,*,fields=None,doc=None,complete=None):
    parents=entry['parents'];names=sorted({p['partner'] for p in parents})
    partner=names[0] if len(names)==1 else None
    details={'retrieval_method':METHOD,'parent_references':parents,'download_url':fetch['final_url'],
             'source_account_used':False,'eligibility_verified':False,'catalogue_complete':complete}
    if doc is not None:
        doc=copy_document(doc,parents[0]['label'])
        return document_records(SID,'pdf:'+sha(entry['url'].encode()),PROGRAM,partner,entry['url'],observed,doc,
            parent_source=parents[0]['source_url'],parent_sha256=parents[0]['content_sha256'],label=parents[0]['label'],extra_details=details)
    f=fields
    value=f['title']+'\n'+f['note']+'\n\n'+'\n'.join(p['name']+' — '+p['url'] for p in f['products'])
    value=text(value)
    return [make_offer(SID,'html:'+sha(entry['url'].encode())+':page:'+str(f['page']),PROGRAM,partner,'',entry['url'],observed,
        title=f['title']+' — страница '+str(f['page']),conditions=value,record_kind='program_rules',source_status='public_linked_rules_text',
        details={**details,'public_rule_text':value,'catalogue_page':f,'products_are_exclusions_not_offers':True},
        warnings=['linked_rules_not_additional_discounts','parent_snapshot_time_separate_from_document_read','user_eligibility_not_verified'])]

def copy_document(doc,label):
    import copy
    doc=copy.deepcopy(doc)
    if not doc.get('title','').strip() or not re.search('[A-Za-zА-Яа-я]',doc['title']):doc['title']=label
    return doc

def assemble(base,audit,folder):
    entries,inventory=discover(base,instant(audit['started_at']))
    if inventory!=audit['inventory'] or [e['url'] for e in entries]!=[x['url'] for x in audit['results']]:raise ValueError('al_inventory')
    rows=[];errors=[];counts=[]
    for entry,result in zip(entries,audit['results']):
        pages=[];seen_products={};totals=set();known={entry['url']};visited=set();pdf_seen=False
        for page in result.get('pages',[]):
            if page['url'] not in known or page['url'] in visited or len(visited)>=MAX_PAGES:raise ValueError('al_undiscovered_page')
            visited.add(page['url']);data,item=checked_fetch(page['url'],page['fetch'],audit,folder)
            if data.startswith(b'%PDF-'):
                if len(visited)!=1 or pdf_seen:raise ValueError('al_extra_pdf')
                pdf_seen=True;doc=page['document']
                native=extract_pdf(data,allow_ocr=False)
                if doc['document_sha256']!=sha(data) or doc['page_count']!=native['page_count'] or len(doc['pages'])!=doc['page_count']:raise ValueError('al_pdf_identity')
                if doc['ocr_pages']!=sum(p['method']=='ocr_unverified' for p in doc['pages']):raise ValueError('al_ocr_count')
                if any(not p['text'] for p in doc['pages']) and not doc['errors']:raise ValueError('al_missing_pdf_text')
                for p,native_page in zip(doc['pages'],native['pages']):
                    if p['number']!=native_page['number'] or p['sha256']!=sha(p['text'].encode()):raise ValueError('al_pdf_page')
                    if p['method']=='native_pdf_text' and p['text']!=native_page['text']:raise ValueError('al_pdf_native_text')
                rows.extend(make_rows(entry,page['fetch'],data,audit['started_at'],doc=doc))
                if doc['errors']:errors.append({'url':entry['url'],'reason':'al_pdf_text_partial'})
            else:
                f=catalog_fields(data,page['fetch']['final_url']);pages.append((page,f,data));totals.add(f['total'])
                known.update(f['next_links']);visited.add(page['fetch']['final_url'])
                for product in f['products']:
                    if product['url'] in seen_products and seen_products[product['url']]!=product['name']:raise ValueError('al_product_conflict')
                    seen_products[product['url']]=product['name']
        complete=bool(pages) and len(totals)==1 and len(seen_products)==next(iter(totals)) and not known-visited and not result.get('errors')
        if pages:
            if result.get('catalogue_complete')!=complete or result.get('unique_products')!=len(seen_products):raise ValueError('al_catalogue_claim')
            for page,f,data in pages:rows.extend(make_rows(entry,page['fetch'],data,audit['started_at'],fields=f,complete=complete))
            if not complete:errors.append({'url':entry['url'],'reason':'al_product_list_partial'})
        for error in result.get('errors',[]):
            if not re.fullmatch('al_[a-z0-9_]+',error['reason']):raise ValueError('al_error_code')
            errors.append(error)
        counts.append({'url':entry['url'],'pages_read':len(result.get('pages',[])),'pdf':pdf_seen,
                       'unique_products':len(seen_products),'advertised_totals':sorted(totals),'catalogue_complete':complete if pages else None})
    if not entries:errors.append({'url':ROOT,'reason':'al_no_linked_targets'})
    report={'source_id':SID,'name':PROGRAM,'root':ROOT,'status':('partial' if errors else 'ok') if rows else 'failed',
        'discovered':max(len(entries),len(rows)),'normalized':len(rows),'failed':len(errors),'errors':errors,'region':None,'observed_at':audit['started_at'],
        'coverage':json.dumps({'method':METHOD,'parent_run':base['run_id'],'parent_observed_at':base['observed_at'],
            'root_documents':len(entries),'scopes':counts,'physical_http_requests':len(audit['requests']),'provider_credits':0,
            'source_account_used':False,'all_external_links_exhausted':False},ensure_ascii=False)}
    bundle={'schema_version':2,'run_id':audit['run_id'],'observed_at':audit['started_at'],'records':rows,'sources':[report]}
    prepare(bundle);return bundle

def validate_record(record):
    d=record['details'];url=checked_url(record['source_url']);parents=d.get('parent_references',[])
    if not parents or d.get('retrieval_method')!=METHOD or d.get('source_account_used') is not False or d.get('eligibility_verified') is not False:
        raise ValueError('al_record_provenance')
    if record['record_kind'] not in ('program_rules','source_observation') or record['rates'] or record['tables'] or record['valid_from'] or record['valid_until']:raise ValueError('al_extra_benefits')
    from aeroflot_import_catalog import formula
    for parent in parents:
        formula(parent['source_url'],'detail')
        if parent['original_link']!=url or not re.fullmatch('[a-f0-9]{64}',parent['record_id']) or not re.fullmatch('[a-f0-9]{64}',parent['content_sha256']) or instant(parent['observed_at'])>instant(record['observed_at']):raise ValueError('al_parent_binding')
    names=sorted({p['partner'] for p in parents})
    if record['partner_name']!=(names[0] if len(names)==1 else None):raise ValueError('al_partner_binding')
    checked_url(d['download_url'])
    if not d.get('live_document_text'):
        if record['benefit_text'] or record['conditions_text']!=d.get('public_rule_text'):raise ValueError('al_html_binding')
        if record['native_id']!='html:'+sha(url.encode())+':page:'+str(d['catalogue_page']['page']):raise ValueError('al_page_identity')
    elif not record['native_id'].startswith('pdf:'+sha(url.encode())):raise ValueError('al_pdf_binding')

def validate_bundle(folder,run_id,commit,clock):
    folder=Path(folder)
    for name in ('audit.json','parents.json','normalized.json'):
        if (folder/name).stat().st_size>25_000_000:raise ValueError('al_bundle_bound')
    audit=json.loads((folder/'audit.json').read_text());base=json.loads((folder/'parents.json').read_text())
    if audit['run_id']!=run_id or audit['commit']!=commit or audit.get('source_account_used') is not False or audit.get('provider_credits')!=0:raise ValueError('al_bundle_identity')
    start,end=instant(audit['started_at']),instant(audit['finished_at'])
    if not start<=end<=clock or (end-start).total_seconds()>MAX_SECONDS+120 or (clock-end).total_seconds()>900 or len(audit['requests'])>MAX_READS:raise ValueError('al_bundle_time')
    last=start
    for item in audit['requests']:
        checked_url(item['url']);a,b=instant(item['requested_at']),instant(item['finished_at'])
        if not last<=a<=b<=end:raise ValueError('al_receipt_time')
        last=b
        if item.get('file'):object_bytes(item,folder)
    bundle=assemble(base,audit,folder)
    if bundle!=json.loads((folder/'normalized.json').read_text()):raise ValueError('al_reconstruction')
    return bundle

def collect(base,folder,run_id,commit,*,get=requests.get,sleep=time.sleep,observed_at=None,allow_ocr=True):
    wall=(lambda:observed_at) if observed_at is not None else now
    started=wall();entries,inventory=discover(base,instant(started));folder=Path(folder);folder.mkdir(exist_ok=True,parents=True)
    reader=Reader(folder,get=get,sleep=sleep,wall=wall)
    audit={'run_id':run_id,'commit':commit,'started_at':started,'inventory':inventory,'source_account_used':False,'provider_credits':0,'results':[],'requests':reader.receipts}
    for entry in entries[:MAX_FILES]:
        result={'url':entry['url'],'pages':[],'errors':[]};audit['results'].append(result)
        pending=[entry['url']];seen=set();products={};totals=set()
        while pending and len(result['pages'])<MAX_PAGES:
            url=pending.pop(0)
            if url in seen:continue
            seen.add(url)
            try:
                fetch=reader.fetch(url);seen.add(fetch['final_url']);data=(folder/fetch['file']).read_bytes()
                page={'url':url,'fetch':fetch}
                if data.startswith(b'%PDF-'):
                    page['document']=extract_pdf(data,allow_ocr=allow_ocr);result['pages'].append(page);break
                fields=catalog_fields(data,fetch['final_url']);page['fields']=fields
                result['pages'].append(page);totals.add(fields['total'])
                products.update({p['url']:p['name'] for p in fields['products']})
                pending.extend(u for u in fields['next_links'] if u not in seen and u not in pending)
            except Exception as exc:
                code=str(exc) if isinstance(exc,ValueError) and str(exc).startswith('al_') else 'al_collection_error'
                result['errors'].append({'url':url,'reason':code})
                if code in ('al_rate_limit','al_request_bound'):break
        if pending:result['errors'].append({'url':entry['url'],'reason':'al_page_bound'})
        if products:
            result['unique_products']=len(products)
            result['catalogue_complete']=len(totals)==1 and len(products)==next(iter(totals)) and not pending and not result['errors']
    for entry in entries[MAX_FILES:]:audit['results'].append({'url':entry['url'],'pages':[],'errors':[{'url':entry['url'],'reason':'al_file_bound'}]})
    audit['policies']={k:v[1] for k,v in reader.policies.items()};audit['finished_at']=wall()
    bundle=assemble(base,audit,folder)
    for name,value in [('audit.json',audit),('parents.json',base),('normalized.json',bundle)]:
        (folder/name).write_text(json.dumps(value,ensure_ascii=False,indent=2))
    return bundle,audit

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--input',default='aeroflot-upstream/normalized.json');parser.add_argument('--out',default='aeroflot-linked-output');args=parser.parse_args()
    run_id=os.environ['GITHUB_RUN_ID']+':'+os.environ['GITHUB_RUN_ATTEMPT'];commit=os.environ['GITHUB_SHA']
    bundle,audit=collect(json.loads(Path(args.input).read_text()),args.out,run_id,commit)
    validate_bundle(args.out,run_id,commit,datetime.now(timezone.utc))
    print(json.dumps({'records':len(bundle['records']),'status':bundle['sources'][0]['status'],'requests':len(audit['requests']),'provider_credits':0}))

if __name__=='__main__':main()
