"""Read public pages with a temporary host-scoped CA bundle; no system trust changes."""
import hashlib,json,re,subprocess,tempfile,time
from pathlib import Path
from urllib.parse import urlsplit
import certifi, requests
from access_check import TARGETS, document
OUT=Path('trust-output');OUT.mkdir(exist_ok=True)
CA_URLS=[
 'https://gu-st.ru/content/lending/russian_trusted_root_ca_pem.crt',
 'https://gu-st.ru/content/lending/russian_trusted_sub_ca_pem.crt',
]

def get(url,verify=True):
 with requests.Session() as s:
  s.trust_env=False
  r=s.get(url,timeout=(7,18),allow_redirects=False,verify=verify,headers={'User-Agent':'Mozilla/5.0','Accept-Language':'ru-RU,ru;q=0.9'},stream=True)
  chunks=[];size=0
  for chunk in r.iter_content(32768):
   size+=len(chunk)
   if size>4_000_000:raise RuntimeError('bounded_response_too_large')
   chunks.append(chunk)
  return r,b''.join(chunks)

def request_page(key,url,label,verify):
 d={'source_id':key,'url':url,'trust_mode':label}
 try:
  r,raw=get(url,verify)
  encoding=r.encoding if r.encoding and r.encoding.lower()!='iso-8859-1' else 'utf8'
  body=raw.decode(encoding,errors='replace');summary,sanitized=document(body,r.status_code)
  d.update(status=r.status_code,location=r.headers.get('Location'),document=summary)
  if r.status_code==200 and summary['classification']=='content_candidate':(OUT/(key+'-'+label+'.html')).write_text(sanitized,encoding='utf8')
 except Exception as exc:d.update(error_type=type(exc).__name__,error=str(exc)[:500])
 return d

def main():
 report={'purpose':'temporary_host_scoped_CA_test','observed_at':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),'ca_sources':[],'checks':[],'system_trust_changed':False,'hostname_and_expiry_verification':True}
 with tempfile.TemporaryDirectory() as tmp:
  ca=Path(tmp)/'ca.pem';ca.write_bytes(Path(certifi.where()).read_bytes()+b'\n')
  for url in CA_URLS:
   d={'url':url}
   try:
    r,raw=get(url)
    if r.status_code!=200 or not raw.startswith(b'-----BEGIN CERTIFICATE-----') or len(raw)>25000:raise RuntimeError('certificate_download_not_accepted')
    p=Path(tmp)/Path(urlsplit(url).path).name;p.write_bytes(raw)
    meta=subprocess.run(['openssl','x509','-in',str(p),'-noout','-subject','-issuer','-dates','-fingerprint','-sha256'],capture_output=True,text=True,check=True,timeout=5).stdout
    if 'Russian Trusted' not in meta:raise RuntimeError('unexpected_CA_identity')
    d.update(status='downloaded_over_verified_https',sha256=hashlib.sha256(raw).hexdigest(),certificate=meta)
    with ca.open('ab') as f:f.write(raw+b'\n')
   except Exception as exc:d.update(error_type=type(exc).__name__,error=str(exc)[:200])
   report['ca_sources'].append(d)
  downloaded=any(d.get('status') for d in report['ca_sources'])
  for key in ('vtb','uralsib','nspk','loyals'):
   url=TARGETS[key]
   report['checks'].append(request_page(key,url,'default',True));time.sleep(1)
   if downloaded:report['checks'].append(request_page(key,url,'scoped_CA',str(ca)));time.sleep(1)
   host=urlsplit(url).hostname
   try:
    r=subprocess.run(['openssl','s_client','-connect',host+':443','-servername',host,'-showcerts','-verify_return_error'],input='',capture_output=True,text=True,timeout=12)
    report.setdefault('certificate_diagnostics',[]).append({'host':host,'returncode':r.returncode,'messages':[line for line in r.stderr.splitlines() if any(x in line for x in ['depth=','verify error','Verification'])][:12]})
   except Exception as exc:report.setdefault('certificate_diagnostics',[]).append({'host':host,'error_type':type(exc).__name__})
  report['code_sha256']=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
  (OUT/'trust.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
  print(json.dumps({'certificates_downloaded':sum(bool(d.get('status')) for d in report['ca_sources']),'checks':len(report['checks'])}))
if __name__=='__main__':main()
