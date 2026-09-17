"""Public RZD-linked partner conditions. No source account or provider key.

The two roots were linked by the RZD catalogue. Current destinations, not the
old catalogue's advertised values, supply every condition. Tour conditions stay
attached to their own URL; bank product/reward documents are not an inferred
confirmation of RZD point exchange.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
import re
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin, urlsplit, unquote, quote
import requests
from bs4 import BeautifulSoup
from protego import Protego
from normalized import make_offer, text
from document_text import extract_pdf, document_records
from sheets_normalized import prepare

TOUR='https://rzdtour.com/'
BANK='https://www.unicreditbank.ru/ru/personal/cards/pi-packages/debit-cash-and-back.html'
METHOD='rzd_external_public_conditions_v1'
SOURCES={'rzd_tour_terms':('РЖД Бонус — условия РЖД Тур',TOUR),
         'rzd_unicredit_terms':('РЖД Бонус — внешняя страница ЮниКредит',BANK),
         'rzd_unicredit_documents':('РЖД Бонус — связанные правила ЮниКредит',BANK)}
MAX_TOURS=220;MAX_REQUESTS=240;MAX_SECONDS=1800;MAX_BYTES=6_000_000
FRAGMENT=18000
LOYALTY=re.compile(r'РЖД[\s«»"-]*Бонус',re.I)
DENIED=re.compile(r'access denied|just a moment|captcha|доступ.{0,60}ограничен|доступ запрещ',re.I)


def now():return datetime.now(timezone.utc).isoformat()
def sha(value):return hashlib.sha256(value if isinstance(value,bytes) else value.encode()).hexdigest()
def safe_error(exc):
    return str(exc) if isinstance(exc,ValueError) and re.fullmatch(r'rx_[a-z_0-9]{1,100}',str(exc)) else 'rx_transport_or_parse_error'

def checked_url(value):
    if not isinstance(value,str) or len(value)>1200:raise ValueError('rx_url')
    u=urlsplit(value);path=unquote(u.path)
    if (u.scheme!='https' or u.netloc not in ('rzdtour.com','www.unicreditbank.ru') or u.query or u.fragment
        or '%' in path or '\\' in path or any(ord(x)<32 or x.isspace() for x in value)
        or any(p in ('.','..') for p in path.split('/'))
        or re.search(r'/(?:login|auth|account|admin|manager|register|connectors|core)(?:/|$)',path,re.I)):
        raise ValueError('rx_url')
    if re.search(r'%2f|%5c',u.path,re.I):raise ValueError('rx_url')
    if u.netloc=='www.unicreditbank.ru' and value!=BANK and path!='/robots.txt' and not (path.startswith('/content/dam/') and path.lower().endswith('.pdf')):
        raise ValueError('rx_url')
    return 'https://'+u.netloc+quote(path or '/',safe="/!$&'()*+,-.:;=@_~")


def sanitize_html(raw):
    if not isinstance(raw,str) or len(raw)>2_000_000:raise ValueError('rx_html_size')
    soup=BeautifulSoup(raw,'html.parser')
    if not soup.html:raise ValueError('rx_html_shape')
    if DENIED.search(soup.title.get_text(' ',strip=True) if soup.title else ''):raise ValueError('rx_access_document')
    for n in soup.select('script,style,noscript,form,input,textarea,button,iframe,header,footer,nav,svg'):
        n.decompose()
    for n in soup.find_all(True):
        for key in list(n.attrs):
            if key not in ('id','class','href','colspan','rowspan'):del n.attrs[key]
        if n.has_attr('href'):
            href=n['href']
            if not isinstance(href,str) or re.search(r'(?:token|session|auth|password|signature)=|^javascript:',href,re.I):del n.attrs['href']
    return str(soup)


def plain(node):
    soup=BeautifulSoup(str(node),'html.parser')
    for tr in soup.select('tr'):
        vals=[c.get_text(' ',strip=True) for c in tr.find_all(['td','th'],recursive=False)]
        if vals:tr.replace_with('\n'+' | '.join(vals)+'\n')
    for br in soup.select('br'):br.replace_with('\n')
    for n in soup.select('p,li,div,h1,h2,h3,h4'):n.insert_before('\n');n.insert_after('\n')
    return '\n'.join(' '.join(x.split()) for x in soup.get_text(' ',strip=False).splitlines() if x.strip())


def tour_targets(sitemap,home):
    if '<!DOCTYPE' in sitemap.upper() or '<!ENTITY' in sitemap.upper():raise ValueError('rx_xml_entities')
    root=ET.fromstring(sitemap)
    if root.tag!='{http://www.sitemaps.org/schemas/sitemap/0.9}urlset' or len(root)>4000:raise ValueError('rx_sitemap_shape')
    result={}
    for n in root.findall('{*}url/{*}loc'):
        value=n.text or ''
        if re.fullmatch(r'/(?:kruiznyie-turyi|ekskursionnyie-turyi)/[^/]+/[^/]+',urlsplit(value).path):
            result.setdefault(checked_url(value),[]).append('advertised_sitemap_tour_section')
    soup=BeautifulSoup(home,'html.parser')
    for a in soup.select('.card > a[href]'):
        try:url=checked_url(urljoin(TOUR,a['href']))
        except ValueError:continue
        if urlsplit(url).netloc=='rzdtour.com' and url!=TOUR:
            reasons=result.setdefault(url,[])
            if 'homepage_tour_card' not in reasons:reasons.append('homepage_tour_card')
    if not result:raise ValueError('rx_no_tour_candidates')
    return dict(sorted(result.items()))


def tour_records(html,url,observed_at,receipt,discovery):
    url=checked_url(url);soup=BeautifulSoup(html,'html.parser')
    heads=soup.select('h1.name');blocks=soup.select('.modal-main.content-price .text-content-route')
    if len(heads)!=1 or not blocks:raise ValueError('rx_tour_layout')
    title=text(heads[0].get_text(' ',strip=True))
    if not 2<=len(title)<=300:raise ValueError('rx_tour_title')
    conditions='\n\n'.join(plain(n) for n in blocks)
    if not conditions.strip():raise ValueError('rx_tour_price_empty')
    clauses=[]
    for block in blocks:
        for node in block.select('p,li'):
            if any(LOYALTY.search(c.get_text(' ',strip=True)) for c in node.select('p,li')):continue
            value=text(node.get_text(' ',strip=True))
            if LOYALTY.search(value) and value not in clauses:clauses.append(value)
    if not clauses:
        if LOYALTY.search(conditions):raise ValueError('rx_unowned_loyalty_clause')
        return []
    benefit='\n'.join(clauses)
    if len(benefit)>10000:raise ValueError('rx_loyalty_clause_bound')
    fragments=[conditions[i:i+FRAGMENT] for i in range(0,len(conditions),FRAGMENT)]
    if len(fragments)>12:raise ValueError('rx_conditions_bound')
    rows=[]
    for index,fragment in enumerate(fragments):
        rows.append(make_offer('rzd_tour_terms',urlsplit(url).path+('' if index==0 else ':part:'+str(index+1)),
            SOURCES['rzd_tour_terms'][0],'РЖД Тур',benefit if index==0 else '',url,observed_at,
            title=title,conditions=fragment,record_kind='partner_offer' if index==0 else 'program_rules',
            locator='.modal-main.content-price .text-content-route',source_status='public_tour_specific_conditions',
            details={'retrieval_method':METHOD,'tour_url':url,'condition_fragment':fragment,
                'part':{'number':index+1,'total':len(fragments),'offset':index*FRAGMENT},
                'rzd_loyalty_clauses':clauses if index==0 else [],'source_receipt':receipt,
                'discovery':discovery,'account_used':False,'personal_eligibility_verified':False},
            warnings=['tour_specific_not_all_tours','source_dates_not_inferred_offer_validity',
                'pricing_tables_preserved_as_text','linked_programme_itineraries_not_fetched',
                'rzd_catalogue_membership_not_rechecked_by_external_reader']))
    return rows


def bank_links(html):
    soup=BeautifulSoup(html,'html.parser');result={}
    for row in soup.select('table.downloadlist tr'):
        label=text(row.get_text(' ',strip=True))
        if not re.search(r'Правила.*вознагражден',label,re.I):continue
        for a in row.select('a[href]'):
            try:url=checked_url(urljoin(BANK,a['href']))
            except ValueError:continue
            if urlsplit(url).netloc=='www.unicreditbank.ru' and urlsplit(url).path.lower().endswith('.pdf'):
                result[url]={'url':url,'label':label}
    if len(result)>4:raise ValueError('rx_bank_document_bound')
    return list(result.values())


def bank_record(html,observed_at,receipt):
    soup=BeautifulSoup(html,'html.parser');regions=soup.select('.parsys')
    if not soup.title or not regions:raise ValueError('rx_bank_layout')
    title=text(soup.title.get_text(' ',strip=True));body=plain(max(regions,key=lambda n:len(n.get_text())))
    if not re.search(r'CASH\s*&\s*BACK',title,re.I) or not 50<=len(body)<=35000:raise ValueError('rx_bank_identity')
    return make_offer('rzd_unicredit_terms',urlsplit(BANK).path,SOURCES['rzd_unicredit_terms'][0],
        'ЮниКредит Банк','',BANK,observed_at,title=title,conditions=body,record_kind='source_observation',
        locator='largest .parsys on catalogue-linked product page',source_status='public_external_product_exchange_unverified',
        details={'retrieval_method':METHOD,'source_receipt':receipt,'rzd_exchange_verified':False,
            'account_used':False,'document_links':bank_links(html)},
        warnings=['external_product_not_confirmation_of_rzd_point_exchange','no_inferred_cancellation',
            'rzd_catalogue_membership_not_rechecked_by_external_reader'])


def validate_record(r):
    d=r.get('details',{})
    if d.get('retrieval_method')!=METHOD or d.get('account_used') is not False:
        raise ValueError('rx_record_scope')
    if r['source_id']=='rzd_tour_terms':
        part=d.get('part',{});primary=part.get('number')==1
        benefit=text('\n'.join(d.get('rzd_loyalty_clauses',[]))) if primary else ''
        if (r['source_url']!=d.get('tour_url') or checked_url(r['source_url'])!=r['source_url']
            or r['conditions_text']!=text(d.get('condition_fragment','')) or r['benefit_text']!=benefit
            or r['record_kind']!=('partner_offer' if primary else 'program_rules')
            or r['partner_name']!='РЖД Тур' or d.get('personal_eligibility_verified') is not False
            or (primary and not all(LOYALTY.search(c) for c in d.get('rzd_loyalty_clauses',[])))):
            raise ValueError('rx_tour_binding')
    elif d.get('rzd_exchange_verified') is not False:
        raise ValueError('rx_unverified_exchange_promoted')
    elif r['source_id']=='rzd_unicredit_terms':
        if r['record_kind']!='source_observation' or r['benefit_text'] or r['source_url']!=BANK:
            raise ValueError('rx_bank_observation_binding')
    elif r['source_id']=='rzd_unicredit_documents':
        if not d.get('live_document_text') or not d.get('parent_id') or d.get('parent_source')!=BANK:
            raise ValueError('rx_bank_pdf_binding')


def report(sid,discovered,records,errors,coverage,observed_at):
    name,root=SOURCES[sid]
    return {'source_id':sid,'name':name,'root':root,'status':'partial' if errors and records else 'failed' if errors else 'ok',
        'discovered':max(discovered,len(records)),'normalized':len(records),'failed':len(errors),
        'coverage':json.dumps({'method':METHOD,'account_used':False,**coverage},ensure_ascii=False),
        'region':None,'errors':errors,'observed_at':observed_at}


class Reader:
    def __init__(self,folder,*,get=requests.get,clock=time.monotonic,sleep=time.sleep):
        self.folder=Path(folder);self.folder.mkdir(exist_ok=True,parents=True)
        self.get=get;self.clock=clock;self.sleep=sleep;self.started=clock();self.next_at={};self.policies={};self.requests=[];self.halted=set()
    def read(self,url,kind):
        url=checked_url(url);u=urlsplit(url);host=u.netloc
        if len(self.requests)>=MAX_REQUESTS or self.clock()-self.started>MAX_SECONDS-40:raise ValueError('rx_budget')
        if host in self.halted:raise ValueError('rx_host_halted')
        if kind not in ('robots','sitemap','html','pdf'):raise ValueError('rx_kind')
        if kind=='robots':
            if u.path!='/robots.txt':raise ValueError('rx_policy_url')
        elif host not in self.policies or not self.policies[host].can_fetch(url,'LoyaltyCatalogResearchBot'):
            raise ValueError('rx_policy_disallow')
        self.sleep(max(0,self.next_at.get(host,0)-self.clock()))
        item={'url':url,'kind':kind,'started_at':now()};self.requests.append(item)
        try:
            with self.get(url,headers={'User-Agent':'LoyaltyCatalogResearchBot/1.0'},timeout=(8,25),stream=True,allow_redirects=False) as response:
                item['status']=response.status_code;item['mime']=response.headers.get('Content-Type','').split(';')[0].lower()
                if response.status_code==429 or response.headers.get('Retry-After'):
                    self.halted.add(host);raise ValueError('rx_rate_limit')
                if response.status_code!=200:raise ValueError('rx_http_'+str(response.status_code))
                if checked_url(unquote(response.url))!=url:raise ValueError('rx_response_url')
                data=bytearray()
                for block in response.iter_content(65536):
                    data.extend(block)
                    if len(data)>MAX_BYTES:raise ValueError('rx_size_bound')
                data=bytes(data);item['raw_sha256']=sha(data);item['raw_bytes']=len(data)
                if kind=='pdf':
                    if item['mime']!='application/pdf' or not data.startswith(b'%PDF-'):raise ValueError('rx_not_pdf')
                else:
                    raw=data.decode('utf-8-sig')
                    if kind=='robots':
                        if not re.search(r'^\s*User-agent\s*:',raw,re.I|re.M) or re.search(r'<html|<!doctype',raw,re.I):raise ValueError('rx_policy_document')
                        self.policies[host]=Protego.parse(raw)
                    if kind=='html':raw=sanitize_html(raw)
                    data=raw.encode()
                name=f'{len(self.requests):04d}.'+('pdf' if kind=='pdf' else 'xml' if kind=='sitemap' else 'html' if kind=='html' else 'txt')
                (self.folder/name).write_bytes(data);item.update(file=name,sha256=sha(data),stored_bytes=len(data))
                return data,item
        except Exception as exc:
            item['error']=safe_error(exc);raise ValueError(item['error']) from None
        finally:
            item['finished_at']=now()
            policy=self.policies.get(host);rate=policy.request_rate('LoyaltyCatalogResearchBot') if policy else None
            delay=max(5,policy.crawl_delay('LoyaltyCatalogResearchBot') or 0,rate.seconds/rate.requests if rate else 0) if policy else 5
            self.next_at[host]=self.clock()+delay


def collect(reader,run_id,observed_at,tour_limit=MAX_TOURS):
    if type(tour_limit) is not int or not 1<=tour_limit<=MAX_TOURS:raise ValueError('rx_tour_limit')
    records=[];reports=[];errors=[];tours=[];excluded=[];targets={};discovered=0
    try:
        policy,_=reader.read(TOUR+'robots.txt','robots')
        sm=re.findall(r'^Sitemap:\s*(\S+)',policy.decode(),re.I|re.M)
        sm=[checked_url(u) for u in sm if urlsplit(u).netloc=='rzdtour.com']
        if len(sm)!=1:raise ValueError('rx_sitemap_inventory')
        homepage,_=reader.read(TOUR,'html');sitemap,_=reader.read(sm[0],'sitemap')
        targets=tour_targets(sitemap.decode(),homepage.decode());discovered=len(targets)
        for index,(url,why) in enumerate(targets.items()):
            if index>=tour_limit:errors.append({'url':TOUR,'reason':'rx_tour_limit','remaining':len(targets)-index});break
            try:
                raw,receipt=reader.read(url,'html');rows=tour_records(raw.decode(),url,observed_at,receipt,why)
                if rows:tours.extend(rows)
                else:excluded.append(url)
            except Exception as exc:
                reason=safe_error(exc);errors.append({'url':url,'reason':reason})
                if reason in ('rx_budget','rx_rate_limit','rx_host_halted'):break
    except Exception as exc:errors.append({'url':TOUR,'reason':safe_error(exc)})
    records.extend(tours)
    reports.append(report('rzd_tour_terms',discovered,tours,errors,{'selected_urls':list(targets),
        'selection':'advertised_sitemap_tour_sections_plus_homepage_cards','no_loyalty_clause_in_owned_price_block':excluded,
        'source_pages_with_loyalty':len({r['source_url'] for r in tours}),'all_website_pages_read':False},observed_at))
    bank=[];docs=[];links=[];errors=[];doc_errors=[]
    try:
        reader.read('https://www.unicreditbank.ru/robots.txt','robots')
        raw,receipt=reader.read(BANK,'html');html=raw.decode();parent=bank_record(html,observed_at,receipt);bank=[parent]
        links=bank_links(html)
        if not links:doc_errors.append({'url':BANK,'reason':'rx_no_reward_rules'})
        for entry in links:
            try:
                data,receipt=reader.read(entry['url'],'pdf');doc=extract_pdf(data,allow_ocr=False)
                docs.extend(document_records('rzd_unicredit_documents','pdf:'+sha(entry['url'])[:32],
                    SOURCES['rzd_unicredit_documents'][0],'ЮниКредит Банк',entry['url'],observed_at,doc,
                    parent_source=BANK,parent_sha256=parent['content_sha256'],label=entry['label'],
                    extra_details={'retrieval_method':METHOD,'source_receipt':receipt,'parent_id':parent['id'],
                        'rzd_exchange_verified':False,'account_used':False}))
                if doc['errors']:doc_errors.append({'url':entry['url'],'reason':'rx_pdf_text_partial','pages':doc['errors']})
            except Exception as exc:doc_errors.append({'url':entry['url'],'reason':safe_error(exc)})
    except Exception as exc:errors.append({'url':BANK,'reason':safe_error(exc)})
    records.extend(bank+docs)
    reports.append(report('rzd_unicredit_terms',1,bank,errors,{'rzd_exchange_verified':False},observed_at))
    reports.append(report('rzd_unicredit_documents',len(docs),docs,doc_errors or ([{'url':BANK,'reason':'rx_parent_unavailable'}] if not bank else []),
        {'discovered_documents':len(links),'downloaded_documents':len({r['details']['document_sha256'] for r in docs}),
         'native_text_pages':sum(r['details']['page_count'] for r in docs if r['details']['document_part']['number']==1),
         'rzd_exchange_verified':False,'ocr_used':False},observed_at))
    bundle={'schema_version':2,'run_id':run_id,'observed_at':observed_at,'records':records,'sources':reports};prepare(bundle);return bundle


class Replay:
    def __init__(self,folder,audit):
        self.folder=Path(folder);self.items=audit['requests'];self.used=0
        self.policies={};self.halted=set();self.start=datetime.fromisoformat(audit['started_at'])
    def read(self,url,kind):
        url=checked_url(url);host=urlsplit(url).netloc
        if self.used>=MAX_REQUESTS:raise ValueError('rx_budget')
        if host in self.halted:raise ValueError('rx_host_halted')
        if kind!='robots' and (host not in self.policies or not self.policies[host].can_fetch(url,'LoyaltyCatalogResearchBot')):
            raise ValueError('rx_policy_disallow')
        if self.used>=len(self.items):
            if self.used and (datetime.fromisoformat(self.items[-1]['finished_at'])-self.start).total_seconds()>MAX_SECONDS-80:
                raise ValueError('rx_budget')
            raise ValueError('rx_replay_missing_request')
        item=self.items[self.used]
        if item['url']!=url or item['kind']!=kind:raise ValueError('rx_replay_discovery')
        self.used+=1
        if 'error' in item:
            if item['error']=='rx_rate_limit':self.halted.add(host)
            raise ValueError(item['error'])
        data=(self.folder/item['file']).read_bytes()
        if kind=='robots':self.policies[host]=Protego.parse(data.decode())
        return data,item.copy()


def validate_bundle(folder,*,run_id,commit,clock):
    folder=Path(folder);audit=json.loads((folder/'report.json').read_text())
    start,end=[datetime.fromisoformat(audit[x]) for x in ('started_at','finished_at')]
    if (audit['run_id']!=run_id or audit['commit']!=commit or audit['accounts_used'] is not False
        or audit['provider_credits']!=0 or start.tzinfo is None or end.tzinfo is None
        or not start<=end<=clock or (clock-start).total_seconds()>7200 or (end-start).total_seconds()>MAX_SECONDS+80):
        raise ValueError('rx_bundle_identity_time')
    items=audit['requests'];policies={};last=start;previous={};files=set()
    if len(items)>MAX_REQUESTS:raise ValueError('rx_request_bound')
    for i,item in enumerate(items,1):
        url=checked_url(item['url']);host=urlsplit(url).netloc;kind=item['kind']
        a,b=[datetime.fromisoformat(item[x]) for x in ('started_at','finished_at')]
        if not last<=a<=b<=end:raise ValueError('rx_receipt_time')
        if host in previous and (a-previous[host]).total_seconds()<4.9:raise ValueError('rx_receipt_delay')
        previous[host]=b;last=b
        if kind!='robots' and (host not in policies or not policies[host].can_fetch(url,'LoyaltyCatalogResearchBot')):raise ValueError('rx_receipt_policy')
        if 'file' in item:
            name=item['file']
            if not re.fullmatch(r'[0-9]{4}\.(?:pdf|html|txt|xml)',name) or name in files:raise ValueError('rx_receipt_file')
            files.add(name);data=(folder/name).read_bytes()
            if item['status']!=200 or sha(data)!=item['sha256'] or not 0<len(data)<=MAX_BYTES:raise ValueError('rx_receipt_hash')
            if kind=='robots':policies[host]=Protego.parse(data.decode())
            if kind=='pdf' and (item['mime']!='application/pdf' or not data.startswith(b'%PDF-')):raise ValueError('rx_receipt_pdf')
    replay=Replay(folder,audit);bundle=collect(replay,run_id,audit['started_at'],audit['tour_limit'])
    if replay.used!=len(items) or bundle!=json.loads((folder/'normalized.json').read_text()):raise ValueError('rx_reconstruction')
    return bundle


def main():
    p=argparse.ArgumentParser();p.add_argument('--tour-limit',type=int,default=MAX_TOURS);p.add_argument('--output',default='rzd-external-output');args=p.parse_args()
    folder=Path(args.output);reader=Reader(folder);start=now();run=os.environ['GITHUB_RUN_ID']+':'+os.environ['GITHUB_RUN_ATTEMPT']
    bundle=collect(reader,run,start,args.tour_limit)
    audit={'run_id':run,'commit':os.environ['GITHUB_SHA'],'started_at':start,'finished_at':now(),
        'tour_limit':args.tour_limit,'accounts_used':False,'provider_credits':0,'requests':reader.requests}
    (folder/'normalized.json').write_text(json.dumps(bundle,ensure_ascii=False))
    (folder/'report.json').write_text(json.dumps(audit,ensure_ascii=False,indent=2))
    validate_bundle(folder,run_id=run,commit=audit['commit'],clock=datetime.now(timezone.utc))
    print(json.dumps({'records':len(bundle['records']),'requests':len(reader.requests),'statuses':{s['source_id']:s['status'] for s in bundle['sources']}}))

if __name__=='__main__':main()
