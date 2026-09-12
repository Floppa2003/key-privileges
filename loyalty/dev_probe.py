"""One-shot public-source inspection. No credentials; not a production parser."""
import asyncio
import json
import re
import shutil
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode
from urllib.robotparser import RobotFileParser
from playwright.async_api import async_playwright
from bs4 import BeautifulSoup, Comment

ROOTS = {
 'moskvich': 'https://moskvichmag.ru/programma-loyalnosti/',
 'noname': 'https://nonameburo.com/card',
 'nordwind': 'https://nordwindairlines.ru/ru/club/partnerlist',
 'azimut': 'https://azimuthotels.com/ru/info/bonus',
 'rusimp': 'https://www.rusimp.su/membership/friends',
 'utair': 'https://www.utair.ru/support/2/kakiye_partnery_est_u_utair_status',
 'ural': 'https://www.uralairlines.ru/partners/',
 's7': 'https://marketplace.s7.ru/partners/category/retail',
 's7_detail': 'https://marketplace.s7.ru/partners/offer/flowwow',
 'coral': 'https://coralbonus.ru/klub-privilegii/',
 'coral_promo': 'https://coralbonus.ru/promo/',
 'rgo': 'https://rgo.ru/membership/loyalty-program/',
 'rgo_detail': 'https://rgo.ru/membership/loyalty-program/gostinitsa-paddok-3-zvezdy/',
 'rzd': 'https://www.rzd-bonus.ru/?accessible=true',
 'aeroflot': 'https://www.aeroflot.ru/ru-ru/afl_bonus/partners',
 'promomiles': 'https://promomiles.aeroflot.ru/',
 'ekp': 'https://ekp.spb.ru/capabilities/loyalty/',
 't2_bolshe': 'https://msk.t2.ru/bolshe/offers',
 't2_mixx': 'https://msk.t2.ru/help/article/what-included-mixx-m-subscription',
 't2_selection': 'https://msk.t2.ru/tariff/premium',
 'sogaz_medi': 'https://medi.spb.ru/medi/spetspredlozheniya/partnerskie-programmy/sogaz/',
 'mir': 'https://vamprivet.ru/',
 't2_mixx_s': 'https://msk.t2.ru/promotions/article/yandex-station-mixx',
 't2_powerbank': 'https://msk.t2.ru/promotions/article/bezlimitnaya-arenda-powerbank',
 'loyals': 'https://loyals.ru/',
}
SENSITIVE = re.compile(r'token|secret|password|cookie|session|csrf|authorization|credential|nonce', re.I)

def safe_url(value):
    u = urlsplit(value)
    if u.scheme not in ('http', 'https') or u.username or u.password:
        return ''
    q = [(k,v) for k,v in parse_qsl(u.query) if not SENSITIVE.search(k)]
    return urlunsplit((u.scheme,u.netloc,u.path,urlencode(q),u.fragment))

def safe_json(data):
    if isinstance(data, dict):
        return {k: safe_json(v) for k,v in data.items() if not SENSITIVE.search(k)}
    if isinstance(data, list):
        return [safe_json(v) for v in data]
    if isinstance(data, str) and data.startswith(('http://','https://')):
        return safe_url(data)
    return data

def clean_html(raw):
    soup = BeautifulSoup(raw, 'html.parser')
    for n in soup.find_all(string=lambda t: isinstance(t, Comment)):
        n.extract()
    for el in soup.find_all(['script','style','input','textarea','iframe','noscript']):
        if el.name == 'script' and (el.get('type') == 'application/ld+json' or el.get('id') == '__NEXT_DATA__'):
            try:
                el.string = json.dumps(safe_json(json.loads(el.string or '')),ensure_ascii=False)
                continue
            except Exception:
                pass
        el.decompose()
    for el in soup.find_all(True):
        el.attrs = {k:v for k,v in el.attrs.items() if k in ('id','class','href','src','alt','title','role','aria-label','data-record-type','data-elem-id','data-field-top-value','data-field-left-value','data-animate-sbs-event','data-artboard-height','data-product-uid','itemprop','itemtype','itemscope')}
        for k in ('href','src'):
            if k in el.attrs and str(el[k]).startswith(('http://','https://')):
                el[k] = safe_url(el[k])
    return str(soup)

async def inspect(browser, sem, key, url, out):
    async with sem:
        ctx = await browser.new_context(locale='ru-RU')
        page = await ctx.new_page()
        report = {'id':key,'url':url,'status':'failed','network':[]}
        pending = []
        host = urlsplit(url).hostname
        async def network(resp):
            try:
                if resp.request.resource_type not in ('xhr','fetch'):
                    return
                u = urlsplit(resp.url)
                if u.hostname != host:
                    return
                entry = {'url':safe_url(resp.url),'status':resp.status,'type':resp.headers.get('content-type','')}
                if len(report['network']) >= 40:
                    return
                report['network'].append(entry)
                if 'application/json' in entry['type'] and resp.status == 200 and not SENSITIVE.search(u.path):
                    data = await resp.body()
                    if len(data) < 2000000:
                        name = f'{key}-api-{len(report["network"])}.json'
                        (out/name).write_text(json.dumps(safe_json(json.loads(data)),ensure_ascii=False),encoding='utf8')
                        entry['file'] = name
            except Exception:
                pass
        page.on('response',lambda r: pending.append(asyncio.create_task(network(r))))
        try:
            robots_url = f'https://{host}/robots.txt'
            res = await ctx.request.get(robots_url, timeout=20000)
            report['robots_status'] = res.status
            policy = RobotFileParser(robots_url)
            if res.status == 404:
                policy.parse([])
            elif res.status == 200:
                text = await res.text()
                (out/f'{key}-robots.txt').write_text(text,encoding='utf8')
                policy.parse(text.splitlines())
            else:
                raise RuntimeError(f'robots_http_{res.status}')
            if not policy.can_fetch('LoyaltyCatalogResearchBot',url):
                raise RuntimeError('robots_disallow')
            res = await page.goto(url,wait_until='domcontentloaded',timeout=40000)
            await page.wait_for_timeout(3500)
            report['http_status'] = res.status if res else None
            report['final_url'] = safe_url(page.url)
            if not res or res.status >= 400:
                raise RuntimeError('page_http_error')
            report['title'] = await page.title()
            if re.search(r'captcha|access denied|just a moment|проверка безопасности',report['title'],re.I):
                raise RuntimeError('access_challenge')
            (out/f'{key}.html').write_text(clean_html(await page.content()),encoding='utf8')
            (out/f'{key}.txt').write_text(await page.locator('body').inner_text(),encoding='utf8')
            report['scripts'] = [safe_url(v) for v in await page.locator('script[src]').evaluate_all('(els)=>els.map(e=>e.src)')]
            report['status'] = 'read'
        except Exception as exc:
            report['error_type'] = type(exc).__name__
            report['reason'] = str(exc)[:200] if isinstance(exc,RuntimeError) else 'network_or_browser_failure'
        finally:
            if pending:
                await asyncio.gather(*pending,return_exceptions=True)
            await ctx.close()
        (out/f'{key}-report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
        print(json.dumps({k:v for k,v in report.items() if k not in ('network','scripts')},ensure_ascii=False),flush=True)
        return report

async def main():
    out = Path('source-inspection'); out.mkdir(exist_ok=True)
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        results = await asyncio.gather(*(inspect(browser,asyncio.Semaphore(1),k,u,out) for k,u in [])) if False else []
        sem = asyncio.Semaphore(4)
        results = await asyncio.gather(*(inspect(browser,sem,k,u,out) for k,u in ROOTS.items()))
        await browser.close()
    (out/'report.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf8')
    # These exact files are already public source code, never environment or credentials.
    for folder in ('loyalty','.github/workflows','key'):
        for f in Path(folder).rglob('*'):
            if f.is_file() and f.suffix in ('.py','.json','.yml','.md','.txt','.sh','.mjs'):
                dest=out/'_code'/f;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(f,dest)

if __name__ == '__main__': asyncio.run(main())
