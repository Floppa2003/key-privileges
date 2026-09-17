"""Read-only access diagnostic, not a recurring collector or publication.

These exact targets were found in current retained Aeroflot/EKP source objects.
No source account, Google identity, provider key, coupon or purchase is used.
Only bounded public response metadata is saved, not cookies or whole documents.
"""
from __future__ import annotations
import hashlib,json,re,time
from datetime import datetime,timezone
from pathlib import Path
from urllib.parse import urljoin,urlsplit,urlunsplit
import requests
from bs4 import BeautifulSoup
from protego import Protego

BOT='LoyaltyCatalogResearchBot'
TARGETS=[
 ('aeroflot','Доктор Столетов','https://stoletov.ru/catalog/groups/'),
 ('aeroflot','Шереметьево Паркинг','https://parkingsvo.ru/vazhno-znat/pravila-ispolzovaniya.html'),
 ('ekp','Пикассо','https://cloud.picasso-diagnostic.ru/s/9RYnpPKDeTknfnw'),
 ('ekp','Лотос','https://lotos-team.ru/kontakty/'),
]
MAX_BYTES=6_000_000

def now():return datetime.now(timezone.utc).isoformat()
def sha(data):return hashlib.sha256(data).hexdigest()
def public_location(value,base):
    u=urlsplit(urljoin(base,value))
    if u.scheme not in ('http','https') or u.username or u.password:return None
    # Never persist signed queries, fragments or response cookies.
    return {'url_without_query':urlunsplit((u.scheme,u.netloc,u.path,'','')),'has_query':bool(u.query),'has_fragment':bool(u.fragment)}

def read(session,url):
    result={'url':url,'requested_at':now()};body=None
    try:
        with session.get(url,headers={'User-Agent':BOT+'/1.0'},timeout=(8,20),stream=True,allow_redirects=False) as r:
            result.update(status=r.status_code,mime=r.headers.get('Content-Type','').split(';')[0].lower(),retry_after_present=bool(r.headers.get('Retry-After')))
            if r.status_code in (301,302,303,307,308):result['redirect']=public_location(r.headers.get('Location',''),url)
            if r.status_code!=200 or result['retry_after_present']:return result,None
            data=bytearray();deadline=time.monotonic()+40
            for chunk in r.iter_content(65536):
                data.extend(chunk)
                if len(data)>MAX_BYTES or time.monotonic()>deadline:
                    result['error']='bounded_response_limit';return result,None
            body=bytes(data);result.update(bytes=len(body),sha256=sha(body),actual_kind='pdf' if body.startswith(b'%PDF-') else 'html_or_text')
    except requests.RequestException as exc:result['error']=type(exc).__name__
    finally:result['finished_at']=now()
    return result,body

def main():
    session=requests.Session();session.trust_env=False
    out=Path('remaining-rule-probe');out.mkdir(exist_ok=True)
    report={'kind':'read_only_GitHub_access_probe_not_recurring_collection','started_at':now(),'source_account_used':False,'provider_credits':0,'google_used':False,'results':[]}
    for program,partner,url in TARGETS:
        host=urlsplit(url).netloc;item={'program':program,'partner':partner,'url':url};report['results'].append(item)
        receipt,raw=read(session,'https://'+host+'/robots.txt');item['robots_receipt']=receipt
        if receipt.get('retry_after_present') or receipt.get('status')==429:
            item['result']='rate_limited_no_target_request';continue
        if receipt.get('status') in (404,410):rules=Protego.parse('User-agent: *\nAllow: /')
        elif raw is not None:
            body=raw.decode('utf8',errors='replace')
            if '<html' in body.lower() or not re.search(r'^\s*User-agent:',body,re.I|re.M):
                item['result']='robots_unreadable_target_not_requested';continue
            rules=Protego.parse(body)
        else:item['result']='robots_unavailable_target_not_requested';continue
        if not rules.can_fetch(url,BOT):item['result']='robots_disallow_target_not_requested';continue
        rate=rules.request_rate(BOT);delay=max(3,rules.crawl_delay(BOT) or 0,rate.seconds/rate.requests if rate else 0)
        if delay>20:item['result']='source_delay_exceeds_diagnostic_bound';continue
        time.sleep(delay)
        target,data=read(session,url);item['target_receipt']=target
        if data is None:item['result']='target_not_read';continue
        item['result']='target_bytes_read'
        if data.startswith(b'%PDF-'):
            # Avoid OCR, rendering, page interpretation or content republication.
            item['pdf_magic_verified']=True
        else:
            dom=BeautifulSoup(data,'html.parser');item['title']=(dom.title.get_text(' ',strip=True) if dom.title else '')[:200]
            item['password_form_present']=bool(dom.select('input[type=password]'))
            links=[]
            for a in dom.select('a[href]'):
                label=a.get_text(' ',strip=True)
                u=urlsplit(urljoin(url,a['href']))
                if u.netloc!=host or u.scheme!='https' or u.query or u.fragment:continue
                if not (u.path.lower().endswith('.pdf') or re.search(r'скачать|download',label,re.I)):continue
                entry={'url':urlunsplit((u.scheme,u.netloc,u.path,'','')),'label':label[:120]}
                if entry not in links:links.append(entry)
                if len(links)>=20:break
            item['public_download_links']=links
    report['finished_at']=now()
    (out/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
    print(json.dumps({'targets':len(report['results']),'results':[r['result'] for r in report['results']],'credits':0}))

if __name__=='__main__':main()
