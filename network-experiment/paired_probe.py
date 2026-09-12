"""Control the user-agent variable on one VM; retain only public evidence."""
import asyncio
import hashlib
import json
import os
import sys
from datetime import datetime,timezone
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'loyalty'/'diagnostics'))
import network_probe as probe
from playwright.async_api import async_playwright

async def main():
    out=Path('external-output');out.mkdir(exist_ok=True)
    report={'purpose':'same_VM_same_browser_same_URL_user_agent_comparison',
        'observed_at':datetime.now(timezone.utc).isoformat(),'run_id':os.getenv('GITHUB_RUN_ID'),
        'code_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'probe_sha256':hashlib.sha256(Path(probe.__file__).read_bytes()).hexdigest(),'checks':[]}
    async with async_playwright() as p:
        browser=await p.chromium.launch()
        try:
            ctx=await browser.new_context();page=await ctx.new_page()
            default_ua=await page.evaluate('navigator.userAgent');await ctx.close()
            bot_ua=probe.UA
            report['user_agents']={'explicit_research_bot':bot_ua,'playwright_default':default_ua}
            url='https://marketplace.s7.ru/partners/offer/flowwow'
            for mode in ('explicit_research_bot','playwright_default','explicit_research_bot'):
                probe.UA=report['user_agents'][mode]
                observation=await probe.browser_read(browser,url,{'marketplace.s7.ru'})
                report['checks'].append({'source_id':'s7','mode':mode,'url':url,'observation':observation})
                await asyncio.sleep(2)
        finally:
            await browser.close()
    report['finished_at']=datetime.now(timezone.utc).isoformat()
    (out/'paired-user-agent.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
    print(json.dumps([{'mode':r['mode'],'status':r['observation'].get('status')} for r in report['checks']]))

if __name__=='__main__':asyncio.run(main())
