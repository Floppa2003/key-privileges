"""Bounded new public EKP reads. One Free account, no production publication.

425 credits / 5 target calls at most. No account cookies or guessed APIs.
The static comparison and detail browsers use fresh root-discovered URLs.
"""
from __future__ import annotations
import base64
import hashlib
import json
import os
import re
import sys
import time
from pathlib import Path
from urllib.parse import urlsplit, parse_qsl
from bs4 import BeautifulSoup
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'loyalty'))
from free_access_probe import FreeReader, ProbeError, free_plan, now

ROOT = 'https://ekp.spb.ru/capabilities/loyalty/'
POLICY = 'https://ekp.spb.ru/robots.txt'
AGENT = 'LoyaltyCatalogResearchBot'
MAX_CREDITS = 425
DAILY_RESERVE = 290
OUT = Path('ekp-detail-output')
DETAIL_JS = r"""
const sleep=ms=>new Promise(r=>setTimeout(r,ms));
const end=Date.now()+12000;
function ready(){const m=document.querySelector('main');return m&&m.innerText.trim().length>400;}
while(!ready()&&Date.now()<end)await sleep(300);
await sleep(1100);
document.documentElement.setAttribute('data-probe-location',location.href);
"""


def card_url(value):
    u = urlsplit(value)
    if (u.scheme != 'https' or u.netloc != 'ekp.spb.ru' or u.fragment
        or not re.fullmatch(r'/capabilities/loyalty/tiles/[0-9]+/?', u.path)):
        raise ProbeError('invalid_card_url')
    q = parse_qsl(u.query, keep_blank_values=True)
    if q and (len(q) != 1 or q[0][0] != 'region' or not q[0][1].isdigit()):
        raise ProbeError('invalid_card_region')
    return value



def index_url(value):
    u = urlsplit(value)
    q = parse_qsl(u.query, keep_blank_values=True)
    if (u.scheme != 'https' or u.netloc != 'ekp.spb.ru' or u.fragment
        or u.path not in ('/capabilities/loyalty/tiles', '/capabilities/loyalty/tiles/')
        or (q and (len(q) != 1 or q[0][0] != 'region' or not q[0][1].isdigit()))):
        raise ProbeError('catalogue_location_changed')
    return value


def catalogue_cards(raw):
    soup = BeautifulSoup(raw, 'html.parser'); found = {}
    for a in soup.select('main a[href]'):
        if '/capabilities/loyalty/tiles/' not in a['href']: continue
        url = card_url(a['href']); box = a.find_parent(class_='v-card')
        title = box.select_one('.v-card-title') if box else None
        if title is None: raise ProbeError('unowned_card')
        record = {'url': url, 'title': title.get_text(' ', strip=True),
                  'login_notice': 'Требуется авторизация' in box.get_text(' ', strip=True)}
        if url in found and found[url] != record: raise ProbeError('conflicting_cards')
        found[url] = record
    if not found: raise ProbeError('empty_catalogue')
    return list(found.values())


def sanitize_detail(raw, requested, browser):
    from public_transport import check_response
    check_response(200, raw)
    soup = BeautifulSoup(raw, 'html.parser')
    actual = soup.html.get('data-probe-location') if soup.html else None
    if browser and actual != requested: raise ProbeError('detail_location_changed')
    main = soup.select_one('main')
    if main is None:
        return '', {'status': 'application_shell_no_main', 'final_url': actual}
    for n in main.select('script,style,noscript,form,input,textarea,iframe,svg,img,[hidden],[aria-hidden="true"]'):
        n.decompose()
    for n in main.find_all(True):
        for k in list(n.attrs):
            if k not in ('class','id','role','title','href'): del n.attrs[k]
        if n.has_attr('href'):
            from urllib.parse import urljoin, urlunsplit
            u = urlsplit(urljoin(requested,n['href']))
            if u.scheme not in ('http','https') or not u.hostname or u.username or u.password:
                del n.attrs['href']
            elif u.netloc=='ekp.spb.ru' and re.fullmatch(r'/capabilities/loyalty/tiles/[0-9]+/?',u.path):
                n['href']=card_url(urljoin(requested,n['href']))
            else: n['href']=urlunsplit((u.scheme,u.netloc,u.path,'',''))
    value = main.get_text('\n', strip=True)
    return str(main), {'status':'public_detail_candidate' if len(value)>400 else 'application_shell_short_main',
        'final_url':actual,'text_chars':len(value),'login_notice':'авториз' in value.lower(),
        'terms_completeness_verified':False}


class Probe:
    def __init__(self, key):
        self.transport = FreeReader(key, [{'url':ROOT}])
        self.calls = 0; self.reserved = 0; self.charged = 0
        self.allowed = {ROOT, POLICY}; self.started = time.monotonic()

    def balance(self):
        payload, _ = self.transport._request('usage', {})
        left = free_plan(payload)
        return {'plan':'Free', 'total':payload['plan_total_credits'], 'remaining':left, 'observed_at':now()}

    def read(self, url, *, js=None):
        if self.transport.halted or url not in self.allowed: raise ProbeError('unapproved_or_stopped')
        cost = 125 if js else 25
        if self.calls>=5 or self.reserved+cost>MAX_CREDITS or time.monotonic()-self.started>480:
            raise ProbeError('probe_budget')
        self.calls+=1; self.reserved+=cost
        params={'url':url,'browser':'true' if js else 'false','proxy_type':'residential','proxy_country':'RU','timeout':'60'}
        if js:
            params.update(js_snippet=base64.b64encode(js.encode()).decode(),block_resource=['image','media','font'])
        raw,meta=self.transport._request('general',params)
        charge=str(meta.get('Ant-credits-cost','')); status=str(meta.get('Ant-page-status-code',''))
        if not charge.isdigit() or int(charge)>cost or not re.fullmatch('[1-5][0-9]{2}',status):
            self.transport.halted=True;raise ProbeError('unverified_cost_or_status')
        self.charged+=int(charge)
        if status=='429' or meta.get('ant-original-header-retry-after'):
            self.transport.halted=True;raise ProbeError('origin_rate_limit')
        if status!='200':raise ProbeError('origin_http_'+status)
        return raw


def main():
    from public_transport import robots_document
    from protego import Protego
    OUT.mkdir(exist_ok=True); probe=None
    report={'run_id':os.getenv('GITHUB_RUN_ID'),'run_attempt':os.getenv('GITHUB_RUN_ATTEMPT'),
        'commit':os.getenv('GITHUB_SHA'),'started_at':now(),'publication':False,'account_session':False,
        'max_credits':MAX_CREDITS,'details':[]}
    def save():
        if probe:report.update(requests=probe.calls,reserved_credits=probe.reserved,successful_cost_headers=probe.charged)
        (OUT/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
    try:
        probe=Probe(os.environ.get('SCRAPINGANT_API_KEY','')); report['opening_balance']=probe.balance();save()
        if report['opening_balance']['remaining']<MAX_CREDITS+DAILY_RESERVE:raise ProbeError('preserve_daily_credit_reserve')
        raw=probe.read(POLICY);rules,state=robots_document(200,raw);policy=Protego.parse(rules)
        if not all(policy.can_fetch(u,AGENT) for u in (ROOT,ROOT+'tiles')):raise ProbeError('robots_disallow')
        rate=policy.request_rate(AGENT)
        delay=max(1.1,policy.crawl_delay(AGENT) or 0,rate.seconds/rate.requests if rate else 0)
        if delay>1.1:raise ProbeError('policy_slower_than_ui_budget')
        report['policy']={'status':200,'state':state,'sha256':hashlib.sha256(raw.encode()).hexdigest()}
        (OUT/'robots.txt').write_text(rules);time.sleep(delay)
        js=Path(__file__).with_name('ekp_catalogue_full_ui.js').read_text()
        raw=probe.read(ROOT,js=js);node=BeautifulSoup(raw,'html.parser').select_one('#loyalty-public-ui-evidence')
        if node is None:raise ProbeError('catalogue_marker_missing')
        result=json.loads(node.get_text());report['catalogue']={k:v for k,v in result.items() if k not in ('snapshots','publicResponses')}
        snaps=result.get('snapshots',[]);snap=next((x for x in reversed(snaps) if x['label']=='expanded'),None)
        if snap is None:raise ProbeError('expanded_snapshot_missing')
        index_url(snap['url'])
        if not policy.can_fetch(snap['url'], AGENT):raise ProbeError('robots_disallow')
        data=snap['html'].encode();cards=catalogue_cards(snap['html'])
        if {x['url'] for x in cards}!={x['url'] for x in snap['cards']}:raise ProbeError('card_inventory_mismatch')
        report['catalogue'].update(cards=len(cards),sha256=hashlib.sha256(data).hexdigest(),observed_at=snap['observedAt'])
        (OUT/'catalogue.html').write_bytes(data);(OUT/'cards.json').write_text(json.dumps(cards,ensure_ascii=False,indent=2));save()
        if result.get('error')=='restriction_document':raise ProbeError('restriction_document')
        # Compare different visible access classes; never click issue-code controls.
        selected=[]
        for login in (False,True):
            choice=next((c for c in cards if c['login_notice'] is login and policy.can_fetch(c['url'],AGENT)),None)
            if choice:selected.append(choice)
        for index,card in enumerate(selected):
            url=card_url(card['url']);probe.allowed.add(url)
            modes=[False,True] if index==0 else [True]
            for browser in modes:
                item={**card,'browser':browser,'started_at':now()};report['details'].append(item)
                try:
                    time.sleep(delay);raw=probe.read(url,js=DETAIL_JS if browser else None)
                    clean,meta=sanitize_detail(raw,url,browser);item.update(meta)
                    if clean:
                        data=clean.encode();name=f'detail-{index}-{int(browser)}.html'
                        (OUT/name).write_bytes(data);item.update(file=name,sha256=hashlib.sha256(data).hexdigest())
                except Exception as exc:
                    item['error']=safe_error(exc)
                    # A refusal is terminal for this URL, never retried in another mode.
                    break
                finally:item['finished_at']=now();save()
            if probe.transport.halted:break
    except Exception as exc:report['error']=safe_error(exc)
    finally:
        if probe and not probe.transport.halted:
            try:report['closing_balance']=probe.balance()
            except Exception as exc:report['balance_error']=safe_error(exc)
        report['finished_at']=now();save()
        (OUT/'executed.py').write_bytes(Path(__file__).read_bytes())
        (OUT/'executed-ui.js').write_bytes(Path(__file__).with_name('ekp_catalogue_full_ui.js').read_bytes())
        print(json.dumps({k:report.get(k) for k in ('error','requests','reserved_credits','successful_cost_headers')}))


def safe_error(exc):
    code=str(exc)
    return code if re.fullmatch('[a-z_0-9]{1,100}',code) else type(exc).__name__


def selfcheck():
    card_url(ROOT+'tiles/123?region=98')
    index_url(ROOT+'tiles?region=98')
    index_url(ROOT+'tiles/')
    for bad in (ROOT+'tiles?token=secret',ROOT+'tiles?region=98&region=1','https://evil.test/capabilities/loyalty/tiles'):
        try:index_url(bad)
        except ProbeError:pass
        else:raise AssertionError('unsafe index URL accepted')
    for bad in ('https://other.test/123',ROOT+'tiles/123?token=secret',ROOT+'tiles/123?region=98&region=1'):
        try:card_url(bad)
        except ProbeError:pass
        else:raise AssertionError('unsafe URL accepted')
    p=Probe('fixture-key');p.allowed.add(ROOT+'tiles/123?region=98')
    p.transport._request=lambda endpoint,params:('x',{'Ant-credits-cost':'125' if params['browser']=='true' else '25','Ant-page-status-code':'200'})
    for url,js in [(POLICY,None),(ROOT,'fixture'),(ROOT+'tiles/123?region=98',None),(ROOT+'tiles/123?region=98','fixture'),(ROOT+'tiles/123?region=98','fixture')]:p.read(url,js=js)
    assert p.reserved==425 and p.calls==5
    try:p.read(ROOT)
    except ProbeError:pass
    else:raise AssertionError('budget not enforced')
    p.transport.halted=True
    try:p.read(ROOT)
    except ProbeError:pass
    else:raise AssertionError('global stop ignored')
    print('EKP URL, credit, request and global-stop checks passed')


if __name__=='__main__':
    selfcheck()
    if '--selfcheck' not in sys.argv:main()
