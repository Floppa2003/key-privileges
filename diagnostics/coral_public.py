"""Read public Coral pages on a standard Windows runner. No auth or action endpoints."""
import json,time,re
from pathlib import Path
from urllib.parse import urlsplit,urljoin
import requests
from bs4 import BeautifulSoup
from protego import Protego
ROOT='https://coralbonus.ru'
PATHS=['/klub-privilegii/zdorov-e/','/klub-privilegii/avtomobili/','/klub-privilegii/zdorov-e/medsi/','/klub-privilegii/avtomobili/sitidraiv/','/klub-privilegii/nedvizhimost/unistroi/','/promo/','/sitemap/']
OUT=Path('coral-inspection');OUT.mkdir(exist_ok=True)
s=requests.Session();s.headers['User-Agent']='Mozilla/5.0 (compatible; LoyaltyCatalogResearchBot/0.1)'
def main():
 reports=[]
 r=s.get(ROOT+'/robots.txt',timeout=(10,20));r.raise_for_status()
 if '<html' in r.text.lower():raise RuntimeError('robots_not_plain_text')
 policy=Protego.parse(r.text)
 for index,path in enumerate(PATHS):
  url=ROOT+path;report={'url':url}
  try:
   if not policy.can_fetch(url,'LoyaltyCatalogResearchBot'):raise RuntimeError('robots_disallow')
   time.sleep(1);response=s.get(url,timeout=(10,25));report['status']=response.status_code
   response.raise_for_status()
   soup=BeautifulSoup(response.content,'html.parser')
   report['title']=soup.title.get_text(' ',strip=True) if soup.title else ''
   report['links']=list(dict.fromkeys(urljoin(response.url,e['href']) for e in soup.select('a[href]') if urlsplit(urljoin(response.url,e['href'])).hostname=='coralbonus.ru'))
   report['script_src']=[e['src'] for e in soup.select('script[src]')]
   report['embedded_arrays']=[e.get('type') for e in soup.select('script:not([src])')]
   for e in soup.select('script,style,noscript,form,input,iframe'):e.decompose()
   for e in soup.find_all(True):
    for key in list(e.attrs):
     if key not in ('id','class','href','title','alt','data-id','data-url','ng-repeat','ng-init','ng-bind-html'):del e.attrs[key]
   (OUT/f'page-{index}.html').write_text(str(soup),encoding='utf8')
   report['file']=f'page-{index}.html'
  except Exception as exc:report['error']=type(exc).__name__
  reports.append(report)
 (OUT/'report.json').write_text(json.dumps(reports,ensure_ascii=False,indent=2),encoding='utf8')
 print(json.dumps(reports,ensure_ascii=True))
if __name__=='__main__':main()
