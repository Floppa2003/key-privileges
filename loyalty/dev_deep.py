"""Bounded follow-up inspection of public catalog transports."""
import asyncio
import json
from pathlib import Path
from urllib.parse import urlsplit
from urllib.robotparser import RobotFileParser
from playwright.async_api import async_playwright
from dev_probe import clean_html, safe_json

ROOTS = {
 'mir_catalog':'https://vamprivet.ru/promo/',
 'mir_detail':'https://vamprivet.ru/promo/transport/ekspress-v-aeroport-s-vygodoy-i-komfortom-1/',
 'rgo_full':'https://rgo.ru/membership/loyalty-program/',
 'ekp_medi':'https://medi.spb.ru/medi/spetspredlozheniya/partnerskie-programmy/ekp/',
 'ekp_neva':'https://neva.travel/ru/promotions/skidka-dlya-derzhateley-edinoy-karty-peterburzhtsa/',
 'mir_neva':'https://neva.travel/ru/promotions/kesbek-10-pri-oplate-kartoi-mir/',
 'ural_ajax':'https://www.uralairlines.ru/partners/?ajax=partners&action=default',
}

async def one(browser,key,url,out,sem):
 async with sem:
  context=await browser.new_context(locale='ru-RU');page=await context.new_page()
  report={'id':key,'url':url,'network':[],'status':'failed'};tasks=[]
  async def capture(resp):
   try:
    u=urlsplit(resp.url)
    if u.hostname!=urlsplit(url).hostname or resp.request.resource_type not in ('xhr','fetch'):return
    if len(report['network'])>=80:return
    index=len(report['network'])+1
    item={'path':u.path,'query':u.query if not any(k in u.query.lower() for k in ('token','session','qsess','password','secret','csrf')) else '[redacted]','status':resp.status,'method':resp.request.method}
    report['network'].append(item)
    kind=resp.headers.get('content-type','')
    if resp.status==200 and ('json' in kind or 'html' in kind) and not any(k in u.path.lower() for k in ('auth','login','session','profile')):
     body=await resp.body()
     if len(body)>3000000:return
     ext='json' if 'json' in kind else 'html';name=f'{key}-response-{index}.{ext}'
     text=json.dumps(safe_json(json.loads(body)),ensure_ascii=False) if ext=='json' else clean_html(body.decode('utf8'))
     (out/name).write_text(text,encoding='utf8');item['file']=name
   except Exception:pass
  page.on('response',lambda r:tasks.append(asyncio.create_task(capture(r))))
  try:
   r=await context.request.get('https://'+urlsplit(url).hostname+'/robots.txt',timeout=30000)
   report['robots_status']=r.status;policy=RobotFileParser()
   if r.status==200:policy.parse((await r.text()).splitlines())
   elif r.status==404:policy.parse([])
   else:raise RuntimeError('robots_http_'+str(r.status))
   if not policy.can_fetch('LoyaltyCatalogResearchBot',url):raise RuntimeError('robots_disallow')
   r=await page.goto(url,wait_until='domcontentloaded',timeout=45000)
   await page.wait_for_timeout(3000);report['page_status']=r.status if r else None
   if not r or r.status>=400:raise RuntimeError('page_http_error')
   if key=='rgo_full':
    counts=[]
    for _ in range(40):
     count=await page.locator('.loyalty-card').count();counts.append(count)
     more=page.locator('.pagination-more .btn').first
     if not await more.count() or not await more.is_visible():break
     await more.click(timeout=5000);await page.wait_for_timeout(2000)
     if await page.locator('.loyalty-card').count()==count:break
    report['card_counts']=counts
   (out/f'{key}.html').write_text(clean_html(await page.content()),encoding='utf8')
   (out/f'{key}.txt').write_text(await page.locator('body').inner_text(),encoding='utf8')
   report['status']='read'
  except Exception as exc:
   report['error_type']=type(exc).__name__;report['reason']=str(exc)[:180] if isinstance(exc,RuntimeError) else 'network_or_browser_error'
  finally:
   if tasks:await asyncio.gather(*tasks,return_exceptions=True)
   await context.close()
  (out/f'{key}-report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
  print(key,report['status'],report.get('card_counts',report.get('reason','')),flush=True)

async def main():
 out=Path('source-inspection');out.mkdir(exist_ok=True)
 async with async_playwright() as p:
  browser=await p.chromium.launch();sem=asyncio.Semaphore(3)
  await asyncio.gather(*(one(browser,k,v,out,sem) for k,v in ROOTS.items()))
  await browser.close()
if __name__=='__main__':asyncio.run(main())
