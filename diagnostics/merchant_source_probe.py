"""Read-only target discovery; no direct catalogue API or model calls."""
import asyncio
import json
import sys
from pathlib import Path
from urllib.parse import urlsplit
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'loyalty'))
from konsierge_source import allowed_read, public_item, API_HOST
from playwright.async_api import async_playwright
NAMES=['Memo','Hide','El Copitas Bar','Po’mestam']

async def main():
    out=Path('source-probe');out.mkdir(exist_ok=True)
    data=json.loads(Path('probe-input/normalized.json').read_text())
    rows=[r for r in data['records'] if r.get('source_id')=='konsierge_public' and r.get('partner_name') in NAMES]
    (out/'catalogue-records.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2))
    wanted={int(r['native_id']) for r in rows};native={};pending=set();errors=[];network=[];cards=[]
    async with async_playwright() as pw:
        browser=await pw.chromium.launch(headless=True)
        context=await browser.new_context(locale='ru-RU',viewport={'width':1024,'height':1024},service_workers='block')
        async def route(r):
            if allowed_read(r.request.method,r.request.url):await r.continue_()
            else:await r.abort()
        await context.route('**/*',route)
        page=await context.new_page()
        async def read(res):
            try:
                network.append({'path':urlsplit(res.url).path,'status':res.status})
                if res.status!=200:return
                d=await res.json();network[-1].update(page=d.get('page'),ids=[i.get('id') for i in d.get('result',[])])
                for item in d.get('result',[]):
                    if item.get('id') in wanted:native[item['id']]=public_item(item)
            except Exception as exc:errors.append(type(exc).__name__)
        def enqueue(res):
            u=urlsplit(res.url)
            if u.netloc==API_HOST and u.path=='/api/client/v1/benefits':
                t=asyncio.create_task(read(res));pending.add(t);t.add_done_callback(pending.discard)
        page.on('response',enqueue)
        urls=list(dict.fromkeys(c['url'] for r in rows for c in r['details'].get('public_categories',[])))
        for url in urls:
            await page.goto(url,wait_until='domcontentloaded',timeout=30000)
            await page.wait_for_selector('qy-benefit-teaser',timeout=20000)
            await page.wait_for_timeout(1000)
            print('SCROLLERS',await page.evaluate('Array.from(document.querySelectorAll("*")).filter(e=>e.scrollHeight>e.clientHeight+50&&["auto","scroll"].includes(getComputedStyle(e).overflowY)).map(e=>({tag:e.tagName,cls:e.className,h:e.clientHeight,total:e.scrollHeight}))'))
            print('FIRST_CARD',await page.locator('qy-benefit-teaser').first.evaluate('(e)=>e.outerHTML'))
            stalls=0
            for _ in range(35):
                if pending:await asyncio.gather(*list(pending))
                count=await page.locator('qy-benefit-teaser').count()
                await page.locator('qy-benefit-teaser').last.scroll_into_view_if_needed()
                await page.mouse.wheel(0,1200)
                await page.evaluate('window.scrollTo(0,document.body.scrollHeight)')
                try:
                    await page.wait_for_function('(n)=>document.querySelectorAll("qy-benefit-teaser").length>n',arg=count,timeout=2000);stalls=0
                except Exception:
                    stalls+=1
                    if stalls>=2:break
            if pending:await asyncio.gather(*list(pending))
            for row in rows:
                name=row['partner_name'];node=page.locator('qy-benefit-teaser').filter(has=page.get_by_text(name,exact=True))
                if await node.count()!=1:continue
                html=await node.evaluate('(e)=>e.outerHTML')
                await node.scroll_into_view_if_needed()
                cards.append({'name':name,'url':url,'html':html})
                # Public card disclosure, not booking/activation.
                await node.click(timeout=5000);await page.wait_for_timeout(500)
                text=await page.locator('body').inner_text()
                (out/(str(row['native_id'])+'-body.txt')).write_text(text)
                print('OPENED',name,'TAIL',text[-7000:])
                print('DIALOGS',await page.evaluate('Array.from(document.querySelectorAll("[role=dialog],mat-dialog-container,[class*=Modal],[class*=Dialog],qy-benefit")).map(e=>({tag:e.tagName,cls:e.className,text:e.innerText}))'))
                await page.keyboard.press('Escape');await page.wait_for_timeout(250)
            if wanted.issubset(native):break
        (out/'native-items.json').write_text(json.dumps(native,ensure_ascii=False,indent=2))
        (out/'cards.json').write_text(json.dumps(cards,ensure_ascii=False,indent=2))
        print('NATIVE',json.dumps(native,ensure_ascii=False));print('CARDS',json.dumps(cards,ensure_ascii=False));print('NETWORK',json.dumps(network));print('READ_ERRORS',errors)
        for t in pending:t.cancel()
        if pending:await asyncio.gather(*list(pending),return_exceptions=True)
        await context.close();await browser.close()
if __name__=='__main__':asyncio.run(main())
