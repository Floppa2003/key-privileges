"""Inspect the exact public Coral promo page using the normal transport.

Production run34962776727 reported accessible-without-adapter. This bounded check
retains sanitized evidence to distinguish real content from an empty shell.
"""
import asyncio
import hashlib
import json
import os
import sys
import time
from pathlib import Path
from datetime import datetime,timezone
from urllib.parse import urljoin,urlsplit
from bs4 import BeautifulSoup
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'loyalty'))
from playwright.async_api import async_playwright
from public_transport import PublicSource
from source_readiness import public_dom,public_url

ROOT='https://coralbonus.ru/promo/'
OUT=Path('coral-promo-content-output')

async def run():
    OUT.mkdir(exist_ok=True)
    report={'source_url':ROOT,'run_id':os.getenv('GITHUB_RUN_ID'),'commit':os.getenv('GITHUB_SHA'),
        'replica':os.getenv('REPLICA'),'observed_at':datetime.now(timezone.utc).isoformat(),
        'stage':'startup','navigation':[],'captures':[],'production_write':False,'catalog_complete':False,
        'script_hashes':{}}
    for src in (Path(__file__),Path(__file__).with_name('source_readiness.py'),Path('loyalty/public_transport.py'),Path('loyalty/model.py')):
        data=src.read_bytes();(OUT/src.name).write_bytes(data)
        report['script_hashes'][src.name]=hashlib.sha256(data).hexdigest()
    def save():(OUT/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
    client=None;save()
    async def capture(raw,page,label):
        safe=public_dom(raw,page.url).encode();name=label+'.html';(OUT/name).write_bytes(safe)
        soup=BeautifulSoup(safe,'html.parser');links=[]
        for a in soup.select('a[href]'):
            url=public_url(urljoin(page.url,a['href']))
            if url and urlsplit(url).hostname=='coralbonus.ru':
                entry={'url':url,'label':a.get_text(' ',strip=True)}
                if entry not in links:links.append(entry)
        report['captures'].append({'file':name,'sha256':hashlib.sha256(safe).hexdigest(),
            'title':soup.title.get_text(' ',strip=True) if soup.title else '',
            'text_characters':len(soup.get_text(' ',strip=True)),
            'headings':[h.get_text(' ',strip=True) for h in soup.select('h1,h2')],
            'same_host_links':links[:200],'url':public_url(page.url),
            'kind':'sanitized_live_DOM_not_original_response'})
        save()
    try:
        async with async_playwright() as p:
            browser=await p.chromium.launch()
            try:
                async with PublicSource(browser,ROOT) as client:
                    client.deadline=time.monotonic()+100
                    report['stage']='robots';save();await client.robots()
                    page=client.page
                    def response(r):
                        if r.request.is_navigation_request() and r.request.frame==page.main_frame:
                            report['navigation'].append({'url':public_url(r.url),'status':r.status})
                    page.on('response',response)
                    try:
                        report['stage']='source';save()
                        raw=await client.read(ROOT,render=True)
                        await capture(raw,page,'normal-read')
                        await asyncio.sleep(5)
                        # No extra navigation: observe only the already loaded page.
                        await capture(await asyncio.wait_for(page.content(),6),page,'settled-read')
                    finally:page.remove_listener('response',response)
                    report['stage']='complete';save()
            finally:await browser.close()
    except Exception as exc:
        allowed={'robots_disallow','access_challenge','robots_not_readable'}
        value=str(exc)
        report['error']=value if value in allowed or (value.startswith('http_') and value[5:].isdigit()) else type(exc).__name__
    finally:
        if client is not None:report['robots']=getattr(client,'robots_info',None)
        report['finished_at']=datetime.now(timezone.utc).isoformat();save()

if __name__=='__main__':asyncio.run(run())
