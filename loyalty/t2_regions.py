"""Two public T2 listing regions, deduplicated only on identical native-ID evidence."""
from __future__ import annotations
import asyncio
import copy
import json
from urllib.parse import urlsplit
from normalized import content_hash
from public_transport import PublicSource
from read_budget import within_source_budget
from t2_source import REGIONS,catalog_records


def regional_comparison(record):
    """Compare extracted source semantics, excluding only observation provenance."""
    value=copy.deepcopy(record)
    for field in ('id','source_url','locator','content_sha256','observed_at'):
        value.pop(field,None)
    value['details'].pop('region',None)
    value['details'].pop('catalog_regions',None)
    return value


def merge_regional_catalogs(catalogs,observed_at):
    """Same native ID and same terms: one row, several observed listing regions.

    A conflicting region does not inherit the primary region's conditions. Keep
    primary evidence and report the conflict for a source-specific variant review.
    """
    records={}; comparable={}; seen_regions=set()
    meta={'method':'anonymous_regional_catalog_union','profiles':[],
          'shared_observations_merged':0,'errors':[]}
    for key,data in catalogs:
        if key not in REGIONS or key in seen_regions:
            raise ValueError('unexpected_or_duplicate_t2_region')
        seen_regions.add(key)
        rows=catalog_records(data,observed_at,region_key=key)
        profile={'key':key,**REGIONS[key],'observed':len(rows),'accepted':0}
        meta['profiles'].append(profile)
        for row in rows:
            native=row['native_id']; fields=regional_comparison(row)
            listing={'key':key,**REGIONS[key]}
            if native in records:
                if comparable[native]!=fields:
                    meta['errors'].append({'phase':'regional_union','region':key,
                        'native_id':native,'reason':'regional_terms_conflict'})
                    continue
                records[native]['details']['catalog_regions'].append(listing)
                meta['shared_observations_merged']+=1
            else:
                comparable[native]=fields
                row['details']['catalog_regions']=[listing]
                row['warnings'].append('listing_region_is_not_a_guarantee_of_eligibility')
                records[native]=row
            profile['accepted']+=1
    for row in records.values():row['content_sha256']=content_hash(row)
    meta['unique_discovered']=len(records)
    return list(records.values()),meta


async def read_catalog_snapshot(client,root):
    """Observe only this landing page's public GET response in its own context."""
    snapshots=[];pending=[]
    host=urlsplit(root).hostname
    async def capture(resp):
        if resp.status!=200:return
        body=await resp.text()
        if len(body.encode())>6000000:raise RuntimeError('t2_response_too_large')
        snapshots.append(json.loads(body))
    def observe(resp):
        parts=urlsplit(resp.url)
        if parts.hostname==host and parts.path=='/api/loyalty/offers' and resp.request.method=='GET':
            pending.append(asyncio.create_task(capture(resp)))
    client.page.on('response',observe)
    try:
        await within_source_budget(client,lambda:client.read(root,render=True))
        for _ in range(12):
            if snapshots:break
            await client.page.wait_for_timeout(500)
        if pending:await asyncio.gather(*pending)
        if not snapshots:raise RuntimeError('t2_public_catalog_response_not_observed')
        return snapshots[-1]
    finally:
        client.page.remove_listener('response',observe)
        for task in pending:
            if not task.done():task.cancel()
        if pending:await asyncio.gather(*pending,return_exceptions=True)


async def read_region_catalog(client,key):
    if key not in REGIONS:raise ValueError('unknown_t2_region')
    root=REGIONS[key]['source_url']
    if key=='msk':
        await within_source_budget(client,client.robots)
        return await read_catalog_snapshot(client,root)
    async with PublicSource(client.browser,root) as regional:
        regional.deadline=getattr(client,'deadline',float('inf'))
        await within_source_budget(regional,regional.robots)
        return await read_catalog_snapshot(regional,root)


async def collect_t2(client,cfg,report,now,limit):
    catalogs=[]
    for key in REGIONS:
        try:
            data=await read_region_catalog(client,key)
            # Validate before merging so one malformed region cannot drop another.
            catalog_records(data,now,region_key=key)
            catalogs.append((key,data))
        except Exception as exc:
            report['errors'].append({'phase':'catalog_region','region':key,
                'reason':str(exc)[:180] if isinstance(exc,RuntimeError) else type(exc).__name__})
    records,meta=merge_regional_catalogs(catalogs,now)
    report['errors'].extend(meta['errors'])
    report['discovered']=len(records)
    report['region']='; '.join(REGIONS[key]['region'] for key,_ in catalogs)
    if len(records)>limit:
        report['errors'].append({'phase':'regional_union','reason':'detail_limit_reached','limit':limit})
    meta['detail_limit']=limit
    report['coverage']=json.dumps(meta,ensure_ascii=False)
    return records[:limit]

