"""Mir catalog uses JSON POST pagination; follow observed anonymous filter profiles."""
from __future__ import annotations
import asyncio,copy,json
from urllib.parse import urlsplit,urljoin,urlencode
from adapters import mir_detail
from normalized import content_hash
FIELDS={'filters','page','customFilter','idCompilation','sort','paymentType'}

def page_body(body:dict,page:int)->dict:
    if not isinstance(body,dict) or set(body)-FIELDS or not isinstance(page,int) or not 1<=page<=100:
        raise ValueError('Unexpected public filter body or page')
    if body.get('paymentType') not in ('sbp','mir'):
        raise ValueError('Unknown payment profile')
    result=copy.deepcopy(body);result['page']=page
    return result

async def walk_catalog(client,url,body,first):
    page_body(body,1)
    queue=[body['page']];seen=set();items={};expected=None;errors=[]
    while queue and len(seen)<60:
        page=queue.pop(0)
        if page in seen:continue
        seen.add(page)
        try:
            current=first if len(seen)==1 else await client.json(url,method='POST',
                data=json.dumps(page_body(body,page)),content_type='application/json')
            if not current.get('success'):raise RuntimeError('catalog_api_unsuccessful')
            data=current['data']
            if expected is None:expected=data.get('counter',{}).get('qt')
            for item in data.get('items',[]):
                if isinstance(item,dict) and item.get('xml_id') and item.get('url'):
                    items[item['xml_id']]=item
            for p in data.get('pagination',[]):
                n=p.get('page')
                if isinstance(n,int) and n not in seen and n not in queue:queue.append(n)
            if expected and len(items)>=expected:break
        except Exception as exc:
            errors.append({'phase':'catalog_page','page':page,'reason':str(exc) if isinstance(exc,RuntimeError) else type(exc).__name__})
    if expected!=len(items):errors.append({'phase':'catalog','reason':'count_not_reconciled','expected':expected,'observed':len(items)})
    return items,{'payment_type':body['paymentType'],'expected':expected,'observed':len(items),
                  'page_title':first.get('data',{}).get('pageTitle'),'pages_visited':len(seen),'errors':errors}

async def collect_mir(client,cfg,report,now,limit):
    captures=[];tasks=[]
    async def capture(resp):
        if urlsplit(resp.url).hostname!=client.host or not urlsplit(resp.url).path.endswith('/promo/filter-json') or resp.status!=200:return
        if resp.request.method!='POST':return
        try:
            body=json.loads(resp.request.post_data or '{}');page_body(body,1)
            captures.append((resp.url,body,await resp.json()))
        except Exception:return
    client.page.on('response',lambda r:tasks.append(asyncio.create_task(capture(r))))
    await client.read(cfg['url'],render=True);await client.page.wait_for_timeout(1500)
    if tasks:await asyncio.gather(*list(tasks),return_exceptions=True)
    # Observed public payment toggle; never opens a personal account or activates a benefit.
    mir_label=client.page.locator('.switch-bar-option-label_mir').first
    if await mir_label.count() and await mir_label.is_visible():
        try:
            await mir_label.click(timeout=4000);await client.page.wait_for_timeout(2000)
            if tasks:await asyncio.gather(*list(tasks),return_exceptions=True)
        except Exception:report['errors'].append({'phase':'catalog_profile','reason':'mir_toggle_not_loaded'})
    profiles={}
    for url,body,payload in captures:
        if body.get('page')==1 and body['paymentType'] not in profiles:profiles[body['paymentType']]=(url,body,payload)
    if not profiles:raise RuntimeError('mir_public_filter_request_not_observed')
    candidates={};summaries=[];memberships={}
    for payment,(url,body,payload) in profiles.items():
        items,summary=await walk_catalog(client,url,body,payload);summaries.append(summary)
        for identity,item in items.items():
            candidates[identity]=item;memberships.setdefault(identity,[]).append(payment)
        report['errors'].extend(summary['errors'])
    report['discovered']=len(candidates)
    report['region']='; '.join(str(x['page_title']) for x in summaries)
    report['coverage']=json.dumps({'catalogs':summaries,'unique_discovered':len(candidates),'detail_limit':limit},ensure_ascii=False)
    records=[]
    for identity,item in list(candidates.items())[:limit]:
        url=urljoin(cfg['url'],item['url']);slug=urlsplit(url).path.rstrip('/').split('/')[-1]
        endpoint='https://vamprivet.ru/api/configs/client/?'+urlencode({'code[]':'promoDetail','promoCode':slug})
        try:
            rs=mir_detail(await client.json(endpoint),url,now)
            if len(rs)!=1 or rs[0]['native_id']!=identity:raise RuntimeError('catalog_detail_identity_mismatch')
            r=rs[0];r['details']['retrieval_url']=endpoint;r['details']['catalog_profiles']=memberships[identity]
            r['details']['catalog_region']=report['region'];r['content_sha256']=content_hash(r);records.append(r)
        except Exception as exc:
            report['errors'].append({'phase':'detail','path':urlsplit(url).path,'reason':str(exc) if isinstance(exc,RuntimeError) else type(exc).__name__})
    if len(candidates)>limit:report['errors'].append({'phase':'detail','reason':'detail_limit_reached','limit':limit})
    return records
