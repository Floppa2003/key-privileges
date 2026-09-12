"""Temporary public-source structure diagnosis. No Google credentials or offer activation."""
import asyncio,json,re
from pathlib import Path
from urllib.parse import urlsplit,urljoin
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright

OUT=Path('finish-browser');OUT.mkdir(exist_ok=True)
def sanitized(raw):
    soup=BeautifulSoup(raw,'html.parser')
    for el in soup.select('script,style,form,input,iframe,noscript'):el.decompose()
    for el in soup.find_all(True):
        for key in list(el.attrs):
            if key not in ('class','id','href','src','alt','title','role','aria-label','aria-selected'):del el.attrs[key]
    return str(soup)

def shape(obj,depth=0):
    if depth>6:return type(obj).__name__
    if isinstance(obj,dict):return {k:shape(v,depth+1) for k,v in obj.items()}
    if isinstance(obj,list):return {'type':'array','count':len(obj),'sample':shape(obj[0],depth+1) if obj else None}
    return type(obj).__name__

async def rgo(browser):
    ctx=await browser.new_context(locale='ru-RU');page=await ctx.new_page();report=[]
    try:
        url='https://rgo.ru/membership/loyalty-program/'
        await page.goto(url,wait_until='domcontentloaded',timeout=30000)
        for _ in range(6):
            btn=page.locator('.pagination-more .btn').first
            if not await btn.count() or not await btn.is_visible():break
            await btn.click();await page.wait_for_timeout(1300)
        links=await page.locator('.loyalty-card__link[href]').evaluate_all('(els)=>els.map(e=>e.href)')
        for link in dict.fromkeys(links):
            if urlsplit(link).hostname!='rgo.ru' or '.pdf' in link:continue
            try:
                resp=await ctx.request.get(link,timeout=25000)
                report.append({'url':link,'status':resp.status})
                if resp.status==200:
                    slug=urlsplit(link).path.rstrip('/').split('/')[-1]
                    (OUT/('rgo-'+slug+'.html')).write_text(sanitized(await resp.text()),encoding='utf8')
            except Exception as e:report.append({'url':link,'error':type(e).__name__})
            await asyncio.sleep(.3)
    finally:await ctx.close()
    (OUT/'rgo-report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')

async def t2(browser):
    ctx=await browser.new_context(locale='ru-RU');page=await ctx.new_page();pending=[];reports=[];n=0
    async def record(resp):
        nonlocal n
        if urlsplit(resp.url).hostname!='msk.t2.ru' or not urlsplit(resp.url).path.startswith('/api/loyalty/'):return
        n+=1;idx=n;entry={'url':resp.url,'status':resp.status,'number':idx}
        try:
            data=await resp.json();entry['shape']=shape(data)
            # This session is anonymous; only explicitly named public offer fields are preserved.
            allow={'id','offerId','name','title','description','shortDescription','fullDescription','longDescription','url','link','category','categories','categoryId','startDate','endDate','expirationDate','partnerName','partner','benefit','conditions','rules','discount','discountDescription','benefitDescription','brand','brandName','image','icon','details','text','code','type','displayName','dateFrom','dateTo','validFrom','validTo'}
            def public(obj):
                if isinstance(obj,list):return [public(x) for x in obj]
                if isinstance(obj,dict):return {k:public(v) for k,v in obj.items() if k in allow or isinstance(v,(dict,list)) and not re.search(r'auth|token|client|user|session|cart|personal',k,re.I)}
                return obj
            (OUT/f't2-public-{idx}.json').write_text(json.dumps(public(data),ensure_ascii=False,indent=2),encoding='utf8')
        except Exception as e:entry['error']=type(e).__name__
        reports.append(entry)
    page.on('response',lambda resp:pending.append(asyncio.create_task(record(resp))))
    try:
        await page.goto('https://msk.t2.ru/bolshe/offers',wait_until='domcontentloaded',timeout=45000)
        await page.wait_for_timeout(12000)
        res=await ctx.request.get('https://msk.t2.ru/robots.txt',timeout=20000)
        (OUT/'t2-robots.txt').write_text(str(res.status)+'\n'+await res.text(),encoding='utf8')
        (OUT/'t2-root.html').write_text(sanitized(await page.content()),encoding='utf8')
        for category in ['Шопинг','Путешествия и транспорт','Отдых','Еда','Кино','Подарки','Культурный гид','Красота и здоровье','Обучение','В вашем регионе']:
            try:
                item=page.get_by_text(category,exact=True).first
                if await item.count():
                    await item.click(timeout=4000);await page.wait_for_timeout(1600)
                    (OUT/('t2-cat-'+str(len(reports))+'.html')).write_text(sanitized(await page.content()),encoding='utf8')
            except Exception:pass
        links=await page.locator('a[href*="/bolshe/offer?"]').evaluate_all('(els)=>els.map(e=>e.href)')
        for idx,link in enumerate(list(dict.fromkeys(links))[:3]):
            if urlsplit(link).hostname!='msk.t2.ru':continue
            await page.goto(link,wait_until='domcontentloaded',timeout=30000);await page.wait_for_timeout(2000)
            (OUT/f't2-detail-{idx}.html').write_text(sanitized(await page.content()),encoding='utf8')
    except Exception as e:reports.append({'phase':'navigation','error':type(e).__name__})
    finally:
        await asyncio.gather(*pending,return_exceptions=True);await ctx.close()
    (OUT/'t2-report.json').write_text(json.dumps(reports,ensure_ascii=False,indent=2),encoding='utf8')

async def main():
    async with async_playwright() as p:
        browser=await p.chromium.launch()
        try:await asyncio.gather(rgo(browser),t2(browser))
        finally:await browser.close()

if __name__=='__main__':asyncio.run(main())
