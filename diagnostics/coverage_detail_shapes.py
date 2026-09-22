"""Bounded public inventory/detail shape inspection; never press redemption."""
import asyncio, hashlib, json, re
from pathlib import Path
from urllib.parse import urlsplit, urljoin
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright
import public_coverage_closure as base

OUT=Path('coverage-detail-shapes');OUT.mkdir(exist_ok=True);base.OUT=OUT
ROOTS=base.ROOTS

def save(name,data):
 (OUT/(name+'.json')).write_text(json.dumps(base.clean_json(data),ensure_ascii=False,indent=2),encoding='utf8')

def nextdata(raw):
 s=BeautifulSoup(raw,'html.parser').select_one('script#__NEXT_DATA__')
 return json.loads(s.get_text())['props']['pageProps'] if s else {}

async def main():
 results=[]
 async with async_playwright() as p:
  browser=await p.chromium.launch()
  for name in ('x5','gorod','magnit','tsvetnoy'):
   url=ROOTS[name];context=await browser.new_context();page=await context.new_page();requests_seen=[]
   def observe(req):
    if req.resource_type in ('xhr','fetch') and req.method=='GET' and urlsplit(req.url).hostname==urlsplit(url).hostname and not base.BAD_PATH.search(urlsplit(req.url).path):
     requests_seen.append(base.clean_url(req.url))
   page.on('request',observe)
   try:
    res=await page.goto(url,wait_until='domcontentloaded',timeout=35000);await page.wait_for_timeout(4000)
    if res.status!=200:raise RuntimeError('root_http_'+str(res.status))
    raw=await page.content()
    if name=='x5':
     counts=[];stable=0
     for _ in range(35):
      await page.evaluate('window.scrollTo(0,document.body.scrollHeight)');await page.wait_for_timeout(900)
      count=await page.locator('a[href^="/partners/"] h3').count();counts.append(count)
      stable=stable+1 if len(counts)>1 and count==counts[-2] else 0
      if stable>=4:break
     raw=await page.content();base.save_html(name,raw,'full-root',page.url,200)
     soup=BeautifulSoup(raw,'html.parser');cards={}
     for a in soup.select('a[href]'):
      path=urlsplit(a['href']).path
      if re.fullmatch('/partners/[0-9]+',path) and a.select_one('h3'):
       cards[path]={'url':urljoin(url,path),'title':a.select_one('h3').get_text(' ',strip=True),'text':a.get_text(' ',strip=True)}
     save('x5-inventory',{'cards':list(cards.values()),'growth':counts,'network':requests_seen})
     for path in ['/partners/222','/partners/116','/partners/230']:
      r=await context.request.get(urljoin(url,path),timeout=30000);base.save_html('x5-'+path.rsplit('/',1)[-1],await r.text(),'detail',r.url,r.status)
    elif name=='gorod':
     store=nextdata(raw)['initialStoreState']['bonusPlusCouponsViewStore'];groups=list(store['couponsPartnersData']['elements']);more=store['couponsPartnersData']['hasMore'];pages=[]
     for _ in range(30):
      if not more:break
      cursor=next(g['id'] for g in reversed(groups) if 'id' in g)
      target=f'https://gorodtroika.ru/api/bonus_plus/coupons/partners?element_id={cursor}&limit=10&region_id=1'
      r=await context.request.get(target,timeout=25000)
      if r.status!=200:raise RuntimeError('gorod_page_http_'+str(r.status))
      data=await r.json();pages.append({'url':target,'data':data})
      if not data.get('elements'):raise RuntimeError('gorod_empty_page')
      groups.extend(data['elements']);more=data.get('hasMore')
      await asyncio.sleep(.5)
     save('gorod-inventory',{'groups':groups,'pages':pages,'hasMore':more,'categories':store['filterDataCategories']})
     for path in ['/bonus-plus/coupons/19560','/bonus-plus/coupons/19547','/bonus-plus/coupons/19629','/partners/321','/bonus-plus/cashback']:
      target=urljoin(url,path);r=await context.request.get(target,timeout=30000);base.save_html('gorod-'+path.rsplit('/',1)[-1],await r.text(),'detail',r.url,r.status)
    elif name=='magnit':
     base.save_html(name,raw,'full-root',page.url,200)
     soup=BeautifulSoup(raw,'html.parser');cards={}
     for a in soup.select('a[href]'):
      path=urlsplit(a['href']).path
      if re.fullmatch('/partners/[0-9]+',path):cards[path]={'url':urljoin(url,path),'text':a.get_text(' ',strip=True)}
     save('magnit-inventory',{'cards':list(cards.values()),'network':requests_seen})
     for path in ['/partners/1768','/partners/1787','/partners/1775']:
      r=await page.goto(urljoin(url,path),wait_until='domcontentloaded',timeout=30000);await page.wait_for_timeout(1800)
      base.save_html('magnit-'+path.rsplit('/',1)[-1],await page.content(),'detail',page.url,r.status)
    else:
     base.save_html(name,raw,'full-root',page.url,200)
     docs=await context.request.get('https://tsvetnoy.com/api/v1/documents',timeout=20000);data=await docs.json();save('tsvetnoy-documents',data)
     selected=[d for d in data if d.get('active') and d.get('type')=='loyalyty_program_discount']
     if len(selected)!=1:raise RuntimeError('tsvetnoy_document_identity')
     target='https://tsvetnoy.com/pdf/'+selected[0]['key'];r=await context.request.get(target,timeout=25000);body=await r.body()
     if r.status!=200 or not body.startswith(b'%PDF-') or len(body)>6000000:raise RuntimeError('tsvetnoy_not_bounded_pdf')
     (OUT/'tsvetnoy-discounts.pdf').write_bytes(body);save('tsvetnoy-pdf-origin',{'url':target,'status':r.status,'sha256':hashlib.sha256(body).hexdigest()})
    results.append({'name':name,'outcome':'read','network':requests_seen})
   except Exception as exc:results.append({'name':name,'error':str(exc)[:160] if isinstance(exc,RuntimeError) else type(exc).__name__})
   await context.close()
  await browser.close()
 save('outcomes',results);print(json.dumps(results,ensure_ascii=False))
if __name__=='__main__':asyncio.run(main())
