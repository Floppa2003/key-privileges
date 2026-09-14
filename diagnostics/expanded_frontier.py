"""Finite discovery probe; no sign-in, publication, stored answers or signed URLs in output."""
import hashlib
import json
import os
import re
import sys
import time
from collections import deque
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin, urlsplit
import requests
from bs4 import BeautifulSoup
sys.path.insert(0, str(Path('loyalty').resolve()))
from document_text import extract_pdf
from utair_documents import ROOT, checked_download_target, discover_documents
from public_frontier import read, MARKERS
OUT=Path('expanded-output');OUT.mkdir(exist_ok=True)
NOW=datetime.now(timezone.utc).isoformat()


def get(url,max_bytes=3000000):
    with requests.Session() as session:
        session.trust_env=False
        with session.get(url,headers={'User-Agent':'Mozilla/5.0'},timeout=(7,15),allow_redirects=False,stream=True) as r:
            data=bytearray()
            for block in r.iter_content(65536):
                data.extend(block)
                if len(data)>max_bytes:raise RuntimeError('size_bound')
            return r.status_code,bytes(data)


def utair():
    status,raw=get(ROOT);out={'parent':ROOT,'http_status':status,'documents':[]}
    if status!=200:return out
    out['parent_sha256']=hashlib.sha256(raw).hexdigest()
    html=raw.decode('utf8');out['shortlinks_count']=len(discover_documents(html))
    soup=BeautifulSoup(html,'html.parser');seen=set()
    for a in soup.select('a[href]'):
        url=urljoin(ROOT,a['href']);u=urlsplit(url)
        if u.hostname!='eu-s3.beelinecloud.ru' or not u.path.lower().endswith('.pdf'):continue
        checked_download_target(url)
        key=u.scheme+'://'+u.netloc+u.path
        if key in seen:continue
        seen.add(key)
        if len(seen)>10:raise RuntimeError('direct_document_count_bound')
        row={'path':u.path,'label':a.get_text(' ',strip=True),'query_present':bool(u.query)}
        try:
            status,data=get(url,20000000);row['status']=status
            if status==200:
                doc=extract_pdf(data,allow_ocr=False)
                row.update(sha256=doc['document_sha256'],page_count=doc['page_count'],title=doc['title'],errors=doc['errors'])
                name='utair-'+hashlib.sha256(key.encode()).hexdigest()[:16]
                (OUT/(name+'.pdf')).write_bytes(data)
                (OUT/(name+'.json')).write_text(json.dumps(doc,ensure_ascii=False,indent=2),encoding='utf8')
                row['document_file']=name+'.pdf'
        except Exception as exc:row['error']=type(exc).__name__
        out['documents'].append(row);time.sleep(1)
    return out


def campaigns():
    root='https://promomiles.aeroflot.ru/'
    queue=deque([(root,0,None)]);seen=set();rows=[]
    while queue and len(seen)<14:
        url,depth,parent=queue.popleft()
        if url in seen:continue
        seen.add(url);row={'url':url,'parent':parent,'depth':depth}
        try:
            status,data=get(url);row['status']=status
            if status==200:
                soup=BeautifulSoup(data,'html.parser');row['title']=soup.title.get_text(' ',strip=True) if soup.title else ''
                row['sha256']=hashlib.sha256(data).hexdigest()
                # Public campaign/rules HTML only, no winners, accounts or application forms.
                name='campaign-'+str(len(rows))+'.html';(OUT/name).write_bytes(data);row['file']=name
                links=[]
                for a in soup.select('a[href]'):
                    target=urljoin(url,a['href']);u=urlsplit(target);label=a.get_text(' ',strip=True)
                    if u.scheme!='https' or u.netloc!='promomiles.aeroflot.ru' or u.query or u.fragment:continue
                    if not re.fullmatch(r'/act/[A-Za-z0-9_-]+(?:/[A-Za-z0-9_-]+)?/?',u.path):continue
                    if re.search(r'winner|result|победител|результат',target+' '+label,re.I):continue
                    links.append({'url':target,'label':label})
                    if depth<2 and target not in seen:queue.append((target,depth+1,url))
                row['advertised_links']=links
        except Exception as exc:row['error']=type(exc).__name__
        rows.append(row);time.sleep(1)
    return {'pages':rows,'queue_remaining':len(queue),'bound':14}


def main():
    # www forms are publisher-advertised domain aliases, not guessed private APIs.
    routes=[('coral','https://www.coralbonus.ru/klub-privilegii/'),
            ('coral_promo','https://www.coralbonus.ru/promo/'),
            ('ekp','https://www.ekp.spb.ru/capabilities/loyalty/'),
            ('ekp','https://www.ekp.spb.ru/api/portal/loyalty/partners')]
    results={'observed_at':NOW,'run_id':os.getenv('GITHUB_RUN_ID'),'code_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
             'alternate_routes':[read(url,sid,'alternate-'+str(i)) for i,(sid,url) in enumerate(routes)]}
    for name,fn in [('utair_direct',utair),('campaigns',campaigns)]:
        try:results[name]=fn()
        except Exception as exc:results[name]={'error':type(exc).__name__}
    (OUT/'report.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf8')
    print(json.dumps({k:len(v) if isinstance(v,list) else 'saved' for k,v in results.items()}))

if __name__=='__main__':main()
