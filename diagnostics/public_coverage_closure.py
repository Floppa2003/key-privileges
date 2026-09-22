"""One-shot, anonymous catalogue evidence; no login, issuance, or storage writes."""
from __future__ import annotations
import asyncio, hashlib, json, re
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode
import requests
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright

OUT = Path('coverage-closure-probe'); OUT.mkdir(exist_ok=True)
ROOTS = {
 'gorod': 'https://gorodtroika.ru/bonus-plus/coupons',
 'x5': 'https://x5club.ru/partners',
 'magnit': 'https://magnit.ru/partners',
 'tsvetnoy': 'https://tsvetnoy.com/loyality',
 'hse': 'https://alumni.hse.ru/loyalty/partners/',
 'nordwind': 'https://nordwindairlines.ru/ru/club/partnerlist',
}
SENSITIVE = re.compile(r'token|cookie|password|authorization|secret|session|csrf|nonce|phone|email|customer|userId|accountId', re.I)
BAD_PATH = re.compile(r'auth|login|logout|register|profile|account|session|token|checkout|basket|cart|order|activate|issue|claim', re.I)

def clean_url(url):
 p = urlsplit(url)
 return urlunsplit((p.scheme,p.netloc,p.path,urlencode([(k,v) for k,v in parse_qsl(p.query) if not SENSITIVE.search(k)]),''))

def clean_json(value):
 if isinstance(value,dict): return {k:('[redacted]' if SENSITIVE.search(k) else clean_json(v)) for k,v in value.items()}
 if isinstance(value,list): return [clean_json(v) for v in value]
 if isinstance(value,str) and value.startswith(('https://','http://')): return clean_url(value)
 return value

def save_html(name,raw,method,url,status):
 soup=BeautifulSoup(raw,'html.parser'); scripts=[]; states={}
 for i,s in enumerate(soup.select('script')):
  if s.get('src'): scripts.append(clean_url(s['src']))
  elif s.get('id') in ('__NEXT_DATA__','__NUXT_DATA__'):
   try: states[s['id']]=clean_json(json.loads(s.get_text()))
   except (ValueError,TypeError): pass
  s.decompose()
 for e in soup.select('input,textarea'): e.attrs.pop('value',None)
 for e in soup.find_all(True):
  for k in list(e.attrs):
   if SENSITIVE.search(k): del e.attrs[k]
   elif k in ('href','src','action') and isinstance(e.attrs[k],str): e.attrs[k]=clean_url(e.attrs[k])
 public=str(soup)
 (OUT/(name+'.'+method+'.html')).write_text(public,encoding='utf8')
 meta={'url':clean_url(url),'http_status':status,'observed_at':datetime.now(timezone.utc).isoformat(),'raw_sha256':hashlib.sha256(raw.encode()).hexdigest(),'public_bytes':len(public.encode()),'script_urls':scripts,'embedded_states':states}
 (OUT/(name+'.'+method+'.json')).write_text(json.dumps(meta,ensure_ascii=False,indent=2),encoding='utf8')
 return {'source':name,'method':method,'status':status,'url':clean_url(url),'bytes':len(raw.encode())}

def direct(name,url):
 try:
  res=requests.get(url,timeout=(8,25),allow_redirects=False)
  result=save_html(name,res.text,'http',url,res.status_code)
  if res.is_redirect: result['redirect_to']=clean_url(res.headers.get('Location',''))
  return result
 except requests.RequestException as exc: return {'source':name,'method':'http','error':type(exc).__name__}

async def main():
 results=await asyncio.gather(*(asyncio.to_thread(direct,name,url) for name,url in ROOTS.items()))
 async with async_playwright() as p:
  browser=await p.chromium.launch()
  for name in ('gorod','x5','magnit','tsvetnoy'):
   url=ROOTS[name];host=urlsplit(url).hostname
   context=await browser.new_context();page=await context.new_page();tasks=[];responses=[]
   async def capture(res,expected=host):
    try:
     parts=urlsplit(res.url)
     if not (parts.hostname==expected or parts.hostname.endswith('.'+expected)):return
     if BAD_PATH.search(parts.path) or any(SENSITIVE.search(k) for k,v in parse_qsl(parts.query)):return
     if res.request.method!='GET' or res.status!=200 or 'application/json' not in res.headers.get('content-type',''):return
     body=await res.body()
     if len(body)>3000000:return
     responses.append({'url':clean_url(res.url),'status':res.status,'observed_at':datetime.now(timezone.utc).isoformat(),'sha256':hashlib.sha256(body).hexdigest(),'data':clean_json(json.loads(body))})
    except Exception:pass
   page.on('response',lambda res:tasks.append(asyncio.create_task(capture(res))))
   try:
    response=await page.goto(url,wait_until='domcontentloaded',timeout=30000)
    await page.wait_for_timeout(5000)
    if response and response.status in (200,301,302):
     await page.evaluate('window.scrollTo(0, document.body.scrollHeight)');await page.wait_for_timeout(2000)
    results.append(save_html(name,await page.content(),'browser',page.url,response.status if response else None))
   except Exception as exc:results.append({'source':name,'method':'browser','error':type(exc).__name__})
   if tasks:await asyncio.gather(*tasks,return_exceptions=True)
   (OUT/(name+'.public-json.json')).write_text(json.dumps(responses,ensure_ascii=False,indent=2),encoding='utf8')
   await context.close()
  await browser.close()
 (OUT/'outcomes.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf8')
 print(json.dumps(results,ensure_ascii=False))

if __name__=='__main__':asyncio.run(main())
