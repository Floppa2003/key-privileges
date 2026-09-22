"""Bounded anonymous diagnostics; no account controls or provider credits."""
import asyncio, hashlib, json, sys
from pathlib import Path
from datetime import datetime, timezone
from urllib.parse import urlsplit
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright
sys.path.insert(0, "loyalty")
from public_transport import PublicSource
from public_reward_projection import plain

OUT=Path("reliability-probe")
PROMOS=['sportmaster','vseinstrumenti','letual','xcom-shop','randewoo','skysmart','skyeng','skillfactory','leomax','ormatek','contented','platipomiru','bbk']
def excerpt(raw, selectors):
    soup=BeautifulSoup(raw,'html.parser')
    result=BeautifulSoup('<html><head></head><body></body></html>','html.parser')
    if soup.title: result.head.append(soup.title)
    for s in selectors:
        for n in soup.select(s):
            for bad in n.select('script,style,iframe,input,textarea,form'):
                bad.decompose()
            result.body.append(n)
    return str(result)
async def main():
    OUT.mkdir(exist_ok=True)
    rows=[]
    async with async_playwright() as p:
        browser=await p.chromium.launch()
        async with PublicSource(browser,'https://backit.me') as c:
            await c.robots()
            c.request_interval=1
            for slug in PROMOS:
                url='https://backit.me/ru/cashback/shops/'+slug
                try:
                    raw=await c.read(url)
                    data=excerpt(raw,['span.mobile.name','.shop-rates','.shop-conditions','.shop-rules','.mu-auth__login_desktop','#activate-button'])
                    (OUT/(slug+'.html')).write_text(data)
                    rows.append({'url':url,'outcome':'ok','sha256':hashlib.sha256(raw.encode()).hexdigest()})
                except Exception as exc:
                    rows.append({'url':url,'outcome':type(exc).__name__,'reason':str(exc)[:160]})
                    if str(exc) in ('http_401','http_403','access_challenge'): break
            for slug in ('shopsozon','shopswb'):
                url='https://backit.me/ru/cashback/shops/compilation/'+slug
                try:
                    await c.read(url,render=True)
                    await c.page.wait_for_timeout(3000)
                    raw=await c.page.content()
                    data=excerpt(raw,['h1','.offers','.mu-pagination'])
                    (OUT/(slug+'.html')).write_text(data)
                    rows.append({'url':url,'outcome':'ok','sha256':hashlib.sha256(raw.encode()).hexdigest()})
                except Exception as exc:rows.append({'url':url,'outcome':type(exc).__name__,'reason':str(exc)[:160]})
            url='https://backit.me/ru/cashback/shops/ozon/products'
            try:
                await c.read(url,render=True)
                await c.page.wait_for_timeout(3000)
                raw=await c.page.content()
                (OUT/'ozon-products.html').write_text(excerpt(raw,['body']))
                rows.append({'url':url,'outcome':'ok','sha256':hashlib.sha256(raw.encode()).hexdigest()})
            except Exception as exc:rows.append({'url':url,'outcome':type(exc).__name__,'reason':str(exc)[:160]})
        url='https://www.clubavolta.com/ru'
        ctx=await p.request.new_context()
        try:
            r=await ctx.get(url,timeout=20000,max_redirects=0)
            raw=await r.text()
            rows.append({'url':url,'mode':'plain_http','status':r.status,'bytes':len(raw.encode())})
            if r.status==200:(OUT/'avolta-http.html').write_text(excerpt(raw,['main#Main']))
        except Exception as exc:rows.append({'url':url,'mode':'plain_http','outcome':type(exc).__name__})
        finally:await ctx.dispose()
        headed=await p.chromium.launch(headless=False)
        try:
            async with PublicSource(headed,url) as c:
                await c.robots()
                try:
                    raw=await c.read(url,render=True)
                    (OUT/'avolta-browser.html').write_text(excerpt(raw,['main#Main']))
                    rows.append({'url':url,'mode':'headed_browser','status':200,'bytes':len(raw.encode())})
                    d=url+'/nashi-partnery/zaly-ozhidaniya/dragonpass'
                    raw=await c.read(d,render=True)
                    (OUT/'dragonpass.html').write_text(excerpt(raw,['main#Main']))
                    rows.append({'url':d,'mode':'headed_browser','status':200})
                except Exception as exc:rows.append({'url':url,'mode':'headed_browser','outcome':type(exc).__name__,'reason':str(exc)[:160]})
        finally:await headed.close()
        ctx=await p.request.new_context()
        try:
            url='https://lk.manteratravel.ru/app/partners'
            r=await ctx.get(url,timeout=20000,max_redirects=0)
            raw=await r.text()
            rows.append({'url':url,'status':r.status,'redirect_path':urlsplit(r.headers.get('location','')).path})
            if r.status==200:(OUT/'mantera-partners.html').write_text(excerpt(raw,['body']))
        except Exception as exc:rows.append({'url':url,'outcome':type(exc).__name__})
        finally:await ctx.dispose()
        await browser.close()
    (OUT/'results.json').write_text(json.dumps({'observed_at':datetime.now(timezone.utc).isoformat(),'results':rows},ensure_ascii=False,indent=2))
    print(json.dumps(rows,ensure_ascii=False))
if __name__=='__main__':asyncio.run(main())
