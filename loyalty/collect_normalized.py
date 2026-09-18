"""Collect the registered public sources; each source has its own coverage report."""
from __future__ import annotations
import argparse
import asyncio
import csv
import hashlib
import json
import os
import re
import time
from datetime import datetime,timezone
from pathlib import Path
from urllib.parse import urljoin,urlsplit,urlencode
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright
from adapters import extract,next_state,s7_catalog,s7_detail,mir_detail,PROGRAMS,node_text,ural_catalog,key_catalog,mir_page_url
from normalized import VERSION,make_offer,content_hash,validate_offer,text
from public_transport import PublicSource
from source_selection import select_sources
from mir_regions import collect_mir
from reviewed_pdf import extract_rgo_pdf
from t2_regions import collect_t2
from ural_ui import collect_ural
from announcements import collect_announcements
from selection_source import collect_selection
from tier_sources import collect_utair_tiers, collect_ural_tiers
from read_budget import within_source_budget, stops_catalog
from known_rules import collect_known_rules
from utair_documents import collect_documents
from recovered_sources import collect_recovered
from utair_support import collect_utair
from hse_alumni import collect_hse
from alfa_access import collect_access as collect_alfa_access


def error_record(exc,phase,url=''):
    reason=str(exc) if isinstance(exc,RuntimeError) else type(exc).__name__
    marker=re.search(r'ERR_[A-Z_]+',str(exc))
    if marker:reason=marker[0]
    return {'phase':phase,'path':urlsplit(url).path,'reason':reason[:180]}


async def collect_s7(client,cfg,report,now,limit):
    raw=await within_source_budget(client,lambda:client.read(cfg['url']))
    if 'initialState' not in raw:raw=await within_source_budget(client,lambda:client.read(cfg['url'],render=True))
    candidates=s7_catalog(next_state(raw));report['discovered']=len(candidates)
    report['coverage']='all_unique_codes_in_public_initialState' if len(candidates)<=limit else 'detail_limit_reached'
    records=[]
    for index,entry in enumerate(candidates[:limit]):
        try:
            state=next_state(await within_source_budget(client,lambda:client.read(entry['url'])))
            rs=s7_detail(state,entry['url'],now)
            for r in rs:
                r['details']['catalog_benefit']=entry['catalog_benefit']
                r['details']['category_codes']=entry['category_codes']
                if entry['catalog_benefit'] and entry['catalog_benefit']!=r['benefit_text']:
                    r['warnings'].append('catalog_and_detail_wording_differ_preserved_separately')
                r['content_sha256']=content_hash(r)
            records.extend(rs)
        except Exception as exc:
            report['errors'].append(error_record(exc,'detail',entry['url']))
            if stops_catalog(exc):
                report['errors'][-1]['remaining']=len(candidates[:limit])-index
                break
    return records


async def collect_rgo(client,cfg,report,now,limit):
    raw=await client.read(cfg['url'],render=True)
    page=client.page;exhausted=False
    for _ in range(30):
        count=await page.locator('.loyalty-card').count()
        more=page.locator('.pagination-more .btn').first
        if not await more.count() or not await more.is_visible():exhausted=True;break
        await more.click(timeout=5000);await page.wait_for_timeout(1500)
        if await page.locator('.loyalty-card').count()==count:
            report['errors'].append({'phase':'catalog','reason':'load_more_did_not_grow'});break
    soup=BeautifulSoup(await page.content(),'html.parser')
    urls=list(dict.fromkeys(urljoin(cfg['url'],x['href']) for x in soup.select('.loyalty-card__link[href]')))
    report['discovered']=len(urls);report['coverage']='load_more_exhausted' if exhausted else 'pagination_not_exhausted'
    records=[]
    for index,url in enumerate(urls[:limit]):
        try:
            if urlsplit(url).path.lower().endswith('.pdf'):
                data=await within_source_budget(client,lambda:client.read_pdf(url))
                rows=await within_source_budget(client,lambda:asyncio.to_thread(extract_rgo_pdf,data,url,now))
                records.extend(rows)
                if rows[0]['details']['document_errors']:
                    report['errors'].append({'phase':'document_text','path':urlsplit(url).path,'errors':rows[0]['details']['document_errors']})
            else:
                records.extend(extract('rgo',await within_source_budget(client,lambda:client.read(url)),url,now))
        except Exception as exc:
            report['errors'].append(error_record(exc,'detail',url))
            if stops_catalog(exc):
                report['errors'][-1]['remaining']=len(urls[:limit])-index
                break
    if len(urls)>limit:report['coverage']='detail_limit_reached'
    return records


async def collect_key(report,now):
    # Reuse the existing reviewed collector, never relabel the checked-in old snapshot.
    proc=await asyncio.create_subprocess_exec('node','key/refresh.mjs',stdout=asyncio.subprocess.PIPE,stderr=asyncio.subprocess.PIPE)
    stdout,stderr=await asyncio.wait_for(proc.communicate(),timeout=100)
    if proc.returncode:raise RuntimeError('key_live_refresh_failed')
    data=json.loads(Path('key/catalog.json').read_text())
    fetched=datetime.fromisoformat(data['fetched_at'].replace('Z','+00:00'))
    if abs((datetime.now(timezone.utc)-fetched).total_seconds())>120:raise RuntimeError('key_snapshot_not_fresh')
    records=key_catalog(data,now)
    report['discovered']=len(records);report['coverage']='live_existing_KEY_collector:'+data['source_mode']
    if not data['remote_ok']:report['errors'].append({'phase':'remote_overrides','reason':'remote_unavailable_base_catalog_only'})
    return records


async def one(browser,cfg,now,limit):
    report={'source_id':cfg['id'],'name':cfg['name'],'root':cfg['url'],'status':'failed',
            'discovered':0,'normalized':0,'failed':0,'coverage':'not_collected',
            'region':None,'errors':[],'observed_at':now}
    records=[];client=None
    deadline=time.monotonic()+source_budget(cfg)
    try:
        if cfg['mode']=='key':records=await collect_key(report,now)
        elif cfg['mode']=='recovered':records=await collect_recovered(cfg,report,now,limit)
        elif cfg['id']=='utair':records=await collect_utair(cfg,report,now,limit)
        elif cfg['id']=='alfa_only_partner_offers':await collect_alfa_access(cfg,report)
        else:
            async with PublicSource(browser,cfg['url']) as client:
                client.deadline=deadline
                if cfg['mode'] not in ('t2','mir','selection'):await client.robots()
                mode=cfg['mode']
                if mode=='hse':records=await collect_hse(client,cfg,report,now,limit)
                elif mode=='s7':records=await collect_s7(client,cfg,report,now,limit)
                elif mode=='ural':records=await collect_ural(client,cfg,report,now,limit)
                elif mode=='rgo':records=await collect_rgo(client,cfg,report,now,limit)
                elif mode=='mir':records=await collect_mir(client,cfg,report,now,limit)
                elif mode=='t2':records=await collect_t2(client,cfg,report,now,limit)
                elif mode=='announcements':records=await collect_announcements(client,cfg,report,now,limit)
                elif mode=='selection':records=await collect_selection(client,cfg,report,now,limit)
                elif mode=='utair_tiers':records=await collect_utair_tiers(client,cfg,report,now,limit)
                elif mode=='ural_tiers':records=await collect_ural_tiers(client,cfg,report,now,limit)
                elif mode=='known_rules':records=await collect_known_rules(client,cfg,report,now,limit)
                elif mode=='utair_documents':records=await collect_documents(client,cfg,report,now,limit)
                elif mode=='html':
                    raw=await client.read(cfg['url'],render=True)
                    records=extract(cfg['id'],raw,cfg['url'],now)
                    if not records:
                        raw=await client.read(cfg['url'],render=True)
                        records=extract(cfg['id'],raw,cfg['url'],now)
                    if not records:raise RuntimeError('no_offer_blocks_found')
                    report['discovered']=len(records);report['coverage']=cfg.get('coverage_scope','all_matched_blocks_on_public_page')
                else:
                    await client.read(cfg['url'],render=True)
                    report['coverage']='page_accessible_adapter_not_yet_implemented'
                    report['errors'].append({'phase':'extraction','reason':'no_reviewed_adapter'})
        for r in records:validate_offer(r)
        # One physical document can create several bounded evidence parts.
        report['discovered_items']=report['discovered']
        report['discovered']=max(report['discovered'],len(records))
        report['normalized']=len(records)
        report['status']='partial' if report['errors'] else 'ok' if records else 'no_normalized_records'
    except Exception as exc:
        phase='robots' if client is not None and client.policy is None else 'source'
        report['errors'].append(error_record(exc,phase,cfg['url']))
        report['status']='failed' if not records else 'partial'
        report['normalized']=len(records)
    if client is not None and getattr(client,'robots_info',None):
        report['robots']=client.robots_info
    report['failed']=len(report['errors'])
    print(json.dumps({k:report[k] for k in ('source_id','status','discovered','normalized','failed')},ensure_ascii=False),flush=True)
    return report,records


def source_budget(cfg):
    budget=cfg.get("timeout_seconds",900 if cfg.get("id")=="mir" else 420)
    if type(budget) is not int or not 30<=budget<=1000:
        raise ValueError("invalid_source_timeout")
    return budget


async def bounded_source(factory,sem,timeout=420):
    # A queued source has not started its network budget yet.
    async with sem:
        return await asyncio.wait_for(factory(),timeout=timeout)


async def main():
    p=argparse.ArgumentParser();p.add_argument('--limit',type=int,default=200);p.add_argument('--out',default='loyalty-output');p.add_argument('--sources',default='',help='Comma-separated registered source IDs; blank retains the full scheduled scope');args=p.parse_args()
    if not 1<=args.limit<=500:p.error('limit must be 1..500')
    cfgs=select_sources(json.loads(Path(__file__).with_name('sources_normalized.json').read_text()),args.sources)
    now=datetime.now(timezone.utc).isoformat();run_id=os.getenv('GITHUB_RUN_ID',now)+':'+os.getenv('GITHUB_RUN_ATTEMPT','1')
    out=Path(args.out);out.mkdir(parents=True,exist_ok=True)
    async with async_playwright() as p:
        browser=await p.chromium.launch();sem=asyncio.Semaphore(4)
        async def guarded(cfg):
            budget=source_budget(cfg)
            try:return await bounded_source(lambda:one(browser,cfg,now,args.limit),sem,timeout=budget)
            except asyncio.TimeoutError:
                return {'source_id':cfg['id'],'name':cfg['name'],'root':cfg['url'],'status':'failed',
                    'discovered':0,'normalized':0,'failed':1,'coverage':'source_timeout',
                    'region':None,'errors':[{'phase':'source','reason':f'{budget}_second_bound'}],'observed_at':now},[]
        try:results=await asyncio.gather(*(guarded(cfg) for cfg in cfgs))
        finally:await browser.close()
    reports=[r for r,_ in results];records=[r for _,rs in results for r in rs]
    bundle={'schema_version':2,'run_id':run_id,'observed_at':now,'records':records,'sources':reports}
    (out/'normalized.json').write_text(json.dumps(bundle,ensure_ascii=False,indent=2),encoding='utf8')
    with (out/'offers.jsonl').open('w',encoding='utf8') as f:
        for r in records:f.write(json.dumps(r,ensure_ascii=False)+'\n')
    manifest={str(f):hashlib.sha256(f.read_bytes()).hexdigest() for f in Path('loyalty').glob('*.py')}
    (out/'code_hashes.json').write_text(json.dumps(manifest,indent=2))
    (out/'coverage.json').write_text(json.dumps(reports,ensure_ascii=False,indent=2),encoding='utf8')
    lines=['# Public loyalty collection','',f'Run: {run_id}',f'Observed: {now}','',
           '| Source | Records | Discovered | Status | Coverage |','|---|---:|---:|---|---|']
    lines.extend(f"| {r['source_id']} | {r['normalized']} | {r['discovered']} | {r['status']} | {r['coverage']} |" for r in reports)
    lines.extend(['','Counts include membership plans and campaigns, not only unique partners. Source publication is not proof of user eligibility. Missing observations never expire or delete stored offers.'])
    summary='\n'.join(lines)+'\n';(out/'summary.md').write_text(summary,encoding='utf8')
    if os.getenv('GITHUB_STEP_SUMMARY'):
        with open(os.environ['GITHUB_STEP_SUMMARY'],'a') as f:f.write(summary)
    if not records:raise SystemExit(2)

if __name__=='__main__':asyncio.run(main())
