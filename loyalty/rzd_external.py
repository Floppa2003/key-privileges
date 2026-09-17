"""Bounded public RZD partner conditions; no accounts, cached answers or credits."""
from __future__ import annotations
import hashlib, json, os, re, time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin, urlsplit
import requests
from bs4 import BeautifulSoup
from protego import Protego
from normalized import make_offer, text, content_hash
from document_text import extract_pdf, document_records

TOUR='https://rzdtour.com/'
PREFIX='/kruiznyie-turyi/kruiznyie-poezda/'
BANK='https://www.unicreditbank.ru/ru/personal/cards/pi-packages/debit-cash-and-back.html'
BOT='LoyaltyCatalogResearchBot'
MAX_TOURS=80; MAX_PDFS=4; MAX_READS=90; MAX_SECONDS=900
MAX_HTML=2_000_000; MAX_PDF=6_000_000
METHOD='rzd_external_direct_v1'
RZD=re.compile(r'РЖД[\s«»"\-]*Бонус',re.I)
RESTRICT=re.compile(r'access denied|just a moment|captcha|доступ.{0,40}(?:ограничен|запрещ)|проверка безопасности',re.I)
INSTRUCTION=re.compile(r'ignore (?:all |previous )?instructions|system prompt|игнорируй.{0,30}инструкц',re.I)
SPECS={'rzd_tour_conditions':('РЖД Бонус — РЖД Тур',TOUR),
       'rzd_unicredit_reference':('РЖД Бонус — страница ЮниКредита',BANK),
       'rzd_unicredit_rules':('РЖД Бонус — связанные правила ЮниКредита',BANK)}


def now():return datetime.now(timezone.utc).isoformat()
def sha(data):return hashlib.sha256(data).hexdigest()
def instant(value):
    result=datetime.fromisoformat(value)
    if result.tzinfo is None:raise ValueError('re_time_zone')
    return result

def checked_url(value):
    if not isinstance(value,str) or len(value)>900:raise ValueError('re_url_scope')
    u=urlsplit(value)
    if (u.scheme!='https' or u.query or u.fragment or '..' in u.path or '%' in u.path
        or '\\' in value or any(c.isspace() for c in value)):raise ValueError('re_url_scope')
    if u.netloc=='rzdtour.com' and (u.path in ('/','/robots.txt') or
        re.fullmatch(re.escape(PREFIX)+r'[a-zA-Z0-9_.-]*/?',u.path)):return value
    if u.netloc=='www.unicreditbank.ru' and (value==BANK or u.path=='/robots.txt' or
        re.fullmatch(r'/content/dam/[A-Za-z0-9_./-]+\.pdf',u.path,re.I)):return value
    raise ValueError('re_url_scope')

def clean_html(raw,url):
    soup=BeautifulSoup(raw,'html.parser')
    heading=soup.title.get_text(' ',strip=True) if soup.title else ''
    if RESTRICT.search(heading) or INSTRUCTION.search(soup.get_text(' ',strip=True)):
        raise ValueError('re_restriction_or_instruction')
    canon=soup.select('link[rel~=canonical][href]')
    if canon and {urljoin(url,c['href']).rstrip('/') for c in canon}!={url.rstrip('/')}:
        raise ValueError('re_canonical_mismatch')
    for e in soup.select('script,style,form,input,textarea,button,iframe,svg,noscript'):e.decompose()
    for e in soup.find_all(True):
        e.attrs={k:v for k,v in e.attrs.items() if k in ('href','id','class','title','rel','colspan','rowspan')}
    if not soup.html:raise ValueError('re_not_html')
    return str(soup)

def policy(raw):
    if '<html' in raw.lower() or not re.search(r'^\s*User-agent:',raw,re.I|re.M):
        raise ValueError('re_robots_unreadable')
    return Protego.parse(raw)

class Reader:
    def __init__(self,folder,*,get=requests.get,clock=time.monotonic,sleep=time.sleep):
        self.folder=Path(folder);(self.folder/'objects').mkdir(parents=True,exist_ok=True)
        self.get=get;self.clock=clock;self.sleep=sleep;self.started=clock()
        self.receipts=[];self.policies={};self.next_at={};self.delay={};self.stopped=set()
    def _get(self,url):
        checked_url(url);host=urlsplit(url).netloc
        self.sleep(max(0,self.next_at.get(host,0)-self.clock()))
        item={'url':url,'requested_at':now()};self.receipts.append(item)
        try:
            if host in self.stopped or len(self.receipts)>MAX_READS or self.clock()-self.started>MAX_SECONDS-35:
                raise ValueError('re_budget_or_stopped')
            with self.get(url,headers={'User-Agent':BOT+'/1.0'},timeout=(8,25),stream=True,allow_redirects=False) as r:
                item['status']=r.status_code;item['mime']=r.headers.get('Content-Type','').split(';')[0].lower()
                if r.status_code==429 or r.headers.get('Retry-After'):
                    self.stopped.add(host);raise ValueError('re_rate_limit')
                if r.status_code!=200:raise ValueError('re_http_'+str(r.status_code))
                is_pdf=url.lower().endswith('.pdf');bound=MAX_PDF if is_pdf else MAX_HTML
                data=bytearray()
                for block in r.iter_content(65536):
                    data.extend(block)
                    if len(data)>bound:raise ValueError('re_response_size')
                item['origin_bytes_sha256']=sha(data)
                if is_pdf:
                    if item['mime']!='application/pdf' or not data.startswith(b'%PDF-'):raise ValueError('re_not_pdf')
                    saved=bytes(data);ext='pdf'
                else:
                    r._content=bytes(data);r.encoding=r.apparent_encoding
                    saved=(r.text if url.endswith('/robots.txt') else clean_html(r.text,url)).encode();ext='txt' if url.endswith('/robots.txt') else 'html'
                    if ext=='txt':policy(saved.decode())
                item['file']='objects/'+sha(url.encode())+'.'+ext
                item['saved_sha256']=sha(saved);item['saved_bytes']=len(saved)
                (self.folder/item['file']).write_bytes(saved)
                return saved
        except Exception as exc:
            item['error']=str(exc) if isinstance(exc,ValueError) and str(exc).startswith('re_') else 're_transport_error'
            raise ValueError(item['error']) from None
        finally:
            item['finished_at']=now();self.next_at[host]=self.clock()+self.delay.get(host,5)
    def read(self,url):
        checked_url(url);host=urlsplit(url).netloc
        if host not in self.policies:
            raw=self._get('https://'+host+'/robots.txt').decode()
            rules=policy(raw);rate=rules.request_rate(BOT)
            delay=max(5,rules.crawl_delay(BOT) or 0,rate.seconds/rate.requests if rate else 0)
            if delay>30:raise ValueError('re_delay_bound')
            self.delay[host]=delay;self.next_at[host]=self.clock()+delay;self.policies[host]=rules
        if not self.policies[host].can_fetch(url,BOT):raise ValueError('re_robots_disallow')
        return self._get(url)


def tour_links(raw,base):
    soup=BeautifulSoup(raw,'html.parser');out=[];unread=[]
    for a in soup.select('a[href]'):
        url=urljoin(base,a['href']);u=urlsplit(url)
        if u.netloc!='rzdtour.com' or not u.path.startswith(PREFIX):continue
        try:checked_url(url)
        except ValueError:
            if u.query:unread.append(url)
            continue
        if url not in out:out.append(url)
    return out,sorted(set(unread))

def tables(block):
    return [[[text(c.get_text(' ',strip=True)) for c in row.find_all(['td','th'],recursive=False)]
             for row in t.find_all('tr')] for t in block.find_all('table')]

def tour_fields(raw,url):
    soup=BeautifulSoup(raw,'html.parser');titles=[text(h.get_text(' ',strip=True)) for h in soup.select('h1') if h.get_text(strip=True)]
    blocks=soup.select('.modal-main.content-price .text-content-route')
    if len(titles)!=1 or len(blocks)!=1:raise ValueError('re_tour_owned_structure')
    block=blocks[0];body=text(block.get_text('\n',strip=True))
    if not 40<=len(body)<=35000:raise ValueError('re_tour_text_bound')
    clauses=[]
    for node in block.find_all(['p','li']):
        value=text(node.get_text(' ',strip=True))
        if RZD.search(value) and value not in clauses:clauses.append(value)
    # If the supported owning elements changed, do not claim a missing benefit.
    if RZD.search(body) and not clauses:raise ValueError('re_tour_clause_structure')
    return {'title':titles[0],'pricing_text':body,'loyalty_text':'\n'.join(clauses),'pricing_tables':tables(block),'url':url}

def tour_record(raw,url,parent,observed):
    p=tour_fields(raw,url)
    if not p['loyalty_text']:return None
    return make_offer('rzd_tour_conditions',urlsplit(url).path,'РЖД Бонус','РЖД Тур',p['loyalty_text'],url,observed,
        title=p['title'],conditions=p['pricing_text'],redemption=p['loyalty_text'],
        record_kind='partner_offer',source_status='public_tour_specific_conditions',locator='.modal-main.content-price .text-content-route',
        details={'retrieval_method':METHOD,'public_tour':p,'discovery_parent':parent,'html_sha256':sha(raw.encode()),'account_used':False,
                 'availability_verified':False,'all_tours_equivalent':False},
        warnings=['tour_specific_not_all_tours','booking_availability_and_user_eligibility_not_verified','pricing_table_context_not_automatic_benefits'])

def bank_fields(raw):
    soup=BeautifulSoup(raw,'html.parser');blocks=soup.select('.ucr-contentpage-parsys')
    if len(blocks)!=1:raise ValueError('re_bank_owned_structure')
    block=blocks[0];titles=[text(h.get_text(' ',strip=True)) for h in block.select('h1') if h.get_text(strip=True)]
    if len(titles)!=1 or 'CASH' not in titles[0].upper():raise ValueError('re_bank_identity')
    docs=[]
    for row in block.select('table.downloadlist tr'):
        cells=row.find_all('td',recursive=False)
        label=text(cells[0].get_text(' ',strip=True)) if cells else ''
        if not re.search(r'Правил.*(?:вознагражден|лояльност)',label,re.I):continue
        for a in row.select('a[href]'):
            url=urljoin(BANK,a['href']);checked_url(url)
            if urlsplit(url).netloc!='www.unicreditbank.ru':raise ValueError('re_bank_pdf_host')
            if url.endswith('.pdf') and url not in [d['url'] for d in docs]:docs.append({'url':url,'label':label})
    body=text(block.get_text('\n',strip=True))
    if not 100<=len(body)<=35000:raise ValueError('re_bank_text_bound')
    return {'title':titles[0],'text':body,'documents':docs,'rzd_mentions':bool(RZD.search(body))}

def bank_record(raw,observed):
    p=bank_fields(raw)
    return make_offer('rzd_unicredit_reference','product-page','РЖД Бонус','ЮниКредит Банк','',BANK,observed,
        title=p['title'],conditions=p['text'],record_kind='source_observation',source_status='external_product_reference_not_exchange_confirmation',
        details={'retrieval_method':METHOD,'public_bank':p,'html_sha256':sha(raw.encode()),'account_used':False,
                 'rzd_exchange_confirmed':False},warnings=['external_product_page_not_rzd_exchange_confirmation','user_eligibility_not_verified'])

def bank_pdf_records(data,entry,parent,observed):
    doc=extract_pdf(data,allow_ocr=False)
    return document_records('rzd_unicredit_rules','pdf:'+sha(entry['url'].encode())[:32],
        'РЖД Бонус — связанные правила ЮниКредита','ЮниКредит Банк',entry['url'],observed,doc,
        parent_source=BANK,parent_sha256=parent['content_sha256'],label=entry['label'],
        extra_details={'retrieval_method':METHOD,'parent_record_id':parent['id'],'rzd_exchange_confirmed':False,
                       'document_rzd_mentions':bool(RZD.search('\n'.join(p['text'] for p in doc['pages'])))})

def collect(reader,run_id,observed):
    states={s:{'records':[],'errors':[],'excluded':[],'targets':[]} for s in SPECS}
    t=states['rzd_tour_conditions']
    try:
        home=reader.read(TOUR).decode();links,unread=tour_links(home,TOUR);parents={u:TOUR for u in links}
        category=TOUR.rstrip('/')+PREFIX
        if category in links:
            page=reader.read(category).decode();more,queries=tour_links(page,category);unread+=queries
            for u in more:
                if u not in parents:links.append(u);parents[u]=category
        targets=[u for u in links if urlsplit(u).path.rstrip('/')!=PREFIX.rstrip('/')]
        t['targets']=targets
        if unread:t['errors'].append({'url':category,'reason':'re_unread_query_links','count':len(set(unread))})
        for u in targets[:MAX_TOURS]:
            try:
                row=tour_record(reader.read(u).decode(),u,parents[u],observed)
                if row:t['records'].append(row)
                else:t['excluded'].append({'url':u,'reason':'no_rzd_clause_in_owned_pricing'})
            except ValueError as exc:t['errors'].append({'url':u,'reason':str(exc)})
        if len(targets)>MAX_TOURS:t['errors'].append({'url':TOUR,'reason':'re_tour_limit'})
    except ValueError as exc:t['errors'].append({'url':TOUR,'reason':str(exc)})
    b=states['rzd_unicredit_reference'];d=states['rzd_unicredit_rules'];b['targets']=[BANK]
    try:
        raw=reader.read(BANK).decode();row=bank_record(raw,observed);b['records'].append(row)
        entries=row['details']['public_bank']['documents'];d['targets']=[x['url'] for x in entries]
        if not entries:d['errors'].append({'url':BANK,'reason':'re_no_reward_rules_links'})
        for entry in entries[:MAX_PDFS]:
            try:
                rows=bank_pdf_records(reader.read(entry['url']),entry,row,observed);d['records'].extend(rows)
                if rows[0]['details']['document_errors']:d['errors'].append({'url':entry['url'],'reason':'re_pdf_text_partial'})
            except ValueError as exc:d['errors'].append({'url':entry['url'],'reason':str(exc)})
        if len(entries)>MAX_PDFS:d['errors'].append({'url':BANK,'reason':'re_pdf_limit'})
    except ValueError as exc:
        b['errors'].append({'url':BANK,'reason':str(exc)});d['errors'].append({'url':BANK,'reason':'re_parent_unavailable'})
    records=[];reports=[]
    for sid,result in states.items():
        rows=result['records'];errors=result['errors'];records+=rows
        coverage={'method':METHOD,'scope':'homepage_and_cruise_category_linked_tours' if sid=='rzd_tour_conditions' else 'linked_bank_product_or_reward_rules',
          'selected_urls':result['targets'],'excluded':result['excluded'],'full_program_verified':False,'account_used':False,'provider_credits':0}
        reports.append({'source_id':sid,'name':SPECS[sid][0],'root':SPECS[sid][1],
          'status':'partial' if errors and rows else 'failed' if errors else 'ok','discovered':max(len(rows),len(result['targets'])),
          'normalized':len(rows),'failed':len(errors),'coverage':json.dumps(coverage,ensure_ascii=False),'region':None,
          'errors':errors,'observed_at':observed})
    bundle={'schema_version':2,'run_id':run_id,'observed_at':observed,'records':records,'sources':reports}
    from sheets_normalized import prepare
    prepare(bundle);return bundle

class Replay(Reader):
    def __init__(self,folder,receipts):
        self.folder=Path(folder);self.receipts=receipts;self.index=0
        self.policies={};self.next_at={};self.delay={};self.clock=lambda:0
    def _get(self,url):
        if self.index>=len(self.receipts):raise ValueError('re_replay_missing')
        r=self.receipts[self.index];self.index+=1
        if r['url']!=url:raise ValueError('re_replay_order')
        if 'error' in r:raise ValueError(r['error'])
        return (self.folder/r['file']).read_bytes()

def validate_bundle(folder,run_id,commit,clock):
    folder=Path(folder);audit=json.loads((folder/'audit.json').read_text());receipts=audit['receipts']
    if audit['run_id']!=run_id or audit['commit']!=commit or not re.fullmatch('[a-f0-9]{40}',commit):raise ValueError('re_run_binding')
    start,end=instant(audit['observed_at']),instant(audit['finished_at'])
    if not 0<=(end-start).total_seconds()<=MAX_SECONDS+60 or not 0<=(clock-end).total_seconds()<=3600:raise ValueError('re_time_binding')
    if len(receipts)>MAX_READS:raise ValueError('re_read_bound')
    seen=set();last=start
    for r in receipts:
        url=checked_url(r['url']);a,z=instant(r['requested_at']),instant(r['finished_at'])
        if url in seen or not last<=a<=z<=end:raise ValueError('re_receipt_order')
        seen.add(url);last=z
        if 'error' in r:
            if not re.fullmatch('re_[a-z0-9_]{1,100}',r['error']):raise ValueError('re_error_contract')
            continue
        ext='pdf' if url.lower().endswith('.pdf') else 'txt' if url.endswith('/robots.txt') else 'html'
        if r.get('file')!='objects/'+sha(url.encode())+'.'+ext or r['status']!=200:raise ValueError('re_file_binding')
        data=(folder/r['file']).read_bytes()
        if len(data)!=r['saved_bytes'] or sha(data)!=r['saved_sha256'] or len(data)>(MAX_PDF if ext=='pdf' else MAX_HTML):raise ValueError('re_file_hash')
        if ext=='pdf' and (r['mime']!='application/pdf' or not data.startswith(b'%PDF-')):raise ValueError('re_not_pdf')
    replay=Replay(folder,receipts);bundle=collect(replay,run_id,audit['observed_at'])
    if replay.index!=len(receipts) or bundle!=json.loads((folder/'normalized.json').read_text()):raise ValueError('re_reconstruction')
    return bundle

def main():
    folder=Path('rzd-external-output');reader=Reader(folder)
    run_id=os.environ['GITHUB_RUN_ID']+':'+os.environ['GITHUB_RUN_ATTEMPT'];observed=now()
    bundle=collect(reader,run_id,observed)
    audit={'run_id':run_id,'commit':os.environ['GITHUB_SHA'],'observed_at':observed,'finished_at':now(),'receipts':reader.receipts}
    (folder/'normalized.json').write_text(json.dumps(bundle,ensure_ascii=False))
    (folder/'audit.json').write_text(json.dumps(audit,ensure_ascii=False,indent=2))
    validate_bundle(folder,run_id,audit['commit'],datetime.now(timezone.utc))
    print(json.dumps({'records':len(bundle['records']),'source_statuses':{s['source_id']:s['status'] for s in bundle['sources']},'requests':len(reader.receipts),'provider_credits':0}))

if __name__=='__main__':main()
