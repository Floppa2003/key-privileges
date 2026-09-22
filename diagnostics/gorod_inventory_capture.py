"""Public partner/offer inventories from the frontend's own GET routes."""
import hashlib,json,time
from pathlib import Path
from urllib.parse import urlencode
import requests
from bs4 import BeautifulSoup
OUT=Path('gorod-complete-inventory');OUT.mkdir(exist_ok=True)
S=requests.Session()
def read(path,params=None):
 u='https://gorodtroika.ru'+path+('?'+urlencode(params) if params else '')
 r=S.get(u,timeout=(8,30),allow_redirects=False);r.raise_for_status()
 if r.is_redirect:raise ValueError('redirect')
 time.sleep(.3);return r,u
results={};outcomes=[]
for key,path,params in [('cashback12','/api/bonus_plus/cashback/partners',{'limit':12,'category_id':12,'spend_bonuses':0,'region_id':1}),('partners','/api/bonus_plus/partners',{'limit':30,'spend_bonuses':0,'region_id':1}),('deals','/api/bonus_plus/deals',{'limit':12,'region_id':1})]:
 try:
  allrows=[];pages=[];seen=set();last=None
  for n in range(100):
   r,u=read(path,params);d=r.json();rows=d.get('elements')
   if not isinstance(rows,list) or (d.get('hasMore') and not rows):raise ValueError('shape_or_empty_nonterminal')
   ids=[x['id'] for x in rows]
   if any(i in seen for i in ids):raise ValueError('duplicate_page_id')
   seen.update(ids);allrows.extend(rows);pages.append({'url':u,'sha256':hashlib.sha256(r.content).hexdigest(),'ids':ids,'hasMore':d.get('hasMore'),'total':d.get('total')})
   if not d.get('hasMore'):break
   params={**params,'element_id':ids[-1]}
   if d.get('searchId'):params['search_id']=d['searchId']
  else:raise ValueError('page_bound')
  results[key]={'elements':allrows,'pages':pages};outcomes.append({'key':key,'count':len(allrows),'pages':len(pages),'complete':True})
 except Exception as exc:outcomes.append({'key':key,'error':type(exc).__name__+':'+str(exc)[:120]})
# Selected samples are already present in the just-read inventory, not guessed IDs.
partners=results.get('partners',{}).get('elements',[])
chosen=[]
for x in partners:
 if len(chosen)<5 or x.get('id') in (3515,359,1463,3211,3517):chosen.append(x)
for x in chosen[:12]:
 try:
  r,u=read('/partners/'+str(x['id']));s=BeautifulSoup(r.text,'html.parser');n=s.select_one('script#__NEXT_DATA__')
  data=json.loads(n.get_text())['props']['pageProps']['initialStoreState']['partnerViewStore']
  safe={k:data.get(k) for k in ('partnerData','partnerBonusesEarn','partnerBonusesSpend','partnerCouponsData','partnerDealsData')}
  # Anonymous public fields only; omit any optional personalization keys.
  for value in safe.values():
   if isinstance(value,dict):
    for k in list(value):
     if any(a in k.lower() for a in ('token','cookie','account','user','session')):del value[k]
  (OUT/('partner-'+str(x['id'])+'.json')).write_text(json.dumps({'url':u,'data':safe,'sha256':hashlib.sha256(r.content).hexdigest()},ensure_ascii=False,indent=2))
 except Exception as exc:outcomes.append({'detail':x['id'],'error':type(exc).__name__})
for key,val in results.items():(OUT/(key+'.json')).write_text(json.dumps(val,ensure_ascii=False,indent=2))
(OUT/'outcomes.json').write_text(json.dumps(outcomes,ensure_ascii=False,indent=2));print(json.dumps(outcomes,ensure_ascii=False))
