"""Collect the registered public sources; each source has its own coverage report."""
from __future__ import annotations
import argparse
import asyncio
import csv
import hashlib
import json
import os
import re
from datetime import datetime,timezone
from pathlib import Path
from urllib.parse import urljoin,urlsplit,urlencode
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright
from adapters import extract,next_state,s7_catalog,s7_detail,mir_detail,PROGRAMS,node_text,ural_catalog,key_catalog,mir_page_url
from normalized import VERSION,make_offer,content_hash,validate_offer,text
from public_transport import PublicSource
from mir_source import collect_mir
from reviewed_pdf import extract_rgo_pdf
from t2_source import collect_t2


def error_record(exc,phase,url=''):
    reason=str(exc) if isinstance(exc,RuntimeError) else type(exc).__name__
    marker=re.search(r'ERR_[A-Z_]+',str(exc))
    if marker:reason=marker[0]
    return {'phase':phase,'path':urlsplit(url).path,'reason':reason[:180]}


async def collect_s7(client,cfg,report,now,limit):
    raw=await client.read(cfg['url'])
    if 'initialState' not in raw:raw=await client.read(cfg['url'],render=True)
    candidates=s7_catalog(next_state(raw));report['discovered']=len(candidates)
    report['coverage']='all_unique_codes_in_public_initialState' if len(candidates)<=limit else 'detail_limit_reached'
    records=[]
    for entry in candidates[:limit]:
        try:
            state=next_state(await client.read(entry['url']))
            rs=s7_detail(state,entry['url'],now)
            for r in rs:
                r['details']['catalog_benefit']=entry['catalog_benefit']
                r['details']['category_codes']=entry['category_codes']
                if entry['catalog_benefit'] and entry['catalog_benefit']!=r['benefit_text']:
                    r['warnings'].append('catalog_and_detail_wording_differ_preserved_separately')
                r['content_sha256']=content_hash(r)
            records.extend(rs)
        except Exception as exc:report['errors'].append(error_record(exc,'detail',entry['url']))
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
    for url in urls[:limit]:
        try:
            if urlsplit(url).path.lower().endswith('.pdf'):
                records.extend(extract_rgo_pdf(await client.read_pdf(url),url,now))
            else:
                records.extend(extract('rgo',await client.read(url),url,now))
        except Exception as exc:report['errors'].append(error_record(exc,'detail',url))
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
    records=[]
    try:
        if cfg['mode']=='key':records=await collect_key(report,now)
        else:
            async with PublicSource(browser,cfg['url']) as client:
                await client.robots()
                mode=cfg['mode']
                if mode=='s7':records=await collect_s7(client,cfg,report,now,limit)
                elif mode=='ural':
                    try:
                        data=await client.json(cfg['url'])
                        records=ural_catalog(data,cfg['url'],now)
                        report['discovered']=len(data['partners'])
                        missing=set('partner_'+str(p['id']) for p in data['partners'])-set(r['native_id'] for r in records)
                        for native in sorted(missing):report['errors'].append({'phase':'detail','native_id':native,'reason':'empty_partner_terms'})
                        report['coverage']='public_partner_array'
                    except Exception as exc:
                        report['errors'].append(error_record(exc,'api',cfg['url']))
                        root='https://www.uralairlines.ru/partners/'
                        await client.read(root,render=True)
                        await client.page.wait_for_selector('li[id^="partner_"]',timeout=12000)
                        records=extract('ural',await client.page.content(),root,now)
                        report['coverage']='browser_partner_blocks_api_fallback'
                        report['discovered']=len(records)
                    if not records:raise RuntimeError('no_partner_terms_found')
                elif mode=='rgo':records=await collect_rgo(client,cfg,report,now,limit)
                elif mode=='mir':records=await collect_mir(client,cfg,report,now,limit)
                elif mode=='t2':records=await collect_t2(client,cfg,report,now,limit)
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
        report['normalized']=len(records)
        report['status']='partial' if report['errors'] else 'ok' if records else 'no_normalized_records'
    except Exception as exc:
        report['errors'].append(error_record(exc,'source',cfg['url']))
        report['status']='failed' if not records else 'partial'
        report['normalized']=len(records)
    report['failed']=len(report['errors'])
    print(json.dumps({k:report[k] for k in ('source_id','status','discovered','normalized','failed')},ensure_ascii=False),flush=True)
    return report,records


async def bounded_source(factory,sem,timeout=420):
    # A queued source has not started its network budget yet.
    async with sem:
        return await asyncio.wait_for(factory(),timeout=timeout)


async def main():
    p=argparse.ArgumentParser();p.add_argument('--limit',type=int,default=200);p.add_argument('--out',default='loyalty-output');args=p.parse_args()
    if not 1<=args.limit<=500:p.error('limit must be 1..500')
    cfgs=json.loads(Path(__file__).with_name('sources_normalized.json').read_text())
    now=datetime.now(timezone.utc).isoformat();run_id=os.getenv('GITHUB_RUN_ID',now)+':'+os.getenv('GITHUB_RUN_ATTEMPT','1')
    out=Path(args.out);out.mkdir(parents=True,exist_ok=True)
    async with async_playwright() as p:
        browser=await p.chromium.launch();sem=asyncio.Semaphore(4)
        async def guarded(cfg):
            try:return await bounded_source(lambda:one(browser,cfg,now,args.limit),sem)
            except asyncio.TimeoutError:
                return {'source_id':cfg['id'],'name':cfg['name'],'root':cfg['url'],'status':'failed',
                    'discovered':0,'normalized':0,'failed':1,'coverage':'source_timeout',
                    'region':None,'errors':[{'phase':'source','reason':'420_second_bound'}],'observed_at':now},[]
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
