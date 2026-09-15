"""Same public targets, reused independent Globalping probes; no credentials."""
import hashlib,json,os,re,time
from datetime import datetime,timezone
from pathlib import Path
from urllib.parse import urlsplit
import requests
BASE='https://api.globalping.io/v1'
TARGETS=[('ekp_tcp','ping','ekp.spb.ru'),('nordwind_tcp','ping','nordwindairlines.ru'),
 ('loyals_tcp','ping','loyals.ru'),('ekp_http','http','https://ekp.spb.ru/capabilities/loyalty/'),
 ('nordwind_http','http','https://nordwindairlines.ru/ru/club/partnerlist'),
 ('coral_http','http','https://coralbonus.ru/klub-privilegii/zdorov-e/medsi/'),
 ('rzd_http','http','https://www.rzd-bonus.ru/?accessible=true'),
 ('s7_control','http','https://marketplace.s7.ru/partners/offer/flowwow')]


def options(kind,target):
    if kind=='ping':return target,{'protocol':'TCP','port':443,'packets':1,'ipVersion':4}
    p=urlsplit(target)
    if p.scheme!='https' or p.username or p.password:raise ValueError('non_public_target')
    request={'method':'GET','path':p.path or '/'}
    if p.query:request['query']=p.query
    return p.hostname,{'protocol':'HTTPS','port':443,'ipVersion':4,'request':request}


def country_pair(payload):
    results=payload.get('results',[])
    return len(results)==2 and {r.get('probe',{}).get('country') for r in results}=={'RU','NL'}


def evidence(result):
    allowed=('status','statusCode','statusCodeName','resolvedAddress','resolvedHostname','timings','stats','tls','error')
    return {k:result[k] for k in allowed if k in result}


def main():
    out=Path('global-output');out.mkdir(exist_ok=True)
    report={'purpose':'independent_network_comparison_not_browser_or_catalogue_proof',
      'observed_at':datetime.now(timezone.utc).isoformat(),'run_id':os.getenv('GITHUB_RUN_ID'),
      'code_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'checks':[]}
    session=requests.Session();session.headers.update({'User-Agent':'LoyaltyNetworkResearch/0.1 (+https://github.com/Floppa2003/key-privileges)','Accept':'application/json','Accept-Encoding':'gzip'})
    def call(method,path,payload=None):
        r=session.request(method,BASE+path,json=payload,timeout=25,allow_redirects=False)
        if r.status_code not in (200,202):raise RuntimeError('globalping_http_'+str(r.status_code)+': '+r.text[:500])
        return r.json()
    def poll(rid):
        for _ in range(20):
            data=call('GET','/measurements/'+rid)
            if data.get('status')!='in-progress':return data
            time.sleep(2)
        raise RuntimeError('measurement_result_timeout')
    def compact(data):
        if not country_pair(data):raise RuntimeError('required_country_pair_not_present')
        return {'measurement_status':data.get('status'),'type':data.get('type'),'target':data.get('target'),
          'results':[{'probe':{k:r['probe'].get(k) for k in ('continent','country','city','asn','network')},
                      'result':evidence(r.get('result',{}))} for r in data['results']]}
    location=[{'country':'RU','limit':1},{'country':'NL','limit':1}]
    jobs=[]
    try:
        for index,(name,kind,target) in enumerate(TARGETS):
            host,opts=options(kind,target)
            request={'type':kind,'target':host,'locations':location,'measurementOptions':opts}
            created=call('POST','/measurements',request)
            rid=created.get('id','')
            if not re.fullmatch(r'[A-Za-z0-9_-]{1,80}',rid) or created.get('probesCount')!=2:
                raise RuntimeError('unexpected_measurement_identity_or_probe_count')
            row={'id':name,'measurement_id':rid,'request':request,'status':'pending'}
            report['checks'].append(row);jobs.append(row)
            if index==0:
                data=poll(rid);row['evidence']=compact(data);row['status']='completed'
                location=rid
                report['reuse_probe_measurement_id']=rid
            time.sleep(1)
    except Exception as exc:
        report['experiment_error']=str(exc) if isinstance(exc,RuntimeError) else type(exc).__name__
    finally:
        # Preserve completed work after a later request-validation failure.
        # A rate limit stops further provider reads for this run.
        if 'http_429' not in report.get('experiment_error',''):
            for row in jobs:
                if row['status']=='completed':continue
                try:
                    row['evidence']=compact(poll(row['measurement_id']));row['status']='completed'
                except Exception as exc:
                    row['status']='failed';row['error']=str(exc) if isinstance(exc,RuntimeError) else type(exc).__name__
                    if 'http_429' in row['error']:break
        report['finished_at']=datetime.now(timezone.utc).isoformat()
        (out/'globalping.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
    print(json.dumps({'checks':len(report['checks']),'complete':sum(c['status']=='completed' for c in report['checks']),'error':report.get('experiment_error')}))

if __name__=='__main__':main()
