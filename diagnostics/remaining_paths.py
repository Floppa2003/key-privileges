"""Bounded public-source experiments. No credentials, publication or saved answers."""
from __future__ import annotations
import argparse
import asyncio
import hashlib
import ipaddress
import json
import os
import re
import socket
import ssl
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin, urlsplit, urlunsplit
from bs4 import BeautifulSoup

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'loyalty'))
IDS=('ekp','nordwind','coral','coral_promo','rzd','aeroflot')
CONFIG={x['id']:x for x in json.loads(Path('loyalty/sources_normalized.json').read_text()) if x['id'] in IDS}
OUT=Path('remaining-paths-output');OUT.mkdir(exist_ok=True)
DENIED=re.compile(r'captcha|access denied|forbidden|доступ.{0,100}ограничен|проверка браузера',re.I)

def now():return datetime.now(timezone.utc).isoformat()
def public_url(value):
    try:
        u=urlsplit(value)
        if u.scheme!='https' or not u.hostname or u.username or u.password or u.port not in (None,443):return None
        return urlunsplit((u.scheme,u.netloc,u.path,'',''))
    except (ValueError,TypeError):return None

def page_evidence(raw,url,label):
    soup=BeautifulSoup(raw,'html.parser')
    for n in soup.select('script,style,noscript,form,input,textarea,iframe'):n.decompose()
    title=soup.title.get_text(' ',strip=True) if soup.title else ''
    text=soup.get_text(' ',strip=True)
    restricted=bool(DENIED.search(title+' '+text[:500]))
    links=[]
    for n in soup.find_all(True):
        for k in list(n.attrs):
            if k not in ('id','class','href','role'):del n.attrs[k]
        if n.has_attr('href'):
            clean=public_url(urljoin(url,n['href']))
            if clean:n['href']=clean;links.append(clean)
            else:del n.attrs['href']
    result={'title':title[:200],'text_chars':len(text),'link_count':len(set(links)),
        'restricted':restricted,'raw_dom_sha256':hashlib.sha256(raw.encode()).hexdigest(),
        'headings':[n.get_text(' ',strip=True)[:200] for n in soup.select('h1,h2,h3')][:30]}
    if not restricted:
        data=str(soup).encode();(OUT/(label+'.html')).write_bytes(data)
        result['sanitized_dom_sha256']=hashlib.sha256(data).hexdigest()
        result['sanitized_file']=label+'.html'
    return result

def save(label,report):
    p=OUT/(label+'.tmp');p.write_text(json.dumps(report,ensure_ascii=False,indent=2));p.replace(OUT/(label+'.json'))

def base(sid,mode):
    return {'source_id':sid,'target_url':CONFIG[sid]['url'],'mode':mode,'run_id':os.getenv('GITHUB_RUN_ID'),
        'commit':os.getenv('GITHUB_SHA'),'started_at':now(),'publication':False,'secrets_used':False,
        'catalogue_restored':False,'script_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}

def external():
    import requests
    from protego import Protego
    count=0;stop=False
    for sid in IDS:
        rep=base(sid,'microlink_free');rep['reads']=[];label='external-'+sid
        if stop:rep['not_attempted']='provider_rate_limit';save(label,rep);continue
        urls=['https://'+urlsplit(rep['target_url']).hostname+'/robots.txt',rep['target_url']]
        for phase,url in zip(('robots','catalogue'),urls):
            item={'phase':phase,'url':url,'started_at':now(),'fresh_copy_requested':True};rep['reads'].append(item);save(label,rep)
            try:
                params={'url':url,'force':'true','data.markup.selector':'html','data.markup.attr':'html',
                    'data.text.selector':'body','data.text.attr':'text'}
                with requests.get('https://api.microlink.io/',params=params,timeout=(10,65),stream=True,allow_redirects=False) as r:
                    count+=1;item['provider_http_status']=r.status_code
                    item['headers']={k:v for k,v in r.headers.items() if k.lower() in ('x-cache-status','x-pricing-plan','x-rate-limit-remaining','x-rate-limit-limit','retry-after','age','date')}
                    if r.status_code==429 or r.headers.get('Retry-After'):stop=True;break
                    raw=bytearray()
                    for chunk in r.iter_content(65536):
                        raw.extend(chunk)
                        if len(raw)>6000000:raise ValueError('provider_payload_limit')
                obj=json.loads(raw);item['provider_status']=obj.get('status');item['provider_code']=obj.get('code')
                item['payload_sha256']=hashlib.sha256(raw).hexdigest()
                data=obj.get('data') or {};html=data.get('markup');text=data.get('text')
                item['reported_url']=public_url(data.get('url'));item['origin_http_status']=obj.get('statusCode')
                if r.status_code!=200 or obj.get('status')!='success':break
                if not isinstance(html,str) or len(html)>6000000:raise ValueError('missing_provider_html')
                item['page']=page_evidence(html,url,label+'-'+phase)
                if item['page']['restricted']:break
                if phase=='robots':
                    if not isinstance(text,str) or not re.search(r'^\s*user-agent\s*:',text,re.I|re.M):
                        item['policy']='unverified_robots_document';break
                    if item['reported_url']!=public_url(url):item['policy']='unverified_robots_origin';break
                    if not Protego.parse(text).can_fetch(rep['target_url'],'LoyaltyCatalogResearchBot'):
                        item['policy']='disallow';break
                    item['policy']='rules_allow_catalogue'
                else:item['classification']='public_content_candidate_requires_review'
            except Exception as exc:item['error_type']=type(exc).__name__;break
            finally:item['finished_at']=now();save(label,rep)
            time.sleep(2)
        rep['finished_at']=now();save(label,rep)
    save('external-summary',{'provider_requests':count,'hard_limit':12,'quota_stop':stop,'finished_at':now()})

def network(sid):
    host=urlsplit(CONFIG[sid]['url']).hostname;rep=base(sid,'dns_tcp_tls');rep['connections']=[]
    try:
        addresses=socket.getaddrinfo(host,443,type=socket.SOCK_STREAM)
        for family in (socket.AF_INET,socket.AF_INET6):
            entry=next((a for a in addresses if a[0]==family),None)
            if entry is None:continue
            _,kind,proto,_,address=entry
            if not ipaddress.ip_address(address[0]).is_global:continue
            item={'family':'ipv4' if family==socket.AF_INET else 'ipv6','dns_address':address[0],'stage':'tcp'}
            rep['connections'].append(item);save('network-'+sid,rep);t=time.monotonic()
            try:
                with socket.socket(family,kind,proto) as sock:
                    sock.settimeout(6);sock.connect(address);item['tcp_ms']=round((time.monotonic()-t)*1000)
                    item['stage']='tls';t=time.monotonic();ctx=ssl.create_default_context();ctx.set_alpn_protocols(['http/1.1'])
                    with ctx.wrap_socket(sock,server_hostname=host) as tls:
                        item['tls_ms']=round((time.monotonic()-t)*1000);item['tls_version']=tls.version()
                        item['stage']='http';tls.sendall(('HEAD /robots.txt HTTP/1.1\r\nHost: '+host+'\r\nUser-Agent: LoyaltyCatalogResearchBot\r\nConnection: close\r\n\r\n').encode())
                        first=tls.recv(4096).split(b'\r\n',1)[0].decode('ascii','replace')
                        item['status_line']=first[:100];item['stage']='http_response'
            except Exception as exc:item['error_type']=type(exc).__name__
            save('network-'+sid,rep)
    except Exception as exc:rep['error_type']=type(exc).__name__
    rep['finished_at']=now();save('network-'+sid,rep)

async def bootstrap(sid):
    from installed_browser import installed_chrome
    from public_transport import PublicSource
    rep=base(sid,'root_before_policy_same_fresh_profile');rep['navigation']=[];label='bootstrap-'+sid
    save(label,rep)
    try:
        async with installed_chrome() as (ctx,page):
            def observe(r):
                if r.request.is_navigation_request() and r.frame==page.main_frame:
                    rep['navigation'].append({'url':public_url(r.url),'status':r.status,'retry_after':bool(r.headers.get('retry-after'))})
            page.on('response',observe);rep['stage']='initial_user_requested_root';save(label,rep)
            try:await page.goto(rep['target_url'],wait_until='commit',timeout=22000)
            except Exception as exc:rep['navigation_error']=type(exc).__name__
            for pause in (2,6,12):
                await asyncio.sleep(pause)
                try:
                    html=await asyncio.wait_for(page.content(),5)
                    rep['root_page']=page_evidence(html,rep['target_url'],label+'-root')
                    save(label,rep)
                    if rep['root_page']['restricted']:break
                    if rep['root_page']['text_chars']>1000:break
                except Exception as exc:rep['dom_error']=type(exc).__name__
            page.remove_listener('response',observe)
            if not rep['navigation'] or rep['navigation'][-1]['status']!=200 or rep['navigation'][-1]['retry_after']:
                rep['stop_reason']='no_accepted_main_document';return
            if rep.get('root_page',{}).get('restricted'):
                rep['stop_reason']='restriction_document';return
            if urlsplit(page.url).hostname!=urlsplit(rep['target_url']).hostname:
                rep['stop_reason']='foreign_navigation';return
            client=PublicSource(None,rep['target_url']);client.context=ctx;client.page=await asyncio.wait_for(ctx.new_page(),5)
            rep['stage']='policy_after_root';save(label,rep)
            try:
                await asyncio.wait_for(client.robots(),45)
                client.check_url(rep['target_url']);rep['policy_after_root_allowed']=True
            finally:rep['robots']=getattr(client,'robots_info',{})
    except Exception as exc:rep['error_type']=type(exc).__name__
    finally:rep['finished_at']=now();save(label,rep)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('mode',choices=['external','network','bootstrap']);p.add_argument('--source',choices=IDS);a=p.parse_args()
    (OUT/'executed-script.py').write_bytes(Path(__file__).read_bytes())
    if a.mode=='external':external()
    elif not a.source:p.error('--source required')
    elif a.mode=='network':network(a.source)
    else:asyncio.run(bootstrap(a.source))
