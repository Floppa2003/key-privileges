"""Read advertised public WordPress posts and test anonymous same-host redirects.
Diagnostic output only; HTTP data explicitly has unauthenticated transport.
"""
from __future__ import annotations
import hashlib,json,re,sys,tempfile,time
from datetime import datetime,timezone
from pathlib import Path
from urllib.parse import urlsplit,urljoin,parse_qs
import certifi,requests
from bs4 import BeautifulSoup
sys.path.insert(0,'loyalty')
from normalized import normalize_rates,lexical_conditions,text
from access_check import document
OUT=Path('structured-output');OUT.mkdir(exist_ok=True)
API='http://loyals.ru/wp-json/wp/v2/posts'
CA_URL='https://gu-st.ru/content/lending/russian_trusted_root_ca_pem.crt'
CA_SHA='936a43fea6e8e525bcc0f81acd9c3d21b4fc4b9b68acea7906d698005afc6504'


def fetch(session,url,verify=True):
 r=session.get(url,headers={'User-Agent':'Mozilla/5.0'},verify=verify,timeout=(7,20),allow_redirects=False,stream=True)
 chunks=[];size=0
 for chunk in r.iter_content(32768):
  size+=len(chunk)
  if size>5_000_000:raise RuntimeError('response_too_large')
  chunks.append(chunk)
 return r,b''.join(chunks)


def project_post(post):
 if type(post.get('id')) is not int or post.get('status')!='publish' or post.get('type')!='post' or post.get('content',{}).get('protected') is not False:
  raise RuntimeError('not_an_unprotected_public_post')
 title=text(post['title']['rendered']);content=text(post['content']['rendered'])
 warnings=['transport_unencrypted_and_unauthenticated','current_eligibility_and_validity_unknown','historical_publication_date_not_offer_expiry']
 if not title or not content:warnings.append('empty_title_or_text_not_a_verified_offer')
 return {'native_id':str(post['id']),'program':'Loyals','partner_name':title or None,'source_url':API+'/'+str(post['id']),'publisher_canonical_url':post['link'],'source_published_at_gmt':post.get('date_gmt'),'source_modified_at_gmt':post.get('modified_gmt'),'observed_at':datetime.now(timezone.utc).isoformat(),'source_status':'public_http_observation_not_current_offer_verification','rates':normalize_rates(content),'conditions':lexical_conditions(content),'source_text':content,'raw':post,'warnings':warnings}


def loyals():
 report={'source':'loyals','transport':'http_unencrypted_and_unauthenticated','complete_api_collection':False,'pages':[],'records':[],'errors':[],'projection_issues':[]}
 with requests.Session() as s:
  s.trust_env=False
  r,raw=fetch(s,'http://loyals.ru/')
  if r.status_code!=200:raise RuntimeError('home_http_'+str(r.status_code))
  soup=BeautifulSoup(raw,'html.parser')
  linked=soup.select_one('link[rel="https://api.w.org/"]')
  if not linked or urlsplit(linked.get('href','')).hostname!='loyals.ru':raise RuntimeError('api_not_advertised_by_source')
  catalog_ids=sorted({int(parse_qs(urlsplit(a['href']).query)['p'][0]) for a in soup.select('a[href]') if parse_qs(urlsplit(a['href']).query).get('p',[''])[0].isdigit()})
  report['homepage_native_ids']=catalog_ids;report['advertised_api']=linked['href']
  seen=set();total=None;pages=None
  for page in range(1,11):
   time.sleep(1)
   url=API+f'?per_page=50&page={page}&orderby=id&order=asc&_fields=id,date_gmt,modified_gmt,link,title,content,excerpt,status,type,slug,categories,tags'
   r,raw=fetch(s,url)
   if r.status_code!=200:report['errors'].append({'page':page,'status':r.status_code});break
   current_total=int(r.headers['X-WP-Total']);current_pages=int(r.headers['X-WP-TotalPages'])
   if not (0<=current_total<=500 and 1<=current_pages<=10):raise RuntimeError('public_api_size_outside_diagnostic_bound')
   if total is not None and (total,pages)!=(current_total,current_pages):raise RuntimeError('pagination_total_changed')
   total,pages=current_total,current_pages
   values=json.loads(raw)
   if not isinstance(values,list) or len(values)>50:raise RuntimeError('not_a_bounded_post_list')
   report['pages'].append({'url':url,'status':r.status_code,'count':len(values),'total':total,'total_pages':pages,'sha256':hashlib.sha256(raw).hexdigest()})
   for post in values:
    if type(post.get('id')) is not int or post['id'] in seen:raise RuntimeError('invalid_or_duplicate_post_id')
    record=project_post(post);seen.add(post['id'])
    record['linked_from_homepage']=post['id'] in catalog_ids
    if not record['partner_name'] or not record['source_text']:report['projection_issues'].append({'native_id':post['id'],'reason':'empty_title_or_text_not_a_verified_offer'})
    report['records'].append(record)
   if page==pages:
    report['complete_api_collection']=len(seen)==total;break
  report['api_total']=total;report['accepted_posts']=len(seen)
  report['homepage_ids_missing_from_api']=sorted(set(catalog_ids)-seen)
  report['api_ids_not_linked_from_homepage']=sorted(seen-set(catalog_ids))
  report['completeness_scope']='Advertised public post collection only, not every benefit on every site page'
 return report


def uralsib():
 url='https://uralsib.ru/aktsii/privetstvennye-bally-rzhd-za-oformlenie-karty'
 report={'source':'uralsib','initial_url':url,'steps':[],'trust_scope':'temporary_requests_session_only','hostname_and_expiry_verification':True}
 with tempfile.TemporaryDirectory() as temp,requests.Session() as s:
  s.trust_env=False;r,ca=fetch(s,CA_URL)
  if r.status_code!=200 or hashlib.sha256(ca).hexdigest()!=CA_SHA:raise RuntimeError('official_ca_digest_changed')
  bundle=Path(temp)/'ca.pem';bundle.write_bytes(Path(certifi.where()).read_bytes()+b'\n'+ca)
  for i in range(3):
   r,raw=fetch(s,url,str(bundle));data,clean=document(raw.decode('utf8','replace'),r.status_code)
   step={'url':url,'http_status':r.status_code,'document':data};report['steps'].append(step)
   if r.status_code==200:
    if data['classification']=='content_candidate':(OUT/'uralsib.html').write_text(clean,encoding='utf8')
    break
   if r.status_code not in (301,302,303,307,308):break
   target=urljoin(url,r.headers.get('Location',''));u=urlsplit(target)
   if u.scheme!='https' or u.hostname!='uralsib.ru' or u.path!=urlsplit(url).path or u.query:raise RuntimeError('redirect_outside_exact_public_page')
   step['redirect']=target;url=target;time.sleep(1)
 return report


def fixture_checks():
 p={'id':1,'title':{'rendered':'Example'},'content':{'rendered':'','protected':False},'status':'publish','type':'post','link':'https://loyals.ru/example/'}
 r=project_post(p)
 assert r['rates']==[] and r['source_text']=='' and 'empty_title_or_text_not_a_verified_offer' in r['warnings']
 p['content']['rendered']='<p>Скидка 15% на меню.</p>';r=project_post(p)
 assert r['rates'][0]['value']=='15' and r['rates'][0]['evidence'] in r['source_text']
 assert r['source_published_at_gmt'] is None
 p['content']['protected']=True
 try:project_post(p)
 except RuntimeError:pass
 else:raise AssertionError('protected content accepted')
 print('Empty/nonempty/protected diagnostic fixtures passed')


def main():
 fixture_checks()
 report={'purpose':'verify_structured_public_access_not_production_integration','observed_at':datetime.now(timezone.utc).isoformat(),'results':{}}
 for name,func in [('loyals',loyals),('uralsib',uralsib)]:
  try:report['results'][name]=func()
  except Exception as exc:report['results'][name]={'error_type':type(exc).__name__,'error':str(exc)[:200]}
 report['code_sha256']=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
 (OUT/'structured.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
 print(json.dumps({'loyals_posts':report['results']['loyals'].get('accepted_posts'),'loyals_complete_api':report['results']['loyals'].get('complete_api_collection'),'uralsib_steps':len(report['results']['uralsib'].get('steps',[]))}))
if __name__=='__main__':main()
