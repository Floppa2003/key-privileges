"""Temporary read-only browser diagnosis; no logins, clicks, or challenge solving."""
import asyncio,json
from pathlib import Path
from urllib.parse import urlsplit
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright

OUT=Path('finish-browser');OUT.mkdir(exist_ok=True)
TARGETS={
 't2':'https://msk.t2.ru/bolshe/offers',
 'coral':'https://coralbonus.ru/klub-privilegii/',
 'ekp':'https://ekp.spb.ru/capabilities/loyalty/',
 'nordwind':'https://nordwindairlines.ru/ru/club/partnerlist',
 'domina':'https://dominapulkovo.ru/nordwind',
 'rgo':'https://rgo.ru/membership/loyalty-program/',
 'moskvich':'https://moskvichmag.ru/programma-loyalnosti/'}

async def probe(browser,key,url,sem):
  async with sem:
    report={'id':key,'url':url,'documents':[],'api_requests':[]}
    context=await browser.new_context(locale='ru-RU');page=await context.new_page()
    def on_response(resp):
      if resp.request.is_navigation_request() and resp.request.frame==page.main_frame:
        report['documents'].append({'url':resp.url,'status':resp.status})
      elif resp.request.resource_type in ('fetch','xhr') and urlsplit(resp.url).hostname==urlsplit(url).hostname:
        path=urlsplit(resp.url).path
        if path not in report['api_requests'] and len(report['api_requests'])<40:report['api_requests'].append(path)
    page.on('response',on_response)
    try:
      await page.goto(url,wait_until='domcontentloaded',timeout=45000)
      # Allow ordinary source JavaScript to settle. No interaction or response to human checks.
      await page.wait_for_timeout(12000)
      report['final_url']=page.url;report['title']=await page.title()
      raw=await page.content();soup=BeautifulSoup(raw,'html.parser')
      report['lead_text']=soup.get_text(' ',strip=True)[:650]
      report['script_urls']=[x.get('src') for x in soup.select('script[src]')]
      for x in soup.select('script,style,form,input,iframe,noscript'):x.decompose()
      for x in soup.find_all(True):
        for attr in list(x.attrs):
          if attr not in ('class','id','href','src','alt','title'):del x.attrs[attr]
      (OUT/f'{key}.html').write_text(str(soup),encoding='utf8')
    except Exception as e:report['error']=type(e).__name__
    finally:await context.close()
    print(json.dumps(report,ensure_ascii=False),flush=True)
    return report

async def main():
  async with async_playwright() as p:
    browser=await p.chromium.launch();sem=asyncio.Semaphore(3)
    try:reports=await asyncio.gather(*(probe(browser,k,u,sem) for k,u in TARGETS.items()))
    finally:await browser.close()
  (OUT/'report.json').write_text(json.dumps(reports,ensure_ascii=False,indent=2),encoding='utf8')

if __name__=='__main__':asyncio.run(main())
