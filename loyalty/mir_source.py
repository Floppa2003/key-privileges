"""Compatibility helpers; production collection uses browser-owned responses only."""
from __future__ import annotations
import copy,json
from mir_ui import collect_mir
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

