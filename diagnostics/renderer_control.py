"""Bounded public read with renderer controls before any source request."""
from __future__ import annotations
import asyncio
import hashlib
import json
import os
import re
import shutil
import signal
import socket
import subprocess
import tempfile
import time
from pathlib import Path
from urllib.parse import urlsplit
from bs4 import BeautifulSoup
from seven_browser_confirm import ready
from source_readiness import public_dom, public_url, stamp
from ekp_followup import cards

TARGETS={'ekp':'https://ekp.spb.ru/capabilities/loyalty/',
         'nordwind':'https://nordwindairlines.ru/ru/club/partnerlist'}
OUT=Path('renderer-control-output')

async def run(key):
    from playwright.async_api import async_playwright
    OUT.mkdir(exist_ok=True);url=TARGETS[key]
    report={'source_id':key,'target_url':url,'run_id':os.getenv('GITHUB_RUN_ID'),
        'commit':os.getenv('GITHUB_SHA'),'replica':os.getenv('REPLICA'),
        'observed_at':stamp(),'stage':'startup','controls':[], 'network':[], 'captures':[],
        'production_write':False,'catalog_complete':False,'script_hashes':{}}
    for name in ('renderer_control.py','seven_browser_confirm.py','source_readiness.py','ekp_followup.py'):
        data=(Path(__file__).parent/name).read_bytes();(OUT/name).write_bytes(data)
        report['script_hashes'][name]=hashlib.sha256(data).hexdigest()
    def save():
        p=OUT/'report.tmp';p.write_text(json.dumps(report,ensure_ascii=False,indent=2));p.replace(OUT/'report.json')
    async def control(label,operation):
        start=time.monotonic();item={'label':label,'stage':report['stage']}
        try:item['result']=await asyncio.wait_for(operation(),5);item['ok']=True
        except Exception as exc:item.update(ok=False,error=type(exc).__name__)
        item['seconds']=round(time.monotonic()-start,3);report['controls'].append(item);save();return item['ok']
    async def capture(page,label):
        raw=await asyncio.wait_for(page.content(),6)
        safe=public_dom(raw,page.url).encode();name=label+'.html';(OUT/name).write_bytes(safe)
        soup=BeautifulSoup(raw,'html.parser');main=soup.select_one('main')
        entry={'label':label,'url':public_url(page.url),'file':name,'sha256':hashlib.sha256(safe).hexdigest(),
            'cards':cards(raw) if key=='ekp' else [],
            'headings':[h.get_text(' ',strip=True) for h in soup.select('h1')],
            'main_text':main.get_text(' ',strip=True) if main else '',
            'title':soup.title.get_text(' ',strip=True) if soup.title else ''}
        report['captures'].append(entry);save();return entry
    async def wait_listing(page,old=frozenset()):
        until=time.monotonic()+25
        while time.monotonic()<until:
            try:
                raw=await asyncio.wait_for(page.content(),5)
                if key=='ekp' and {c['url'] for c in cards(raw)}-old:return True
                if key=='nordwind' and len(BeautifulSoup(raw,'html.parser').get_text(' ',strip=True))>500:return True
            except Exception:pass
            await asyncio.sleep(2)
        return False
    proc=None;save()
    try:
        exe=shutil.which('google-chrome') or shutil.which('google-chrome-stable')
        if not exe:raise RuntimeError('installed_chrome_missing')
        async with async_playwright() as p:
            with tempfile.TemporaryDirectory() as profile:
                with socket.socket() as sock:sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
                proc=subprocess.Popen([exe,f'--user-data-dir={profile}',f'--remote-debugging-port={port}',
                    '--remote-debugging-address=127.0.0.1','--no-first-run','--no-default-browser-check',
                    '--no-sandbox','--lang=ru-RU','--window-size=1365,900','about:blank'],
                    stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,start_new_session=True)
                until=time.monotonic()+35
                while time.monotonic()<until and proc.poll() is None:
                    if await asyncio.to_thread(ready,port):break
                    await asyncio.sleep(.3)
                else:raise RuntimeError('chrome_startup_timeout')
                browser=await p.chromium.connect_over_cdp(f'http://127.0.0.1:{port}',timeout=10000)
                context=browser.contexts[0];initial=context.pages[0]
                report['stage']='before_source_request';save()
                old_ok=await control('initial_tab_renderer',lambda:initial.evaluate('1 + 1'))
                page=await asyncio.wait_for(context.new_page(),8)
                new_ok=await control('new_tab_renderer',lambda:page.evaluate('1 + 1'))
                report['initial_tab_healthy']=old_ok;report['new_tab_healthy']=new_ok;save()
                if not new_ok:raise RuntimeError('new_tab_control_failed_before_source_request')
                page.set_default_timeout(5000)
                def record(kind,obj):
                    u=public_url(obj.url)
                    if not u or urlsplit(u).hostname!=urlsplit(url).hostname or len(report['network'])>=100:return
                    entry={'kind':kind,'url':u,'seconds':round(time.monotonic()-start,3)}
                    if kind=='response':entry['status']=obj.status;entry['type']=obj.request.resource_type
                    else:
                        entry['type']=obj.resource_type
                        if kind=='failed':
                            marker=re.search(r'net::ERR_[A-Z_]+',obj.failure or '')
                            entry['error']=marker[0] if marker else 'request_failed'
                    if entry['type'] in ('document','xhr','fetch'):report['network'].append(entry);save()
                page.on('request',lambda r:record('request',r))
                page.on('response',lambda r:record('response',r))
                page.on('requestfailed',lambda r:record('failed',r))
                report['stage']='source_navigation';save();start=time.monotonic()
                try:await page.goto(url,wait_until='domcontentloaded',timeout=20000)
                except Exception as exc:report['navigation_error']=type(exc).__name__;save()
                loaded=await wait_listing(page);report['listing_ready']=loaded;save()
                if loaded:
                    first=await capture(page,'initial-listing')
                    if key=='ekp':
                        report['stage']='load_more';save()
                        try:
                            await page.get_by_role('button',name=re.compile(r'^Показать еще$')).click(timeout=5000)
                            grew=await wait_listing(page,frozenset(c['url'] for c in first['cards']))
                            after=await capture(page,'after-load-more')
                            report['load_more']={'grew':grew,'before':len(first['cards']),'after':len(after['cards'])};save()
                        except Exception as exc:report['load_more']={'error':type(exc).__name__};save()
                        eligible=[c for c in first['cards'] if not c['login_notice']]
                        if eligible:
                            chosen=eligible[0];report['stage']='public_detail';report['selected_card']=chosen;save()
                            await page.locator('main a[href="'+urlsplit(chosen['url']).path+'"]').first.click(timeout=5000)
                            await asyncio.sleep(8)
                            detail=await capture(page,'selected-detail')
                            report['detail_identity_matches']=(detail['url']==chosen['url'] and chosen['title'] in detail['main_text'] and not detail['cards'])
                report['stage']='after_source_request';save()
                await control('source_tab_renderer',lambda:page.evaluate('1 + 1'))
                blank=await asyncio.wait_for(context.new_page(),8)
                await control('fresh_blank_renderer_after_source',lambda:blank.evaluate('1 + 1'))
                report['stage']='complete';save()
                try:await asyncio.wait_for(browser.close(),3)
                except Exception:pass
                finally:
                    if proc.poll() is None:os.killpg(proc.pid,signal.SIGKILL)
                    proc.wait(timeout=3)
    except Exception as exc:
        safe={'chrome_startup_timeout','new_tab_control_failed_before_source_request','installed_chrome_missing'}
        report['error']=str(exc) if str(exc) in safe else type(exc).__name__
    finally:
        if proc and proc.poll() is None:os.killpg(proc.pid,signal.SIGKILL);proc.wait(timeout=3)
        report['finished_at']=stamp();save()

if __name__=='__main__':asyncio.run(run(os.environ['SOURCE_ID']))
