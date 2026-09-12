"""Read-only investigation; sanitized DOM only, no login or challenge solving."""
import asyncio,json,re
from pathlib import Path
from urllib.parse import urlsplit,urljoin
from urllib.robotparser import RobotFileParser
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright
from public_transport import allowed_request,check_response

OUT=Path('inspection-output')
EXTRA=[
 ('t2_main','https://t2.ru/bolshe/offers'),
 ('t2_spb','https://spb.t2.ru/bolshe/offers'),
 ('utair_media','https://media.utair.ru/status'),
 ('nordwind_www','https://www.nordwindairlines.ru/ru/club/partnerlist'),
 ('rusimp','https://www.rusimp.su/membership/friends'),
 ('rgo','https://rgo.ru/membership/loyalty-program/'),
 ('moskvich','https://moskvichmag.ru/programma-loyalnosti/'),
]

def sanitized(raw):
    soup=BeautifulSoup(raw,'html.parser')
    for n in soup.select('script,style,iframe,input,textarea,form,noscript,svg'):n.decompose()
    for n in soup.find_all(True):
        n.attrs={k:v for k,v in n.attrs.items() if k in ('id','class','href','title','colspan','rowspan')}
        if n.has_attr('href'):
            u=urlsplit(n['href'])
            if u.scheme and u.scheme not in ('https','http'):del n['href']
            else:n['href']=u._replace(query='',fragment=u.fragment).geturl()
    return str(soup)

async def inspect(browser,sid,url,sem):
    report={'id':sid,'url':url,'robots':None,'status':None}
    async with sem:
      context=await browser.new_context(locale='ru-RU');page=await context.new_page()
      host=urlsplit(url).hostname
      try:
        robot_url='https://'+host+'/robots.txt'
        r=await context.request.get(robot_url,timeout=18000)
        status=r.status;body=await r.text();report['robots']=status
        # RFC 9309 2.3.1.3: 4xx for robots alone is unavailable, not Disallow.
        # Rate limits, server failures and challenges remain stop conditions.
        if status==429 or status>=500:raise RuntimeError('robots_unreachable')
        policy=RobotFileParser(robot_url)
        if 400<=status<500:policy.parse([])
        elif status==200:
          check_response(status,body)
          if '<html' in body.lower():raise RuntimeError('robots_invalid_html')
          policy.parse(body.splitlines())
        else:raise RuntimeError('robots_unhandled_status')
        if not policy.can_fetch('LoyaltyCatalogResearchBot',url):raise RuntimeError('robots_disallow')
        await asyncio.sleep(1)
        r=await page.goto(url,wait_until='domcontentloaded',timeout=28000)
        await page.wait_for_timeout(1500)
        report['status']=r.status if r else None;report['final_url']=page.url
        raw=await page.content();check_response(report['status'] or 0,raw)
        if not allowed_request(page.url,host):raise RuntimeError('redirect_outside_source')
        soup=BeautifulSoup(raw,'html.parser')
        report['title']=soup.title.get_text(' ',strip=True) if soup.title else ''
        report['scripts']=[urlsplit(urljoin(url,x['src']))._replace(query='',fragment='').geturl() for x in soup.select('script[src]') if urlsplit(urljoin(url,x['src'])).hostname==host]
        report['json_scripts']=[{'id':x.get('id'),'type':x.get('type'),'size':len(x.get_text())} for x in soup.select('script') if x.get('type') in ('application/json','application/ld+json')]
        dom=sanitized(raw)
        if len(dom)>2000000:raise RuntimeError('dom_too_large')
        (OUT/(sid+'.html')).write_text(dom,encoding='utf8')
        report['text_size']=len(BeautifulSoup(dom,'html.parser').get_text())
      except Exception as e:
        report['error']=str(e)[:160] if isinstance(e,RuntimeError) else type(e).__name__
      finally:await context.close()
    print(json.dumps(report,ensure_ascii=False),flush=True)
    return report

async def main():
    OUT.mkdir(exist_ok=True)
    cfg=json.loads(Path(__file__).with_name('sources_normalized.json').read_text())
    targets=[(c['id'],c['url']) for c in cfg if c['mode']=='probe']+EXTRA
    async with async_playwright() as p:
      b=await p.chromium.launch();sem=asyncio.Semaphore(4)
      reports=await asyncio.gather(*(inspect(b,s,u,sem) for s,u in targets))
      await b.close()
    (OUT/'report.json').write_text(json.dumps(reports,ensure_ascii=False,indent=2),encoding='utf8')

if __name__=='__main__':asyncio.run(main())
