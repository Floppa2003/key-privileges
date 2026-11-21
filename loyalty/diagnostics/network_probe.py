"""Bounded anonymous network experiment, never a discount publisher.

Same script/targets/UA across cold runners. Network and browser observations are
reported separately; an HTTP 200 is not certified catalogue completeness.
Only public fixed targets and same-host links are visited. No auth, proxy, TLS
bypass, private sessions, POST replay, cookies or headers are exported.
"""
from __future__ import annotations
import argparse
import asyncio
import hashlib
import ipaddress
import json
import os
import platform
import re
import socket
import ssl
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin, urlsplit, parse_qsl
from bs4 import BeautifulSoup

UA = 'LoyaltyCatalogResearchBot/0.2 (+https://github.com/Floppa2003/key-privileges)'
CHALLENGE = re.compile(r'access denied|forbidden|just a moment|captcha|доступ ограничен|проверка безопасности|запрос заблокирован|blocked by', re.I)
BENEFIT = re.compile(r'скидк|к[еэ]шб[еэ]к|мил[ьяи]|бонус|\d\s*%', re.I)
BAD_QUERY = re.compile(r'token|secret|password|auth|session|signature|code', re.I)


def safe_url(url, hosts):
    try:
        p=urlsplit(url)
        return (p.scheme=='https' and p.hostname in hosts and not p.username and not p.password
                and p.port in (None,443) and not p.fragment
                and not re.search(r'/(?:auth|login|personal|register|activate|participate)(?:/|$)',p.path,re.I)
                and not any(BAD_QUERY.search(k) for k,_ in parse_qsl(p.query)))
    except (ValueError,TypeError):
        return False


def error_info(exc):
    return {'type':type(exc).__name__,'message':str(exc)[:350],
            **({'verify_code':exc.verify_code,'verify_message':exc.verify_message}
               if isinstance(exc,ssl.SSLCertVerificationError) and hasattr(exc,'verify_code') else {})}


def robots_result(status, body):
    if status is None or status>=500:return 'unreachable'
    if status==429:return 'rate_limited'
    if 400<=status<500:return 'unavailable_4xx'
    if status!=200:return 'redirect_or_other'
    if re.search(r'<(?:!doctype|html|body|script)',body,re.I) or CHALLENGE.search(body[:500]):
        return 'invalid_document'
    return 'parseable'


def document_summary(raw, url):
    soup=BeautifulSoup(raw,'html.parser')
    title=soup.title.get_text(' ',strip=True) if soup.title else ''
    for el in soup.select('script,style,noscript,input,textarea,form'):
        el.decompose()
    main=soup.select_one('main,article') or soup.body or soup
    txt=main.get_text(' ',strip=True)
    challenge=bool(CHALLENGE.search(title) or CHALLENGE.search(txt[:350]))
    links=[];seen=set();host=urlsplit(url).hostname
    for a in soup.select('a[href]'):
        target=urljoin(url,a['href']).split('#',1)[0]
        label=a.get_text(' ',strip=True)
        if target not in seen and safe_url(target,{host}) and label:
            seen.add(target);links.append({'url':target,'label':label[:160]})
        if len(links)>=150:break
    return {'title':title[:200], 'visible_chars':len(txt), 'challenge':challenge,
            'benefit_evidence':bool(not challenge and BENEFIT.search(txt)),
            'body_sha256':hashlib.sha256(raw.encode()).hexdigest(),
            'excerpt':txt[:600] if not challenge else title[:200],
            'excerpt_is_partial':len(txt)>600, 'links':links}


async def network_layers(host):
    """Resolve, then connect and validate TLS against normal public DNS answers."""
    loop=asyncio.get_running_loop();result={'host':host};t=time.monotonic()
    try:
        answers=await asyncio.wait_for(loop.getaddrinfo(host,443,type=socket.SOCK_STREAM),6)
        addresses=[]
        for family,_,_,_,address in answers:
            ip=address[0]
            if not ipaddress.ip_address(ip).is_global:
                raise RuntimeError('non_public_dns_answer')
            if (family,address) not in addresses:addresses.append((family,address))
        result['dns']={'status':'ok','milliseconds':round(1000*(time.monotonic()-t)),
                       'addresses':[a[1][0] for a in addresses]}
    except Exception as exc:
        result['dns']={'status':'failed','error':error_info(exc),'milliseconds':round(1000*(time.monotonic()-t))}
        return result
    result['connections']=[]
    for family,address in addresses[:2]:
        item={'ip':address[0],'family':int(family)};s=socket.socket(family,socket.SOCK_STREAM);s.setblocking(False)
        t=time.monotonic()
        try:
            await asyncio.wait_for(loop.sock_connect(s,address),6)
            item['tcp']={'status':'ok','milliseconds':round(1000*(time.monotonic()-t))}
        except Exception as exc:
            item['tcp']={'status':'failed','error':error_info(exc),'milliseconds':round(1000*(time.monotonic()-t))}
            s.close();result['connections'].append(item);continue
        t=time.monotonic()
        try:
            ctx=ssl.create_default_context();ctx.set_alpn_protocols(['http/1.1'])
            _,writer=await asyncio.wait_for(asyncio.open_connection(sock=s,ssl=ctx,server_hostname=host,ssl_handshake_timeout=8),10)
            tls=writer.get_extra_info('ssl_object');cert=tls.getpeercert()
            item['tls']={'status':'ok','milliseconds':round(1000*(time.monotonic()-t)),
                         'protocol':tls.version(),'not_before':cert.get('notBefore'),
                         'not_after':cert.get('notAfter'),'issuer':cert.get('issuer'),
                         'subject':cert.get('subject')}
            writer.close()
            try:await asyncio.wait_for(writer.wait_closed(),2)
            except Exception:pass
        except Exception as exc:
            item['tls']={'status':'failed','error':error_info(exc),'milliseconds':round(1000*(time.monotonic()-t))};s.close()
        result['connections'].append(item)
    return result


async def certificate_evidence(host):
    """Inspect public handshake certificate only; verification remains enabled."""
    proc=await asyncio.create_subprocess_exec('openssl','s_client','-connect',host+':443',
        '-servername',host,'-showcerts','-verify_return_error','-verify_hostname',host,
        stdin=asyncio.subprocess.PIPE,stdout=asyncio.subprocess.PIPE,stderr=asyncio.subprocess.PIPE)
    try:out,err=await asyncio.wait_for(proc.communicate(b''),12)
    except asyncio.TimeoutError:
        proc.kill();await proc.communicate();return {'status':'timeout'}
    pem=re.search(rb'-----BEGIN CERTIFICATE-----.*?-----END CERTIFICATE-----',out,re.S)
    result={'returncode':proc.returncode,'verification_messages':[
        line for line in err.decode(errors='replace').splitlines()
        if re.search(r'verify error|Verification|certificate has expired|notAfter',line,re.I)][:8]}
    if pem:
        p=await asyncio.create_subprocess_exec('openssl','x509','-noout','-subject','-issuer','-dates','-fingerprint','-sha256',
            stdin=asyncio.subprocess.PIPE,stdout=asyncio.subprocess.PIPE,stderr=asyncio.subprocess.PIPE)
        info,_=await p.communicate(pem[0]);result['certificate_metadata']=info.decode(errors='replace')[:2000]
    return result


async def request_read(context,url,hosts):
    chain=[];start=time.monotonic();body=''
    for _ in range(6):
        if not safe_url(url,hosts):return {'status':None,'error':{'type':'UnsafeRedirect','message':'redirect_not_allowlisted'},'chain':chain},''
        try:
            response=await context.request.get(url,timeout=18000,max_redirects=0)
            status=response.status;entry={'url':url,'status':status};chain.append(entry)
            if 300<=status<400:
                url=urljoin(url,response.headers.get('location',''));continue
            body=await response.text()
            if len(body.encode())>6000000:raise RuntimeError('response_too_large')
            return {'status':status,'url':url,'milliseconds':round(1000*(time.monotonic()-start)),
                    'content_type':response.headers.get('content-type'), 'server_date':response.headers.get('date'),
                    'chain':chain, 'document':document_summary(body,url)},body
        except Exception as exc:
            return {'status':None,'url':url,'milliseconds':round(1000*(time.monotonic()-start)),
                    'error':error_info(exc),'chain':chain},''
    return {'status':None,'error':{'type':'RedirectLimit','message':'six_redirects'},'chain':chain},''


async def browser_read(browser,url,hosts):
    """Fresh anonymous browser; passively summarize only same-host public responses."""
    from playwright.async_api import Error
    context=await browser.new_context(locale='ru-RU',user_agent=UA)
    page=await context.new_page();start=time.monotonic();navigation=[];requests_failed=[];metadata=[];pending=set();details=[]
    async def capture(response):
        p=urlsplit(response.url)
        if p.hostname not in hosts:return
        if response.request.is_navigation_request() and response.frame==page.main_frame:
            navigation.append({'url':response.url.split('?',1)[0],'status':response.status})
        if response.request.resource_type in ('xhr','fetch') and len(metadata)<80:
            metadata.append({'path':p.path,'status':response.status})
        if p.hostname=='vamprivet.ru' and p.path.rstrip('/')=='/api/configs/client' and response.status==200:
            try:
                obj=await response.json()
                for key in ('data','content','promoDetail','promo','promoAction'):
                    obj=obj.get(key) if isinstance(obj,dict) else None
                if isinstance(obj,dict):
                    details.append({k:obj.get(k) for k in ('xml_id','url','name','promoIsCancelled','promoIsFinished','status')})
            except Exception:pass
    def observe(response):
        task=asyncio.create_task(capture(response));pending.add(task);task.add_done_callback(pending.discard)
    def fail(request):
        p=urlsplit(request.url)
        if p.hostname in hosts and len(requests_failed)<30:
            requests_failed.append({'path':p.path,'error':request.failure})
    page.on('response',observe);page.on('requestfailed',fail)
    try:
        response=await page.goto(url,wait_until='domcontentloaded',timeout=25000)
        await page.wait_for_timeout(3500 if urlsplit(url).hostname!='vamprivet.ru' else 16000)
        raw=await page.content()
        result={'status':navigation[-1]['status'] if navigation else (response.status if response else None),
                'url':page.url,'milliseconds':round(1000*(time.monotonic()-start)),
                'document':document_summary(raw,page.url)}
        if response:
            result['security']=await response.security_details()
    except Exception as exc:
        result={'status':None,'error':error_info(exc),'milliseconds':round(1000*(time.monotonic()-start))}
    finally:
        page.remove_listener('response',observe);page.remove_listener('requestfailed',fail)
        if pending:await asyncio.gather(*list(pending),return_exceptions=True)
        await context.close()
    result.update(navigation=navigation,failed_requests=requests_failed,public_network=metadata,mir_detail_identity=details)
    return result


async def probe(browser,cfg,semaphore):
    from protego import Protego
    async with semaphore:
        host=urlsplit(cfg['url']).hostname;hosts={host};out={'source_id':cfg['id'],'root':cfg['url'],'checks':[]}
        out['layers']=await network_layers(host)
        if cfg['id']=='loyals':out['certificate_probe']=await certificate_evidence(host)
        async with await browser.new_context(locale='ru-RU',user_agent=UA) as context:
            robots_url=f'https://{host}/robots.txt'
            rep,raw=await request_read(context,robots_url,hosts)
            decision=robots_result(rep.get('status'),raw)
            out['robots']={'request':rep,'decision':decision}
            # Compare the ordinary browser with the HTTP client. Never solve a challenge.
            if decision not in ('parseable','unavailable_4xx','rate_limited'):
                out['robots']['browser']=await browser_read(browser,robots_url,hosts)
            if decision not in ('parseable','unavailable_4xx'):
                out['stop_reason']='robots_'+decision;return out
            policy=Protego.parse(raw if decision=='parseable' else '')
            targets=[cfg['url']]+cfg.get('canaries',[]);visited=set();next_visited=False;found_details=0
            for url in targets:
                if url in visited:continue
                visited.add(url)
                if not safe_url(url,hosts) or not policy.can_fetch(url,'LoyaltyCatalogResearchBot'):
                    out['checks'].append({'url':url,'stop_reason':'policy_disallow'});continue
                await asyncio.sleep(max(0.8,policy.crawl_delay('LoyaltyCatalogResearchBot') or 0))
                http,_=await request_read(context,url,hosts)
                check={'url':url,'http':http}
                if http.get('status')==429:
                    check['stop_reason']='rate_limited';out['checks'].append(check);break
                check['browser']=await browser_read(browser,url,hosts)
                out['checks'].append(check)
                doc=check['browser'].get('document',{})
                if check['browser'].get('status')==200 and not doc.get('challenge'):
                    for link in doc.get('links',[]):
                        target=link['url']
                        if target in targets:continue
                        if not next_visited and re.fullmatch(r'(?:следующая|далее|next|2|›|»)',link['label'],re.I):
                            targets.append(target);next_visited=True
                        elif found_details<2 and re.search(cfg.get('detail_pattern',r'(?!)'),urlsplit(target).path):
                            targets.append(target);found_details+=1
                if len(visited)>=6:break
        out['stop_reason']='bounded_canaries_complete'
        return out


async def main():
    from playwright.async_api import async_playwright
    parser=argparse.ArgumentParser()
    parser.add_argument('--out',default='network-output')
    args=parser.parse_args();out=Path(args.out);out.mkdir(parents=True,exist_ok=True)
    cfgs=json.loads(Path(__file__).with_name('targets.json').read_text())
    started=datetime.now(timezone.utc).isoformat()
    async with async_playwright() as p:
        browser=await p.chromium.launch();sem=asyncio.Semaphore(2)
        async def bounded(cfg):
            try:return await asyncio.wait_for(probe(browser,cfg,sem),timeout=900)
            except Exception as exc:return {'source_id':cfg['id'],'root':cfg['url'],'experiment_error':error_info(exc)}
        try:results=await asyncio.gather(*(bounded(c) for c in cfgs))
        finally:await browser.close()
    output={'schema_version':1,'purpose':'network_feasibility_not_offer_publication','observed_at':started,
            'finished_at':datetime.now(timezone.utc).isoformat(),'user_agent':UA,
            'environment':{'os':platform.system(),'release':platform.release(),'arch':platform.machine(),
                'python':platform.python_version(),'openssl':ssl.OPENSSL_VERSION,
                'runner_os':os.getenv('RUNNER_OS'),'runner_arch':os.getenv('RUNNER_ARCH'),
                'trial':os.getenv('PROBE_TRIAL'),'run_id':os.getenv('GITHUB_RUN_ID')},
            'code_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            'targets_sha256':hashlib.sha256(Path(__file__).with_name('targets.json').read_bytes()).hexdigest(),
            'results':results}
    (out/'network.json').write_text(json.dumps(output,ensure_ascii=False,indent=2),encoding='utf8')
    for r in results:print(json.dumps({'id':r['source_id'],'stop':r.get('stop_reason'),
        'robots':r.get('robots',{}).get('decision'),'pages':len(r.get('checks',[]))},ensure_ascii=False))

if __name__=='__main__':asyncio.run(main())
