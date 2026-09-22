"""Read source-discovered catalogue routes only; no coupon actions or sign-in."""
import asyncio, json, hashlib, re
from pathlib import Path
from urllib.parse import urlsplit
from playwright.async_api import async_playwright
import public_coverage_closure as base

OUT=Path('coverage-pagination-contracts');OUT.mkdir(exist_ok=True);base.OUT=OUT

def save(name,value):
 (OUT/(name+'.json')).write_text(json.dumps(base.clean_json(value),ensure_ascii=False,indent=2),encoding='utf8')

async def main():
 outcomes=[]
 async with async_playwright() as p:
  browser=await p.chromium.launch()
  context=await browser.new_context();page=await context.new_page()
  for index in (0,3,4,5):
   url=f'https://x5club.ru/partners.data?page={index}&_routes=routes%2F_unauth.partners._index'
   try:
    r=await context.request.get(url,timeout=25000);raw=await r.text()
    # This is the anonymous route loader; no root/session loader is requested.
    if re.search(r'"(?:access_token|refresh_token|csrf|password)"\s*:',raw,re.I):raise RuntimeError('sensitive_route_field')
    if len(raw)>2000000:raise RuntimeError('response_too_large')
    (OUT/f'x5-page-{index}.txt').write_text(raw,encoding='utf8')
    outcomes.append({'source':'x5','page':index,'status':r.status,'url':url,'sha256':hashlib.sha256(raw.encode()).hexdigest()})
   except Exception as exc:outcomes.append({'source':'x5','page':index,'error':type(exc).__name__})
   await asyncio.sleep(.5)
  responses=[];tasks=[]
  async def capture(res):
   try:
    u=urlsplit(res.url)
    if u.hostname!='gorodtroika.ru' or res.request.method!='GET' or res.status!=200:return
    if not u.path.startswith('/api/bonus_plus/'):return
    if 'application/json' not in res.headers.get('content-type',''):return
    value=await res.json();responses.append({'url':base.clean_url(res.url),'data':base.clean_json(value)})
   except Exception:pass
  page.on('response',lambda r:tasks.append(asyncio.create_task(capture(r))))
  for path in ['/partners/3515','/partners/359','/bonus-plus/cashback']:
   url='https://gorodtroika.ru'+path
   try:
    r=await page.goto(url,wait_until='domcontentloaded',timeout=25000);await page.wait_for_timeout(1500)
    if path.endswith('cashback'):
     button=page.locator('button[data-id="12"]').filter(has_text='Все')
     await button.click(timeout=8000);await page.wait_for_timeout(1800)
     await page.evaluate('window.scrollTo(0,document.body.scrollHeight)');await page.wait_for_timeout(1500)
    else:
     await page.evaluate('window.scrollTo(0,document.body.scrollHeight)');await page.wait_for_timeout(1500)
    outcomes.append(base.save_html('gorod-'+path.rsplit('/',1)[-1],await page.content(),'page',page.url,r.status))
   except Exception as exc:outcomes.append({'source':'gorod','path':path,'error':type(exc).__name__})
  if tasks:await asyncio.gather(*tasks,return_exceptions=True)
  save('gorod-network',responses)
  for name,url in [('gorod-other-region','https://gorodtroika.ru/api/bonus_plus/coupons/partners?limit=10&region_id=4'),('gorod-all-regions','https://gorodtroika.ru/api/system/regions?region_id=1')]:
   try:
    r=await context.request.get(url,timeout=20000);save(name,{'url':url,'status':r.status,'data':await r.json()})
   except Exception as exc:outcomes.append({'source':name,'error':type(exc).__name__})
  for name,url in [('gorod','https://gorodtroika.ru/robots.txt'),('x5','https://x5club.ru/robots.txt'),('magnit','https://magnit.ru/robots.txt'),('tsvetnoy','https://tsvetnoy.com/robots.txt')]:
   try:
    r=await context.request.get(url,timeout=12000);raw=await r.text();save(name+'-robots',{'url':url,'status':r.status,'text':raw[:50000]})
   except Exception as exc:outcomes.append({'source':name+'-robots','error':type(exc).__name__})
  await context.close();await browser.close()
 save('outcomes',outcomes);print(json.dumps(outcomes,ensure_ascii=False))
if __name__=='__main__':asyncio.run(main())
