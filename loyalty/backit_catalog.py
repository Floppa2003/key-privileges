"""Complete Backit inventory traversal with explicit exclusions and read limits."""
import json, math, re
from urllib.parse import urlsplit
from bs4 import BeautifulSoup
from playwright.async_api import TimeoutError as BrowserTimeout
from backit_source import SOURCE, ROOT, MAX_CARDS, EXCLUDED_NAME, ExcludedOffer, inventory, parse_detail

# Backit's server-rendered cards arrive before the client-side paginator. Waiting
# for a fixed sleep (or just DOMContentLoaded) is not a completeness criterion.
INVENTORY_READY = """expected => {
  const nodes = document.querySelectorAll('.mu-pagination');
  if (nodes.length !== 1) return false;
  const p = nodes[0], total = Number(p.getAttribute('total'));
  const size = Number(p.getAttribute('pagesize'));
  const current = Number(p.getAttribute('currentpage'));
  const cards = document.querySelectorAll('.offers .offer-cards a.mu-store__wrapper[href]');
  return Number.isInteger(total) && total > 0 && total <= 1200 &&
    Number.isInteger(size) && size > 0 && size <= 100 && current === expected &&
    cards.length === Math.min(size, total - (expected - 1) * size) &&
    Array.from(cards).every(c => c.querySelector('.mu-store__title')?.textContent.trim());
}"""

async def collect(client,cfg,report,observed_at,limit):
    from read_budget import within_source_budget, stops_catalog
    if cfg['id']!=SOURCE or cfg['url']!=ROOT:raise ValueError('backit_config_identity')
    bound=cfg.get('detail_limit',limit)
    if not isinstance(bound,int) or not 1<=bound<=MAX_CARDS:raise ValueError('backit_detail_bound')
    client.request_interval=max(.5,client.request_interval)
    async def read(url,render=False):return await within_source_budget(client,lambda:client.read(url,render=render))
    async def read_inventory(url,page):
        await read(url,render=True)
        try:
            await within_source_budget(client,lambda:client.page.wait_for_function(INVENTORY_READY,arg=page,timeout=15000))
        except (TimeoutError,BrowserTimeout) as exc:
            raise RuntimeError('backit_catalogue_not_ready:page='+str(page)) from exc
        client.check_url(client.page.url)
        raw=await client.page.content()
        if len(raw.encode())>6000000:raise RuntimeError('source_response_too_large')
        try:return inventory(raw,page)
        except ValueError as exc:
            # Only anonymous catalogue path/DOM counters, never headers, query
            # strings, scripts, cookies or account data. Useful for layout drift.
            soup=BeautifulSoup(raw,'html.parser');nodes=soup.select('.mu-pagination')
            report['inventory_diagnostics']={'page':page,'pagination':[dict((k,n.get(k)) for k in ('total','pagesize','currentpage')) for n in nodes[:3]],
                'cards':[{'path':urlsplit(n.get('href','')).path,'titles':len(n.select('.mu-store__title'))} for n in soup.select('.offers .offer-cards a.mu-store__wrapper[href]')[:100]]}
            code=str(exc) if re.fullmatch(r'[a-z_:. -]{1,140}',str(exc)) else 'invalid_inventory'
            raise RuntimeError('backit_inventory_validation:page='+str(page)+':'+code) from exc
    cards,total,size=await read_inventory(ROOT,1);seen={c['url'] for c in cards}
    pages=math.ceil(total/size)
    for page in range(2,pages+1):
        current,nt,ns=await read_inventory(ROOT+'?page='+str(page),page)
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
            if stops_catalog(exc) or str(exc) in ('http_401','http_403','access_challenge','unexpected_redirect'):break
    report['discovered']=len(rows)+len(report['errors'])
    report['coverage']=json.dumps({'scope':'public_ru_cashback_shop_inventory','listed':total,'inventory_pages':pages,
        'parsed':len(rows),'excluded':excluded,'details_attempted':len(rows)+len(excluded)-(total-len(eligible))+len(report['errors']),
        'all_inventory_accounted':len(rows)+len(excluded)+len(report['errors'])==total,
        'source_local_detail_limit':bound,'product_level_marketplace_catalogue_included':False},ensure_ascii=False)
    return rows
