"""Test ordinary inline EKP detail navigation in one 150-credit Free batch.

No schedule, publication, account, private cookies, API replay or coupon action.
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
from free_residential_comparison import ComparisonReader, ProbeError, now
from ekp_detail_probe import card_url
from free_access_probe import free_plan
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


class Reader(ComparisonReader):
    balance=None
    def _request(self,endpoint,params):
        if endpoint=='general' and params.get('browser')=='true':
            params={**params,'js_snippet':base64.b64encode(JS.encode()).decode()}
        data,meta=super()._request(endpoint,params)
        if endpoint=='usage':
            left=free_plan(data)
            self.balance={'plan':'Free','total':data['plan_total_credits'],'remaining':left,'observed_at':now()}
            if left<440:raise ProbeError('preserve_daily_credit_reserve')
        return data,meta


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
        value=owners[0].get_text('\n',strip=True);check_response(200,value)
        locked='Для просмотра подробной информации о программе лояльности авторизуйтесь' in value
        if not locked and 'Программа лояльности' not in value:raise ProbeError('detail_terms_missing')
        try: parsed={'owned_terms':extract(item['html'],url,item['title'])}
        except ValueError as exc: parsed={'parse_error':str(exc)}
        data=item['html'].encode();name='partner-'+ident+'.html'
        rows.append({k:v for k,v in item.items() if k!='html'}|{'file':name,'html':item['html'],
            'sha256':hashlib.sha256(data).hexdigest(),'access':'login_required' if locked else 'public_terms',
            'full_terms_verified':False,**parsed})
        seen.add(url)
    if len(rows)>9:raise ProbeError('batch_size_exceeded')
    return rows


def main():
    from public_transport import robots_document
    from protego import Protego
    OUT.mkdir(exist_ok=True);reader=None
    report={'run_id':os.getenv('GITHUB_RUN_ID'),'run_attempt':os.getenv('GITHUB_RUN_ATTEMPT'),
        'commit':os.getenv('GITHUB_SHA'),'started_at':now(),'publication':False,'account_session':False,
        'max_credits':150,'details':[]}
    try:
        reader=Reader(os.environ.get('SCRAPINGANT_API_KEY',''),[{'url':ROOT}],max_credits=150,max_requests=2)
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
        rows=checked_details(result,policy)
        for item in rows:
            (OUT/item['file']).write_text(item.pop('html'));report['details'].append(item)
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
        print(json.dumps({'records':len(report['details']),'error':report.get('error'),'published':False}))


def selfcheck():
    terms_selfcheck()
    namespace_allowed('User-agent: *\nDisallow: /cabinet\nDisallow: /docs')
    for rules in ('Disallow: /','Disallow: /capabilities','Disallow: /capabilities/loyalty/tiles/5','Disallow: /*'):
        try:namespace_allowed(rules)
        except ProbeError:pass
        else:raise AssertionError('overlapping policy accepted')
    print('Conservative namespace policy checks passed')


if __name__=='__main__':
    selfcheck()
    if '--selfcheck' not in sys.argv:main()
