"""One paired anonymous browser experiment on the configured Utair URL.
Same installed Chrome, headful display, fresh disposable profiles. Compare
Playwright-managed launch with attaching CDP to separately launched Chrome.
No injected stealth script, modified fingerprint property, login, user profile,
manual challenge answer, cookie export or source-text replacement.
"""
import asyncio
import hashlib
import json
import os
import shutil
import socket
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit
from playwright.async_api import async_playwright
from seven_routes_transport import describe, safe_url

OUT=Path('utair-browser-output')


def public_path(url):
    try:return urlsplit(url)._replace(query='',fragment='').geturl()
    except ValueError:return None


async def observe(context,url,mode):
    row={'mode':mode,'url':url,'navigation_responses':[],'snapshots':[],'tls_verification':True}
    page=context.pages[0] if context.pages else await context.new_page()
    def response(r):
        try:
            if r.request.is_navigation_request() and r.frame==page.main_frame:
                row['navigation_responses'].append({'status':r.status,'url':public_path(r.url)})
        except Exception:pass
    page.on('response',response)
    row['environment']=await page.evaluate('({ua:navigator.userAgent,webdriver:navigator.webdriver,languages:navigator.languages})')
    try:
        first=await page.goto(url,wait_until='domcontentloaded',timeout=25000)
        row['initial_status']=first.status if first else None
    except Exception as exc:row['navigation_error']=type(exc).__name__
    prior=0
    for second in (2,8,20):
        await page.wait_for_timeout((second-prior)*1000);prior=second
        try:
            raw=(await page.content()).encode('utf8')
            latest=row['navigation_responses'][-1]['status'] if row['navigation_responses'] else 0
            doc=describe(raw,latest)
            row['snapshots'].append({'after_seconds':second,'last_navigation_status':latest,'document':doc})
            if doc['classification']=='content_candidate':break
            if '403' in doc['title'] or 'запрещен' in doc['text'].lower():break
        except Exception as exc:row['snapshots'].append({'after_seconds':second,'error_type':type(exc).__name__})
    row['final_url']=safe_url(page.url)
    row['cookie_names_only']=sorted({c['name'] for c in await context.cookies(url)})
    row['finished_at']=datetime.now(timezone.utc).isoformat()
    return row


async def main():
    OUT.mkdir(exist_ok=True)
    url=next(x['url'] for x in json.loads(Path('loyalty/sources_normalized.json').read_text()) if x['id']=='utair')
    exe=shutil.which('google-chrome') or shutil.which('google-chrome-stable')
    if not exe:raise RuntimeError('installed_chrome_unavailable')
    report={'run_id':os.getenv('GITHUB_RUN_ID'),'commit':os.getenv('GITHUB_SHA'),
            'observed_at':datetime.now(timezone.utc).isoformat(),
            'chrome_version':subprocess.check_output([exe,'--version']).decode().strip(),'results':[],
            'script_hashes':{n:hashlib.sha256((Path('diagnostics')/n).read_bytes()).hexdigest()
                 for n in ('utair_browser_lifecycle.py','seven_routes_transport.py')}}
    async with async_playwright() as p:
        with tempfile.TemporaryDirectory() as profile:
            context=await p.chromium.launch_persistent_context(profile,executable_path=exe,headless=False,
                     args=['--lang=ru-RU','--window-size=1365,900'],viewport=None)
            try:report['results'].append(await observe(context,url,'playwright_persistent_chrome'))
            finally:await context.close()
        (OUT/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
        with tempfile.TemporaryDirectory() as profile:
            with socket.socket() as s:s.bind(('127.0.0.1',0));port=s.getsockname()[1]
            args=[exe,f'--user-data-dir={profile}',f'--remote-debugging-port={port}',
                  '--remote-debugging-address=127.0.0.1','--no-first-run','--no-default-browser-check',
                  '--no-sandbox','--lang=ru-RU','--window-size=1365,900','about:blank']
            proc=subprocess.Popen(args,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
            browser=None
            try:
                for _ in range(30):
                    try:
                        with socket.create_connection(('127.0.0.1',port),timeout=0.2):break
                    except OSError:await asyncio.sleep(0.2)
                browser=await p.chromium.connect_over_cdp(f'http://127.0.0.1:{port}',timeout=10000)
                report['results'].append(await observe(browser.contexts[0],url,'external_chrome_cdp'))
            finally:
                if browser:await browser.close()
                if proc.poll() is None:proc.terminate()
                try:proc.wait(timeout=5)
                except subprocess.TimeoutExpired:proc.kill();proc.wait()
    report['finished_at']=datetime.now(timezone.utc).isoformat()
    (OUT/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
    for n in report['script_hashes']:(OUT/n).write_bytes((Path('diagnostics')/n).read_bytes())
    for r in report['results']:
        print(json.dumps({'mode':r['mode'],'initial_status':r.get('initial_status'),
                         'snapshots':[{'after_seconds':s['after_seconds'],'status':s.get('last_navigation_status'),
                         'title':s.get('document',{}).get('title')} for s in r['snapshots']]}),flush=True)

if __name__=='__main__':asyncio.run(main())
