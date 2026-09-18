"""Bounded practical-gap checks; no full recrawl, accounts or provider credits.

RZD retries only prior transient failures after fresh catalogue membership.
Coral reads category inventories, not every detail or linked regulation.
Outputs are public-source evidence, never an export of the discount workbook.
"""
from __future__ import annotations
import argparse,json,os,re,shutil
from datetime import datetime,timezone
from pathlib import Path
from urllib.parse import urljoin
import rzd_import_catalog as rz
import rzd_import_collect as rc
import rzd_catalogue_cards as cards
import coral_import as cg
import coral_catalog as coral
from sheets_normalized import prepare

BOT='LoyaltyCatalogResearchBot'
RETRYABLE={'rzd_import_error_cell','rzd_import_calculation_timeout'}
MAX_TARGETS=8
MAX_CATEGORIES=30
MAX_AGE=7*86400

def load(path):
    path=Path(path)
    if path.stat().st_size>25000000:raise ValueError('frontier_file_bound')
    return json.loads(path.read_text())

def save(path,value):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf8')

def targets(parent):
    """Parent must pass the original RZD bundle validator before transport."""
    selected={}
    for row in parent['records']:
        d=row.get('details',{})
        if d.get('detail_failure') not in RETRYABLE:continue
        if row['source_id']!='rzd' or row['record_kind']!='source_observation':raise ValueError('frontier_parent_kind')
        cards.validate_record(row)
        url=rz.checked_url(d['discovered_detail_url'])
        entry={'url':url,'catalogue_url':d['catalogue_preview']['catalogue_url'],'parent_record_id':row['id']}
        if url in selected and selected[url]!=entry:raise ValueError('frontier_parent_duplicate')
        selected[url]=entry
    if len(selected)>MAX_TARGETS:raise ValueError('frontier_target_bound')
    return list(selected.values())

def parent_bundle(folder,clock):
    audit=load(Path(folder)/'evidence.json')
    end=rz.instant(audit['finished_at'])
    if not 0<=(clock-end).total_seconds()<=MAX_AGE:raise ValueError('frontier_parent_age')
    return rc.validate_bundle(folder,run_id=audit['run_id'],commit=audit['commit'],clock=end)

def rzd_collect(parent,reader,run_id,observed_at):
    selected=targets(parent);rows=[];errors=[];members={};pages={}
    # No failed targets means no source traffic, including robots/home.
    if selected:
        rules=rc.policy_from(reader.read(rz.ROBOTS,'robots'))
        rate=rules.request_rate(BOT)
        reader.delay=max(20,rules.crawl_delay(BOT) or 0,rate.seconds/rate.requests if rate else 0)
        if reader.delay>60:raise ValueError('rzd_source_delay_bound')
        def read(url,kind):
            if not rules.can_fetch(url,BOT):raise ValueError('rzd_policy_disallow')
            return reader.read(url,kind)
        home=rz.checked_observation(read(rz.HOME,'home'))
        if not re.search('РЖД.*Бонус',home[0]['text'],re.I) or rz.ROOT not in {urljoin(rz.HOME,c['text'].strip()) for c in home[1:]}:
            raise ValueError('rzd_home_catalogue_link_missing')
        for entry in selected:
            page=entry['catalogue_url']
            if page not in pages:
                try:
                    obs=read(page,'catalog_cards');pages[page]=cards.previews(obs)
                except Exception as exc:
                    pages[page]={};errors.append({'phase':'catalogue','url':page,'reason':rc.reason(exc)})
                    if not getattr(reader,'cleanup_verified',True):raise
            members[entry['url']]=entry['url'] in pages[page]
        for entry in selected:
            url=entry['url']
            if not members[url]:
                errors.append({'phase':'detail','url':url,'reason':'rzd_target_not_in_fresh_parent_page'});continue
            try:rows.append(rz.detail(read(url,'detail'),observed_at))
            except Exception as exc:
                errors.append({'phase':'detail','url':url,'reason':rc.reason(exc)})
                # An ambiguous cleanup, quota or identity failure cannot continue.
                if not getattr(reader,'cleanup_verified',True):raise
    report={'source_id':'rzd','name':'РЖД Бонус — точечное повторное чтение','root':rz.ORIGINAL,
        'status':('partial' if errors else 'ok') if rows or not selected else 'failed',
        'discovered':len(selected),'normalized':len(rows),'failed':len(errors),'errors':errors,
        'region':None,'observed_at':observed_at,'coverage':json.dumps({
            'scope':'transient_detail_retry_not_full_catalogue','parent_run_id':parent['run_id'],
            'parent_observed_at':parent['observed_at'],'selected':selected,'fresh_membership':members,
            'full_program_catalogue_verified':False,'source_account_used':False,
            'origin_http_status_exposed':False,'origin_cache_age_verified':False,
            'unchosen_parent_records_refreshed':False},ensure_ascii=False)}
    out={'schema_version':2,'run_id':run_id,'observed_at':observed_at,'records':rows,'sources':[report]}
    prepare(out);return out

class RecordingReader:
    def __init__(self,reader):self.reader=reader;self.events=[]
    @property
    def delay(self):return self.reader.delay
    @delay.setter
    def delay(self,value):self.reader.delay=value
    @property
    def cleanup_verified(self):return self.reader.cleanup_verified
    def read(self,url,kind):
        event={'url':url,'kind':kind};self.events.append(event)
        try:
            result=self.reader.read(url,kind);event['observation']=result;return result
        except Exception as exc:
            event['error']=rc.reason(exc);raise

class ReplayReader:
    def __init__(self,events):self.events=iter(events);self.used=0;self.cleanup_verified=True;self.delay=20
    def read(self,url,kind):
        event=next(self.events);self.used+=1
        if event.get('url')!=url or event.get('kind')!=kind:raise ValueError('frontier_replay_order')
        if set(event)=={'url','kind','error'}:raise ValueError(event['error'])
        if set(event)!={'url','kind','observation'}:raise ValueError('frontier_replay_shape')
        obs=event['observation'];rz.checked_observation(obs)
        if obs['url']!=url or obs['kind']!=kind:raise ValueError('frontier_replay_identity')
        return obs

def validate_rzd(folder,run_id,commit,clock):
    folder=Path(folder);a=load(folder/'evidence.json');b=load(folder/'normalized.json')
    if (a.get('run_id')!=run_id or a.get('commit')!=commit or a.get('cleanup_verified') is not True
        or a.get('source_account_used') is not False or a.get('provider_credits')!=0):raise ValueError('frontier_identity')
    start,end=rz.instant(a['started_at']),rz.instant(a['finished_at'])
    if not start<=end<=clock or (clock-end).total_seconds()>900 or (end-start).total_seconds()>1800:raise ValueError('frontier_time')
    parent=parent_bundle(folder/'parent',start)
    if rz.digest(parent)!=a['parent_sha256']:raise ValueError('frontier_parent_hash')
    events=a['events']
    if len(events)>2+2*MAX_TARGETS:raise ValueError('frontier_events_bound')
    last=start
    for event in events:
        if 'observation' in event:
            obs=event['observation'];first,finish=rz.instant(obs['requested_at']),rz.instant(obs['calculated_at'])
            if not last<=first<=finish<=end:raise ValueError('frontier_observation_time')
            last=finish
    replay=ReplayReader(events);expected=rzd_collect(parent,replay,run_id,a['started_at'])
    if replay.used!=len(events) or expected!=b:raise ValueError('frontier_reconstruction')
    prepare(b);return b

def rzd_main(args):
    run_id=os.environ['GITHUB_RUN_ID']+':'+os.environ['GITHUB_RUN_ATTEMPT'];commit=os.environ['GITHUB_SHA']
    out=Path(args.out);out.mkdir(parents=True,exist_ok=True);start=rc.now()
    parent=parent_bundle(args.parent,rz.instant(start))
    for name in ('normalized.json','evidence.json'):
        (out/'parent').mkdir(exist_ok=True);shutil.copyfile(Path(args.parent)/name,out/'parent'/name)
    reader=None;recording=None
    try:
        reader=rc.ImportReader(os.environ['GOOGLE_ACCESS_TOKEN'],run_id)
        recording=RecordingReader(reader);bundle=rzd_collect(parent,recording,run_id,start)
        reader.close()
        audit={'run_id':run_id,'commit':commit,'started_at':start,'finished_at':rc.now(),
            'cleanup_verified':reader.cleanup_verified,'events':recording.events,'parent_sha256':rz.digest(parent),
            'source_account_used':False,'provider_credits':0,'import_requests':reader.calls}
        save(out/'evidence.json',audit);save(out/'normalized.json',bundle)
        validate_rzd(out,run_id,commit,datetime.now(timezone.utc))
        print(json.dumps({'mode':'rzd_targeted_verified','records':len(bundle['records']),
            'selected':len(targets(parent)),'imports':reader.calls}))
    finally:
        if reader and not reader.cleanup_verified:reader.close()

def coral_inventory(reader):
    rules=cg.policy(cg.checked(reader._read_once(cg.ROBOTS)))
    rate=rules.request_rate(BOT);reader.delay=max(5,rules.crawl_delay(BOT) or 0,rate.seconds/rate.requests if rate else 0)
    if reader.delay>60:raise ValueError('cg_source_delay_bound')
    def read(url):
        if not rules.can_fetch(url,BOT):raise ValueError('cg_robots_disallow')
        return reader._read_once(url)
    root=read(coral.CLUB);sitemap=read(cg.SITEMAP)
    categories=coral.listing(cg.checked(root),'coral');names={c['url']:c['title'] for c in categories}
    if len(categories)>MAX_CATEGORIES:raise ValueError('cg_category_inventory_bound')
    urls=json.loads(cg.checked(sitemap))
    if len(urls)!=len(set(urls)):raise ValueError('cg_sitemap_duplicate_or_bound')
    candidates={u for u in urls if u.rsplit('/',2)[0]+'/' in names}
    listed={};entries=[];errors=[]
    for category in categories:
        try:
            observation=read(category['url'])
            found,excluded=coral.category_cards(cg.checked(observation),category,names)
            entries.append({'category':category,'offers':found,'excluded_merchandise':excluded,
                'observed_at':observation['calculated_at']})
            for item in found:listed.setdefault(item['url'],[]).append(category['url'])
        except Exception as exc:
            errors.append({'url':category['url'],'reason':cg.error(exc)})
            if not getattr(reader,'cleanup_verified',True):raise
    return {'scope':'current_category_inventories_not_all_detail_conditions',
        'categories':entries,'category_count':len(categories),'errors':errors,'complete':not errors,
        'interactive_offer_urls':sorted(listed),'sitemap_candidate_urls':sorted(candidates),
        'interactive_not_sitemap':sorted(set(listed)-candidates),
        'sitemap_not_observed_interactive':sorted(candidates-set(listed)),
        'sitemap_only_may_be_merchandise_or_unread_categories':True,'source_account_used':False,'provider_credits':0}

def coral_main(args):
    run_id=os.environ['GITHUB_RUN_ID']+':'+os.environ['GITHUB_RUN_ATTEMPT'];out=Path(args.out);out.mkdir(parents=True,exist_ok=True)
    reader=cg.Reader(os.environ['GOOGLE_ACCESS_TOKEN'],run_id);start=cg.now()
    try:
        inventory=coral_inventory(reader)
        reader.clear('idle:'+run_id)
        save(out/'inventory.json',inventory)
        save(out/'evidence.json',{'run_id':run_id,'commit':os.environ['GITHUB_SHA'],'started_at':start,
            'finished_at':cg.now(),'observations':reader.observations,'cleanup_verified':reader.cleanup_verified})
        print(json.dumps({'mode':'coral_inventory','categories':len(inventory['categories']),
            'errors':len(inventory['errors']),'offers':len(inventory['interactive_offer_urls']),'imports':reader.calls}))
    finally:
        if not reader.cleanup_verified:reader.clear('idle:'+run_id)

def main():
    p=argparse.ArgumentParser();p.add_argument('mode',choices=['rzd','coral','validate-rzd']);p.add_argument('--parent');p.add_argument('--out',required=True);a=p.parse_args()
    if a.mode=='rzd':rzd_main(a)
    elif a.mode=='coral':coral_main(a)
    else:validate_rzd(a.out,os.environ['GITHUB_RUN_ID']+':'+os.environ['GITHUB_RUN_ATTEMPT'],os.environ['GITHUB_SHA'],datetime.now(timezone.utc))

if __name__=='__main__':
    try:main()
    except Exception as exc:
        print('Practical frontier failed ('+type(exc).__name__+'); no completion claim.')
        raise SystemExit(1)
