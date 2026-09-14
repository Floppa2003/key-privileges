"""Finish the explicit public reference inventory, without repeating prior probes."""
import asyncio,json
from collections import defaultdict
from urllib.parse import urlsplit
from playwright.async_api import async_playwright
from reconcile_probe import OUT,inspect_host
URLS=[
'https://www.personalguide.ru/rossiya/novosibirsk/oteli/gorskiy-city-hotel',
'https://telemetr.io/uk/channels/1286757893',
'https://v.page/0ACuh',
'https://smart--hotel--chain.orgs.biz/',
'https://promokod.com/coupon-store/rzd-bonus-ru',
'https://promokodoff.ru/promokody-rzhd/',
'https://privatbankrf.ru/aktsii/akcziya-poluchite-1100-ballov-rzhd-bonus-za-oformlenie-i-pokupki-po-debetovoj-karte-black-ot-t-banka.html',
'https://t.me/s/promomir',
'https://t.me/s/promomir/1457',
]
async def main():
 OUT.mkdir(exist_ok=True);groups=defaultdict(list);sem=asyncio.Semaphore(3)
 for u in URLS:groups[urlsplit(u).hostname].append(u)
 async with async_playwright() as p:
  browser=await p.chromium.launch()
  try:result=await asyncio.gather(*(inspect_host(browser,v,sem) for v in groups.values()))
  finally:await browser.close()
 (OUT/'discovery-extra.json').write_text(json.dumps({'run_id':__import__('os').environ.get('GITHUB_RUN_ID'),'results':[r for group in result for r in group]},ensure_ascii=False,indent=2),encoding='utf8')
if __name__=='__main__':asyncio.run(main())
