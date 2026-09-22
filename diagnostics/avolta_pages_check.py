"""Temporary anonymous Club Avolta page samples for selector verification."""
import asyncio, hashlib, json, sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright
sys.path.insert(0, 'loyalty')
from public_transport import PublicSource

async def main():
    out=Path('source-check');out.mkdir(exist_ok=True);report=[]
    async with async_playwright() as p:
        browser=await p.chromium.launch(headless=False)
        root='https://www.clubavolta.com/ru'
        async with PublicSource(browser,root) as client:
            await client.robots();client.request_interval=max(1,client.request_interval)
            html=await client.read(root,render=True)
            soup=BeautifulSoup(html,'html.parser')
            urls=list(dict.fromkeys(urljoin(root,a['href']) for a in soup.select('a.partners-tile[href]')))
            assert 1<=len(urls)<=10
            urls+=['https://www.clubavolta.com/ru/nashi-partnery/zaly-ozhidaniya/plaza','https://www.clubavolta.com/ru/nashi-partnery/zaly-ozhidaniya/dragonpass']
            for i,url in enumerate(urls):
                assert url.startswith('https://www.clubavolta.com/ru/nashi-partnery/')
                html=await client.read(url,render=True);soup=BeautifulSoup(html,'html.parser')
                for node in soup.select('script,style,noscript,svg,iframe'):
                    if node.parent is not None:node.decompose()
                name='avolta-sample-'+str(i)+'.html';(out/name).write_text(str(soup))
                report.append({'url':url,'file':name,'observed_at':datetime.now(timezone.utc).isoformat(),'sha256':hashlib.sha256(html.encode()).hexdigest()})
        await browser.close()
    (out/'avolta-samples.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
asyncio.run(main())
