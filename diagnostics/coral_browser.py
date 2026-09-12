"""Temporary public browser read, preserving only reviewed page evidence."""
import asyncio,json,sys
from pathlib import Path
from urllib.parse import urljoin,urlsplit
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright
sys.path.insert(0,'loyalty')
from public_transport import PublicSource
OUT=Path('coral-inspection');OUT.mkdir(exist_ok=True)
PATHS=['/klub-privilegii/zdorov-e/','/klub-privilegii/avtomobili/','/klub-privilegii/zdorov-e/medsi/','/klub-privilegii/avtomobili/sitidraiv/','/klub-privilegii/nedvizhimost/unistroi/','/promo/','/sitemap/']
async def main():
 reports=[]
 async with async_playwright() as p:
  browser=await p.chromium.launch()
  async with PublicSource(browser,'https://coralbonus.ru/') as client:
   try:
    await client.robots()
    for index,path in enumerate(PATHS):
     report={'url':'https://coralbonus.ru'+path}
     try:
      raw=await client.read(report['url'],render=True)
      soup=BeautifulSoup(raw,'html.parser')
      report['title']=soup.title.get_text(' ',strip=True) if soup.title else ''
      report['links']=list(dict.fromkeys(urljoin(report['url'],e['href']) for e in soup.select('a[href]') if urlsplit(urljoin(report['url'],e['href'])).hostname==client.host))
      for e in soup.select('script,style,noscript,input,form,iframe'):e.decompose()
      for e in soup.find_all(True):
       for k in list(e.attrs):
        if k not in ('id','class','href','title','alt','data-id','data-url','ng-repeat','ng-init','ng-bind-html'):del e.attrs[k]
      (OUT/f'page-{index}.html').write_text(str(soup),encoding='utf8')
      report['file']=f'page-{index}.html'
     except Exception as exc:report['error']=str(exc) if isinstance(exc,RuntimeError) else type(exc).__name__
     reports.append(report)
   except Exception as exc:reports.append({'phase':'robots','error':str(exc) if isinstance(exc,RuntimeError) else type(exc).__name__})
  await browser.close()
 (OUT/'browser-report.json').write_text(json.dumps(reports,ensure_ascii=False,indent=2),encoding='utf8')
 print(json.dumps(reports,ensure_ascii=True))
if __name__=='__main__':asyncio.run(main())
