"""One-shot public HTML structure probe; no account or destination writes."""
import hashlib,json,re,time
from datetime import datetime,timezone
from pathlib import Path
from urllib.parse import urljoin,urlsplit,urlunsplit
import requests
from bs4 import BeautifulSoup
from protego import Protego
from public_transport import robots_document,check_response

ROOT='https://greatlist.ru';BOT='LoyaltyCatalogResearchBot'
out=Path('discovery');out.mkdir(exist_ok=True)
report={'observed_at':datetime.now(timezone.utc).isoformat(),'pages':[],'cities':[],'catalogues':[],'details':[]}
s=requests.Session();s.trust_env=False;s.headers['User-Agent']=BOT+'/1.0'
def canonical(u):
    p=urlsplit(u)
    if p.scheme!='https' or p.netloc!='greatlist.ru' or p.query:raise ValueError('outside_origin')
    return urlunsplit((p.scheme,p.netloc,p.path,'',''))
def get(u,policy=None):
    u=canonical(u)
    if policy is not None and not policy.can_fetch(u,BOT):raise RuntimeError('robots_disallow')
    time.sleep(0.5)
    with s.get(u,timeout=(8,30),allow_redirects=False,stream=True) as r:
        if r.status_code==429 or r.headers.get('Retry-After'):raise RuntimeError('rate_limited')
        raw=bytearray()
        for b in r.iter_content(65536):
            raw.extend(b)
            if len(raw)>12000000:raise RuntimeError('size_bound')
        body=bytes(raw).decode('utf8','replace')
        if policy is None:return r.status_code,body
        check_response(r.status_code,body)
        name=hashlib.sha256(u.encode()).hexdigest()[:16]+'.html'
        (out/name).write_text(body)
        soup=BeautifulSoup(body,'html.parser')
        report['pages'].append({'url':u,'status':r.status_code,'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest(),'file':name})
        return soup
try:
    status,raw=get(ROOT+'/robots.txt');rules,state=robots_document(status,raw);policy=Protego.parse(rules)
    report['robots']={'status':status,'state':state};(out/'robots.txt').write_text(rules)
    seed=get(ROOT+'/spb/alfa-only/',policy)
    cities={}
    for a in seed.select('a[href]'):
        try:u=canonical(urljoin(ROOT,a['href']))
        except ValueError:continue
        if re.fullmatch(r'/(msk|spb|ekb|kzn|nn|dlv)/',urlsplit(u).path):cities[u]=a.get_text(' ',strip=True)
    if len(cities)>10:raise ValueError('city_bound')
    for city,label in cities.items():
        item={'url':city,'name':label}
        try:
            soup=get(city,policy)
            alfas={canonical(urljoin(city,a['href'])) for a in soup.select('a[data-id="alfa-only"][href]')}
            if len(alfas)!=1:raise ValueError('alfa_tab_not_unique')
            url=alfas.pop();soup=seed if url==ROOT+'/spb/alfa-only/' else get(url,policy)
            cards={}
            for a in soup.select('a.place_card[href][data-objectid]'):
                u=canonical(urljoin(url,a['href']));name=a.select_one('.h2')
                if not name:raise ValueError('card_name_missing')
                cards[a['data-objectid']]={'id':a['data-objectid'],'url':u,'name':name.get_text(' ',strip=True)}
            item.update(catalogue=url,cards=list(cards.values()))
            report['catalogues'].append(item)
        except Exception as e:item['error']=str(e) if isinstance(e,(ValueError,RuntimeError)) else type(e).__name__
        report['cities'].append(item)
    chosen=[]
    for cat in report['catalogues']:
        chosen.extend(cat.get('cards',[])[:1])
    chosen.append({'url':ROOT+'/spb/restaurant/fresas/','name':'FRESA'})
    for entry in chosen[:7]:
        item=dict(entry)
        try:
            soup=get(item['url'],policy)
            for el in soup(['script','style','form']):el.decompose()
            txt=soup.get_text(' ',strip=True)
            item.update(title=soup.title.get_text(' ',strip=True) if soup.title else '',text=txt[:45000],blocks=[str(el.parent)[:25000] for el in soup.find_all(string=re.compile(r'к[еэ]шб[еэ]к|привилеги|Alfa Only',re.I))][:30])
        except Exception as e:item['error']=str(e) if isinstance(e,(ValueError,RuntimeError)) else type(e).__name__
        report['details'].append(item)
except Exception as e:report['error']=str(e) if isinstance(e,(ValueError,RuntimeError)) else type(e).__name__
finally:
    (out/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
    print(json.dumps({'catalogues':[(x['name'],len(x.get('cards',[])),x.get('error')) for x in report['cities']],'details':[(x['url'],x.get('error')) for x in report['details']],'error':report.get('error')},ensure_ascii=False))
