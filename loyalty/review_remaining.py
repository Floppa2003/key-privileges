"""Bounded anonymous diagnostics; no credentials, private state or access workarounds."""
import asyncio
import json
from pathlib import Path
from urllib.parse import urlsplit
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright
from public_transport import PublicSource

TARGETS = [
 ('ekp_channel','https://t.me/s/ekpcard'),
 ('rzd_channel','https://t.me/s/fpcrussia'),
 ('ekp_www','https://www.ekp.spb.ru/capabilities/loyalty/'),
 ('coral_www','https://www.coralbonus.ru/klub-privilegii/'),
 ('rzd_canonical','https://rzd-bonus.ru/'),
 ('nordwind_www','https://www.nordwindairlines.ru/ru/club/partnerlist'),
]
OUT=Path('review-output')
async def probe(browser,key,url,sem):
 async with sem:
  report={'id':key,'url':url}
  try:
   async with asyncio.timeout(75):
    async with PublicSource(browser,url) as source:
     await source.robots()
     html=await source.read(url,render=True)
     soup=BeautifulSoup(html,'html.parser')
     report['title']=soup.title.get_text(' ',strip=True) if soup.title else ''
     report['links']=[{'text':a.get_text(' ',strip=True),'url':a.get('href')} for a in soup.select('a[href]') if a.get_text(' ',strip=True)][:300]
     report['script_paths']=[s.get('src') for s in soup.select('script[src]')][:30]
     for n in soup.select('script,style,form,input,textarea'):n.decompose()
     main=soup.select_one('.tgme_channel_history,main') or soup.body or soup
     (OUT/f'{key}.html').write_text(str(main),encoding='utf8')
     report['text_size']=len(main.get_text(' ',strip=True))
     report['status']='read'
  except Exception as exc:
   report['status']='failed'
   report['error']=str(exc) if isinstance(exc,RuntimeError) else type(exc).__name__
  print(json.dumps(report,ensure_ascii=False),flush=True)
  return report
async def main():
 OUT.mkdir(exist_ok=True)
 async with async_playwright() as p:
  browser=await p.chromium.launch()
  try:reports=await asyncio.gather(*(probe(browser,k,u,asyncio.Semaphore(1)) for k,u in TARGETS))
  finally:await browser.close()
 (OUT/'remaining.json').write_text(json.dumps(reports,ensure_ascii=False,indent=2),encoding='utf8')
if __name__=='__main__':asyncio.run(main())
