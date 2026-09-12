"""Ural's own anonymous browser response, reconciled against same-ID page blocks."""
from __future__ import annotations
import asyncio,json
from urllib.parse import urlsplit,parse_qs
from adapters import extract,ural_catalog
from normalized import content_hash
ROOT='https://www.uralairlines.ru/partners/'


def reconcile_partners(partners,api_records,html_records):
    expected=['partner_'+str(x['id']) for x in partners]
    if len(set(expected))!=len(expected):raise ValueError('duplicate_catalog_partner_id')
    api={r['native_id']:r for r in api_records};html={r['native_id']:r for r in html_records}
    if len(api)!=len(api_records) or len(html)!=len(html_records) or set(api)-set(expected):
        raise ValueError('duplicate_or_foreign_partner_record')
    records=[];errors=[]
    for identity in expected:
        record=api.get(identity) or html.get(identity)
        if record is None:
            errors.append({'phase':'detail','native_id':identity,'reason':'empty_partner_terms'})
            continue
        record['details']['retrieval_method']='browser_catalog_response' if identity in api else 'same_native_id_HTML_fallback'
        record['content_sha256']=content_hash(record);records.append(record)
    return records,errors


async def collect_ural(client,cfg,report,now,limit):
    snapshots=[];pending=set();capture_errors=[]
    async def capture(response):
        try:
            if response.status!=200:return
            raw=await response.text()
            if len(raw.encode())>6000000:raise ValueError('response_too_large')
            data=json.loads(raw)
            if not isinstance(data.get('partners'),list) or len(data['partners'])>1000:
                raise ValueError('invalid_partner_array')
            snapshots.append({key:data[key] for key in ('partners','category') if key in data})
        except Exception as exc:capture_errors.append({'phase':'public_response','reason':type(exc).__name__})
    def observe(response):
        u=urlsplit(response.url);q=parse_qs(u.query)
        if u.hostname=='www.uralairlines.ru' and u.path=='/partners/' and q.get('ajax')==['partners'] and response.request.method=='GET':
            task=asyncio.create_task(capture(response));pending.add(task);task.add_done_callback(pending.discard)
    page=client.page;page.on('response',observe)
    try:
        await client.read(ROOT,render=True)
        await page.wait_for_selector('li[id^="partner_"]',timeout=15000)
        if pending:await asyncio.gather(*list(pending),return_exceptions=True)
        html=extract('ural',await page.content(),ROOT,now)
        if snapshots:
            data=snapshots[-1];records,errors=reconcile_partners(data['partners'],ural_catalog(data,ROOT,now),html)
            report['discovered']=len(data['partners']);report['coverage']='all_native_ids_in_observed_anonymous_browser_response'
            report['errors'].extend(errors)
        else:
            records=html;report['discovered']=len(html)
            report['coverage']='all_rendered_partner_blocks_total_API_count_not_observed'
            report['errors'].append({'phase':'coverage','reason':'catalog_total_not_independently_observed'})
        report['errors'].extend(capture_errors)
        if len(records)>limit:
            report['errors'].append({'phase':'detail','reason':'detail_limit_reached','limit':limit})
        return records[:limit]
    finally:
        page.remove_listener('response',observe)
        for task in pending:task.cancel()
        if pending:await asyncio.gather(*list(pending),return_exceptions=True)
