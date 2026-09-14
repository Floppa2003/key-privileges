"""Finite anonymous discovery for the source-reconciliation pass; no Google access."""
import asyncio,json,hashlib,re
from pathlib import Path
from collections import defaultdict
from urllib.parse import urlsplit
from datetime import datetime,timezone
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright
from public_transport import PublicSource
from normalized import canonical_url

URLS = '''https://ramadayekaterinburg.com/wings/
https://www.park-hotel-graal.ru/uralpartners.html
https://seagalaxy.com/spec/programma-loyalnosti-krylya-offer
https://online.smart-inc.ru/smartmedia/partner-projects/smart-ural-airlines
https://hotel.iktport.ru/ru/akcii/drugie.html
https://sykt.arendacar.ru/news/novyj-partnjor-kompanii-uralskie-avialinii/
https://hotelamur.com/partners-bonus-ural-airlines/
https://gthotel.ru/offers/uralskie-avialinii/
https://visotsky-hotel.ru/special-offers
https://www.aerootel.com/rooms/city
https://angarahotel.ru/stock/skidki-dlya-uchastnikov-programmy-krylya/
https://ecospa-visotsky.ru/about/actions/item/154-programma-loyalnosti-krylya-ot-aviakompanii-uralskie-avialinii
https://azimuthotels.com/ru/tl/availability
https://www.uralairlines.ru/baggage_detail/sverkhnormativnyy-bagazh/
https://101hotels.com/?utm_source=privetMIR6
https://ekt.t2.ru/about/news-list/2026/07/28/informacionnoe-soobshchenie
https://vamprivet.ru/
https://ekp.spb.ru/capabilities/loyalty/tiles/1301?region=78
https://ekp.spb.ru/news/1724
https://ekp.spb.ru/capabilities/transport
https://ekp.spb.ru/capabilities/loyalty/tiles/2952?region=78
https://t.me/s/fpcrussia?before=1615
https://t.me/s/ekpcard/4483
https://t.me/s/mybspb
https://t.me/s/ekpcard?before=5080
https://t.me/s/ekpcard?before=4652&q=%23%D0%9F%D0%BE%D0%B4%D1%80%D0%BE%D0%B1%D0%BD%D0%BE%D0%95%D0%9A%D0%9F
https://t.me/promomir/1457
https://t.me/s/promomir?before=1466
https://t.me/s/promomir?before=1906
https://t.me/s/promomir/1348
https://t.me/s/promomir?before=1189
https://t.me/s/promomir?before=909
https://t.me/s/promomir/1335
https://t.me/s/promomir?before=1354
https://t.me/s/promomir/1278
https://t.me/s/promomir?before=1192
https://coralbonus.ru/klub-privilegii/zdorov-e/medsi/
https://coralbonus.ru/klub-privilegii/zdorov-e/napopravku/
https://coralbonus.ru/klub-privilegii/odezhda-i-aksessuary/saboo/
https://coralbonus.ru/klub-privilegii/zdorov-e/proprikus/
https://coralbonus.ru/klub-privilegii/zdorov-e/dinastiya-vrachei/
https://coralbonus.ru/klub-privilegii/krasota/feedback/
https://coralbonus.ru/klub-privilegii/avtomobili/sitidraiv-rent/
https://coralbonus.ru/klub-privilegii/servisy/pauri/
https://coralbonus.ru/klub-privilegii/obrazovanie/anecole/
https://coralbonus.ru/klub-privilegii/dlya-detei/aitigenio/
https://coralbonus.ru/klub-privilegii/avtomobili/portal/
https://coralbonus.ru/klub-privilegii/avtomobili/sitidraiv/
https://coralbonus.ru/klub-privilegii/avtomobili/the-mashina/
https://coralbonus.ru/klub-privilegii/razvlecheniya/brodvei-moskva/
https://coralbonus.ru/klub-privilegii/podarki/flowwow/
https://coralbonus.ru/klub-privilegii/bagazh/eberhart/
https://coralbonus.ru/klub-privilegii/razvlecheniya/litres/
https://coralbonus.ru/klub-privilegii/odezhda-i-aksessuary/vkruzhevakh-rf/
https://coralbonus.ru/klub-privilegii/odezhda-i-aksessuary/lena/
https://coralbonus.ru/klub-privilegii/mobil-naya-svyaz/kaspersky/
https://coralbonus.ru/klub-privilegii/vse-dlya-doma-i-otdykha/airo/
https://coralbonus.ru/klub-privilegii/zdorov-e/sberzdorov-e/
https://coralbonus.ru/klub-privilegii/avtomobili/careta/
https://coralbonus.ru/klub-privilegii/servisy/goldenkey/
https://coralbonus.ru/klub-privilegii/nedvizhimost/aps-dsk/
https://coralbonus.ru/klub-privilegii/sport/flex-gym/
https://coralbonus.ru/klub-privilegii/krasota/geltek/
https://coralbonus.ru/klub-privilegii/kafe-restorany-produkty/russkie-pirogi/
https://coralbonus.ru/klub-privilegii/razvlecheniya/kion/
https://coralbonus.ru/klub-privilegii/mobil-naya-svyaz/megafon/
https://coralbonus.ru/klub-privilegii/odezhda-i-aksessuary/sunlight_gift/
https://coralbonus.ru/klub-privilegii/nedvizhimost/artel/
https://coralbonus.ru/klub-privilegii/nedvizhimost/gk-nndk/
https://coralbonus.ru/klub-privilegii/nedvizhimost/unistroi/
https://coralbonus.ru/klub-privilegii/zdorov-e/stomatologii-na-22-etazhe/
https://coralbonus.ru/klub-privilegii/kafe-restorany-produkty/gayane-s/
https://coralbonus.ru/klub-privilegii/nedvizhimost/nazare/
https://coralbonus.ru/klub-privilegii/vse-dlya-doma-i-otdykha/madame-coco/
https://coralbonus.ru/klub-privilegii/nedvizhimost/muza/
https://coralbonus.ru/klub-privilegii/uslugi-aeroporta/biznes-zaly-vip-lounge-vnukovo/
https://coralbonus.ru/klub-privilegii/uslugi-aeroporta/biznes-zaly-sheremet-evo-vip/
https://coralbonus.ru/klub-privilegii/nedvizhimost/a101/
https://coralbonus.ru/klub-privilegii/nedvizhimost/smu-88/
https://coralbonus.ru/klub-privilegii/krasota/styx-silk-body/
https://coralbonus.ru/klub-privilegii/transfer/bookingcar/
https://coralbonus.ru/klub-privilegii/nedvizhimost/rdi-yuzhnaya-dolina/
https://coralbonus.ru/promo/territoriya-bonusov-20-07-2026/?erid=2W5zFHddcUR
https://coralbonus.ru/promo/zhemchuzhina-vostoka/
https://coralbonus.ru/promo/rixos-tersane-istanbul/
https://coralbonus.ru/promo/rixos-hotels-v-egipte/
https://coralbonus.ru/promo/rixos-hotels-turkiye/?erid=2W5zFHnF4xZ
https://coralbonus.ru/promo/mesto-pod-solnfem/
https://coralbonus.ru/promo/more-zovet/?erid=2W5zFGgeLtq
https://coralbonus.ru/promo/papillon-2026/
https://coralbonus.ru/promo/xanadu-resort/
https://coralbonus.ru/promo/the-land-of-legends-kingdom-hotel/
https://coralbonus.ru/promo/xanadu-makadi-bay/
https://coralbonus.ru/promo/the-land-of-legends-nickelodeon-hotels-resorts-antalya/
https://coralbonus.ru/promo/xanadu-club-makadi-bay/
https://coralbonus.ru/promo/seven-seas-hotel-life/
https://coralbonus.ru/promo/kaya-palazzo-golf-resort/
https://coralbonus.ru/promo/marvida-family-eco/
https://coralbonus.ru/promo/rox-2026/
https://coralbonus.ru/promo/greenwood/
https://coralbonus.ru/promo/seven-seas-jolie-bay/
https://coralbonus.ru/promo/na-volne-doveriya/
https://coralbonus.ru/promo/shedryi-podarok/
https://coralbonus.ru/programma-loyal-nosti/'''.splitlines()
OUT=Path('reconcile-output')

def sanitized(html):
    soup=BeautifulSoup(html,'html.parser')
    for n in soup.select('script,style,form,input,textarea,noscript'):n.decompose()
    for n in soup.find_all(True):
        for key in list(n.attrs):
            if re.search(r'token|secret|session|signature|nonce|password|auth',key,re.I):del n.attrs[key]
        if n.get('href'):
            try:canonical_url(n['href'])
            except (ValueError,TypeError):del n.attrs['href']
    return str(soup)

async def inspect_host(browser,urls,sem):
    async with sem:
        results=[]
        async with PublicSource(browser,urls[0]) as client:
            try:
                async with asyncio.timeout(45):await client.robots()
            except Exception as exc:
                return [{'url':u,'status':'blocked_before_target','stage':'robots','error':str(exc)[:200] if isinstance(exc,RuntimeError) else type(exc).__name__} for u in urls]
            client.request_interval=max(1.0,client.request_interval)
            for u in urls:
                r={'url':u,'stage':'target','observed_at':datetime.now(timezone.utc).isoformat()}
                try:
                    async with asyncio.timeout(45):html=await client.read(u,render=True)
                    clean=sanitized(html);name=hashlib.sha256(u.encode()).hexdigest()[:20]+'.html'
                    (OUT/name).write_text(clean,encoding='utf8')
                    r.update(status='read',file=name,sha256=hashlib.sha256(clean.encode()).hexdigest(),text_size=len(BeautifulSoup(clean,'html.parser').get_text(' ',strip=True)))
                except Exception as exc:r.update(status='failed',error=str(exc)[:200] if isinstance(exc,RuntimeError) else type(exc).__name__)
                results.append(r);print(json.dumps(r,ensure_ascii=False),flush=True)
                if '429' in r.get('error','') or 'retry_after' in r.get('error',''):
                    results.extend({'url':v,'status':'not_requested_after_rate_limit','stage':'host_backoff'} for v in urls[len(results):]);break
        return results

async def main():
    OUT.mkdir(exist_ok=True);groups=defaultdict(list)
    for u in URLS:groups[urlsplit(u).hostname].append(u)
    async with async_playwright() as p:
        browser=await p.chromium.launch()
        try:result=await asyncio.gather(*(inspect_host(browser,v,asyncio.Semaphore(1)) for v in groups.values()))
        finally:await browser.close()
    flat=[r for group in result for r in group]
    (OUT/'discovery.json').write_text(json.dumps({'run_id':__import__('os').environ.get('GITHUB_RUN_ID'),'results':flat},ensure_ascii=False,indent=2),encoding='utf8')
if __name__=='__main__':asyncio.run(main())
