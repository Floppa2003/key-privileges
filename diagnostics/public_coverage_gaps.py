"""Resolve exact public coverage gaps. Read-only; no redirects into accounts."""
from datetime import datetime, timezone
import hashlib, json, time
from pathlib import Path
from urllib.parse import urlsplit, urljoin
import requests
from bs4 import BeautifulSoup
OUT=Path('reliability-probe');OUT.mkdir(exist_ok=True)
URLS={
 'mantera-landing':'https://manteratravel.ru/mantera-moments-loyalty-program',
 'mantera-congress':'https://manteracongress.ru/loyalty-program',
 'ozon-compilation':'https://backit.me/ru/cashback/shops/compilation/shopsozon',
 'wb-compilation':'https://backit.me/ru/cashback/shops/compilation/shopswb',
 'mixit-ozon':'https://backit.me/ru/cashback/shops/mixit-ozon',
 'roborock-ozon':'https://backit.me/ru/cashback/shops/roborock-ozon',
 'avolta-root':'https://www.clubavolta.com/ru',
}
reports=[]
for name,url in URLS.items():
    time.sleep(1)
    row={'url':url,'observed_at':datetime.now(timezone.utc).isoformat()}
    try:
        r=requests.get(url,timeout=(8,25),allow_redirects=False)
        row['status']=r.status_code
        row['sha256']=hashlib.sha256(r.content).hexdigest()
        if r.is_redirect:
            to=urljoin(url,r.headers.get('Location',''))
            row['redirect_origin']=urlsplit(to).scheme+'://'+urlsplit(to).netloc
            row['redirect_path']=urlsplit(to).path
        if r.status_code==200 and len(r.content)<2000000:
            s=BeautifulSoup(r.content,'html.parser')
            row['title']=s.title.get_text(' ',strip=True) if s.title else ''
            row['links']=[{'text':a.get_text(' ',strip=True),'url':urljoin(url,a['href'])} for a in s.select('a[href]') if a.get('href','').startswith(('https://','/')) and 'auth' not in a['href'] and not urlsplit(urljoin(url,a['href'])).query]
            row['images']=[{'alt':x.get('alt',''),'src':x.get('src','')} for x in s.select('img')]
            for bad in s.select('script,style,iframe,input,textarea,form'):
                bad.decompose()
            (OUT/(name+'.html')).write_text(str(s))
        reports.append(row)
    except requests.RequestException as e:
        row['error']=type(e).__name__;reports.append(row)
(OUT/'gaps.json').write_text(json.dumps(reports,ensure_ascii=False,indent=2))
print(json.dumps([{k:v for k,v in r.items() if k not in ('links','images')} for r in reports],ensure_ascii=False))
