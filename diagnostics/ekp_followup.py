"""Diagnostic only: public EKP UI load-more and one discovered non-login card."""
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
from urllib.parse import urljoin, urlsplit
from bs4 import BeautifulSoup
from source_readiness import public_dom, public_url, stamp

ROOT='https://ekp.spb.ru/capabilities/loyalty/'
OUT=Path('ekp-followup-output')


def cards(raw):
    soup=BeautifulSoup(raw,'html.parser');result={}
    for a in soup.select('main a[href]'):
        url=urljoin(ROOT,a['href']);u=urlsplit(url)
        if u.scheme!='https' or u.netloc!='ekp.spb.ru' or not re.fullmatch(r'/capabilities/loyalty/tiles/[0-9]+/?',u.path) or u.query or u.fragment:continue
        box=a.find_parent(class_='v-card')
        if box is None:continue
        name=box.select_one('.v-card-title')
        result[url]={'url':url,'title':name.get_text(' ',strip=True) if name else '',
            'listing_text':box.get_text(' ',strip=True),
            'login_notice':'Требуется авторизация' in box.get_text(' ',strip=True)}
    return list(result.values())


def selfcheck():
    def fixture(ident,title='Новый партнер',suffix=''):
        return f'<main><div class="v-card"><div class="v-card-title">{title}</div>{suffix}<a href="/capabilities/loyalty/tiles/{ident}">Подробнее</a></div></main>'
    for ident in ('2','67890'):
        d=cards(fixture(ident))[0];assert d['url'].endswith('/'+ident) and d['title']=='Новый партнер'
    assert cards(fixture('1',suffix='Требуется авторизация'))[0]['login_notice']
    assert not cards(fixture('1').replace('/capabilities/','https://foreign.example/capabilities/'))
    assert not cards(fixture('1').replace('tiles/1','tiles/not-a-card'))
    assert not cards(fixture('1').replace('tiles/1','tiles/1?token=x'))
    assert len(cards(fixture('1')+fixture('1')))==1
    assert not cards(fixture('1').replace('<main>','<footer>').replace('</main>','</footer>'))
    print('8 EKP ownership, identity and login-boundary assertions passed',flush=True)


async def run():
    from playwright.async_api import async_playwright
    from seven_browser_confirm import ready
    OUT.mkdir(exist_ok=True)
    report={'run_id':os.getenv('GITHUB_RUN_ID'),'commit':os.getenv('GITHUB_SHA'),
        'replica':os.getenv('REPLICA'),'observed_at':stamp(),'target_url':ROOT,'stage':'startup',
        'main_responses':[],'captures':[],'steps':[],'full_catalog_collected':False,
        'no_authentication_or_private_storage_used':True,'production_write':False}
    def save():
        p=OUT/'report.tmp';p.write_text(json.dumps(report,ensure_ascii=False,indent=2));p.replace(OUT/'report.json')
    report['script_hashes']={}
    for n in ('ekp_followup.py','source_readiness.py','seven_browser_confirm.py'):
        data=(Path(__file__).parent/n).read_bytes();(OUT/n).write_bytes(data)
        report['script_hashes'][n]=hashlib.sha256(data).hexdigest()
    save();proc=None
    async def capture(page,label):
        raw=await asyncio.wait_for(page.content(),6)
        data=public_dom(raw,page.url).encode();name=label+'.html';(OUT/name).write_bytes(data)
        body=BeautifulSoup(raw,'html.parser');main=body.select_one('main')
        item={'label':label,'url':public_url(page.url),'observed_at':stamp(),
            'file':name,'sha256':hashlib.sha256(data).hexdigest(),
            'cards':cards(raw),'headings':[n.get_text(' ',strip=True) for n in body.select('main h1,main h2')],
            'main_text':main.get_text(' ',strip=True) if main else '',
            'kind':'sanitized_live_DOM_not_original_response'}
        report['captures'].append(item);save();return item
    async def wait_cards(page,old=frozenset()):
        until=time.monotonic()+35
        while time.monotonic()<until:
            try:
                found=cards(await asyncio.wait_for(page.content(),6))
                if {x['url'] for x in found}-old:return found
            except Exception:pass
            if report['main_responses'] and report['main_responses'][-1]['status'] in (403,429):raise RuntimeError('public_http_refusal')
            await asyncio.sleep(2)
        raise RuntimeError('public_cards_not_loaded_in_budget')
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
                page=browser.contexts[0].pages[0];page.set_default_timeout(6000)
                def response(r):
                    if r.request.is_navigation_request() and r.frame==page.main_frame:
                        report['main_responses'].append({'url':public_url(r.url),'status':r.status})
                page.on('response',response);report['stage']='catalog';save()
                try:await page.goto(ROOT,wait_until='domcontentloaded',timeout=20000)
                except Exception as exc:report['navigation_error']=type(exc).__name__;save()
                first=await wait_cards(page);await capture(page,'initial-listing')
                report['stage']='load_more';save()
                try:
                    button=page.get_by_role('button',name=re.compile(r'^Показать еще$'))
                    await button.press('Enter',timeout=6000)
                    expanded=await wait_cards(page,frozenset(c['url'] for c in first))
                    after=await capture(page,'after-load-more')
                    report['steps'].append({'action':'visible_load_more_button','result':'new_card_urls_observed',
                        'before':len(first),'after':len(expanded),'new_urls':len({c['url'] for c in expanded}-{c['url'] for c in first})})
                except Exception as exc:
                    report['steps'].append({'action':'visible_load_more_button','error_type':type(exc).__name__})
                save();eligible=[c for c in first if not c['login_notice']]
                if not eligible:raise RuntimeError('no_public_non_login_card_discovered')
                selected=eligible[0];report['selected_card']=selected;report['stage']='detail';save()
                await page.locator(f'main a[href="{urlsplit(selected["url"]).path}"]').first.press('Enter',timeout=6000)
                until=time.monotonic()+30
                while time.monotonic()<until:
                    await asyncio.sleep(2)
                    raw=await asyncio.wait_for(page.content(),6);soup=BeautifulSoup(raw,'html.parser');main=soup.select_one('main')
                    if public_url(page.url)==selected['url'] and main and len(main.get_text(' ',strip=True))>300 and not cards(raw):break
                detail=await capture(page,'selected-detail')
                report['steps'].append({'action':'public_discovered_card_link','url_matches':detail['url']==selected['url'],
                    'listing_title_in_detail':bool(selected['title']) and selected['title'] in detail['main_text'],
                    'human_source_review_required':True})
                report['stage']='followup_complete';save();page.remove_listener('response',response)
                try:await asyncio.wait_for(browser.close(),3)
                except Exception:report['cleanup_warning']='browser_close_timeout_or_error'
                finally:
                    if proc.poll() is None:os.killpg(proc.pid,signal.SIGTERM)
                    try:proc.wait(timeout=3)
                    except subprocess.TimeoutExpired:os.killpg(proc.pid,signal.SIGKILL);proc.wait(timeout=3)
    except Exception as exc:
        safe={'public_cards_not_loaded_in_budget','public_http_refusal','chrome_startup_timeout','installed_chrome_missing','no_public_non_login_card_discovered'}
        report['error']=str(exc) if str(exc) in safe else type(exc).__name__
    finally:
        if proc and proc.poll() is None:os.killpg(proc.pid,signal.SIGKILL);proc.wait(timeout=3)
        report['finished_at']=stamp();save()

if __name__=='__main__':
    import sys
    if '--selfcheck' in sys.argv:selfcheck()
    else:asyncio.run(run())
