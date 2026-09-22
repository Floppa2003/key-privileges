"""Read two anonymous Backit catalogue pages; no account or activation actions."""
import asyncio, json, sys
from pathlib import Path
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright
sys.path.insert(0, 'loyalty')
from public_transport import PublicSource

async def main():
    out = Path('source-check'); out.mkdir(exist_ok=True)
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        async with PublicSource(browser, 'https://backit.me/ru/cashback/shops') as client:
            await client.robots()
            await client.read('https://backit.me/ru/cashback/shops', render=True)
            await client.page.locator('.mu-pagination .btn-next').click()
            await client.page.wait_for_timeout(2500)
            soup = BeautifulSoup(await client.page.content(), 'html.parser')
            pagination = soup.select_one('.mu-pagination')
            assert pagination is not None and pagination.get('currentpage') == '2'
            for node in soup.select('script,style,noscript,svg,iframe'):
                if node.parent is not None: node.decompose()
            (out/'backit-page2.html').write_text(str(soup))
            (out/'backit-page2.json').write_text(json.dumps({'url':client.page.url,'total':pagination.get('total'),'page':pagination.get('currentpage'),'page_size':pagination.get('pagesize')}))
        await browser.close()
asyncio.run(main())
