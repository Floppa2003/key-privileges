"""Test ordinary inline EKP details plus one source-observed public GET.

175-credit/3-request ceiling. No schedule, publication, account, private cookies,
guessed API request bodies or coupon action.
"""
import base64
import hashlib
import json
import os
import re
import sys
import time
from pathlib import Path
from bs4 import BeautifulSoup
from free_residential_comparison import ProbeError, now
from ekp_detail_probe import card_url
from free_access_probe import free_plan, FreeReader
from ekp_owned_terms import extract, selfcheck as terms_selfcheck

ROOT='https://ekp.spb.ru/capabilities/loyalty/'
PREFIX='/capabilities/loyalty/tiles'
OUT=Path('ekp-inline-output')
JS=Path(__file__).with_suffix('.js').read_text()


def namespace_allowed(rules):
    # Conservative diagnostic gate: every disallow in every group must be outside
    # the namespace; fine-grained/wildcard overlap needs a reviewed policy adapter.
    for line in rules.splitlines():
        line=line.split('#',1)[0].strip()
        if ':' not in line:continue
        key,value=line.split(':',1);value=value.strip()
        if key.lower()=='disallow' and value:
            prefix=value.rstrip('$').split('*',1)[0]
            if not prefix or PREFIX.startswith(prefix) or prefix.startswith(PREFIX):
                raise ProbeError('namespace_policy_needs_review')


class Reader(FreeReader):
    balance=None
    def _request(self,endpoint,params):
        if endpoint=='general' and params.get('browser')=='true':
            params={**params,'js_snippet':base64.b64encode(JS.encode()).decode()}
        data,meta=super()._request(endpoint,params)
        if endpoint=='usage':
            left=free_plan(data)
            self.balance={'plan':'Free','total':data['plan_total_credits'],'remaining':left,'observed_at':now()}
            if left<465:raise ProbeError('preserve_daily_credit_reserve')
        return data,meta

    def read(self, url, *, browser):
        if not self.ready or self.halted or url not in self.allowed:
            raise ProbeError('unapproved_comparison_request')
        cost = 125 if browser else 25
        if self.calls >= 3 or self.reserved + cost > 175:
            raise ProbeError('comparison_budget')
        self.calls += 1; self.reserved += cost
        params = {'url': url, 'browser': str(browser).lower(), 'proxy_type': 'residential',
                  'proxy_country': 'RU', 'timeout': '60'}
        if browser: params['block_resource'] = ['image', 'media', 'font']
        raw, meta = self._request('general', params)
        charged = str(meta.get('Ant-credits-cost', ''))
        status = str(meta.get('Ant-page-status-code', ''))
        if not charged.isdigit() or int(charged) > cost or not re.fullmatch('[1-5][0-9]{2}', status):
            self.halted = True; raise ProbeError('comparison_cost_or_status_unverified')
        self.known_charged_credits += int(charged)
        if status == '429' or meta.get('ant-original-header-retry-after'):
            self.halted = True; raise ProbeError('origin_rate_limit')
        return int(status), raw, int(charged)


def checked_details(result,policy):
    from public_transport import check_response
    allowed={card_url(x['url']):x for x in result['initialCards']}
    if len(allowed)!=len(result['initialCards']) or not 1<=len(allowed)<=120:raise ProbeError('initial_cards_invalid')
    rows=[];seen=set()
    for item in result.get('details',[]):
        url=card_url(item['url']);ident=url.split('?')[0].rstrip('/').split('/')[-1]
        if url not in allowed or url in seen or item['finalUrl']!=url or not policy.can_fetch(url,'LoyaltyCatalogResearchBot'):
            raise ProbeError('detail_identity_invalid')
        if item['title']!=allowed[url]['title']:raise ProbeError('discovery_title_changed')
        soup=BeautifulSoup(item['html'],'html.parser');owners=soup.find_all(id='partner.'+ident)
        if len(owners)!=1 or len(soup.find_all(id=re.compile(r'^partner\.\d+$')))!=1:raise ProbeError('detail_owner_invalid')
        title=owners[0].select_one('.v-card-title')
        if title is None or title.get_text(' ',strip=True)!=item['title']:raise ProbeError('detail_title_invalid')
        if soup.select('script,style,iframe,form,input,textarea,button'):raise ProbeError('interactive_detail_not_sanitized')
        value=owners[0].get_text(' ',strip=True);check_response(200,value)
        try: parsed={'owned_terms':extract(item['html'],url,item['title'])}
        except ValueError as exc: parsed={'parse_error':str(exc)}
        access=parsed.get('owned_terms',{}).get('read_access','unparsed_public_document')
        data=item['html'].encode();name='partner-'+ident+'.html'
        rows.append({k:v for k,v in item.items() if k!='html'}|{'file':name,'html':item['html'],
            'sha256':hashlib.sha256(data).hexdigest(),'access':access,
            'full_terms_verified':False,**parsed})
        seen.add(url)
    if len(rows)>9:raise ProbeError('batch_size_exceeded')
    return rows


def main():
    from public_transport import robots_document, check_response
    from protego import Protego
    OUT.mkdir(exist_ok=True);reader=None
    report={'run_id':os.getenv('GITHUB_RUN_ID'),'run_attempt':os.getenv('GITHUB_RUN_ATTEMPT'),
        'commit':os.getenv('GITHUB_SHA'),'started_at':now(),'publication':False,'account_session':False,
        'max_credits':175,'details':[]}
    try:
        reader=Reader(os.environ.get('SCRAPINGANT_API_KEY',''),[{'url':ROOT}],max_credits=175,max_requests=3)
        reader.preflight();report['opening_balance']=reader.balance
        status,raw,_=reader.read('https://ekp.spb.ru/robots.txt',browser=False)
        rules,state=robots_document(status,raw);policy=Protego.parse(rules);namespace_allowed(rules)
        if not policy.can_fetch(ROOT,'LoyaltyCatalogResearchBot'):raise ProbeError('robots_disallow')
        rate=policy.request_rate('LoyaltyCatalogResearchBot')
        delay=max(1.1,policy.crawl_delay('LoyaltyCatalogResearchBot') or 0,rate.seconds/rate.requests if rate else 0)
        if delay>1.1:raise ProbeError('policy_slower_than_ui_budget')
        report['policy']={'status':status,'state':state,'sha256':hashlib.sha256(raw.encode()).hexdigest()}
        (OUT/'robots.txt').write_text(rules);time.sleep(delay)
        status,raw,_=reader.read(ROOT,browser=True)
        if status!=200:raise ProbeError('root_http_'+str(status))
        node=BeautifulSoup(raw,'html.parser').select_one('#loyalty-inline-evidence')
        if node is None:raise ProbeError('inline_marker_missing')
        result=json.loads(node.get_text())
        report['ui']={k:v for k,v in result.items() if k!='details'}
        rows=[];report['detail_errors']=[]
        # A malformed card must not discard other independently owned pages.
        for item in result.get('details',[]):
            try: rows.extend(checked_details({**result,'details':[item]},policy))
            except Exception as exc:
                report['detail_errors'].append({'url':item.get('url'),'reason':type(exc).__name__})
        if len(rows)>9:raise ProbeError('batch_size_exceeded')
        for item in rows:
            (OUT/item['file']).write_text(item.pop('html'));report['details'].append(item)
        # One GET capability check of the exact public route just observed by
        # the source UI. No guessed request body, pagination, headers or login.
        resources=result.get('finalResources',[])
        target=next((x.get('url') for x in resources
            if x.get('url')=='https://ekp.spb.ru/api/portal/loyalty/partners'),None)
        if target and not result.get('error') and not reader.halted and policy.can_fetch(target,'LoyaltyCatalogResearchBot'):
            reader.allowed.add(target);time.sleep(delay)
            api={'url':target,'method':'GET','observed_at':now(),'publication':False}
            report['public_route_check']=api
            try:
                status,body,_=reader.read(target,browser=False)
                api['origin_status']=status;api['sha256']=hashlib.sha256(body.encode()).hexdigest()
                if status!=200:raise ProbeError('public_route_http_'+str(status))
                check_response(status,body)
                obj=json.loads(body)
                api['shape']=json_shape(obj)
                # Unknown payloads are not persisted; inspect only fields that
                # are catalogue descriptions, not auth/account data.
                candidates=obj if isinstance(obj,list) else next((v for v in obj.values() if isinstance(v,list)),[]) if isinstance(obj,dict) else []
                allowed_fields={'id','name','title','description','discount','conditions','benefit','benefits','isAuth','isPrivate','requiredAuth','isAuthorizationRequired','region','regions','category','categories','text','shortDescription','loyaltyProgram','loyalty_program','howToGetDiscount'}
                api['sample']=[{k:v for k,v in item.items() if k in allowed_fields and isinstance(v,(str,int,float,bool,type(None))) and len(str(v))<20000} for item in candidates[:3] if isinstance(item,dict)]
            except Exception as exc:
                code=str(exc);api['error']=code if re.fullmatch('[a-z_0-9]{1,100}',code) else type(exc).__name__
    except Exception as exc:
        code=str(exc);report['error']=code if re.fullmatch('[a-z_0-9]{1,100}',code) else type(exc).__name__
    finally:
        if reader:
            report.update(requests=reader.calls,reserved_credits=reader.reserved,successful_cost_headers=reader.known_charged_credits)
            if not reader.halted:
                try:reader._request('usage',{});report['closing_balance']=reader.balance
                except Exception:report['balance_error']='unavailable'
        report['finished_at']=now();(OUT/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
        (OUT/'executed.py').write_bytes(Path(__file__).read_bytes());(OUT/'executed-ui.js').write_text(JS)
        (OUT/'owned-parser.py').write_bytes(Path(__file__).with_name('ekp_owned_terms.py').read_bytes())
        print(json.dumps({'records':len(report['details']),'error':report.get('error'),'published':False}))


def json_shape(obj, depth=0):
    if depth>2:return type(obj).__name__
    if isinstance(obj,dict):return {str(k):json_shape(v,depth+1) for k,v in list(obj.items())[:50]}
    if isinstance(obj,list):return {'length':len(obj),'first_item':json_shape(obj[0],depth+1) if obj else None}
    return type(obj).__name__


def selfcheck():
    terms_selfcheck()
    namespace_allowed('User-agent: *\nDisallow: /cabinet\nDisallow: /docs')
    for rules in ('Disallow: /','Disallow: /capabilities','Disallow: /capabilities/loyalty/tiles/5','Disallow: /*'):
        try:namespace_allowed(rules)
        except ProbeError:pass
        else:raise AssertionError('overlapping policy accepted')
    r=Reader('fixture-key',[{'url':ROOT}],max_credits=175,max_requests=3);r.ready=True
    r.allowed.add('https://ekp.spb.ru/api/portal/loyalty/partners')
    r._request=lambda e,p:('fixture',{'Ant-credits-cost':'125' if p['browser']=='true' else '25','Ant-page-status-code':'200'})
    r.read('https://ekp.spb.ru/robots.txt',browser=False);r.read(ROOT,browser=True)
    r.read('https://ekp.spb.ru/api/portal/loyalty/partners',browser=False)
    assert r.reserved==175 and r.calls==3
    try:r.read(ROOT,browser=False)
    except ProbeError:pass
    else:raise AssertionError('credit ceiling not enforced')
    print('Conservative namespace and 175-credit/3-request checks passed')


if __name__=='__main__':
    selfcheck()
    if '--selfcheck' not in sys.argv:main()
