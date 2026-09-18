"""Inventory public rendered categories only; two bounded free-reader shards.

The parent is a recent checked Google root/sitemap snapshot. No detail pages,
account session, coupon issuance, publication, paid plan or new provider.
"""
from __future__ import annotations
import argparse,hashlib,json,os,time
from datetime import datetime,timezone
from pathlib import Path
from free_access_probe import FreeReader,ProbeError,read_policy,sanitized_page,now
from public_transport import robots_document,check_response
from protego import Protego
import coral_catalog as c
import coral_import as cg

MAX_CREDITS=222

def sha(raw):return hashlib.sha256(raw).hexdigest()
def save(path,data):Path(path).write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf8')

def parent_inputs(folder,clock):
    path=Path(folder)/'evidence.json'
    if path.stat().st_size>8000000:raise ValueError('cb_parent_size')
    a=json.loads(path.read_text());end=cg.instant(a['finished_at'])
    if not a.get('cleanup_verified') or not 0<=(clock-end).total_seconds()<=86400:raise ValueError('cb_parent_age_or_cleanup')
    matches={}
    for obs in a['observations']:
        if obs['url'] in (c.CLUB,cg.SITEMAP):
            if obs['url'] in matches:raise ValueError('cb_parent_duplicate')
            if not cg.instant(a['started_at'])<=cg.instant(obs['requested_at'])<=cg.instant(obs['calculated_at'])<=end:raise ValueError('cb_parent_time')
            matches[obs['url']]=cg.checked(obs)
    if set(matches)!={c.CLUB,cg.SITEMAP}:raise ValueError('cb_parent_missing')
    categories=c.listing(matches[c.CLUB],'coral')
    if len(categories)>20:raise ValueError('cb_category_bound')
    sitemap=json.loads(matches[cg.SITEMAP]);names={x['url'] for x in categories}
    if len(sitemap)!=len(set(sitemap)):raise ValueError('cb_sitemap_duplicate')
    candidates=sorted(u for u in sitemap if u.rsplit('/',2)[0]+'/' in names)
    return categories,candidates,{'run_id':a['run_id'],'commit':a['commit'],'observed_at':a['started_at'],
        'evidence_sha256':sha(path.read_bytes()),'sitemap_is_not_active_listing':True}

def assemble(categories,candidates,pages,parent):
    expected={x['url']:x['title'] for x in categories};seen=set();found={};errors=[];merchandise=0
    for page in pages:
        url=page['url']
        if url not in expected or url in seen:raise ValueError('cb_category_identity')
        seen.add(url)
        if page.get('error'):errors.append({'url':url,'reason':page['error']});continue
        if page.get('origin_http_status')!=200 or page.get('final_url')!=url:raise ValueError('cb_response_identity')
        offers,count=c.category_cards(page['html'],{'url':url,'title':expected[url]},expected)
        merchandise+=count
        for offer in offers:found.setdefault(offer['url'],[]).append(url)
    missing=sorted(set(expected)-seen)
    return {'scope':'rendered_category_inventory_not_detail_terms','parent':parent,'category_count':len(categories),
        'categories_read':len(pages)-len(errors),'unattempted':missing,'errors':errors,
        'complete':not errors and not missing,'interactive_offer_urls':sorted(found),
        'excluded_merchandise_boxes':merchandise,'sitemap_candidate_urls':candidates,
        'interactive_not_sitemap':sorted(set(found)-set(candidates)),
        'sitemap_not_observed_interactive':sorted(set(candidates)-set(found)),
        'missing_from_sitemap_does_not_mean_missing_from_sheet':True,
        'source_account_used':False,'details_read':0,'coupons_issued':0}

def collect(folder,key,*,reader_factory=FreeReader,sleep=time.sleep):
    out=Path(folder);out.mkdir(parents=True,exist_ok=True)
    cats,candidates,parent=parent_inputs(out/'parent',datetime.now(timezone.utc));pages=[];shards=[]
    report={'run_id':os.environ['GITHUB_RUN_ID']+':'+os.environ['GITHUB_RUN_ATTEMPT'],'commit':os.environ['GITHUB_SHA'],
        'started_at':now(),'parent':parent,'credit_ceiling':MAX_CREDITS,'shards':shards,'pages':pages}
    def checkpoint():
        report['finished_at']=now();save(out/'report.json',report)
        save(out/'inventory.json',assemble(cats,candidates,pages,parent))
    try:
        for number,part in enumerate((cats[::2],cats[1::2])):
            if not part:continue
            reader=reader_factory(key,[{'url':c.CLUB}],max_credits=111,max_requests=12)
            shard={'number':number,'reserved_credits':0,'known_charged_credits':0};shards.append(shard)
            try:
                reader.preflight();policy_meta={};status,raw,_=read_policy(reader,cg.ROBOTS,policy_meta)
                rules,_=robots_document(status,raw);policy=Protego.parse(rules)
                shard.update(policy_status=status,policy_text=rules,policy_meta=policy_meta)
                rate=policy.request_rate('LoyaltyCatalogResearchBot')
                delay=max(1,policy.crawl_delay('LoyaltyCatalogResearchBot') or 0,rate.seconds/rate.requests if rate else 0)
                if delay>30:raise ProbeError('crawl_delay_exceeds_budget')
                for entry in part:
                    url=c.checked_url(entry['url'],'/klub-privilegii/',2)
                    page={'url':url,'started_at':now()};pages.append(page)
                    try:
                        if not policy.can_fetch(url,'LoyaltyCatalogResearchBot'):raise ProbeError('robots_disallow')
                        sleep(delay);reader.allowed.add(url)
                        status,raw,cost=reader.read(url,browser=True);page.update(origin_http_status=status,credits=cost)
                        check_response(status,raw)
                        clean,meta=sanitized_page(raw,url);page.update(meta)
                        # Full owned-page mapper must succeed before accepting an empty category.
                        c.category_cards(clean,entry,{x['url']:x['title'] for x in cats})
                        page.update(html=clean,sha256=sha(clean.encode()))
                    except Exception as exc:page['error']=c.safe_error(exc)
                    finally:
                        page['finished_at']=now();shard.update(reserved_credits=reader.reserved,known_charged_credits=reader.known_charged_credits)
                        checkpoint()
                    if reader.halted:raise ProbeError('reader_stopped')
            finally:
                shard.update(reserved_credits=reader.reserved,known_charged_credits=reader.known_charged_credits)
                if sum(s['reserved_credits'] for s in shards)>MAX_CREDITS:raise ValueError('cb_global_budget')
    except Exception as exc:report['terminal_error']=c.safe_error(exc)
    finally:checkpoint()
    result=json.loads((out/'inventory.json').read_text())
    print(json.dumps({'categories_read':result['categories_read'],'complete':result['complete'],
        'offers':len(result['interactive_offer_urls']),'reserved_credits':sum(s['reserved_credits'] for s in shards)}))
    return result

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--out',default='coral-browser-output');a=p.parse_args()
    try:collect(a.out,os.environ['SCRAPINGANT_API_KEY'])
    except Exception as exc:
        print('Browser inventory failed ('+type(exc).__name__+'); not certified complete.');raise SystemExit(1)
