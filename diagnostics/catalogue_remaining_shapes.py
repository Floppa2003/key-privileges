"""Read-only bounded diagnosis of actual rejected anonymous catalogue cards."""
import sys,json,time,hashlib
from pathlib import Path
from datetime import datetime,timezone
import requests
from bs4 import BeautifulSoup
from protego import Protego
sys.path.insert(0,'loyalty')
from x5_partners import page_data,ROOT as XROOT
from gorod_source import slim_partner,source_fields
from expansion_common import next_store,sha
from normalized import text
OUT=Path('catalogue-remaining-shapes');OUT.mkdir(exist_ok=True)
s=requests.Session()
def read(u):
 r=s.get(u,timeout=(8,30),allow_redirects=False)
 if r.status_code!=200:raise ValueError('http_'+str(r.status_code))
 if len(r.content)>6000000:raise ValueError('response_bound')
 time.sleep(.3);return r.text

def save(n,v):
 (OUT/(n+'.json')).write_text(json.dumps(v,ensure_ascii=False,indent=2),encoding='utf8')

try:
 root='https://magnit.ru/partners';raw=read('https://magnit.ru/robots.txt');p=Protego.parse(raw)
 save('magnit-policy',dict(text=raw,root=root,allowed=p.can_fetch(root,'LoyaltyCatalogResearchBot'),slash_allowed=p.can_fetch(root+'/','LoyaltyCatalogResearchBot'),observed_at=datetime.now(timezone.utc).isoformat()))
except Exception as exc:save('magnit-policy',{'error':type(exc).__name__+':'+str(exc)[:100]})
# Narrow pattern tests diagnose the parser separately from the live response.
probes={}
for rule in ('/*?$','*?SECTION','*?=','*in=','/*?page=1$'):
 p=Protego.parse('User-agent: *\nDisallow: '+rule)
 probes[rule]={u:p.can_fetch(u,'LoyaltyCatalogResearchBot') for u in ('https://magnit.ru/partners','https://magnit.ru/partners/','https://magnit.ru/partners/1768','https://magnit.ru/partners?')}
save('policy-patterns',probes)
cards={}
for page in range(4):
 d=page_data(read(XROOT+'.data?page='+str(page)+'&_routes=routes%2F_unauth.partners._index'),page)
 for c in d['partnerOffers']['partnerOffers']+d.get('paidOffers',[]):cards[c['idOffer']]=c
for i in (202,143,226,225,219):
 try:
  raw=read(XROOT+'/'+str(i));b=BeautifulSoup(raw,'html.parser').select_one('main')
  for n in b.select('script,style,input,form,iframe'):n.decompose()
  save('x5-'+str(i),{'card':cards[i],'main_html':str(b),'sha256':sha(raw),'observed_at':datetime.now(timezone.utc).isoformat()})
 except Exception as e:save('x5-'+str(i),{'error':type(e).__name__+':'+str(e)[:100]})
for i in (3530,3206,3227,359):
 try:
  raw=read('https://gorodtroika.ru/partners/'+str(i));store=next_store(raw,'partnerViewStore');d=slim_partner(store)
  e=dict(native='partner:'+str(i),kind='partner',url='https://gorodtroika.ru/partners/'+str(i),data=d,catalogue_regions=['Москва'],page_sha256=sha(raw))
  out={'evidence':e,'coupon_list':store.get('partnerCouponsData'),'observed_at':datetime.now(timezone.utc).isoformat()}
  try:
   f=source_fields(e);out['normalization_differences']={k:{'source':v,'normalized':text(v)} for k,v in f.items() if isinstance(v,str)and v!=text(v)}
  except Exception as ex:out['parse_error']=str(ex)
  save('gorod-partner-'+str(i),out)
 except Exception as e:save('gorod-partner-'+str(i),{'error':type(e).__name__+':'+str(e)[:100]})
for i in (19464,19629,19547,2,4):
 try:
  raw=read('https://gorodtroika.ru/bonus-plus/coupons/'+str(i));d=next_store(raw,'couponViewStore')['couponData']
  safe={k:d.get(k) for k in ('id','name','available','price','terms','endAt','couponEndAt','countdown','howToAsList','cashback','message','address')}
  safe['partner']={k:d.get('partner',{}).get(k)for k in ('id','name','subtitle','available')}
  save('gorod-coupon-'+str(i),{'data':safe,'sha256':sha(raw),'observed_at':datetime.now(timezone.utc).isoformat()})
 except Exception as e:save('gorod-coupon-'+str(i),{'error':type(e).__name__+':'+str(e)[:100]})
print('Read-only selected-card diagnosis complete; no activation or account access.')
