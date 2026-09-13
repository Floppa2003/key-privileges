"""Temporary plain-HTML reading of known public rule pages through the existing transport."""
import asyncio,json,hashlib
from pathlib import Path
from datetime import datetime,timezone
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright
from public_transport import PublicSource
URLS=[
'https://www.rendez-vous.ru/aeroflotbonus/',
'https://media.utair.ru/wmiles',
'https://marketplace.s7.ru/city/offer/tsum',
'https://marketplace.s7.ru/city/offer/CozyHome',
'https://marketplace.s7.ru/partners/offer/airo',
'https://www.vtb.ru/privilegia/karty/debetovye/privilegiya-aeroflot/',
'https://vip-zal.ru/aeroflot-bonus.php',
'https://afl.premier.one/',
'https://www.primbank.ru/d/tariffs-aeroflot-bonus',
'https://www.nspk.ru/press-center/details/00d06ff9-ac6f-41fd-9aad-39965b9762cd']
OUT=Path('known-review')
async def read(browser,url,sem):
 async with sem:
  report={'url':url,'method':'existing_transport_plain_html','observed_at':datetime.now(timezone.utc).isoformat()}
  try:
   async with asyncio.timeout(75):
    async with PublicSource(browser,url) as c:
     await c.robots();report['robots']=c.robots_info
     raw=await c.read(url)
     soup=BeautifulSoup(raw,'html.parser')
     report['title']=soup.title.get_text(' ',strip=True) if soup.title else ''
     for n in soup.select('script,style,form,input,textarea'):n.decompose()
     body=soup.body or soup;name=hashlib.sha256(url.encode()).hexdigest()[:16]+'.html'
     (OUT/name).write_text(str(body),encoding='utf8')
     report.update(status='read',html_file=name,text_length=len(body.get_text()))
  except Exception as exc:report.update(status='failed',reason=str(exc)[:180] if isinstance(exc,RuntimeError) else type(exc).__name__)
  print(json.dumps(report,ensure_ascii=False),flush=True);return report
async def main():
 OUT.mkdir(exist_ok=True)
 async with async_playwright() as p:
  browser=await p.chromium.launch()
  try:reports=await asyncio.gather(*(read(browser,u,asyncio.Semaphore(1)) for u in URLS))
  finally:await browser.close()
 (OUT/'report.json').write_text(json.dumps(reports,ensure_ascii=False,indent=2),encoding='utf8')
if __name__=='__main__':asyncio.run(main())
