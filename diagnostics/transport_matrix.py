"""Bounded public GET diagnostics; no login, proxy, TLS override or credential export."""
import concurrent.futures,json,platform,re
from pathlib import Path
from urllib.parse import urlsplit,urljoin
import requests
from bs4 import BeautifulSoup
TARGETS={
 'ekp':'https://ekp.spb.ru/capabilities/loyalty/',
 'coral':'https://coralbonus.ru/klub-privilegii/',
 'rzd':'https://www.rzd-bonus.ru/?accessible=true',
 'aeroflot':'https://www.aeroflot.ru/ru-ru/afl_bonus/partners',
 'nordwind':'https://nordwindairlines.ru/ru/club/partnerlist',
 'loyals':'https://loyals.ru/',
 'utair':'https://www.utair.ru/support/2/kakiye_partnery_est_u_utair_status'}
OUT=Path('transport-output');OUT.mkdir(exist_ok=True)

def probe(pair):
 name,url=pair;report={'source':name,'platform':platform.system(),'url':url,'reads':[]}
 session=requests.Session();session.headers['User-Agent']='Mozilla/5.0 (compatible; LoyaltyCatalogResearchBot/0.1)'
 for label,target in [('robots',f'https://{urlsplit(url).hostname}/robots.txt'),('page',url)]:
  r={'kind':label}
  try:
   response=session.get(target,timeout=(10,20))
   r.update(status=response.status_code,final_url=response.url,bytes=len(response.content))
   if response.status_code==200 and len(response.content)<6000000:
    soup=BeautifulSoup(response.content,'html.parser')
    r['title']=soup.title.get_text(' ',strip=True) if soup.title else ''
    r['text_prefix']=soup.get_text(' ',strip=True)[:350]
    r['scripts']=[urljoin(response.url,s['src']) for s in soup.select('script[src]') if urlsplit(urljoin(response.url,s['src'])).hostname==urlsplit(url).hostname][:20]
    if label=='robots':(OUT/f'{name}-robots.txt').write_text(response.text,encoding='utf8')
    else:
     for e in soup.select('script,style,noscript,form,input,iframe'):e.decompose()
     for e in soup.find_all(True):
      for key in list(e.attrs):
       if key not in ('class','id','href','title','alt','aria-label','role'):del e.attrs[key]
     (OUT/f'{name}.html').write_text(str(soup),encoding='utf8')
  except Exception as exc:r['error']=type(exc).__name__
  report['reads'].append(r)
 return report

if __name__=='__main__':
 with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:reports=list(executor.map(probe,TARGETS.items()))
 (OUT/'report.json').write_text(json.dumps(reports,ensure_ascii=False,indent=2),encoding='utf8')
 print(json.dumps(reports,ensure_ascii=False))
