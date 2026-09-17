"""One bounded diagnostic of links in two already verified public catalogues.
Parent times are historical; target GETs are new. No source accounts or publication.
"""
from __future__ import annotations
import concurrent.futures, hashlib, ipaddress, json, os, re, socket, time
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin, urlsplit, urldefrag
import requests
from bs4 import BeautifulSoup
from protego import Protego

OUT=Path('linked-probe-output'); OUT.mkdir(exist_ok=True)
BOT='LoyaltyCatalogResearchBot'
BLOCK=re.compile(r'captcha|access denied|just a moment|доступ.{0,40}(?:запрещ|ограничен)|проверка безопасности',re.I)
INSTRUCTION=re.compile(r'ignore (?:all |previous )?instructions|reveal.{0,20}system prompt|игнорируй.{0,30}инструкц',re.I)
RELEVANT=re.compile(r'аэрофлот|aeroflot|afl.bonus|един.{0,15}карт.{0,20}петербур|\bекп\b|услови|правил|исключени',re.I)
ACTION=re.compile(r'/(?:personal|aac|login|logout|register|signup|booking|lk|cart|checkout|order|g|r)(?:/|$)|/(?:buy|kupit)[-/]|/send',re.I)
DENIED_HOST=re.compile(r'(?:^|\.)(?:t\.me|telegram\.me|gosuslugi\.ru|2gis\.com|2gis\.ru|go\.link|admitad\.com)$',re.I)

def now():return datetime.now(timezone.utc).isoformat()
def sha(b):return hashlib.sha256(b).hexdigest()
def safe(value):
    if not isinstance(value,str) or len(value)>1600 or any(c.isspace() or ord(c)<32 for c in value) or '\\' in value:return False
    try:u=urlsplit(value)
    except ValueError:return False
    if u.scheme!='https' or not u.hostname or u.username or u.password or u.port not in (None,443):return False
    if ACTION.search(u.path) or DENIED_HOST.search(u.hostname) or re.search(r'(?:^|&)(?:key|token|signature|auth|session|return_url)=',u.query,re.I):return False
    if u.hostname in ('localhost','metadata.google.internal') or '.' not in u.hostname:return False
    try:ipaddress.ip_address(u.hostname);return False
    except ValueError:return True

def inventory():
    entries={};excluded=[]
    for filename in ('parent-af/normalized.json','parent-ekp/normalized.json'):
        b=json.loads(Path(filename).read_text())
        for r in b['records']:
            p=r['details'].get('public_partner',{}); links=[]
            if r['source_id']=='aeroflot':links=p.get('outgoing_links',[])
            elif r['source_id']=='ekp' and not p.get('description_authorized'):
                for field in ('loyaltyDescription','discountScheme','text'):
                    soup=BeautifulSoup(p.get(field) or '', 'html.parser')
                    links.extend({'url':a['href'],'label':a.get_text(' ',strip=True),'field':field} for a in soup.select('a[href]'))
            for l in links:
                url=urldefrag(l['url'])[0]
                ref={'source_id':r['source_id'],'record_id':r['id'],'record_hash':r['content_sha256'],
                     'parent_observed_at':r['observed_at'],'partner':r['partner_name'],'label':l['label'],'field':l['field']}
                if not safe(url):excluded.append({'url':url,'parent':ref,'reason':'action_account_scheme_or_url_scope'});continue
                entries.setdefault(url,[]).append(ref)
    return entries,excluded

def sanitize(data,encoding,url):
    raw=data.decode(encoding or 'utf-8',errors='replace');soup=BeautifulSoup(raw,'html.parser')
    headings=' '.join(n.get_text(' ',strip=True) for n in soup.select('title,h1'))
    if BLOCK.search(headings) or INSTRUCTION.search(soup.get_text(' ',strip=True)):raise ValueError('restriction_or_agent_directive')
    for n in soup.select('script,style,form,input,textarea,button,iframe,noscript,svg'):n.decompose()
    for n in soup.find_all(True):n.attrs={k:v for k,v in n.attrs.items() if k in ('href','src','id','class','title','rel','alt','colspan','rowspan')}
    main=soup.find('main') or soup.find('article') or soup.body
    if main is None:raise ValueError('no_html_content')
    content=main.get_text(' ',strip=True)
    paragraphs=[n.get_text(' ',strip=True) for n in main.select('p,li,h1,h2,h3,td') if RELEVANT.search(n.get_text(' ',strip=True))]
    links=[]
    for a in main.select('a[href]'):
        target=urljoin(url,a['href']);label=a.get_text(' ',strip=True)
        if (RELEVANT.search(label+' '+target) or urlsplit(target).path.lower().endswith('.pdf')) and safe(target):
            links.append({'url':target,'label':label,'same_host':urlsplit(url).hostname==urlsplit(target).hostname})
    return str(soup).encode(),headings[:500],content[:1000],paragraphs[:30],links[:80]

def host_read(host,targets,deadline):
    results=[];policy=None;delay=5;next_at=0;terminal=False
    # DNS is a safety check, not a substitute origin or direct-IP access path.
    try:
        addresses={x[4][0] for x in socket.getaddrinfo(host,443,type=socket.SOCK_STREAM)}
        if not addresses or any(not ipaddress.ip_address(a).is_global for a in addresses):raise ValueError('non_public_dns')
    except Exception:return [{'url':u,'reason':'dns_unavailable_or_nonpublic','parents':p} for u,p in targets]
    urls=[('https://'+host+'/robots.txt',None)]+targets
    for url,parents in urls:
        item={'url':url,'parents':parents,'requested_at':now()};results.append(item)
        if terminal or time.monotonic()>deadline:item['reason']='host_stopped_or_deadline';continue
        if parents is not None and (policy is None or not policy.can_fetch(url,BOT)):
            item['reason']='robots_unavailable_or_disallowed';continue
        time.sleep(max(0,next_at-time.monotonic()))
        try:
            with requests.get(url,headers={'User-Agent':BOT+'/1.0'},timeout=(7,18),stream=True,allow_redirects=False) as resp:
                item.update(status=resp.status_code,mime=resp.headers.get('Content-Type','').split(';')[0].lower())
                if resp.status_code in (401,403,429) or resp.headers.get('Retry-After'):
                    terminal=True;raise ValueError('http_refusal_or_rate_limit')
                if resp.is_redirect:
                    target=urljoin(url,resp.headers.get('Location',''))
                    item['redirect']=target if safe(target) else 'unreviewed_or_action_target'
                    raise ValueError('redirect_not_followed')
                if parents is None and resp.status_code in (404,410):
                    policy=Protego.parse('User-agent: *\nAllow: /');item['reason']='robots_absent_4xx';continue
                if resp.status_code!=200:raise ValueError('http_not_200')
                raw=bytearray();max_bytes=6_000_000 if item['mime']=='application/pdf' else 2_000_000
                for chunk in resp.iter_content(65536):
                    raw.extend(chunk)
                    if len(raw)>max_bytes:raise ValueError('response_size_bound')
                item['origin_bytes_sha256']=sha(raw);item['bytes']=len(raw)
                if parents is None:
                    text=raw.decode('utf-8',errors='replace')
                    if '<html' in text.lower() or not re.search(r'^\s*User-agent:',text,re.I|re.M):raise ValueError('robots_unreadable')
                    policy=Protego.parse(text);rate=policy.request_rate(BOT)
                    delay=max(5,policy.crawl_delay(BOT) or 0,rate.seconds/rate.requests if rate else 0)
                    if delay>30:terminal=True;raise ValueError('source_delay_bound')
                    saved=bytes(raw);ext='txt'
                elif item['mime']=='application/pdf' and raw.startswith(b'%PDF-'):
                    saved=bytes(raw);ext='pdf';item['reason']='pdf_candidate_not_semantically_validated'
                elif item['mime'] in ('text/html','application/xhtml+xml',''):
                    resp._content=bytes(raw);enc=resp.apparent_encoding
                    saved,title,sample,paragraphs,links=sanitize(bytes(raw),enc,url);ext='html'
                    item.update(title=title,sample=sample,relevant_paragraphs=paragraphs,relevant_links=links,reason='html_candidate_not_semantically_validated')
                else:raise ValueError('unsupported_mime')
                path=sha(url.encode())+'.'+ext;(OUT/path).write_bytes(saved)
                item.update(file=path,saved_sha256=sha(saved))
        except Exception as exc:
            item['reason']=str(exc) if isinstance(exc,ValueError) else type(exc).__name__
        finally:next_at=time.monotonic()+delay;item['finished_at']=now()
    return results

def main():
    entries,excluded=inventory();groups=defaultdict(list)
    for u,p in list(entries.items())[:360]:groups[urlsplit(u).hostname].append((u,p))
    started=now();deadline=time.monotonic()+1000;results=[]
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        futures=[pool.submit(host_read,h,v,deadline) for h,v in groups.items()]
        for f in concurrent.futures.as_completed(futures):results.extend(f.result())
    report={'run_id':os.environ['GITHUB_RUN_ID']+':'+os.environ['GITHUB_RUN_ATTEMPT'],'commit':os.environ['GITHUB_SHA'],
      'started_at':started,'finished_at':now(),'historical_parent_catalogues':True,'parent_catalogue_refreshed':False,
      'publication_performed':False,'source_accounts_used':False,'provider_credits':0,'target_count':len(entries),
      'unattempted_due_to_target_limit':list(entries)[360:],'excluded':excluded,'responses':results}
    (OUT/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
    print(json.dumps({'targets':len(entries),'exclusions':len(excluded),'results':dict(Counter(x.get('reason','policy_read') for x in results))}))

if __name__=='__main__':main()
