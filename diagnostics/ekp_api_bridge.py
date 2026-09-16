"""Verify a source-observed anonymous POST against its actual public UI.
The extended envelope is never saved. Only the known catalogue projection leaves
memory, and auth-gated condition fields are dropped before artifact creation.
"""
import base64,hashlib,json,os,re,sys,time
from pathlib import Path
from urllib.parse import urlsplit
import requests
from bs4 import BeautifulSoup
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'loyalty'))
from free_access_probe import FreeReader,ProbeError,free_plan,now
from ekp_inline_batch import namespace_allowed
from ekp_detail_probe import card_url,index_url
from ekp_owned_terms import extract,plain
ROOT='https://ekp.spb.ru/capabilities/loyalty/'
POLICY='https://ekp.spb.ru/robots.txt'
API='https://ekp.spb.ru/api/portal/loyalty/partners'
OUT=Path('ekp-api-bridge-output')

def checked_request(value):
    if isinstance(value,str):value=json.loads(value)
    if not isinstance(value,dict) or set(value)!={'pagination','filters'}:raise ValueError('unexpected_query_shape')
    p,f=value['pagination'],value['filters']
    if set(p)!={'limit','offset'} or type(p['limit']) is not int or p['limit'] not in (30,60,120) or type(p['offset']) is not int or p['offset']!=0:raise ValueError('unexpected_pagination')
    if set(f)!={'categories','name','qrDiscount','region'} or f['categories']!=[] or f['name']!='' or type(f['qrDiscount']) is not bool or not re.fullmatch(r'\d+',f['region']):raise ValueError('unexpected_public_filter')
    return value

def public_markup(value):
    soup=BeautifulSoup(value,'html.parser')
    for n in soup.select('script,style,noscript,form,input,textarea,iframe,[hidden],[aria-hidden="true"]'):n.decompose()
    for n in soup.find_all(True):
        for k in list(n.attrs):
            if k!='href':del n.attrs[k]
        if n.has_attr('href'):
            u=urlsplit(n['href'])
            if u.scheme not in ('http','https') or not u.hostname or u.username or u.password:n.attrs.pop('href',None)
            else:n['href']=u._replace(query='',fragment='').geturl()
    return str(soup)

def projection(payload):
    if not isinstance(payload,dict) or not {'total','offset','partners'}<=set(payload):raise ValueError('unexpected_response_shape')
    if type(payload['total']) is not int or not 1<=payload['total']<=5000 or type(payload['offset']) is not int or payload['offset']<0 or not isinstance(payload['partners'],list) or len(payload['partners'])>120:raise ValueError('invalid_response_bounds')
    rows=[];seen=set()
    for row in payload['partners']:
        if not isinstance(row,dict) or not isinstance(row.get('id'),str) or not re.fullmatch(r'\d+',row['id']) or row['id'] in seen:raise ValueError('invalid_partner_identity')
        seen.add(row['id'])
        for flag in ('active','description_authorized'):
            if type(row.get(flag)) is not bool:raise ValueError('invalid_source_access_flag')
        item={k:row[k] for k in ('id','name','active','description_authorized')}
        if not isinstance(item['name'],str) or not item['name'].strip() or len(item['name'])>1000:raise ValueError('invalid_partner_name')
        item['categories']=[]
        for c in row.get('categories',[]):
            if type(c.get('categoryId')) is not int or not isinstance(c.get('categoryName'),str):raise ValueError('invalid_source_category')
            item['categories'].append({k:c[k] for k in ('categoryId','categoryName')})
        for key in ('text','loyaltyDescription','discountScheme'):
            if key!='text' and row['description_authorized']:continue
            value=row.get(key)
            if not isinstance(value,str) or len(value)>80000:raise ValueError('invalid_source_text')
            if key=='text' or not row['description_authorized']:item[key]=public_markup(value)
        # No shtrich/coupon/QR, contacts, sessions, subscriptions or hidden terms.
        rows.append(item)
    return {k:payload[k] for k in ('total','offset')}|{'partners':rows}

def normal(x):return ' '.join(plain(BeautifulSoup(x,'html.parser')).split())

def main():
    from public_transport import robots_document,check_response
    from protego import Protego
    OUT.mkdir(exist_ok=True);reader=None;post_body=None
    report={'run_id':os.getenv('GITHUB_RUN_ID'),'commit':os.getenv('GITHUB_SHA'),'started_at':now(),'publication':False,'source_login':False,'checks':[]}
    def get(url,**kwargs):
        if post_body is not None and url.endswith('/general') and kwargs.get('params',{}).get('url')==API:
            kwargs['headers']={**kwargs['headers'],'Ant-Content-Type':'application/json'}
            return requests.post(url,data=json.dumps(post_body,separators=(',',':')),**kwargs)
        return requests.get(url,**kwargs)
    def save():
        if reader:report.update(requests=reader.calls,reserved=reader.reserved,charged=reader.known_charged_credits)
        (OUT/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
    try:
        reader=FreeReader(os.environ.get('SCRAPINGANT_API_KEY',''),[{'url':ROOT}],get=get,max_credits=175,max_requests=3)
        usage,_=reader._request('usage',{});report['opening_balance']=free_plan(usage)
        if report['opening_balance']<465:raise ProbeError('preserve_daily_reserve')
        def read(url,*,extended=False):
            cost=125 if extended else 25
            if reader.halted or url not in (ROOT,POLICY,API) or reader.calls>=3 or reader.reserved+cost>175:raise ProbeError('request_limit')
            reader.calls+=1;reader.reserved+=cost;save()
            params={'url':url,'browser':'true' if extended else 'false','proxy_country':'RU','proxy_type':'residential','timeout':'60'}
            if extended:params.update(js_snippet=base64.b64encode(Path(__file__).with_suffix('.js').read_bytes()).decode(),block_resource=['image','media','font'])
            raw,meta=reader._request('extended' if extended else 'general',params)
            cost_header=str(meta.get('Ant-credits-cost',''))
            if not cost_header.isdigit() or int(cost_header)>cost:raise ProbeError('cost_unconfirmed')
            reader.known_charged_credits+=int(cost_header)
            status=json.loads(raw).get('status_code') if extended else int(meta.get('Ant-page-status-code') or 0)
            if status!=200 or meta.get('ant-original-header-retry-after'):raise ProbeError('source_http_refusal')
            return raw
        raw=read(POLICY);rules,_=robots_document(200,raw);namespace_allowed(rules);policy=Protego.parse(rules)
        if not all(policy.can_fetch(u,'LoyaltyCatalogResearchBot') for u in (ROOT,API)):raise ProbeError('robots_disallow')
        (OUT/'robots.txt').write_text(rules);time.sleep(1.1)
        envelope=json.loads(read(ROOT,extended=True));html=envelope.get('html',envelope.get('content'));check_response(200,html)
        node=BeautifulSoup(html,'html.parser').select_one('#loyalty-api-bridge')
        if node is None:raise ProbeError('marker_missing')
        ui=json.loads(node.get_text());index_url(ui['catalogueUrl']);report['ui']={k:v for k,v in ui.items() if k!='details'}
        source_responses=[]
        for x in envelope.get('xhrs',[]):
            if x.get('url')!=API or x.get('method')!='POST' or x.get('status')!=200:continue
            request=checked_request(x['request_body']);data=projection(json.loads(x['body']))
            source_responses.append((request,data))
        if not source_responses:raise ProbeError('no_public_catalogue_response')
        request,data=max(source_responses,key=lambda x:x[0]['pagination']['limit'])
        by_id={x['id']:x for x in data['partners']}
        for i,d in enumerate(ui.get('details',[])):
            url=card_url(d['url']);p=extract(d['html'],url,d['title']);row=by_id[p['native_id']]
            checks={'id':p['native_id'],'title':normal(row['name'])==p['partner_name'],
                'access':row['description_authorized']==(p['read_access']=='login_required')}
            if not row['description_authorized']:
                checks.update(program=normal(row['loyaltyDescription'])==normal(p['program_text'] or ''),redemption=normal(row['discountScheme'])==normal(p['redemption_text'] or ''))
            report['checks'].append(checks)
            (OUT/('ui-'+p['native_id']+'.html')).write_text(d['html'])
        if not report['checks'] or any(v is not True for c in report['checks'] for k,v in c.items() if k!='id'):raise ProbeError('api_ui_mismatch')
        if len({c['id'] for c in report['checks']})<3:raise ProbeError('too_few_ui_checks')
        report['observed_request']=request;report['observed_total']=data['total'];report['observed_count']=len(data['partners'])
        (OUT/'observed-public.json').write_text(json.dumps(data,ensure_ascii=False,indent=2));time.sleep(1.1)
        # Replay precisely the independently observed read-only public query.
        post_body=request;raw=read(API);check_response(200,raw);fresh=projection(json.loads(raw))
        (OUT/'direct-public.json').write_text(json.dumps(fresh,ensure_ascii=False,indent=2))
        report['direct_total']=fresh['total'];report['direct_count']=len(fresh['partners'])
        report['direct_matches_observed']=fresh==data;report['direct_response_sha256']=hashlib.sha256(raw.encode()).hexdigest()
    except Exception as exc:
        reason=str(exc);report['error']=reason if re.fullmatch('[a-z_0-9]{1,100}',reason) else type(exc).__name__
    finally:
        if reader and not reader.halted:
            try:usage,_=reader._request('usage',{});report['closing_balance']=free_plan(usage)
            except Exception:pass
        report['finished_at']=now();save();(OUT/'executed.py').write_bytes(Path(__file__).read_bytes());(OUT/'executed.js').write_bytes(Path(__file__).with_suffix('.js').read_bytes())
        print(json.dumps({'status':report.get('error','complete'),'published':False}))
if __name__=='__main__':main()
