"""Observe only public catalogue XHR metadata; discard sessions and other traffic."""
import base64,hashlib,json,os,re,sys,time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'loyalty'))
from bs4 import BeautifulSoup
from free_access_probe import FreeReader,ProbeError,free_plan,now
from ekp_inline_batch import namespace_allowed
from ekp_detail_probe import card_url,index_url
from ekp_owned_terms import extract
ROOT='https://ekp.spb.ru/capabilities/loyalty/'
POLICY='https://ekp.spb.ru/robots.txt'
PUBLIC_API='https://ekp.spb.ru/api/portal/loyalty/partners'
OUT=Path('ekp-response-output')

def shape(x,depth=0):
    if isinstance(x,dict) and depth<3:return {k:shape(v,depth+1) for k,v in list(x.items())[:90]}
    if isinstance(x,list):return {'length':len(x),'first':shape(x[0],depth+1) if x and depth<3 else None}
    return type(x).__name__

def request_fields(x):
    allowed={'page','pageSize','size','count','skip','take','offset','limit','region','regionId','regionIds','category','categoryId','categoryIds','sort','order','search','filter','filters','isAuth','isActive'}
    if not isinstance(x,dict):return None
    out={}
    for k,v in x.items():
        if k not in allowed:continue
        if v is None or isinstance(v,(bool,int,float)) or (isinstance(v,str) and (not v or re.fullmatch('[A-Za-z_0-9,-]{1,50}',v))):out[k]=v
        elif isinstance(v,list) and len(v)<100 and all(isinstance(i,(int,bool)) for i in v):out[k]=v
        elif isinstance(v,dict):out[k]=request_fields(v)
    return out

def inspect_response(x):
    out={'shape':shape(x)}
    candidates=[]
    if isinstance(x,list):candidates=x
    if isinstance(x,dict):
        out['counts']={k:v for k,v in x.items() if isinstance(v,(int,bool)) or v is None}
        for k,v in x.items():
            if isinstance(v,list) and v and isinstance(v[0],dict):candidates=v;out['array_key']=k;break
            if isinstance(v,dict):
                for sub,arr in v.items():
                    if isinstance(arr,list) and arr and isinstance(arr[0],dict):candidates=arr;out['array_key']=[k,sub];break
    allowed={'id','name','title','shortDescription','description','discount','requiredAuth','isAuth','isAuthorizationRequired','isPrivate','isActive','isNeedAuth','isNeedAuthorization','benefit','benefits','loyaltyProgram','loyaltyProgramDescription','program','loyalty','howToGetDiscount','loyalty_program','regions','categories'}
    # Only names/IDs and access flags leave this schema-discovery step; condition
    # values are reviewed only later after their actual ownership is understood.
    preview={'id','name','title','isAuth','isAuthorizationRequired','isPrivate','isActive','requiredAuth','isNeedAuth','isNeedAuthorization'}
    out['items_count']=len(candidates)
    out['item_shapes']=[shape(item) for item in candidates[:2]]
    out['public_identity_sample']=[{k:v for k,v in item.items() if k in preview and isinstance(v,(int,bool,str,type(None))) and len(str(v))<500} for item in candidates[:8] if isinstance(item,dict)]
    return out

def main():
    from public_transport import robots_document,check_response
    from protego import Protego
    OUT.mkdir(exist_ok=True);r=None;report={'run_id':os.getenv('GITHUB_RUN_ID'),'commit':os.getenv('GITHUB_SHA'),'started_at':now(),'publication':False,'source_login':False,'observed_responses':[],'details':[]}
    try:
        r=FreeReader(os.environ.get('SCRAPINGANT_API_KEY',''),[{'url':ROOT}],max_credits=150,max_requests=2)
        payload,_=r._request('usage',{});left=free_plan(payload);report['opening_balance']=left
        if left<440:raise ProbeError('preserve_daily_reserve')
        def read(url,js=None):
            cost=125 if js else 25
            if r.halted or url not in r.allowed or r.calls>=2 or r.reserved+cost>150:raise ProbeError('request_not_allowed')
            r.calls+=1;r.reserved+=cost
            params={'url':url,'browser':'true' if js else 'false','proxy_country':'RU','proxy_type':'residential','timeout':'60'}
            if js:params.update(js_snippet=base64.b64encode(js.encode()).decode(),block_resource=['image','media','font'])
            data,meta=r._request('extended' if js else 'general',params)
            c=str(meta.get('Ant-credits-cost',''));s=str(meta.get('Ant-page-status-code',''))
            if not c.isdigit() or int(c)>cost or s!='200' or meta.get('ant-original-header-retry-after'):raise ProbeError('status_or_cost_invalid')
            r.known_charged_credits+=int(c);return data
        raw=read(POLICY);rules,state=robots_document(200,raw);namespace_allowed(rules);policy=Protego.parse(rules)
        if not all(policy.can_fetch(x,'LoyaltyCatalogResearchBot') for x in (ROOT,PUBLIC_API)):raise ProbeError('robots_disallow')
        (OUT/'robots.txt').write_text(rules);time.sleep(1.1)
        js=Path(__file__).with_name('ekp_inline_batch.js').read_text()
        blob=read(ROOT,js);payload=json.loads(blob)
        # Never persist extended envelope, cookies, headers, iframe or other XHR.
        report['envelope_shape']=shape({k:v for k,v in payload.items() if k not in ('cookies','headers','iframes','xhrs','html','text')})
        html=payload.get('html');check_response(payload.get('status_code'),html)
        node=BeautifulSoup(html,'html.parser').select_one('#loyalty-inline-evidence')
        if node is None:raise ProbeError('marker_missing')
        ui=json.loads(node.get_text());report['ui']={k:v for k,v in ui.items() if k not in ('details','initialResources','finalResources')}
        for d in ui.get('details',[]):
            url=card_url(d['url']);parsed=extract(d['html'],url,d['title']);ident=parsed['native_id']
            data=d['html'].encode();file='partner-'+ident+'.html';(OUT/file).write_bytes(data)
            report['details'].append({'url':url,'file':file,'sha256':hashlib.sha256(data).hexdigest(),'terms':parsed})
        for entry in payload.get('xhrs',[]):
            if entry.get('url')!=PUBLIC_API:continue
            obs={'url':PUBLIC_API,'method':entry.get('method'),'status':entry.get('status')}
            body=entry.get('request_body')
            if isinstance(body,str) and len(body)<20000:
                try:obj=json.loads(body);obs['request_shape']=shape(obj);obs['request_fields']=request_fields(obj)
                except ValueError:obs['request_encoding']='not_json'
            raw=entry.get('body')
            if isinstance(raw,str) and len(raw)<5000000:
                obs['response_sha256']=hashlib.sha256(raw.encode()).hexdigest()
                try:obs.update(inspect_response(json.loads(raw)))
                except ValueError:obs['response_encoding']='not_json'
            report['observed_responses'].append(obs)
    except Exception as exc:
        s=str(exc);report['error']=s if re.fullmatch('[a-z_0-9]{1,100}',s) else type(exc).__name__
    finally:
        if r:
            report.update(requests=r.calls,reserved=r.reserved,charged=r.known_charged_credits)
            if not r.halted:
                try:payload,_=r._request('usage',{});report['closing_balance']=free_plan(payload)
                except Exception:pass
        report['finished_at']=now();(OUT/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2));(OUT/'executed.py').write_bytes(Path(__file__).read_bytes())
        print(json.dumps({'responses':len(report['observed_responses']),'error':report.get('error'),'publication':False}))
if __name__=='__main__':main()
