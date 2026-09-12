"""Anonymous T2 response verification; only public offer fields are exported."""
import asyncio,json
from pathlib import Path
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright
OUT=Path('finish-browser');OUT.mkdir(exist_ok=True)
def clean(raw):
    s=BeautifulSoup(raw,'html.parser')
    for e in s.select('script,style,form,input,iframe,noscript'):e.decompose()
    for e in s.find_all(True):
        for k in list(e.attrs):
            if k not in ('class','id','href','src','alt','title'):del e.attrs[k]
    return str(s)
async def main():
    report=[]
    async with async_playwright() as p:
        b=await p.chromium.launch();ctx=await b.new_context(locale='ru-RU');page=await ctx.new_page()
        try:
            for key,path in [('robots','/robots.txt'),('root','/bolshe/offers'),('mixx','/help/article/what-included-mixx-m-subscription'),('selection','/tariff/premium'),('mixx_s','/promotions/article/yandex-station-mixx'),('powerbank','/promotions/article/bezlimitnaya-arenda-powerbank')]:
                url='https://msk.t2.ru'+path;docs=[]
                def observe(r):
                    if r.request.is_navigation_request() and r.request.frame==page.main_frame:docs.append({'status':r.status,'url':r.url})
                page.on('response',observe)
                try:
                    await page.goto(url,wait_until='domcontentloaded',timeout=35000);await page.wait_for_timeout(14000 if key in ('robots','root') else 2000)
                    raw=await page.content();report.append({'id':key,'documents':docs,'title':await page.title(),'size':len(raw)})
                    (OUT/(key+'.html')).write_text(clean(raw),encoding='utf8')
                    if key=='robots':(OUT/'robots.txt').write_text(await page.locator('body').inner_text(),encoding='utf8')
                    if key=='root':
                        data=await page.evaluate('''async () => {const r=await fetch('/api/loyalty/offers?siteId=siteMSK&withPersonal=false');return {status:r.status,body:await r.json()};}''')
                        report.append({'id':'public_api','status':data['status'],'meta':data['body'].get('meta')})
                        obj=data['body'].get('data',{})
                        fields=('id','name','info','agreement','dateTo','duration','offerType','offlineOffer','availableForAll','forAllTariffs','areaType','buttonText','promoCodeType','activationCount','companyName')
                        rows=[]
                        for offer in obj.get('offers',[]):
                            row={k:offer.get(k) for k in fields}
                            row['partner']={k:offer.get('partner',{}).get(k) for k in ('name','domain')}
                            row['segments']=[{k:x.get(k) for k in ('id','name')} for x in offer.get('segments',[])]
                            rows.append(row)
                        (OUT/'catalog.json').write_text(json.dumps({'meta':data['body'].get('meta'),'data':{'offers':rows,'lifestyles':[{k:x.get(k) for k in ('id','name')} for x in obj.get('lifestyles',[])]}},ensure_ascii=False,indent=2),encoding='utf8')
                except Exception as e:report.append({'id':key,'error':type(e).__name__})
                finally:page.remove_listener('response',observe)
        finally:await ctx.close();await b.close()
    (OUT/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
if __name__=='__main__':asyncio.run(main())
