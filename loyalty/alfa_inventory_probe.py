"""One-time bounded public discovery; no account, activation or publication."""
from __future__ import annotations
import hashlib,json,re,ssl,tempfile,time
from datetime import datetime,timezone
from pathlib import Path
from urllib.parse import urlsplit,urljoin
import certifi,requests
from bs4 import BeautifulSoup
from protego import Protego
from recovered_contract import CA_FILES

BOT='LoyaltyCatalogResearchBot'
OUT=Path('alfa-inventory-check')
TARGETS=[
 'https://greatlist.ru/spb/alfa-only/',
 'https://greatlist.ru/msk/alfa-only/',
 'https://greatlist.ru/spb/restaurant/mina/',
 'https://greatlist.ru/msk/restaurant/mina-3/',
 'https://alfabank.ru/retail/tariffs/',
 'https://alfabank.ru/actions/rules/',
]

def read(s,url,verify=True,bound=18000000,timeout=25):
    with s.get(url,headers={'User-Agent':BOT+'/1.0'},verify=verify,timeout=(6,timeout),allow_redirects=False,stream=True) as r:
        if r.status_code==429 or r.headers.get('Retry-After'):raise RuntimeError('rate_limited')
        if r.status_code!=200:return r.status_code,b''
        data=bytearray();deadline=time.monotonic()+timeout
        for chunk in r.iter_content(65536):
            data.extend(chunk)
            if len(data)>bound or time.monotonic()>deadline:raise RuntimeError('response_bound')
        return r.status_code,bytes(data)

def main():
    OUT.mkdir(exist_ok=True)
    rows=[];policies={}
    with requests.Session() as s,tempfile.TemporaryDirectory() as td:
        s.trust_env=False
        bank_verify=None
        try:
            u,h=CA_FILES[0];status,ca=read(s,u,bound=16384,timeout=10)
            if status!=200 or hashlib.sha256(ca).hexdigest()!=h:
                raise RuntimeError('official_ca_unavailable_or_changed')
            bank_verify=str(Path(td)/'bank.pem')
            Path(bank_verify).write_bytes(Path(certifi.where()).read_bytes()+b'\n'+ca)
        except Exception:
            # A public mirror is accepted only if the independently pinned DER matches.
            try:
                status,ca=read(s,'https://raw.githubusercontent.com/koenrh/russian-trusted-root-ca/main/root-ca_rsa-2022.pem',bound=16384,timeout=10)
                der=ssl.PEM_cert_to_DER_cert(ca.decode('ascii'))
                if status!=200 or hashlib.sha256(der).hexdigest()!='d26d2d0231b7c39f92cc738512ba54103519e4405d68b5bd703e9788ca8ecf31':
                    raise RuntimeError('root_identity')
                bank_verify=str(Path(td)/'bank.pem')
                Path(bank_verify).write_bytes(Path(certifi.where()).read_bytes()+b'\n'+ca)
            except Exception:pass
        for n,url in enumerate(TARGETS):
            row={'url':url,'observed_at':datetime.now(timezone.utc).isoformat()}
            try:
                host=urlsplit(url).netloc;verify=bank_verify if host=='alfabank.ru' else True
                if not verify:raise RuntimeError('verified_bank_tls_unavailable')
                if host not in policies:
                    status,raw=read(s,'https://'+host+'/robots.txt',verify,bound=500000,timeout=12)
                    if status==200:rules=Protego.parse(raw.decode('utf8','replace'))
                    elif status in (401,403,404,410):rules=Protego.parse('')
                    else:raise RuntimeError('policy_unavailable')
                    policies[host]=(status,rules)
                    (OUT/(host+'-robots.txt')).write_bytes(raw)
                row['robots_status']=policies[host][0]
                if not policies[host][1].can_fetch(url,BOT):raise RuntimeError('robots_disallow')
                s.cookies.clear()
                status,raw=read(s,url,verify)
                row['status']=status
                if status!=200:raise RuntimeError('page_not_200')
                row.update(bytes=len(raw),raw_sha256=hashlib.sha256(raw).hexdigest())
                soup=BeautifulSoup(raw,'html.parser')
                row['title']=soup.title.get_text(' ',strip=True) if soup.title else ''
                row['api_links']=[el.get('href') for el in soup.select('link[rel="https://api.w.org/"]')]
                for el in soup(['script','style','form','iframe','svg']):el.decompose()
                links=[]
                for a in soup.select('a[href]'):
                    u=urljoin(url,a['href']);parsed=urlsplit(u)
                    if parsed.scheme not in ('http','https') or parsed.username or parsed.password:continue
                    if len(u)>1500:continue
                    links.append({'url':u,'label':a.get_text(' ',strip=True)[:600],'class':a.get('class',[])})
                row['links']=links
                row['text']=' '.join(soup.stripped_strings)[:120000]
                # Public guide markup only; no banking HTML or query/cookie/session data saved.
                if host=='greatlist.ru':(OUT/('guide-'+str(n)+'.html')).write_text(str(soup),encoding='utf8')
            except Exception as exc:row['error']=str(exc) if isinstance(exc,RuntimeError) else type(exc).__name__
            rows.append(row)
            print(json.dumps({'url':url,'status':row.get('status'),'error':row.get('error'),'links':len(row.get('links',[]))}),flush=True)
    (OUT/'public_indexes.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2),encoding='utf8')

if __name__=='__main__':main()
