"""One bounded, read-only comparison for the two still-uncollected catalogues.
No source accounts, publication, CAPTCHA interaction, TLS override or paid plan.
The original roots remain the comparison targets; sitemap links are discoveries.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
import re
import sys
import time
import xml.etree.ElementTree as ET
from pathlib import Path
from urllib.parse import urljoin,urlsplit,urlunsplit
import requests
from bs4 import BeautifulSoup
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'loyalty'))
from free_access_probe import FreeReader,ProbeError,free_plan,now,LOCATION_JS

HOSTS={'rzd-bonus.ru','www.rzd-bonus.ru','www.aeroflot.ru'}
ROOTS={'rzd':'https://www.rzd-bonus.ru/?accessible=true','aeroflot':'https://www.aeroflot.ru/ru-ru/afl_bonus/partners'}
CAP=75
# This one-shot Sept16 experiment reserves the already calculated Sep17-Oct15
# recurring workload. It is not a universal rolling budget implementation.
RECURRING_RESERVE=5273


def safe_url(value):
    try:
        u=urlsplit(value)
        if u.scheme!='https' or u.netloc not in HOSTS or u.username or u.password or u.query or u.fragment:return None
        if any(x in u.path.lower() for x in ('auth','cabinet','login','password','logout','purchase','order','ajax','bitrix/admin')):return None
        return urlunsplit((u.scheme,u.netloc,u.path or '/','',''))
    except (TypeError,ValueError):return None


def sitemap(raw,base):
    if '<!DOCTYPE' in raw.upper() or '<!ENTITY' in raw.upper():raise ValueError('xml_declaration_not_allowed')
    tree=ET.fromstring(raw)
    kind=tree.tag.rsplit('}',1)[-1]
    if kind not in ('sitemapindex','urlset'):raise ValueError('not_a_sitemap')
    links=[]
    for node in tree.iter():
        if node.tag.rsplit('}',1)[-1]=='loc':
            value=safe_url((node.text or '').strip())
            if value and urlsplit(value).netloc==urlsplit(base).netloc and value not in links:links.append(value)
    if len(links)>10000:raise ValueError('sitemap_size_bound')
    return kind,links


def public_html(raw,base):
    soup=BeautifulSoup(raw,'html.parser')
    for node in soup.select('script,style,form,input,textarea,iframe,noscript,[hidden],[aria-hidden="true"]'):node.decompose()
    for node in soup.find_all(True):
        for key in list(node.attrs):
            if key not in ('id','class','href','title','role'):del node.attrs[key]
        if node.has_attr('href'):
            target=safe_url(urljoin(base,node['href']))
            if target:node['href']=target
            else:del node.attrs['href']
    return str(soup)


def run(mode):
    from public_transport import robots_document,check_response
    from protego import Protego
    out=Path('last-catalogues-output')/mode;out.mkdir(parents=True,exist_ok=True)
    report={'run_id':os.getenv('GITHUB_RUN_ID'),'commit':os.getenv('GITHUB_SHA'),'mode':mode,'started_at':now(),
            'source_ids':['rzd','aeroflot'],'requests':[],'sources':{},'publication':False,'source_accounts':False,
            'maximum_provider_credits':CAP if mode=='provider' else 0,'reserved_credits':0,'source_requests':0}
    def save():
        p=out/'report.tmp';p.write_text(json.dumps(report,ensure_ascii=False,indent=2));p.replace(out/'report.json')
    (out/'executed.py').write_bytes(Path(__file__).read_bytes());save()
    http=None;last={};intervals={};deadline=time.monotonic()+420
    def read(url,*,pool='datacenter',browser=False):
        nonlocal http
        if not safe_url(url):raise ProbeError('unreviewed_target')
        host=urlsplit(url).netloc
        delay=max(0,intervals.get(host,1)-(time.monotonic()-last.get(host,0)))
        if time.monotonic()+delay+80>deadline:raise ProbeError('diagnostic_time_bound')
        time.sleep(delay)
        item={'url':url,'started_at':now(),'transport':mode,'browser':browser,'pool':pool if mode=='provider' else None}
        report['requests'].append(item);save()
        try:
            if mode=='provider':
                cost=(125 if browser else 25) if pool=='residential' else (10 if browser else 1)
                if http.halted or report['reserved_credits']+cost>CAP:raise ProbeError('provider_budget_or_stop')
                report['reserved_credits']+=cost
                params={'url':url,'proxy_country':'RU','proxy_type':pool,'browser':str(browser).lower(),'timeout':'60'}
                if browser:params.update(js_snippet=LOCATION_JS,block_resource=['image','media','font'])
                raw,meta=http._request('general',params)
                charge=str(meta['Ant-credits-cost']);value=str(meta['Ant-page-status-code'])
                if not charge.isdigit() or int(charge)>cost:http.halted=True;raise ProbeError('unverified_cost')
                item['confirmed_cost']=int(charge)
                if not re.fullmatch('[1-5][0-9]{2}',value):raise ProbeError('origin_status_unknown')
                status=int(value)
                if status==429 or meta['ant-original-header-retry-after']:http.halted=True;raise ProbeError('rate_limit')
                if browser:
                    soup=BeautifulSoup(raw,'html.parser');item['browser_final_url']=safe_url(soup.html.get('data-loyalty-probe-location')) if soup.html else None
                item['final_url_verified']=bool(browser and item.get('browser_final_url')==url)
            else:
                with requests.get(url,headers={'User-Agent':'LoyaltyCatalogResearchBot/1.0'},timeout=(5,18),stream=True,allow_redirects=False) as r:
                    status=r.status_code;item['location']=safe_url(urljoin(url,r.headers.get('Location',''))) if r.headers.get('Location') else None
                    if r.headers.get('Retry-After') or status==429:raise ProbeError('rate_limit')
                    data=bytearray()
                    for chunk in r.iter_content(65536):
                        data.extend(chunk)
                        if len(data)>6000000:raise ProbeError('body_size_bound')
                    raw=data.decode('utf-8','replace');item['final_url_verified']=True
            item.update(status=status,chars=len(raw),sha256=hashlib.sha256(raw.encode()).hexdigest())
            return status,raw,item
        except Exception as exc:
            item['error']=str(exc) if isinstance(exc,ProbeError) else type(exc).__name__;raise
        finally:
            last[host]=time.monotonic();item['finished_at']=now();report['source_requests']=len(report['requests']);save()
    try:
        if mode=='provider':
            http=FreeReader(os.environ.get('SCRAPINGANT_API_KEY',''),[],max_credits=CAP,max_requests=15)
            usage,_=http._request('usage',{});left=free_plan(usage);report.update(free_plan_confirmed=True,balance_before=left)
            if left<CAP+RECURRING_RESERVE:raise ProbeError('preserve_existing_scheduled_credits')
        for sid,host in (('aeroflot','www.aeroflot.ru'),('rzd','rzd-bonus.ru')):
            info={'original_root':ROOTS[sid],'catalogue_published':False};report['sources'][sid]=info;save()
            try:
                policy_url='https://'+host+'/robots.txt'
                status,raw,item=read(policy_url,pool='residential' if mode=='provider' and sid=='aeroflot' else 'datacenter')
                rules,state=robots_document(status,raw);policy=Protego.parse(rules)
                info['policy']={'state':state,'status':status,'sha256':hashlib.sha256(rules.encode()).hexdigest(),
                                'original_root_allowed':policy.can_fetch(ROOTS[sid],'LoyaltyCatalogResearchBot')}
                (out/(sid+'-robots.txt')).write_text(rules)
                rate=policy.request_rate('LoyaltyCatalogResearchBot')
                intervals[host]=max(1,policy.crawl_delay('LoyaltyCatalogResearchBot') or 0,rate.seconds/rate.requests if rate else 0)
                if intervals[host]>60:raise ProbeError('crawl_delay_exceeds_budget')
                if sid=='aeroflot':
                    info['result']='source_policy_disallow' if not info['policy']['original_root_allowed'] else 'policy_allows_target_not_recovered'
                    continue
                info['canonical_host_basis']='Host and HTTPS Sitemap in previously observed source robots; not a claimed redirect'
                maps=[safe_url(x) for x in re.findall(r'^Sitemap:\s*(\S+)',rules,re.I|re.M)]
                maps=[x for x in maps if x and urlsplit(x).netloc==host]
                if not maps:maps=['https://rzd-bonus.ru/sitemap.xml']
                queue=list(dict.fromkeys(maps));visited=set();pages=[];info['sitemaps']=[]
                while queue and len(visited)<3:
                    url=queue.pop(0)
                    if url in visited:continue
                    visited.add(url)
                    if not policy.can_fetch(url,'LoyaltyCatalogResearchBot'):continue
                    try:
                        status,raw,item=read(url);check_response(status,raw)
                        kind,links=sitemap(raw,url)
                        info['sitemaps'].append({'url':url,'kind':kind,'links':len(links),'sha256':item['sha256']})
                        (out/('rzd-sitemap-'+str(len(visited))+'.xml')).write_text(raw)
                        if kind=='sitemapindex':queue.extend(x for x in links if x not in visited)
                        else:pages.extend(links)
                    except Exception as exc:
                        info.setdefault('map_errors',[]).append({'url':url,'error':str(exc) if isinstance(exc,(ProbeError,RuntimeError)) else type(exc).__name__})
                pages=list(dict.fromkeys(pages));info['discovered_public_urls']=pages
                candidates=[u for u in pages if re.search(r'/partners?/?$|/privileges?/?$|/privilegii/?$|/discounts?/?$',urlsplit(u).path,re.I)]
                info['catalogue_candidates']=candidates
                url=candidates[0] if candidates else 'https://rzd-bonus.ru/'
                if not policy.can_fetch(url,'LoyaltyCatalogResearchBot'):raise ProbeError('candidate_policy_disallow')
                status,raw,item=read(url,browser=mode=='provider');check_response(status,raw)
                dom=public_html(raw,url);(out/'rzd-candidate.html').write_text(dom)
                soup=BeautifulSoup(dom,'html.parser')
                info['candidate']={'url':url,'status':status,'title':soup.title.get_text(' ',strip=True) if soup.title else '',
                    'text_chars':len(soup.get_text(' ',strip=True)),'links':[{'url':a['href'],'text':a.get_text(' ',strip=True)[:200]} for a in soup.select('a[href]')],
                    'source_sha256':item['sha256'],'sanitized_sha256':hashlib.sha256(dom.encode()).hexdigest(),'complete_catalogue':False}
                info['result']='candidate_requires_content_review'
            except Exception as exc:
                info['result']='not_recovered';info['error']=str(exc) if isinstance(exc,(ProbeError,RuntimeError)) else type(exc).__name__
            finally:save()
    except Exception as exc:
        report['error']=str(exc) if isinstance(exc,ProbeError) else type(exc).__name__
    finally:
        if http and not http.halted:
            try:usage,_=http._request('usage',{});report['balance_after']=free_plan(usage)
            except Exception:report['balance_after_unavailable']=True
        report['finished_at']=now();save()


def selfcheck():
    for bad in ('http://rzd-bonus.ru/','https://rzd-bonus.ru.evil.test/','https://u:p@rzd-bonus.ru/','https://rzd-bonus.ru/cabinet/','https://rzd-bonus.ru/?token=x'):
        assert safe_url(bad) is None
    assert safe_url('https://rzd-bonus.ru/sitemap.xml')=='https://rzd-bonus.ru/sitemap.xml'
    kind,links=sitemap('<urlset><url><loc>https://rzd-bonus.ru/partners/</loc></url><url><loc>https://foreign.example/a</loc></url></urlset>','https://rzd-bonus.ru/sitemap.xml')
    assert kind=='urlset' and links==['https://rzd-bonus.ru/partners/']
    try:sitemap('<!DOCTYPE x><urlset/>','https://rzd-bonus.ru/sitemap.xml')
    except ValueError:pass
    else:raise AssertionError('doctype accepted')
    clean=public_html('<form>PRIVATE</form><script>PRIVATE</script><a href="/partners/" onclick="PRIVATE">PUBLIC</a>','https://rzd-bonus.ru/')
    assert 'PRIVATE' not in clean and 'https://rzd-bonus.ru/partners/' in clean
    print('9 boundary and discovery checks passed')


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--mode',choices=['direct','provider']);p.add_argument('--selfcheck',action='store_true');args=p.parse_args()
    if args.selfcheck:selfcheck()
    elif args.mode:run(args.mode)
    else:p.error('mode or selfcheck required')
