"""Exact public URLs observed in run 34958485244, no private API or cookies.
Diagnostic only. No pagination, inferred IDs, authentication or API challenge replay.
"""
import hashlib
import json
import os
import re
import time
from pathlib import Path
from datetime import datetime,timezone
from urllib.parse import urlsplit
import requests
from bs4 import BeautifulSoup
from protego import Protego

ROOT='https://ekp.spb.ru'
URLS=[ROOT+'/capabilities/loyalty/',ROOT+'/api/portal/loyalty/partners']
OUT=Path('ekp-public-http-output')
ALLOWED={'id','name','title','description','discount','benefit','url','slug','active','is_active','requires_auth','require_auth','total','count','total_count','page','pages','per_page','last_page','current_page'}


def structure(value,depth=0):
    if depth>4:return type(value).__name__
    if isinstance(value,dict):return {k:structure(v,depth+1) for k,v in list(value.items())[:60]}
    if isinstance(value,list):return {'array_length':len(value),'first_item_shape':structure(value[0],depth+1) if value else None}
    return type(value).__name__


def public_examples(value,path='$',out=None):
    out=[] if out is None else out
    if len(out)>=5:return out
    if isinstance(value,dict):
        fields={k:v for k,v in value.items() if k in ALLOWED and isinstance(v,(str,int,float,bool))}
        fields={k:(v[:600] if isinstance(v,str) else v) for k,v in fields.items()}
        if 'name' in fields or 'title' in fields:out.append({'path':path,'public_fields':fields})
        for key,child in value.items():
            if isinstance(child,(dict,list)) and not re.search('token|session|auth|account|user|secret|cookie',key,re.I):
                public_examples(child,path+'.'+key,out)
    elif isinstance(value,list):
        for i,child in enumerate(value[:5]):public_examples(child,path+f'[{i}]',out)
    return out


def run():
    OUT.mkdir(exist_ok=True);raw=Path(__file__).read_bytes();(OUT/'ekp_public_http.py').write_bytes(raw)
    report={'observed_at':datetime.now(timezone.utc).isoformat(),'run_id':os.getenv('GITHUB_RUN_ID'),
        'commit':os.getenv('GITHUB_SHA'),'replica':os.getenv('REPLICA'),
        'script_sha256':hashlib.sha256(raw).hexdigest(),'observations':[],
        'catalog_complete':False,'authentication_used':False,'production_write':False}
    def save():(OUT/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
    with requests.Session() as session:
        session.trust_env=False
        for url in [ROOT+'/robots.txt']+URLS:
            started=time.monotonic();item={'url':url};report['observations'].append(item);save()
            try:
                with session.get(url,timeout=(8,15),allow_redirects=False,stream=True) as r:
                    item['status']=r.status_code;item['content_type']=r.headers.get('Content-Type','')
                    if r.status_code==429 or r.headers.get('Retry-After'):
                        item['result']='rate_limited';save();break
                    if r.status_code!=200:item['result']='not_readable_http_response';continue
                    data=bytearray()
                    for chunk in r.iter_content(65536):
                        data.extend(chunk)
                        if len(data)>2000000:raise RuntimeError('response_size_bound')
                    item['response_bytes']=len(data);item['sha256']=hashlib.sha256(data).hexdigest()
                    text=bytes(data).decode('utf-8',errors='replace')
                    if url.endswith('/robots.txt'):
                        policy=Protego.parse(text)
                        item['crawler_policy']={u:policy.can_fetch(u,'*') for u in URLS}
                        item['result']='robots_observed'
                    elif 'json' in item['content_type'].lower():
                        value=json.loads(text);item['json_structure']=structure(value)
                        item['public_examples']=public_examples(value)
                        item['result']='public_json_observed' if item['public_examples'] else 'json_without_partner_examples'
                    else:
                        soup=BeautifulSoup(text,'html.parser')
                        item['title']=soup.title.get_text(' ',strip=True)[:200] if soup.title else ''
                        item['numeric_card_urls']=len({a['href'] for a in soup.select('a[href]') if re.fullmatch(r'/capabilities/loyalty/tiles/[0-9]+/?',urlsplit(a['href']).path)})
                        item['result']='public_html_observed_not_catalog_certified'
            except Exception as exc:
                item['error_type']=type(exc).__name__
                if isinstance(exc,requests.exceptions.SSLError):item['result']='tls_verification_failed'
                elif isinstance(exc,requests.exceptions.ConnectTimeout):item['result']='connection_timeout'
                elif isinstance(exc,requests.exceptions.ReadTimeout):item['result']='read_timeout'
                else:item['result']='read_failed'
            finally:item['seconds']=round(time.monotonic()-started,3);save()
            time.sleep(1)
    report['finished_at']=datetime.now(timezone.utc).isoformat();save()

if __name__=='__main__':run()
