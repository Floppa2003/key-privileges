"""Read Mir through its public browser UI, observing responses without API replay."""
from __future__ import annotations
import asyncio
import json
import time
from urllib.parse import urlsplit, urljoin
from bs4 import BeautifulSoup
from adapters import mir_detail
from normalized import content_hash

DETAIL_FIELDS = ('xml_id','url','name','owner','templates','desc','short_desc','startDate','endDate',
                 'promoBadges','freeFormBlock','promoIsCancelled','promoIsFinished','promoIsStarted',
                 'status','perPromoActionLimit','clientTimeLimit','prizeIsSuspended')


def public_detail_envelope(payload):
    obj = payload
    for key in ('data','content','promoDetail','promo','promoAction'):
        if not isinstance(obj,dict):return None
        obj=obj.get(key)
    if not isinstance(obj,dict) or not obj.get('xml_id') or not obj.get('url'):
        return None
    public = {key:obj[key] for key in DETAIL_FIELDS if key in obj}
    return {'data':{'content':{'promoDetail':{'promo':{'promoAction':public}}}}}


def catalog_snapshot(payload, payment, number):
    if payment not in ('sbp','mir') or not isinstance(number,int) or not 1 <= number <= 100:
        raise ValueError('unexpected_catalog_profile')
    if not payload.get('success'):
        raise ValueError('catalog_unsuccessful')
    data = payload['data']; count = data.get('counter',{}).get('qt')
    items = data.get('items')
    if not isinstance(count,int) or not 0 <= count <= 10000 or not isinstance(items,list) or len(items)>1000:
        raise ValueError('invalid_catalog_bounds')
    safe = []
    for item in items:
        url = item.get('url',''); parts = urlsplit(url)
        if not item.get('xml_id') or parts.scheme or parts.netloc or not parts.path.startswith('/promo/') or parts.query:
            raise ValueError('invalid_catalog_item')
        safe.append({k:item.get(k) for k in ('xml_id','url','name')})
    return {'payment_type':payment,'page':number,'items':safe,'expected':count,'page_title':data.get('pageTitle')}


CARDS = 'main [class*="__promos__"] a.promo-card-v2__link'

def dom_snapshot(raw, profile, payment, number):
    soup=BeautifulSoup(raw,'html.parser');items=[]
    native_ids={x['url']:x.get('xml_id') for x in profile.get('items',[])}
    for card in soup.select(CARDS):
        url=card.get('href','');parts=urlsplit(url)
        if parts.scheme or parts.netloc or parts.query or not parts.path.startswith('/promo/'):
            raise ValueError('invalid_public_card_url')
        owner=card.select_one('.promo-card-v2-owner__name')
        if owner is None:raise ValueError('public_card_partner_missing')
        items.append({'xml_id':native_ids.get(url),'url':url,'name':owner.get_text(' ',strip=True)})
    if not items or len(items)>50:raise ValueError('unexpected_visible_card_count')
    return {'payment_type':payment,'page':number,'items':items,'expected':profile['expected'],
            'page_title':profile['page_title']}


async def walk_ui_catalog(first, click_page):
    """A callback clicks a visible numbered control; it must return that page's snapshot."""
    items = {}; errors = []; visited = 0; current = first
    expected = first['expected']; payment = first['payment_type']
    for number in range(1,61):
        try:
            if number != 1:
                current = await click_page(number)
            if current['page'] != number or current['payment_type'] != payment:
                raise RuntimeError('unexpected_page_or_payment_response')
            if current['expected'] != expected:
                raise RuntimeError('catalog_count_changed_during_collection')
            visited += 1
            before = len(items)
            for item in current['items']:
                items[item['url']] = item
            if len(items) >= expected:
                break
            if len(items) == before:
                raise RuntimeError('pagination_did_not_add_unique_items')
        except Exception as exc:
            errors.append({'phase':'catalog_page','page':number,'reason':str(exc) if isinstance(exc,RuntimeError) else type(exc).__name__})
            break
    if len(items) != expected:
        errors.append({'phase':'catalog','reason':'count_not_reconciled','expected':expected,'observed':len(items)})
    return items, {'payment_type':payment,'expected':expected,'observed':len(items),
                   'page_title':first['page_title'],'pages_visited':visited,'errors':errors}


class BrowserResponses:
    """Keep only bounded, allowlisted public objects; never cookies/auth/client configs."""
    def __init__(self, page, host):
        self.page=page; self.host=host; self.catalogs=[]; self.details=[]; self.errors=[]; self.pending=set()
        self.changed=asyncio.Event()

    def observe(self, response):
        parts=urlsplit(response.url)
        if parts.hostname != self.host or not (parts.path.endswith('/promo/filter-json') or parts.path.rstrip('/')=='/api/configs/client'):
            return
        task=asyncio.create_task(self.capture(response)); self.pending.add(task)
        task.add_done_callback(self.pending.discard)

    async def capture(self, response):
        try:
            if response.status != 200:
                self.errors.append({'phase':'public_response','reason':f'http_{response.status}'})
                return
            raw=await response.text()
            if len(raw.encode()) > 6000000:
                raise ValueError('response_too_large')
            payload=json.loads(raw)
            if urlsplit(response.url).path.endswith('/promo/filter-json'):
                body=json.loads(response.request.post_data or '{}')
                self.catalogs.append(catalog_snapshot(payload,body.get('paymentType'),body.get('page')))
            else:
                public=public_detail_envelope(payload)
                if public:self.details.append(public)
        except Exception as exc:
            self.errors.append({'phase':'public_response','reason':type(exc).__name__})
        finally:self.changed.set()

    async def wait(self, collection, start, predicate, timeout=15):
        async def until():
            while True:
                self.changed.clear()
                for item in collection[start:]:
                    if predicate(item):return item
                await self.changed.wait()
        try:return await asyncio.wait_for(until(),timeout)
        except asyncio.TimeoutError:raise RuntimeError('expected_public_response_not_observed') from None

    async def close(self):
        self.page.remove_listener('response',self.observe)
        for task in self.pending:task.cancel()
        if self.pending:await asyncio.gather(*list(self.pending),return_exceptions=True)


async def read_matching_detail(client, captured, url, now, *, expected_id=None,
                               deadline=float('inf'), wait_timeout=15):
    """One repeat for a missing browser-owned response, within the source budget.

    The offset is reset before each navigation. Old observations cannot satisfy a
    new read. Authentication, rate limits and malformed responses do not retry.
    """
    for attempt in range(2):
        if time.monotonic() >= deadline:
            raise RuntimeError('source_time_budget_reached')
        offset=len(captured.details); error_offset=len(captured.errors)
        try:
            async with asyncio.timeout(max(.001,deadline-time.monotonic())):
                await client.read(url,render=True)
                data=await captured.wait(captured.details,offset,
                    lambda x:urlsplit(x['data']['content']['promoDetail']['promo']['promoAction']['url']).path==urlsplit(url).path,
                    timeout=min(wait_timeout,max(.001,deadline-time.monotonic())))
            obj=data['data']['content']['promoDetail']['promo']['promoAction']
            if expected_id is not None and str(obj['xml_id']) != str(expected_id):
                raise RuntimeError('catalog_detail_identity_mismatch')
            rs=mir_detail(data,url,now)
            if len(rs)!=1 or urlsplit(rs[0]['source_url']).path!=urlsplit(url).path:
                raise RuntimeError('catalog_detail_identity_mismatch')
            record=rs[0]
            record['details']['retrieval_attempts']=attempt+1
            record['content_sha256']=content_hash(record)
            return record
        except TimeoutError as exc:
            raise RuntimeError('source_time_budget_reached') from exc
        except RuntimeError as exc:
            if str(exc)!='expected_public_response_not_observed':
                raise
            response_errors=captured.errors[error_offset:]
            if response_errors:
                raise RuntimeError(response_errors[-1]['reason']) from exc
            if attempt==1:
                raise
            await asyncio.sleep(max(.5,client.request_interval))
    raise AssertionError('unreachable detail retry state')


async def collect_mir(client,cfg,report,now,limit):
    deadline=min(time.monotonic()+cfg.get("timeout_seconds",900)-50,
                 getattr(client,"deadline",float("inf"))-5)
    page=client.page; captured=BrowserResponses(page,client.host)
    page.on('response',captured.observe)
    candidates={}; memberships={}; summaries=[]; records=[]
    try:
        await client.read(cfg['url'],render=True)
        first=await captured.wait(captured.catalogs,0,lambda x:x['page']==1)
        default=first['payment_type']
        for payment in (default,'mir' if default=='sbp' else 'sbp'):
            if payment != default:
                offset=len(captured.catalogs)
                label=page.locator('.switch-bar-option-label_'+payment).first
                try:
                    await label.click(timeout=5000)
                    first=await captured.wait(captured.catalogs,offset,lambda x:x['payment_type']==payment and x['page']==1)
                except Exception as exc:
                    report['errors'].append({'phase':'catalog_profile','reason':str(exc) if isinstance(exc,RuntimeError) else type(exc).__name__})
                    continue
            await page.wait_for_function("""({selector,expected})=>{
                const actual=[...document.querySelectorAll(selector)].map(e=>e.getAttribute('href')).sort();
                return JSON.stringify(actual)===JSON.stringify(expected.sort());
            }""",arg={'selector':CARDS,'expected':[x['url'] for x in first['items']]},timeout=15000)
            first=dom_snapshot(await page.content(),first,payment,1)
            async def click(number):
                before=await page.locator(CARDS).evaluate_all('(els)=>els.map(e=>e.getAttribute("href"))')
                button=page.locator('[class*="_pagination_"]').get_by_role('button',name=str(number),exact=True)
                if await button.count()!=1 or not await button.is_visible():
                    raise RuntimeError('next_page_not_visible')
                await page.wait_for_timeout(int(client.request_interval*1000))
                await button.click(timeout=5000)
                await page.wait_for_function("""({number,before,selector,expectedLength})=>{
                    const active=[...document.querySelectorAll('[class*="_pagination_"] button')]
                      .some(e=>e.textContent.trim()===String(number)&&e.className.includes('selected'));
                    const links=[...document.querySelectorAll(selector)].map(e=>e.getAttribute('href'));
                    return active&&links.length===expectedLength&&JSON.stringify(links)!==JSON.stringify(before);
                }""",arg={'number':number,'before':before,'selector':CARDS,
                    'expectedLength':min(len(first['items']),first['expected']-(number-1)*len(first['items']))},timeout=15000)
                return dom_snapshot(await page.content(),first,payment,number)
            items,summary=await walk_ui_catalog(first,click)
            summaries.append(summary); report['errors'].extend(summary['errors'])
            for identity,item in items.items():
                candidates[identity]=item; memberships.setdefault(identity,[]).append(payment)
        report['discovered']=len(candidates)
        report['region']='; '.join(str(x['page_title']) for x in summaries)
        report['coverage']=json.dumps({'method':'anonymous_browser_UI_no_API_replay','catalogs':summaries,
            'unique_discovered':len(candidates),'detail_limit':limit},ensure_ascii=False)
        for identity,item in list(candidates.items())[:limit]:
            if time.monotonic()>=deadline:
                report['errors'].append({'phase':'detail','reason':'source_time_budget_reached','remaining':len(candidates)-len(records)})
                break
            url=urljoin(cfg['url'],item['url'])
            try:
                record=await read_matching_detail(client,captured,url,now,
                    expected_id=item.get('xml_id'),deadline=deadline)
                record['details'].update(catalog_profiles=memberships[identity],
                    catalog_region=report['region'],retrieval_method='anonymous_browser_response_no_API_replay')
                record['content_sha256']=content_hash(record);records.append(record)
            except Exception as exc:
                report['errors'].append({'phase':'detail','path':urlsplit(url).path,
                    'reason':str(exc) if isinstance(exc,RuntimeError) else type(exc).__name__})
        if len(candidates)>limit:report['errors'].append({'phase':'detail','reason':'detail_limit_reached','limit':limit})
        report['errors'].extend(captured.errors)
        return records
    finally:await captured.close()
