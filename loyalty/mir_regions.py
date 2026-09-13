"""Mir regional UI collection with exact-ID, unchanged-terms deduplication."""
from __future__ import annotations
import copy
import json
from normalized import content_hash
from public_transport import PublicSource
from read_budget import within_source_budget
from mir_ui import collect_mir as collect_region, LISTING_REGIONS


def merge_regions(catalogs):
    records={};semantics={};seen=set();meta={'shared_observations_merged':0,'errors':[]}
    for key,rows in catalogs:
        if key not in LISTING_REGIONS or key in seen:raise ValueError('invalid_mir_region')
        seen.add(key);local=set()
        for raw in rows:
            row=copy.deepcopy(raw);identity=row['id']
            if identity in local:raise ValueError('duplicate_mir_native_record')
            local.add(identity)
            value=copy.deepcopy(row)
            for field in ('content_sha256','observed_at'):value.pop(field,None)
            for field in ('catalog_region','catalog_profiles','retrieval_attempts','retrieval_recovered_errors'):
                value['details'].pop(field,None)
            listing={'region_key':key,'region':LISTING_REGIONS[key]['label'],
                     'payment_types':row['details'].get('catalog_profiles',[]),
                     'page_titles':row['details'].get('catalog_region'),
                     'detail_checked':True}
            if identity in records:
                if semantics[identity]!=value:
                    meta['errors'].append({'phase':'regional_union','region':key,'native_id':row['native_id'],
                                           'reason':'regional_terms_conflict'})
                    continue
                records[identity]['details']['catalog_listings'].append(listing)
                meta['shared_observations_merged']+=1
            else:
                semantics[identity]=value;row['details']['catalog_listings']=[listing]
                row['warnings'].append('listing_region_is_not_a_guarantee_of_eligibility')
                records[identity]=row
    for row in records.values():row['content_sha256']=content_hash(row)
    return list(records.values()),meta


async def read_region(client,cfg,key,now,limit):
    report={'errors':[]}
    region_cfg={**cfg,'listing_region':key}
    if key=='msk':
        await within_source_budget(client,client.robots)
        rows=await within_source_budget(client,lambda:collect_region(client,region_cfg,report,now,limit))
    else:
        async with PublicSource(client.browser,cfg['url']) as regional:
            regional.deadline=getattr(client,'deadline',float('inf'))
            await within_source_budget(regional,regional.robots)
            rows=await within_source_budget(regional,lambda:collect_region(regional,region_cfg,report,now,limit))
    return rows,report


async def collect_mir(client,cfg,report,now,limit):
    catalogs=[];profiles=[];discovered_urls=set()
    for key in LISTING_REGIONS:
        try:
            rows,result=await read_region(client,cfg,key,now,500)
            catalogs.append((key,rows));discovered_urls.update(result['discovered_urls'])
            profiles.append({'key':key,'region':LISTING_REGIONS[key]['label'],
                             'normalized':len(rows),'discovered':result['discovered'],
                             'coverage':result['coverage']})
            report['errors'].extend({**e,'region':key} for e in result['errors'])
        except Exception as exc:
            report['errors'].append({'phase':'catalog_region','region':key,
                'reason':str(exc)[:180] if isinstance(exc,RuntimeError) else type(exc).__name__})
    records,meta=merge_regions(catalogs)
    report['errors'].extend(meta['errors'])
    # Counts of per-region URLs are deliberately not summed into unique offers.
    report['discovered']=len(discovered_urls)
    report['region']='; '.join(LISTING_REGIONS[key]['label'] for key,_ in catalogs)
    if len(records)>limit:
        report['errors'].append({'phase':'regional_union','reason':'detail_limit_reached','limit':limit})
    meta.update(method='two_public_UI_regions_with_independently_read_details',profiles=profiles,
                unique_normalized=len(records),unique_discovered=len(discovered_urls),detail_limit=limit,
                undiscovered_or_failed_details_reported_per_region=True)
    report['coverage']=json.dumps(meta,ensure_ascii=False)
    return records[:limit]
