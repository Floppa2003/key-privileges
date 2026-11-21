"""Small controlled confirmation: normal public clients, no credentials or TLS disable."""
import asyncio,hashlib,json,os,platform,re,shutil,subprocess,time
from pathlib import Path
from urllib.parse import urljoin,urlsplit
import requests
from bs4 import BeautifulSoup
from access_check import document,safe_url
OUT=Path('confirm-output');OUT.mkdir(exist_ok=True)
URLS={
 'coral_root':'https://coralbonus.ru/klub-privilegii/',
 'coral_category':'https://coralbonus.ru/klub-privilegii/zdorov-e/',
 'coral_medsi':'https://coralbonus.ru/klub-privilegii/zdorov-e/medsi/',
 'coral_napopravku':'https://coralbonus.ru/klub-privilegii/zdorov-e/napopravku/',
 'coral_promo':'https://coralbonus.ru/promo/',
 'coral_promo_detail':'https://coralbonus.ru/promo/rixos-tersane-istanbul/?erid=2W5zFHhe3eH',
 'loyals_root':'http://loyals.ru/',
 'loyals_card1':'http://loyals.ru/?post_type=post&p=5481',
 'loyals_card2':'http://loyals.ru/?post_type=post&p=5570',
 'loyals_api':'http://loyals.ru/wp-json/wp/v2/posts/5481',
}

def digest(body,status,url,key,method):
 s=BeautifulSoup(body,'html.parser');data,sanitized=document(body,status)
 data['h1']=[h.get_text(' ',strip=True) for h in s.select('h1')]
 h=s.select_one('h1');article=h.find_parent('section') if h else s.select_one('article')
 if article:
  for x in article.select('script,style,form,input,textarea,.modal'):x.decompose()
  data['article_text']=article.get_text(' ',strip=True)[:20000]
 data['catalog_links']=list(dict.fromkeys(urljoin(url,a['href']) for a in s.select('a[href]') if '/klub-privilegii/' in a['href'] or '/promo/' in a['href'] or 'post_type=post' in a['href']))[:150]
 if 200<=status<300 and data['classification']=='content_candidate':
  (OUT/(key+'-'+method+'.html')).write_text(sanitized,encoding='utf8')
 return data

def curl_get(url,key,exe,label):
 body=OUT/(key+'-'+label+'.tmp');d={'key':key,'method':label,'url':url,'https_verified':url.startswith('https:')}
 cmd=[exe,'--silent','--show-error','--connect-timeout','7','--max-time','20','--max-filesize','4000000','-A','Mozilla/5.0','-o',str(body),'-w','%{json}',url]
 try:
  r=subprocess.run(cmd,capture_output=True,encoding='utf8',errors='replace',timeout=25)
  d['returncode']=r.returncode
  try:m=json.loads(r.stdout)
  except (ValueError,TypeError):m={}
  d.update({k:m.get(k) for k in ('http_code','http_version','ssl_verify_result','remote_ip','redirect_url')})
  if r.returncode:d['error']=r.stderr[:400]
  if body.exists():
   raw=body.read_bytes();body.unlink();text=raw.decode('utf8','replace')
   d['document']=digest(text,d.get('http_code') or 0,url,key,label)
   if key=='loyals_api' and d.get('http_code')==200:
    try:
     v=json.loads(text);d['api_identity']={'id':v.get('id'),'type':v.get('type'),'status':v.get('status'),'title':v.get('title')};(OUT/'loyals-api.json').write_text(json.dumps(v,ensure_ascii=False,indent=2),encoding='utf8')
    except (ValueError,AttributeError):d['api_parse_error']=True
 except Exception as exc:d['error_type']=type(exc).__name__
 return d

def requests_get(url,key):
 d={'key':key,'method':'requests','url':url,'https_verified':url.startswith('https:')}
 try:
  with requests.Session() as s:
   s.trust_env=False
   r=s.get(url,headers={'User-Agent':'Mozilla/5.0'},allow_redirects=False,timeout=(7,20))
   d['http_code']=r.status_code;d['location']=r.headers.get('Location')
   d['document']=digest(r.content.decode('utf8','replace'),r.status_code,url,key,'requests')
 except Exception as exc:d['error_type']=type(exc).__name__;d['error']=str(exc)[:300]
 return d

async def browser_get():
 from playwright.async_api import async_playwright
 rows=[]
 async with async_playwright() as p:
  browser=await p.chromium.launch()
  try:
   for key in ('coral_medsi','coral_category','coral_promo_detail'):
    url=URLS[key];d={'key':key,'url':url,'method':'chromium','https_verified':True}
    context=await browser.new_context(locale='ru-RU');page=await context.new_page()
    try:
     r=await page.goto(url,wait_until='domcontentloaded',timeout=25000);await page.wait_for_timeout(2500)
     d['http_code']=r.status if r else 0;d['final_url']=safe_url(page.url);d['document']=digest(await page.content(),d['http_code'],url,key,'chromium')
    except Exception as exc:d['error_type']=type(exc).__name__;d['error']=str(exc).split('Call log:')[0][:250]
    finally:await context.close()
    rows.append(d);await asyncio.sleep(1)
  finally:await browser.close()
 return rows

def main():
 exe=shutil.which('curl');report={'purpose':'content_confirmation_not_production_publication','observed_at':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),'os':platform.platform(),'curl_path':exe,'checks':[]}
 report['curl_version']=subprocess.run([exe,'--version'],capture_output=True,encoding='utf8',errors='replace').stdout
 for key,url in URLS.items():
  d=curl_get(url,key,exe,'curl');report['checks'].append(d);print(json.dumps({'key':key,'method':'curl','status':d.get('http_code')}),flush=True);time.sleep(1)
 for key in ('coral_medsi','coral_napopravku','loyals_root'):
  report['checks'].append(requests_get(URLS[key],key));time.sleep(1)
 if os.name=='nt':
  for label,path in [('system_curl',r'C:\Windows\System32\curl.exe'),('git_curl',r'C:\Program Files\Git\mingw64\bin\curl.exe')]:
   if Path(path).exists():
    report.setdefault('additional_clients',[]).append({'label':label,'path':path,'version':subprocess.run([path,'--version'],capture_output=True,encoding='utf8',errors='replace').stdout})
    report['checks'].append(curl_get(URLS['coral_medsi'],'coral_medsi',path,label));time.sleep(1)
 report['checks'].extend(asyncio.run(browser_get()))
 report['code_sha256']=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
 (OUT/'confirmation.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
if __name__=='__main__':main()
