"""Bounded diagnostic reads, isolated by Actions job; never a production fallback.
A public HTML shell is not a loaded catalog. Read only the seven configured URLs
in fresh disposable Chrome profiles; no accounts, spoofing, proxy, or saved text.
"""
from __future__ import annotations
import argparse
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
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin, urlsplit, urlunsplit
from bs4 import BeautifulSoup

IDS = ('utair','ekp','nordwind','coral','coral_promo','rzd','aeroflot')
OUT = Path('source-readiness-output')


def stamp():
    return datetime.now(timezone.utc).isoformat()


def public_url(value):
    try:
        u = urlsplit(value)
        if u.scheme not in ('http','https') or not u.hostname or u.username or u.password:
            return None
        return urlunsplit((u.scheme,u.netloc,u.path,'',''))
    except ValueError:
        return None


def classify(key, html, status, url):
    soup = BeautifulSoup(html,'html.parser')
    for e in soup.select('script,style,noscript,form,input,textarea,iframe'):
        e.decompose()
    title = soup.title.get_text(' ',strip=True) if soup.title else ''
    body = soup.get_text(' ',strip=True)
    result = {'status':status,'url':public_url(url),'title':title[:300],
              'text_chars':len(body),'raw_sha256':hashlib.sha256(html.encode()).hexdigest(),
              'classification':'unclassified_public_page','catalog_complete':False}
    if not status:
        result['classification']='no_main_document_response'
    elif status >= 400:
        result['classification']='http_refusal' if status < 500 else 'http_server_error'
    elif re.search(r'доступ.{0,50}ограничен|access denied|forbidden|captcha|проверка браузера',title+' '+body[:500],re.I):
        result['classification']='restriction_document'
    elif status != 200:
        result['classification']='non_content_status'
    elif key == 'utair':
        article = soup.select_one('[class*="SupportWidgets_content"]')
        headings = soup.select('h1')
        good = article and any('Utair Status' in h.get_text() for h in headings)
        links = [a for a in article.select('a[href]')] if article else []
        result['article_links']=len(links)
        result['classification']='public_article_loaded' if good and links else 'public_shell_no_article'
    elif key == 'ekp':
        cards = sorted({public_url(urljoin(url,a['href'])) for a in soup.select('a[href]')
                        if urlsplit(urljoin(url,a['href'])).hostname=='ekp.spb.ru'
                        and re.fullmatch(r'/capabilities/loyalty/tiles/[0-9]+/?',urlsplit(urljoin(url,a['href'])).path)})
        result['card_urls']=cards
        result['classification']='catalog_cards_loaded' if cards else 'public_shell_no_cards'
    return result


def public_dom(html,url):
    soup=BeautifulSoup(html,'html.parser')
    for e in soup.select('script,style,noscript,form,input,textarea,iframe,[hidden],[aria-hidden="true"]'):
        e.decompose()
    for e in soup.find_all(True):
        for a in list(e.attrs):
            if a not in ('id','class','href','title','role'):del e.attrs[a]
        if e.has_attr('href'):
            clean=public_url(urljoin(url,e['href']))
            if clean:e['href']=clean
            else:del e.attrs['href']
    return str(soup)


def selfcheck():
    shell='<html><title>Партнеры</title><main>Партнеры Скидки Показать еще 30 60 120</main></html>'
    assert classify('ekp',shell,200,'https://ekp.spb.ru/')['classification']=='public_shell_no_cards'
    for ident in ('12','987654'):
        card=shell+f'<a href="/capabilities/loyalty/tiles/{ident}">Новый партнер</a>'
        d=classify('ekp',card,200,'https://ekp.spb.ru/')
        assert d['classification']=='catalog_cards_loaded' and not d['catalog_complete']
    assert not classify('ekp',shell+'<a href="https://evil.example/capabilities/loyalty/tiles/1">x</a>',200,'https://ekp.spb.ru/')['card_urls']
    for status in (401,403,429,503):
        assert classify('utair',shell,status,'https://www.utair.ru/')['classification']!='public_article_loaded'
    assert classify('aeroflot','<title>Доступ к сайту временно ограничен владельцем</title>',200,'https://www.aeroflot.ru/')['classification']=='restriction_document'
    article='<h1>Партнеры Utair Status</h1><div class="SupportWidgets_content__new"><a href="/new">Пример 17%</a></div>'
    assert classify('utair',article,200,'https://www.utair.ru/')['classification']=='public_article_loaded'
    assert classify('utair',article.replace('SupportWidgets_content','Other'),200,'https://www.utair.ru/')['classification']=='public_shell_no_article'
    assert classify('ekp',shell,0,'chrome-error://chromewebdata/')['classification']=='no_main_document_response'
    safe=public_dom('<script>secret</script><form>private</form><p onclick="x()">public</p><a href="/x?accessToken=secret#private">x</a>','https://example.org')
    assert 'secret' not in safe and 'onclick' not in safe and 'private' not in safe
    assert public_url('https://user:password@example.org/') is None
    print('14 diagnostic assertions passed',flush=True)


async def run(key):
    from playwright.async_api import async_playwright
    from seven_browser_confirm import ready
    targets={s['id']:s['url'] for s in json.loads(Path('loyalty/sources_normalized.json').read_text()) if s['id'] in IDS}
    if key not in IDS or set(targets)!=set(IDS):raise ValueError('unexpected_source_configuration')
    url=targets[key];exe=shutil.which('google-chrome') or shutil.which('google-chrome-stable')
    if not exe:raise RuntimeError('installed_chrome_missing')
    OUT.mkdir(exist_ok=True)
    report={'source_id':key,'target_url':url,'run_id':os.getenv('GITHUB_RUN_ID'),'commit':os.getenv('GITHUB_SHA'),
            'replica':os.getenv('REPLICA'),'observed_at':stamp(),'stage':'startup','snapshots':[],
            'navigation':[],'public_network':[],'secrets_used':False,'production_write':False,
            'chrome_version':subprocess.check_output([exe,'--version'],timeout=5).decode().strip(),
            'script_hashes':{n:hashlib.sha256((Path(__file__).parent/n).read_bytes()).hexdigest()
                 for n in ('source_readiness.py','seven_browser_confirm.py')},
            'tls_verification':True,'catalog_complete':False}
    def save():
        tmp=OUT/'report.tmp';tmp.write_text(json.dumps(report,ensure_ascii=False,indent=2));tmp.replace(OUT/'report.json')
    for n in report['script_hashes']:(OUT/n).write_bytes((Path(__file__).parent/n).read_bytes())
    save()
    proc=None;browser=None
    try:
        async with async_playwright() as p:
            with tempfile.TemporaryDirectory() as profile:
                with socket.socket() as sock:sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
                proc=subprocess.Popen([exe,f'--user-data-dir={profile}',f'--remote-debugging-port={port}',
                      '--remote-debugging-address=127.0.0.1','--no-first-run','--no-default-browser-check',
                      '--no-sandbox','--lang=ru-RU','--window-size=1365,900','about:blank'],
                      stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,start_new_session=True)
                start=time.monotonic()
                while time.monotonic()-start<35 and proc.poll() is None:
                    if await asyncio.to_thread(ready,port):break
                    await asyncio.sleep(.3)
                else:raise RuntimeError('chrome_startup_timeout')
                browser=await p.chromium.connect_over_cdp(f'http://127.0.0.1:{port}',timeout=10000)
                context=browser.contexts[0];page=context.pages[0]
                context.set_default_timeout(8000)
                def response(r):
                    try:
                        req=r.request;u=public_url(r.url)
                        if req.is_navigation_request() and r.frame==page.main_frame:
                            report['navigation'].append({'status':r.status,'url':u})
                        if u and req.resource_type in ('document','xhr','fetch') and urlsplit(u).hostname==urlsplit(url).hostname and len(report['public_network'])<120:
                            report['public_network'].append({'url':u,'status':r.status,'type':req.resource_type})
                    except Exception:pass
                page.on('response',response)
                report['stage']='navigating';save()
                try:await page.goto(url,wait_until='domcontentloaded',timeout=20000)
                except Exception as exc:report['navigation_error']=type(exc).__name__
                report['stage']='waiting_for_source_content';save();previous=0
                for second in (2,8,20,45):
                    await asyncio.sleep(second-previous);previous=second
                    try:
                        raw=await asyncio.wait_for(page.content(),timeout=6)
                        status=report['navigation'][-1]['status'] if report['navigation'] else 0
                        item=classify(key,raw,status,page.url);item['after_seconds']=second
                        report['snapshots'].append(item)
                        if item['classification'] in ('public_article_loaded','catalog_cards_loaded','public_shell_no_cards','public_shell_no_article'):
                            data=public_dom(raw,page.url).encode();(OUT/'public-dom.html').write_bytes(data)
                            report['public_dom']={'file':'public-dom.html','sha256':hashlib.sha256(data).hexdigest(),'kind':'sanitized_live_DOM_not_original_response'}
                        save()
                        if item['classification'] in ('public_article_loaded','catalog_cards_loaded','restriction_document') or status in (403,429):break
                        if not status and second>=8:break
                    except Exception as exc:
                        report['snapshots'].append({'after_seconds':second,'error_type':type(exc).__name__});save()
                page.remove_listener('response',response)
                report['stage']='read_complete';report['finished_at']=stamp();save()
                try:await asyncio.wait_for(browser.close(),timeout=3)
                except Exception:report['cleanup_warning']='browser_close_timeout_or_error'
                finally:
                    if proc.poll() is None:os.killpg(proc.pid,signal.SIGTERM)
                    try:proc.wait(timeout=3)
                    except subprocess.TimeoutExpired:os.killpg(proc.pid,signal.SIGKILL);proc.wait(timeout=3)
    except Exception as exc:
        report['harness_error']=type(exc).__name__
    finally:
        if proc and proc.poll() is None:
            os.killpg(proc.pid,signal.SIGKILL)
            proc.wait(timeout=3)
        report['harness_finished_at']=stamp();save()
    if report.get('harness_error'):raise RuntimeError('diagnostic_harness_failed')


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--source',choices=IDS);parser.add_argument('--selfcheck',action='store_true');args=parser.parse_args()
    if args.selfcheck:selfcheck()
    elif args.source:asyncio.run(run(args.source))
    else:parser.error('--source or --selfcheck is required')
