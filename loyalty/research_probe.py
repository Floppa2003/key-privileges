"""Temporary anonymous transport diagnosis; no Google access and no session exports."""
import asyncio,json,re
from pathlib import Path
from urllib.parse import urljoin,urlsplit,parse_qsl
from bs4 import BeautifulSoup,Comment
from playwright.async_api import async_playwright
from public_transport import PublicSource
SENSITIVE=re.compile(r'token|secret|password|session|sessid|cookie|csrf|authorization|credential|nonce',re.I)
OUT=Path('research-output')
def sanitize_html(raw):
 s=BeautifulSoup(raw,'html.parser')
 for el in s(['script','style','input','textarea','iframe','noscript']):el.decompose()
 for x in s.find_all(string=lambda t:isinstance(t,Comment)):x.extract()
 for el in s.find_all(True):
  el.attrs={k:v for k,v in el.attrs.items() if k in ('id','class','href','alt','title','role','aria-label','data-id')}
  if el.has_attr('href') and SENSITIVE.search(el['href']):del el['href']
 return str(s)
def sanitize(data):
 if isinstance(data,dict):return {k:sanitize(v) for k,v in data.items() if not SENSITIVE.search(k)}
 if isinstance(data,list):return [sanitize(x) for x in data]
 return data
async def mir(browser):
 async with PublicSource(browser,'https://vamprivet.ru/promo/') as c:
  await c.robots();events=[];tasks=[]
  async def capture(r):
   if urlsplit(r.url).hostname!=c.host or not urlsplit(r.url).path.endswith('/promo/filter-json'):return
   body=r.request.post_data or ''
   try:parsed=json.loads(body)
   except Exception:parsed=dict(parse_qsl(body))
   item={'url':r.url,'method':r.request.method,'content_type':r.request.headers.get('content-type'),'body_fields':sanitize(parsed),'status':r.status}
   if r.status==200:
    try:
     d=await r.json();item['query']=d.get('data',{}).get('query');item['counter']=d.get('data',{}).get('counter');item['ids']=[x.get('xml_id') for x in d.get('data',{}).get('items',[])];item['pagination']=d.get('data',{}).get('pagination')
    except Exception:pass
   events.append(item)
  c.page.on('response',lambda r:tasks.append(asyncio.create_task(capture(r))))
  await c.read('https://vamprivet.ru/promo/',render=True)
  await c.page.wait_for_timeout(1500)
  (OUT/'mir-before.html').write_text(sanitize_html(await c.page.content()))
  clicked=False
  for loc in [c.page.get_by_role('link',name='2',exact=True),c.page.get_by_role('button',name='2',exact=True),c.page.locator('[href*="page_catalog_list=2"]')]:
   if await loc.count() and await loc.first.is_visible():
    await loc.first.click(timeout=4000);clicked=True;await c.page.wait_for_timeout(2000);break
  if tasks:await asyncio.gather(*tasks,return_exceptions=True)
  (OUT/'mir-events.json').write_text(json.dumps({'clicked':clicked,'events':events},ensure_ascii=False,indent=2))
async def coral(browser):
 async with PublicSource(browser,'https://coralbonus.ru/klub-privilegii/') as c:
  await c.robots();seen=set();queue=['https://coralbonus.ru/klub-privilegii/','https://coralbonus.ru/promo/'];report=[]
  while queue and len(seen)<6:
   url=queue.pop(0)
   if url in seen:continue
   seen.add(url);raw=await c.read(url,render=True);await c.page.wait_for_timeout(1600);raw=await c.page.content()
   name='coral-'+str(len(seen))+'.html';(OUT/name).write_text(sanitize_html(raw))
   soup=BeautifulSoup(raw,'html.parser');links=[]
   for a in soup.select('a[href]'):
    target=urljoin(url,a['href']);p=urlsplit(target)
    if p.hostname==c.host and re.fullmatch(r'/klub-privilegii/[^/]+/[^/]+/?',p.path):links.append(target)
   links=list(dict.fromkeys(links));report.append({'url':url,'file':name,'detail_links':links})
   queue.extend([x for x in links[:2] if x not in seen and x not in queue])
  (OUT/'coral-pages.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
async def main():
 OUT.mkdir(exist_ok=True)
 async with async_playwright() as p:
  b=await p.chromium.launch()
  for name,fn in [('mir',mir),('coral',coral)]:
   try:await fn(b)
   except Exception as e:(OUT/(name+'-error.txt')).write_text(type(e).__name__+': '+str(e)[:300])
  await b.close()
if __name__=='__main__':asyncio.run(main())
