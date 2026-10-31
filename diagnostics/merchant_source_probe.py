"""Read-only diagnosis: existing collector artifact and anonymous native catalogue UI."""
import asyncio
import json
import sys
from pathlib import Path
from urllib.parse import urlsplit

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'loyalty'))
from konsierge_source import allowed_read, public_item, HOST, API_HOST, API_PATHS
from playwright.async_api import async_playwright

NAMES=['Memo','Hide','El Copitas Bar','Po’mestam']

async def main():
    out=Path('source-probe');out.mkdir(exist_ok=True)
    data=json.loads(Path('probe-input/normalized.json').read_text())
    rows=[r for r in data['records'] if r.get('source_id')=='konsierge_public' and r.get('partner_name') in NAMES]
    (out/'catalogue-records.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2))
    print('CATALOGUE',json.dumps([{'partner':r['partner_name'],'native_id':r.get('native_id'),'keys':list(r),
        'source_url':r.get('source_url'),'public_item':r.get('details',{}).get('public_item')} for r in rows],ensure_ascii=False))
    wanted={int(r['native_id']) for r in rows};native={};pending=set();errors=[]
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
                if res.status!=200:return
                data=await res.json()
                for item in data.get('result',[]):
                    if item.get('id') in wanted:native[item['id']]=public_item(item)
            except Exception as exc:errors.append(type(exc).__name__)
        def enqueue(res):
            u=urlsplit(res.url)
            if u.netloc==API_HOST and u.path=='/api/client/v1/benefits':
                t=asyncio.create_task(read(res));pending.add(t);t.add_done_callback(pending.discard)
        page.on('response',enqueue)
        await page.goto('https://konsierge.com/benefits',wait_until='domcontentloaded',timeout=30000)
        await page.wait_for_selector('qy-benefit-teaser',timeout=20000)
        for _ in range(45):
            if pending:await asyncio.gather(*list(pending))
            if wanted.issubset(native):break
            count=await page.locator('qy-benefit-teaser').count()
            await page.evaluate('window.scrollTo(0,0)');await page.wait_for_timeout(300)
            await page.evaluate('window.scrollTo(0,document.body.scrollHeight)')
            try:await page.wait_for_function('(n)=>document.querySelectorAll("qy-benefit-teaser").length>n',arg=count,timeout=12000)
            except Exception:break
        if pending:await asyncio.gather(*list(pending))
        cards=[]
        for row in rows:
            name=row['partner_name']
            node=page.locator('qy-benefit-teaser').filter(has=page.get_by_text(name,exact=True))
            n=await node.count()
            cards.append({'name':name,'matches':n,'html':await node.first.evaluate('(e)=>e.outerHTML') if n else None})
        (out/'native-items.json').write_text(json.dumps(native,ensure_ascii=False,indent=2))
        (out/'cards.json').write_text(json.dumps(cards,ensure_ascii=False,indent=2))
        print('NATIVE',json.dumps(native,ensure_ascii=False))
        print('CARDS',json.dumps(cards,ensure_ascii=False));print('READ_ERRORS',errors)
        for t in pending:t.cancel()
        if pending:await asyncio.gather(*list(pending),return_exceptions=True)
        await context.close();await browser.close()

if __name__=='__main__':asyncio.run(main())
