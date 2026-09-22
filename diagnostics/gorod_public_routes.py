"""Inspect public frontend routing strings, not authorization or user data."""
import json,re,time
from pathlib import Path
import requests
from bs4 import BeautifulSoup
OUT=Path('gorod-route-evidence');OUT.mkdir(exist_ok=True)
root='https://gorodtroika.ru/bonus-plus/cashback'
r=requests.get(root,timeout=(8,25));r.raise_for_status();s=BeautifulSoup(r.text,'html.parser')
st=json.loads(s.select_one('script#__NEXT_DATA__').get_text())['props']['pageProps']['initialStoreState']['bonusPlusCashbackViewStore']
(OUT/'cashback-store.json').write_text(json.dumps(st,ensure_ascii=False,indent=2))
links=[a['src'] for a in s.select('script[src]') if a['src'].startswith('/_next/static/chunks/') and any(x in a['src'] for x in ('pages/bonus-plus/cashback','pages/_app','7236-','446-'))]
for i,path in enumerate(links):
 res=requests.get('https://gorodtroika.ru'+path,timeout=(8,25));res.raise_for_status()
 text=res.text;snippets=[]
 for pattern in ('/bonus_plus/','cashback/partners','cashbackPartners','category_id','element_id','filterDataCategories'):
  for m in list(re.finditer(re.escape(pattern),text))[:30]:snippets.append({'needle':pattern,'context':text[max(0,m.start()-400):m.end()+600]})
 (OUT/f'route-{i}.json').write_text(json.dumps({'url':'https://gorodtroika.ru'+path,'status':res.status_code,'snippets':snippets},ensure_ascii=False,indent=2))
 time.sleep(.5)
print(json.dumps({'files':len(links),'store_keys':list(st)},ensure_ascii=False))
