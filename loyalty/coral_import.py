"""Public Coral sitemap/detail reads via Google; reuse the released HTML mapper.

The sitemap is discovery, not proof of active listing or user eligibility. No
source account, coupon issuance, raw script/session archive or provider credits.
"""
from __future__ import annotations
import hashlib, json, os, re, time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit
import xml.etree.ElementTree as ET
from bs4 import BeautifulSoup
import coral_catalog as c
from free_access_probe import sanitized_page
from normalized import content_hash, validate_offer
from sheets_normalized import prepare
from sheets_sync import Sheets

HOST='https://coralbonus.ru'
ROBOTS=HOST+'/robots.txt';SITEMAP=HOST+'/sitemap/'
STAGING='1nIH7seMlDR_3Hw1iOMQ0bnrD-iWspj73zvqCVT4dxW8'
TAB='coral_public_fetch';TAB_ID=2026091604;ROWS=4096
MARKER='CORAL_PUBLIC_IMPORT_V1';METHOD='google_import_public_html_lines'
MAX_READS=164;MAX_SECONDS=2700;MAX_DETAILS=160
OUT=Path('coral-import-output')


def now():return datetime.now(timezone.utc).isoformat()
def digest(value):return hashlib.sha256(json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()
def error(exc):
    s=str(exc)
    return s if re.fullmatch(r'(?:coral|cg)_[a-z_0-9]{1,100}',s) else type(exc).__name__
def instant(s):
    d=datetime.fromisoformat(s)
    if d.tzinfo is None:raise ValueError('cg_timezone')
    return d

def formula(url):
    if url not in (ROBOTS,SITEMAP,c.CLUB,c.PROMO):
        if url.startswith(c.CLUB):c.checked_url(url,'/klub-privilegii/',3)
        else:c.checked_url(url,'/promo/',2)
    return f'=IMPORTDATA("{url}";"¦";"en_US")'

def policy(raw):
    from protego import Protego
    if not re.search(r'^User-agent\s*:',raw,re.I|re.M) or '<html' in raw.lower() or 'captcha' in raw.lower():
        raise ValueError('cg_robots_unreadable')
    if not re.search(r'^Sitemap:\s*'+re.escape(SITEMAP)+r'\s*$',raw,re.M|re.I):raise ValueError('cg_sitemap_not_advertised')
    return Protego.parse(raw)

def sanitize(raw,url):
    if len(raw)>2000000:raise ValueError('cg_response_bound')
    if url==ROBOTS:
        policy(raw);return raw
    if url==SITEMAP:
        if '<!DOCTYPE' in raw.upper() or '<!ENTITY' in raw.upper():raise ValueError('cg_xml_entities')
        root=ET.fromstring(raw)
        if root.tag!='{http://www.sitemaps.org/schemas/sitemap/0.9}urlset':raise ValueError('cg_sitemap_shape')
        if len(root)>4000:raise ValueError('cg_sitemap_bound')
        urls=[n.text for n in root.findall('{*}url/{*}loc')]
        if any(not isinstance(u,str) or len(u)>800 or urlsplit(u).netloc!='coralbonus.ru' or urlsplit(u).scheme!='https' or urlsplit(u).query or urlsplit(u).fragment for u in urls):
            raise ValueError('cg_sitemap_url')
        return json.dumps(urls,ensure_ascii=False)
    soup=BeautifulSoup(raw,'html.parser')
    if not soup.html or not soup.select('h1'):raise ValueError('cg_empty_html')
    if re.search(r'captcha|access denied|доступ.{0,50}ограничен',str(soup.title),re.I):raise ValueError('cg_restriction')
    return sanitized_page(raw,url,canonical_identity=True)[0]

def checked(obs):
    if set(obs)!={'url','requested_at','calculated_at','formula_sha256','typed_lines_sha256','text','sha256'}:raise ValueError('cg_observation_shape')
    if obs['formula_sha256']!=digest(formula(obs['url'])) or obs['sha256']!=digest(obs['text']) or not re.fullmatch('[a-f0-9]{64}',obs['typed_lines_sha256']):raise ValueError('cg_observation_hash')
    if not 0<=(instant(obs['calculated_at'])-instant(obs['requested_at'])).total_seconds()<=180:raise ValueError('cg_observation_time')
    if not isinstance(obs['text'],str) or len(obs['text'])>2000000:raise ValueError('cg_observation_bound')
    return obs['text']

class Reader:
    """Isolated public scratch tab; literal formula, stable typed reads, cleanup."""
    def __init__(self,token,run_id,*,client=None,clock=time.monotonic,sleep=time.sleep,checkpoint=lambda:None):
        self.client=client or Sheets(STAGING,token);self.clock=clock;self.sleep=sleep;self.checkpoint=checkpoint
        self.run_id=run_id;self.calls=0;self.started=clock();self.next_at=0;self.delay=5;self.observations=[];self.cleanup_verified=False
        meta=self.client.request('GET',params={'fields':'spreadsheetId,properties(importFunctionsExternalUrlAccessAllowed),sheets.properties'})
        tabs=[s['properties'] for s in meta.get('sheets',[]) if s['properties']['sheetId']==TAB_ID]
        if meta['spreadsheetId']!=STAGING or not meta.get('properties',{}).get('importFunctionsExternalUrlAccessAllowed') or len(tabs)!=1 or tabs[0]['title']!=TAB or tabs[0]['gridProperties']['rowCount']!=ROWS or tabs[0]['gridProperties']['columnCount']!=4:raise ValueError('cg_workspace_identity')
        rows=self.snapshot()
        if len(rows[0])<3 or not rows[0][2].get('userEnteredValue',{}).get('stringValue','').startswith('idle:') or any(v.get('userEnteredValue') or v.get('effectiveValue') for row in rows[1:] for v in row):raise ValueError('cg_workspace_not_idle')
    def snapshot(self):
        data=self.client.request('GET',params={'ranges':f"'{TAB}'!A1:D{ROWS}",'includeGridData':'true','fields':'spreadsheetId,sheets(properties(sheetId,title),data(startRow,startColumn,rowData.values(userEnteredValue,effectiveValue)))'})
        sheets=data.get('sheets',[])
        if data['spreadsheetId']!=STAGING or len(sheets)!=1 or sheets[0]['properties']!={'sheetId':TAB_ID,'title':TAB}:raise ValueError('cg_workspace_response')
        blocks=sheets[0].get('data',[])
        if len(blocks)!=1 or blocks[0].get('startRow',0)!=0 or blocks[0].get('startColumn',0)!=0:raise ValueError('cg_workspace_offset')
        rows=[r.get('values',[]) for r in blocks[0].get('rowData',[])]
        if not rows or not rows[0] or rows[0][0].get('userEnteredValue',{}).get('stringValue')!=MARKER:raise ValueError('cg_workspace_marker')
        return rows
    def clear(self,generation):
        self.cleanup_verified=False
        self.client.request('POST',':batchUpdate',json={'requests':[{'updateCells':{'range':{'sheetId':TAB_ID,'startRowIndex':1,'endRowIndex':ROWS,'startColumnIndex':0,'endColumnIndex':4},'rows':[],'fields':'userEnteredValue'}},{'updateCells':{'start':{'sheetId':TAB_ID,'rowIndex':0,'columnIndex':2},'rows':[{'values':[{'userEnteredValue':{'stringValue':generation}}]}],'fields':'userEnteredValue'}}]})
        for _ in range(5):
            rows=self.snapshot()
            if len(rows[0])<3 or rows[0][2].get('userEnteredValue',{}).get('stringValue')!=generation:raise ValueError('cg_generation')
            if not any(v.get('userEnteredValue') or v.get('effectiveValue') for row in rows[1:] for v in row):
                self.cleanup_verified=True;return
            self.sleep(1)
        raise ValueError('cg_cleanup_failed')
    def read(self,url):
        f=formula(url)
        if self.calls>=MAX_READS or self.clock()-self.started>MAX_SECONDS-80:raise ValueError('cg_budget')
        generation=f'{self.run_id}:{self.calls+1}';self.clear(generation)
        self.sleep(max(0,self.next_at-self.clock()));requested=now();self.calls+=1;self.cleanup_verified=False
        self.next_at=self.clock()+self.delay;previous=None;until=self.clock()+65
        try:
            self.client.request('POST',':batchUpdate',json={'requests':[{'updateCells':{'start':{'sheetId':TAB_ID,'rowIndex':1,'columnIndex':0},'rows':[{'values':[{'userEnteredValue':{'formulaValue':f}}]}],'fields':'userEnteredValue'}}]})
            while self.clock()<until:
                rows=self.snapshot()
                if rows[0][2].get('userEnteredValue',{}).get('stringValue')!=generation:raise ValueError('cg_generation')
                if len(rows)<2 or not rows[1]:self.sleep(2);continue
                if rows[1][0].get('userEnteredValue',{}).get('formulaValue')!=f:raise ValueError('cg_formula_changed')
                lines=[];waiting=False
                for i,row in enumerate(rows[1:]):
                    if any(v.get('userEnteredValue') or v.get('effectiveValue') for v in row[1:]):raise ValueError('cg_import_wide')
                    cell=row[0] if row else {};v=cell.get('effectiveValue',{})
                    if i and cell.get('userEnteredValue'):raise ValueError('cg_extra_input')
                    if 'errorValue' in v:waiting=True;break
                    if v and set(v)!={'stringValue'}:raise ValueError('cg_import_type_coercion')
                    lines.append(v.get('stringValue',''))
                if waiting or not any(lines):previous=None;self.sleep(3);continue
                if len(lines)>=ROWS-2 or sum(map(len,lines))>2000000:raise ValueError('cg_import_bound')
                h=digest(lines)
                if h==previous:
                    safe=sanitize('\n'.join(lines),url)
                    obs={'url':url,'requested_at':requested,'calculated_at':now(),'formula_sha256':digest(f),'typed_lines_sha256':h,'text':safe,'sha256':digest(safe)}
                    checked(obs);self.observations.append(obs);self.checkpoint();return obs
                previous=h;self.sleep(2)
            raise ValueError('cg_import_timeout_or_error')
        finally:self.clear('idle:'+self.run_id)

def candidates(club,promo,sitemap):
    cats={e['url']:e['title'] for e in c.listing(checked(club),'coral')}
    promotions=c.listing(checked(promo),'coral_promo');urls=json.loads(checked(sitemap))
    if not isinstance(urls,list) or len(urls)>4000 or len(urls)!=len(set(urls)):raise ValueError('cg_sitemap_duplicate_or_bound')
    out=[]
    for url in urls:
        parent=url.rsplit('/',2)[0]+'/'
        if parent not in cats:continue
        c.checked_url(url,'/klub-privilegii/',3)
        out.append(('coral',{'url':url,'category':cats[parent],'parent_url':parent}))
    out.extend(('coral_promo',dict(e,parent_url=c.PROMO)) for e in promotions)
    if not out or len(out)>MAX_DETAILS:raise ValueError('cg_candidate_bound')
    return out,len(cats),len(promotions)

def map_detail(obs,sid,entry,observed_at):
    raw=checked(obs)
    if obs['url']!=entry['url']:raise ValueError('cg_detail_identity')
    soup=BeautifulSoup(raw,'html.parser')
    # Ordinary souvenir-store merchandise is not a loyalty offer. Keep an
    # explicit exclusion, never turn purchase prices into cashback or discounts.
    if sid=='coral' and soup.select('.product-purchase-box:not(.referal)') and not soup.select('.product-purchase-box.referal'):
        return None
    row=c.detail(raw,sid,entry,observed_at,{'method':METHOD,'identity':'source_canonical_url','fetched_at':obs['calculated_at'],'origin_status':None,'import_sha256':obs['sha256']})
    row['details']['google_import']={'formula_sha256':obs['formula_sha256'],'typed_lines_sha256':obs['typed_lines_sha256'],'origin_http_status':None,'origin_cache_age_verified':False,'discovery':'current_sitemap_in_current_category' if sid=='coral' else 'current_promo_index','active_catalogue_listing_verified':sid=='coral_promo','account_used':False}
    row['warnings']+=['google_import_not_original_http_response','origin_cache_age_not_exposed']
    if sid=='coral':row['warnings'].append('sitemap_presence_does_not_prove_active_catalogue_listing')
    row['content_sha256']=content_hash(row);validate_offer(row);return row

def collect(reader,run_id,observed_at):
    results={s:{'records':[],'errors':[],'excluded':[],'discovered':0} for s in ('coral','coral_promo')};counts={}
    try:
        rules=policy(checked(reader.read(ROBOTS)))
        rate=rules.request_rate('LoyaltyCatalogResearchBot');reader.delay=max(5,rules.crawl_delay('LoyaltyCatalogResearchBot') or 0,rate.seconds/rate.requests if rate else 0)
        if reader.delay>60:raise ValueError('cg_source_delay_bound')
        def read(url):
            if not rules.can_fetch(url,'LoyaltyCatalogResearchBot'):raise ValueError('cg_robots_disallow')
            return reader.read(url)
        club=read(c.CLUB);promo=read(c.PROMO);sitemap=read(SITEMAP)
        targets,cat_count,promo_count=candidates(club,promo,sitemap);counts={'categories':cat_count,'promo_index':promo_count}
        for sid,_ in targets:results[sid]['discovered']+=1
        for sid,entry in targets:
            try:
                obs=read(entry['url']);row=map_detail(obs,sid,entry,observed_at)
                if row is None:results[sid]['excluded'].append(entry['url'])
                else:results[sid]['records'].append(row)
            except Exception as exc:
                results[sid]['errors'].append({'url':entry['url'],'reason':error(exc)})
                if not getattr(reader,'cleanup_verified',True) or error(exc)=='cg_budget':break
    except Exception as exc:
        for v in results.values():v['errors'].append({'phase':'discovery','reason':error(exc)})
    return summarize(results,counts,run_id,observed_at)

def summarize(results,counts,run_id,observed_at):
    rows=[];reports=[]
    for sid,v in results.items():
        rows+=v['records'];n=len(v['records']);unresolved=v['discovered']-n-len(v['excluded'])
        meta={'method':METHOD,'scope':'sitemap_pages_in_current_categories' if sid=='coral' else 'current_promo_index',**counts,'candidates':v['discovered'],'accepted':n,'excluded_store_products':v['excluded'],'unresolved':unresolved,'full_program_catalogue_verified':False,'source_account_used':False,'origin_http_status_exposed':False,'origin_cache_age_verified':False}
        reports.append({'source_id':sid,'name':'CoralBonus — '+('Клуб' if sid=='coral' else 'Акции'),'root':c.CLUB if sid=='coral' else c.PROMO,'status':('partial' if v['errors'] or unresolved else 'ok') if n else 'failed','discovered':v['discovered'],'normalized':n,'failed':len(v['errors']),'errors':v['errors'],'coverage':json.dumps(meta,ensure_ascii=False),'region':None,'observed_at':observed_at})
    return {'schema_version':2,'run_id':run_id,'observed_at':observed_at,'records':rows,'sources':reports}

def validate_bundle(folder,run_id,commit,clock):
    folder=Path(folder);b=json.loads((folder/'normalized.json').read_text());a=json.loads((folder/'evidence.json').read_text())
    if a['run_id']!=run_id or b['run_id']!=run_id or a['commit']!=commit or a['cleanup_verified'] is not True or a['scrapingant_credits']!=0 or a.get('source_account_used') is not False or b.get('observed_at')!=a['started_at']:raise ValueError('cg_bundle_identity')
    start,end=instant(a['started_at']),instant(a['finished_at'])
    if not start<=end<=clock or (clock-end).total_seconds()>900 or (end-start).total_seconds()>3000:raise ValueError('cg_bundle_time')
    observations=a['observations'];lookup={o['url']:o for o in observations}
    if len(lookup)!=len(observations) or len(lookup)>MAX_READS:raise ValueError('cg_bundle_duplicate')
    last=start
    for o in observations:
        checked(o)
        if not last<=instant(o['requested_at'])<=instant(o['calculated_at'])<=end:raise ValueError('cg_bundle_observation_time')
        last=instant(o['calculated_at'])
    expected=[];counts={};results={sid:{'records':[],'errors':[],'excluded':[],'discovered':0} for sid in ('coral','coral_promo')}
    supplied={r['source_id']:r for r in b.get('sources',[])}
    if len(b.get('sources',[]))!=2 or set(supplied)!=set(results):raise ValueError('cg_source_reports')
    targets=[]
    if all(u in lookup for u in (ROBOTS,c.CLUB,c.PROMO,SITEMAP)):
        rules=policy(checked(lookup[ROBOTS]));targets,ncats,npromo=candidates(lookup[c.CLUB],lookup[c.PROMO],lookup[SITEMAP])
        counts={'categories':ncats,'promo_index':npromo}
        controls=(c.CLUB,c.PROMO,SITEMAP)
        if not all(rules.can_fetch(u,'LoyaltyCatalogResearchBot') for u in controls):raise ValueError('cg_policy_binding')
        for sid,_ in targets:results[sid]['discovered']+=1
        allowed={u for u in (ROBOTS,c.CLUB,c.PROMO,SITEMAP)}|{e['url'] for s,e in targets}
        if set(lookup)-allowed:raise ValueError('cg_undiscovered_read')
        for sid,entry in targets:
            obs=lookup.get(entry['url'])
            if not obs:continue
            if not rules.can_fetch(obs['url'],'LoyaltyCatalogResearchBot'):raise ValueError('cg_policy_binding')
            try:r=map_detail(obs,sid,entry,b['observed_at'])
            except ValueError:continue
            if r:
                expected.append(r);results[sid]['records'].append(r)
            else:results[sid]['excluded'].append(entry['url'])
    for sid,r in supplied.items():
        urls={e['url'] for source,e in targets if source==sid}
        errors=r.get('errors')
        if not isinstance(errors,list) or len(errors)>MAX_READS:raise ValueError('cg_error_report_shape')
        for item in errors:
            if not isinstance(item,dict) or not isinstance(item.get('reason'),str) or len(item['reason'])>110:raise ValueError('cg_error_report_shape')
            if 'url' in item and (set(item)!={'url','reason'} or item['url'] not in urls):raise ValueError('cg_error_report_source')
            if 'url' not in item and (set(item)!={'phase','reason'} or item['phase']!='discovery' or targets):raise ValueError('cg_error_report_phase')
        results[sid]['errors']=errors
    rebuilt=summarize(results,counts,run_id,b['observed_at'])
    if rebuilt['sources']!=b['sources']:raise ValueError('cg_coverage_reconstruction')
    expected.sort(key=lambda r:0 if r['source_id']=='coral' else 1)
    if expected!=b['records']:raise ValueError('cg_bundle_reconstruction')
    prepare(b);return b

def main():
    OUT.mkdir(exist_ok=True);run_id=os.environ['GITHUB_RUN_ID']+':'+os.environ['GITHUB_RUN_ATTEMPT'];started=now();reader=None
    audit={'run_id':run_id,'commit':os.environ['GITHUB_SHA'],'started_at':started,'observations':[],'cleanup_verified':False,'scrapingant_credits':0,'source_account_used':False}
    def checkpoint():
        if reader:audit.update(observations=reader.observations,cleanup_verified=reader.cleanup_verified)
        temp=OUT/'evidence.tmp';temp.write_text(json.dumps(audit,ensure_ascii=False));temp.replace(OUT/'evidence.json')
    try:
        reader=Reader(os.environ.get('GOOGLE_ACCESS_TOKEN',''),run_id,checkpoint=checkpoint);b=collect(reader,run_id,started);reader.clear('idle:'+run_id)
        audit.update(observations=reader.observations,cleanup_verified=reader.cleanup_verified,finished_at=now(),import_requests=reader.calls)
        (OUT/'normalized.json').write_text(json.dumps(b,ensure_ascii=False));(OUT/'evidence.json').write_text(json.dumps(audit,ensure_ascii=False))
        validate_bundle(OUT,run_id,os.environ['GITHUB_SHA'],datetime.now(timezone.utc))
        with open(os.environ['GITHUB_OUTPUT'],'a') as f:f.write('has_payload=true\n')
        print(json.dumps({'records':len(b['records']),'sources':[(r['source_id'],r['normalized'],r['status']) for r in b['sources']],'scrapingant_credits':0}))
    except Exception as exc:
        audit.update(finished_at=now(),error=error(exc))
        if reader:audit.update(observations=reader.observations,cleanup_verified=reader.cleanup_verified)
        (OUT/'evidence.json').write_text(json.dumps(audit,ensure_ascii=False));print('Coral import failed: '+error(exc));raise SystemExit(1)
if __name__=='__main__':main()
