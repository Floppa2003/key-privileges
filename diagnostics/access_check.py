"""Finite anonymous public-access experiment, never a production fallback.
No login, proxy, hidden-origin discovery, challenge solving or TLS bypass.
The experiment deliberately separates endpoint reads from crawler prechecks.
"""
from __future__ import annotations
import argparse, asyncio, hashlib, json, os, platform, re, socket, ssl, subprocess, time
from pathlib import Path
from urllib.parse import urlsplit, urljoin
import requests
from bs4 import BeautifulSoup

TARGETS = {
 'ekp':'https://ekp.spb.ru/capabilities/loyalty/',
 'nordwind':'https://nordwindairlines.ru/ru/club/partnerlist',
 'coral':'https://coralbonus.ru/klub-privilegii/',
 'coral_promo':'https://coralbonus.ru/promo/',
 'coral_card':'https://coralbonus.ru/klub-privilegii/zdorov-e/medsi/',
 'rzd':'https://www.rzd-bonus.ru/?accessible=true',
 'aeroflot':'https://www.aeroflot.ru/ru-ru/afl_bonus/partners',
 'loyals':'https://loyals.ru/',
 'utair':'https://www.utair.ru/support/2/kakiye_partnery_est_u_utair_status',
 'vtb':'https://www.vtb.ru/privilegia/karty/debetovye/privilegiya-aeroflot/',
 'uralsib':'https://uralsib.ru/aktsii/privetstvennye-bally-rzhd-za-oformlenie-karty',
 'nspk':'https://www.nspk.ru/press-center/details/00d06ff9-ac6f-41fd-9aad-39965b9762cd',
 'control':'https://example.com/'
}
DENIED=re.compile(r'доступ.{0,120}(?:ограничен|запрещ[её]н).{0,60}владельц|access denied|forbidden|verify you are human|captcha|challenge-platform',re.I|re.S)
BENEFIT=re.compile(r'скидк|миль|мили|привилеги|партн[её]р|бонус|к[еэ]шб[эе]к|loyalty',re.I)
OUT=Path('access-output'); MAX_BYTES=4_000_000


def safe_url(url):
 try:
  u=urlsplit(url)
  if u.scheme not in ('http','https') or not u.hostname or u.username or u.password:return None
  if re.search(r'token|signature|secret|session|password|code=',u.query,re.I):return None
  return url
 except ValueError:return None


def document(body,status):
 soup=BeautifulSoup(body,'html.parser')
 title=soup.title.get_text(' ',strip=True) if soup.title else ''
 for n in soup.select('script,style,form,input,textarea,noscript'):n.decompose()
 text=soup.get_text(' ',strip=True)
 blocked=bool(DENIED.search(title+' '+text[:1500]))
 links=[{'text':a.get_text(' ',strip=True)[:160],'url':a.get('href')} for a in soup.select('a[href]') if safe_url(a.get('href','')) and BENEFIT.search(a.get_text(' ',strip=True)+' '+a.get('href',''))][:80]
 state='refused' if status>=400 or blocked else 'content_candidate' if len(text)>600 and BENEFIT.search(text) else 'shell_or_other'
 return {'classification':state,'title':title,'text_chars':len(text),'text':text[:6000],'text_truncated':len(text)>6000,'links':links,'body_sha256':hashlib.sha256(body.encode()).hexdigest()},str(soup)


def ssl_info(host):
 report={'host':host}
 try:
  report['addresses']=sorted({r[4][0] for r in socket.getaddrinfo(host,443,type=socket.SOCK_STREAM)})
  with socket.create_connection((host,443),timeout=7) as tcp:
   report['tcp']='ok'
   with ssl.create_default_context().wrap_socket(tcp,server_hostname=host) as tls:
    report['tls']='verified';report['certificate']=tls.getpeercert();report['protocol']=tls.version()
 except Exception as exc:
  report['error_type']=type(exc).__name__;report['verify_code']=getattr(exc,'verify_code',None);report['error']=getattr(exc,'verify_message',str(exc)[:180])
 return report


def curl_read(url,key,mode):
 body=OUT/(key+'-'+mode+'.body');headers=OUT/(key+'-'+mode+'.headers')
 flags={'default':[], 'tls12':['--tlsv1.2','--tls-max','1.2','--http1.1'],'ipv4':['-4'], 'http':[]}[mode]
 cmd=['curl','--silent','--show-error','--max-time','22','--connect-timeout','7','--max-filesize',str(MAX_BYTES),*flags,'--user-agent','Mozilla/5.0','--output',str(body),'--dump-header',str(headers),'--write-out','%{json}',url]
 r=subprocess.run(cmd,capture_output=True,text=True,timeout=27)
 report={'source_id':key,'url':url,'method':'curl_'+mode,'returncode':r.returncode}
 try:
  meta=json.loads(r.stdout);report.update({k:meta.get(k) for k in ['http_code','http_version','remote_ip','time_connect','time_appconnect','time_starttransfer','time_total','ssl_verify_result','redirect_url','num_connects']})
 except ValueError:report['metadata_error']='not_json'
 if r.returncode:report['error']=r.stderr[:240]
 status=report.get('http_code') or 0
 if body.exists():
  raw=body.read_bytes();body.unlink()
  text=raw.decode('utf8','replace');data,sanitized=document(text,status);report['document']=data
  if data['classification']=='content_candidate':(OUT/(key+'-'+mode+'.html')).write_text(sanitized,encoding='utf8')
 if headers.exists():
  text=headers.read_text(errors='replace');headers.unlink()
  report['response_headers']={line.split(':',1)[0].lower():line.split(':',1)[1].strip() for line in text.splitlines() if ':' in line and line.split(':',1)[0].lower() in ('content-type','location','retry-after','server','date','via')}
 # Persist no cookies, signed URLs, request credential headers or cURL's full metadata.
 return report


def transports():
 reports=[];layers=[]
 for host in dict.fromkeys(urlsplit(u).hostname for u in TARGETS.values()):layers.append(ssl_info(host))
 for key,url in TARGETS.items():
  a=curl_read(url,key,'default');reports.append(a)
  print(json.dumps({k:a.get(k) for k in ['source_id','method','http_code','returncode'] }),flush=True)
  time.sleep(1)
  if key in ('ekp','nordwind','coral','rzd','aeroflot','utair'):
   reports.append(curl_read(url,key,'tls12'));time.sleep(1)
  if key in ('ekp','nordwind','loyals'):
   reports.append(curl_read(url.replace('https:','http:',1),key,'http'));time.sleep(1)
 for key,url in [('loyals_www','https://www.loyals.ru/'),('rzd_canonical','https://rzd-bonus.ru/'),('utair_canonical','https://utair.ru/support/2/kakiye_partnery_est_u_utair_status')]:
  reports.append(curl_read(url,key,'default'));time.sleep(1)
 return {'layers':layers,'checks':reports}


async def browser_checks():
 from playwright.async_api import async_playwright
 result=[]
 async with async_playwright() as p:
  engines=['chromium','firefox','webkit'] if os.environ.get('RUNNER_ARCH')=='X64' else ['chromium']
  for engine in engines:
   try:browser=await getattr(p,engine).launch(headless=False if engine=='chromium' else True)
   except Exception as exc:result.append({'engine':engine,'launch_error':type(exc).__name__});continue
   try:
    for key in ('ekp','nordwind','coral_card','rzd','aeroflot','utair','loyals'):
     url=TARGETS[key];report={'source_id':key,'url':url,'engine':engine,'mode':'ordinary_browser','tls_verification':True}
     context=await browser.new_context(locale='ru-RU')
     page=await context.new_page();pending=[];captured=[]
     async def save_catalog(response):
      try:
       u=urlsplit(response.url)
       if (u.hostname=='ekp.spb.ru' and u.path.startswith('/api/portal/loyalty/partners') and response.request.method=='GET' and response.status==200 and safe_url(response.url)):
        raw=await response.body()
        if len(raw)>MAX_BYTES:return
        obj=json.loads(raw)
        if re.search(r'"(?:access_token|refresh_token|password|session)"',raw.decode(),re.I):return
        ident=hashlib.sha256(response.url.encode()).hexdigest()[:16]
        name=engine+'-'+ident+'.json';(OUT/name).write_bytes(raw)
        captured.append({'url':response.url,'file':name,'sha256':hashlib.sha256(raw).hexdigest()})
      except Exception:pass
     def capture(response):
      if '/api/portal/loyalty/partners' in response.url:
       task=asyncio.create_task(save_catalog(response));pending.append(task)
     page.on('response',capture)
     start=time.monotonic()
     try:
      response=await page.goto(url,wait_until='domcontentloaded',timeout=22000)
      await page.wait_for_timeout(3000)
      status=response.status if response else 0
      body=await page.content();report['status']=status;report['final_url']=safe_url(page.url)
      data,sanitized=document(body,status);report['document']=data
      if data['classification']=='content_candidate':(OUT/(key+'-'+engine+'.html')).write_text(sanitized,encoding='utf8')
     except Exception as exc:
      report['error_type']=type(exc).__name__;report['error']=str(exc).split('Call log:')[0][:250]
     finally:
      if pending:await asyncio.gather(*pending,return_exceptions=True)
      report['catalog_responses']=captured;report['seconds']=round(time.monotonic()-start,3)
      await context.close()
     result.append(report);print(json.dumps({'source_id':key,'engine':engine,'status':report.get('status'),'error_type':report.get('error_type')}),flush=True)
     await asyncio.sleep(1)
   finally:await browser.close()
 return result


def main():
 parser=argparse.ArgumentParser();parser.add_argument('--mode',choices=['transport','browser'],required=True);args=parser.parse_args()
 OUT.mkdir(exist_ok=True)
 now=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime())
 result=transports() if args.mode=='transport' else asyncio.run(browser_checks())
 report={'purpose':'finite_public_access_test_not_collected_offers','observed_at':now,'environment':{'os':platform.platform(),'arch':platform.machine(),'runner_arch':os.environ.get('RUNNER_ARCH'),'python':platform.python_version(),'ssl':ssl.OPENSSL_VERSION},'code_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'results':result}
 (OUT/(args.mode+'.json')).write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
if __name__=='__main__':main()
