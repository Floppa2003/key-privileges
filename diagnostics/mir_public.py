"""Temporary anonymous Mir UI inspection. No internal API replay or credentials."""
import asyncio,json
from pathlib import Path
from urllib.parse import urlsplit
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright
import sys
sys.path.insert(0,'loyalty')
from public_transport import PublicSource
OUT=Path('mir-ui-probe');OUT.mkdir(exist_ok=True)

def sanitize(raw):
 s=BeautifulSoup(raw,'html.parser')
 for e in s.select('script,style,input,form,iframe,noscript'):e.decompose()
 for e in s.find_all(True):
  for k in list(e.attrs):
   if k not in ('class','id','href','type','aria-label','role','data-page','disabled'):del e.attrs[k]
 return str(s)

async def main():
 async with async_playwright() as p:
  b=await p.chromium.launch();report=[];tasks=[];n=0
  async with PublicSource(b,'https://vamprivet.ru/promo/') as client:
   await client.robots()
   async def capture(resp):
    nonlocal n
    if urlsplit(resp.url).hostname!='vamprivet.ru' or resp.status!=200 or resp.request.resource_type not in ('xhr','fetch'):return
    try:
     obj=await resp.json();public=None
     if urlsplit(resp.url).path.endswith('/promo/filter-json'):
      data=obj.get('data',{});public={'success':obj.get('success'),'data':{k:data.get(k) for k in ('items','pagination','counter','pageTitle')}}
     elif '/api/configs/client' in urlsplit(resp.url).path:
      detail=obj.get('data',{}).get('content',{}).get('promoDetail',{}).get('promo',{}).get('promoAction')
      if detail:
       public={'promoAction':{k:detail.get(k) for k in ('xml_id','url','name','owner','templates','desc','short_desc','startDate','endDate','promoBadges','freeFormBlock','promoIsCancelled','promoIsFinished','promoIsStarted','status','perPromoActionLimit','clientTimeLimit','prizeIsSuspended')}}
     if public:
      n+=1;(OUT/f'public-{n}.json').write_text(json.dumps(public,ensure_ascii=False,indent=2),encoding='utf8')
      report.append({'response':n,'path':urlsplit(resp.url).path})
    except Exception:pass
   client.page.on('response',lambda r:tasks.append(asyncio.create_task(capture(r))))
   for key,url in [('catalog','https://vamprivet.ru/promo/'),('detail','https://vamprivet.ru/promo/produkty-pitaniya/rybnye-delikatesy-ikra-i-moreprodukty-3/')]:
    try:
     await client.read(url,render=True);await client.page.wait_for_timeout(2000)
     (OUT/(key+'.html')).write_text(sanitize(await client.page.content()),encoding='utf8')
     report.append({'page':key,'url':client.page.url,'title':await client.page.title(),'request_interval':client.request_interval})
     if key=='catalog':
      for selector in ['.pagination','[class*="pagination"]','button']:
       els=await client.page.locator(selector).all_inner_texts();report.append({'selector':selector,'texts':els[:30]})
    except Exception as e:report.append({'page':key,'error':str(e)[:120] if isinstance(e,RuntimeError) else type(e).__name__})
   await asyncio.gather(*tasks,return_exceptions=True)
  await b.close()
 (OUT/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
 print(json.dumps(report,ensure_ascii=False))
if __name__=='__main__':asyncio.run(main())
