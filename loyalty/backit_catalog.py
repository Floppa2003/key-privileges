"""Complete Backit inventory traversal with explicit exclusions and read limits."""
import json, math
from backit_source import SOURCE, ROOT, MAX_CARDS, EXCLUDED_NAME, ExcludedOffer, inventory, parse_detail

async def collect(client,cfg,report,observed_at,limit):
    from read_budget import within_source_budget, stops_catalog
    if cfg['id']!=SOURCE or cfg['url']!=ROOT:raise ValueError('backit_config_identity')
    bound=cfg.get('detail_limit',limit)
    if not isinstance(bound,int) or not 1<=bound<=MAX_CARDS:raise ValueError('backit_detail_bound')
    client.request_interval=max(.5,client.request_interval)
    async def read(url):return await within_source_budget(client,lambda:client.read(url))
    seed=await read(ROOT);cards,total,size=inventory(seed,1);seen={c['url'] for c in cards}
    pages=math.ceil(total/size)
    for page in range(2,pages+1):
        # Query shape observed from the site's ordinary next-page button.
        current,nt,ns=inventory(await read(ROOT+'?page='+str(page)),page)
        if nt!=total or ns!=size or any(c['url'] in seen for c in current):raise RuntimeError('backit_inventory_drift')
        cards.extend(current);seen.update(c['url'] for c in current)
    if len(seen)!=total:raise RuntimeError('backit_incomplete_inventory')
    eligible=[c for c in cards if not EXCLUDED_NAME.search(c['name'])]
    excluded=[{'url':c['url'],'reason':'financial_or_acquisition_ad'} for c in cards if EXCLUDED_NAME.search(c['name'])]
    if len(eligible)>bound:raise RuntimeError('backit_detail_limit_exceeded')
    rows=[]
    for card in eligible:
        try:rows.append(parse_detail(await read(card['url']),card,observed_at))
        except ExcludedOffer as exc:excluded.append({'url':card['url'],'reason':str(exc)})
        except Exception as exc:
            report['errors'].append({'phase':'detail','url':card['url'],'reason':str(exc)[:140] if isinstance(exc,(RuntimeError,ValueError)) else type(exc).__name__})
            if stops_catalog(exc):break
    report['discovered']=len(rows)+len(report['errors'])
    report['coverage']=json.dumps({'scope':'public_ru_cashback_shop_inventory','listed':total,'inventory_pages':pages,
        'parsed':len(rows),'excluded':excluded,'details_attempted':len(rows)+len(excluded)-(total-len(eligible))+len(report['errors']),
        'all_inventory_accounted':len(rows)+len(excluded)+len(report['errors'])==total,
        'source_local_detail_limit':bound,'product_level_marketplace_catalogue_included':False},ensure_ascii=False)
    return rows
