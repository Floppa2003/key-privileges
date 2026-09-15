"""Independent fresh-runner confirmation; never replay a saved page.
Uses the same installed-Chrome CDP route that returned the real Utair article.
Only public page content is retained; disposable browser profiles and cookie
values are never uploaded. No manual answers, account login or property spoof.
"""
import asyncio
import hashlib
import json
import os
import shutil
import socket
import subprocess
import tempfile
from datetime import datetime,timezone
from pathlib import Path
from urllib.parse import urljoin,urlsplit
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright
from seven_routes_transport import safe_url
from utair_browser_lifecycle import observe

OUT=Path('seven-browser-output')
IDS=('utair','coral','coral_promo','rzd','aeroflot','ekp','nordwind')


def sanitize(html,url):
    soup=BeautifulSoup(html,'html.parser')
    for e in soup.select('script,style,form,input,textarea,iframe,noscript'):e.decompose()
    for e in soup.find_all(True):
        for a in list(e.attrs):
            if a not in ('id','class','href','title','role','aria-expanded','aria-controls'):del e.attrs[a]
        if e.has_attr('href'):
            clean=safe_url(urljoin(url,e['href']))
            if clean:e['href']=clean
            else:del e.attrs['href']
    return str(soup)


async def main():
    OUT.mkdir(exist_ok=True)
    sources=json.loads(Path('loyalty/sources_normalized.json').read_text())
    targets={s['id']:s['url'] for s in sources if s['id'] in IDS}
    assert set(targets)==set(IDS)
    exe=shutil.which('google-chrome') or shutil.which('google-chrome-stable')
    if not exe:raise RuntimeError('installed_chrome_unavailable')
    report={'run_id':os.getenv('GITHUB_RUN_ID'),'commit':os.getenv('GITHUB_SHA'),
            'replica':os.getenv('REPLICA'),'observed_at':datetime.now(timezone.utc).isoformat(),
            'chrome_version':subprocess.check_output([exe,'--version']).decode().strip(),
            'scope':'seven_exact_public_routes_fresh_anonymous_browser_no_google_or_private_inputs',
            'results':[],'script_hashes':{n:hashlib.sha256((Path('diagnostics')/n).read_bytes()).hexdigest()
                  for n in ('seven_browser_confirm.py','utair_browser_lifecycle.py','seven_routes_transport.py')}}
    async with async_playwright() as p:
        with tempfile.TemporaryDirectory() as profile:
            with socket.socket() as s:s.bind(('127.0.0.1',0));port=s.getsockname()[1]
            proc=subprocess.Popen([exe,f'--user-data-dir={profile}',f'--remote-debugging-port={port}',
                '--remote-debugging-address=127.0.0.1','--no-first-run','--no-default-browser-check',
                '--no-sandbox','--lang=ru-RU','--window-size=1365,900','about:blank'],
                stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
            browser=None
            try:
                for _ in range(30):
                    try:
                        with socket.create_connection(('127.0.0.1',port),timeout=.2):break
                    except OSError:await asyncio.sleep(.2)
                browser=await p.chromium.connect_over_cdp(f'http://127.0.0.1:{port}',timeout=10000)
                context=browser.contexts[0]
                for key in IDS:
                    try:
                        row=await observe(context,targets[key],'external_chrome_cdp')
                        row['id']=key
                        last=row['snapshots'][-1].get('document',{}) if row['snapshots'] else {}
                        if last.get('classification')=='content_candidate':
                            html=await context.pages[0].content()
                            public=sanitize(html,targets[key]).encode('utf8')
                            name=key+'-public-dom.html';(OUT/name).write_bytes(public)
                            row['public_dom']={'file':name,'sha256':hashlib.sha256(public).hexdigest(),
                                               'note':'sanitized_DOM_not_original_response_bytes'}
                        report['results'].append(row)
                    except Exception as exc:report['results'].append({'id':key,'error_type':type(exc).__name__})
                    (OUT/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
                    print(json.dumps({'id':key,'completed':True}),flush=True)
                    await asyncio.sleep(1)
            finally:
                if browser:await browser.close()
                if proc.poll() is None:proc.terminate()
                try:proc.wait(timeout=5)
                except subprocess.TimeoutExpired:proc.kill();proc.wait()
    report['finished_at']=datetime.now(timezone.utc).isoformat()
    (OUT/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
    for n in report['script_hashes']:(OUT/n).write_bytes((Path('diagnostics')/n).read_bytes())

if __name__=='__main__':asyncio.run(main())
