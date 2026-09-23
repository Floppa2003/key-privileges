"""Read only six known rejected anonymous cards; no account or activation."""
import asyncio,json,sys
from pathlib import Path
from datetime import datetime,timezone
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright
sys.path.insert(0,'loyalty')
from public_transport import PublicSource
from magnit_policy import QuerylessMagnitPolicy
from magnit_partners import inventory,public_data,detail
from expansion_common import next_store,sha
from public_reward_projection import plain
OUT=Path('catalogue-remaining-shapes');OUT.mkdir(exist_ok=True)
def save(name,data):
 (OUT/(name+'.json')).write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf8')
async def main():
 async with async_playwright() as p:
  b=await p.chromium.launch()
  try:
   async with PublicSource(b,'https://magnit.ru/partners') as c:
    await c.robots();c.policy=QuerylessMagnitPolicy(c.robots_rules)
    await c.read('https://magnit.ru/partners',render=True)
    await c.page.locator('.card').first.wait_for(state='attached',timeout=12000)
    raw=await c.page.content();cards,categories=inventory(raw)
    for i in ('1752','1758','1773','1777'):
     try:
      await c.read('https://magnit.ru/partners/'+i,render=True)
      await c.page.locator('h1.partners-detail-page__title').wait_for(state='attached',timeout=12000)
      raw=await c.page.content();data=public_data(raw,'partners-detail:'+i);s=BeautifulSoup(raw,'html.parser')
      selected={k:data.get(k)for k in ('id','title','partner','content','steps','categories')}
      result={'catalogue_card':cards[i],'detail':selected,'categories':categories,'dom_title':plain(s.select_one('h1.partners-detail-page__title')),'disclaimer':[plain(n)for n in s.select('.partners-detail-page__disclaimer')],'sha256':sha(raw),'observed_at':datetime.now(timezone.utc).isoformat()}
      try:detail(raw,cards[i],categories,result['observed_at']);result['parsed']=True
      except Exception as exc:result['error']=type(exc).__name__+':'+str(exc)[:100]
      save('magnit-'+i,result)
     except Exception as exc:save('magnit-'+i,{'error':type(exc).__name__+':'+str(exc)[:100]})
   async with PublicSource(b,'https://gorodtroika.ru/bonus-plus/coupons') as c:
    await c.robots()
    for i in ('19607','19610'):
     raw=await c.read('https://gorodtroika.ru/bonus-plus/coupons/'+i)
     d=next_store(raw,'couponViewStore')['couponData']
     safe={k:d.get(k)for k in ('id','name','available','price','terms','endAt','couponEndAt','countdown','howToAsList','cashback','message','address')}
     safe['partner']={k:d.get('partner',{}).get(k)for k in ('id','name','subtitle','available')}
     save('gorod-coupon-'+i,{'data':safe,'public_main_text':plain(BeautifulSoup(raw,'html.parser').select_one('main')),'sha256':sha(raw),'observed_at':datetime.now(timezone.utc).isoformat()})
  finally:await b.close()
asyncio.run(main())
