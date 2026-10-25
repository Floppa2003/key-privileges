"""Independent public reachability measurements; not a browser or proxy.

The third party receives only the fixed public target URL/port. No account,
Google permission, login token or browser state is provided. HTTP status from
this service cannot establish page contents, offer validity or TLS correctness.
"""
import hashlib
import json
import os
import re
import time
from datetime import datetime,timezone
from pathlib import Path
import requests

BASE='https://check-host.net'
TARGETS=[
 ('ekp_tcp','tcp','ekp.spb.ru:443'),
 ('nordwind_tcp','tcp','nordwindairlines.ru:443'),
 ('loyals_tcp','tcp','loyals.ru:443'),
 ('ekp_http','http','https://ekp.spb.ru/capabilities/loyalty/'),
 ('nordwind_http','http','https://nordwindairlines.ru/ru/club/partnerlist'),
 ('coral_http','http','https://coralbonus.ru/klub-privilegii/zdorov-e/medsi/'),
 ('rzd_http','http','https://www.rzd-bonus.ru/?accessible=true'),
 ('s7_control','http','https://marketplace.s7.ru/partners/offer/flowwow')]


def choose_nodes(payload):
    selected=[]
    for country in ('ru','nl'):
        choices=sorted(name for name,value in payload.get('nodes',{}).items()
            if re.fullmatch(country+r'[0-9]+\.node\.check-host\.net',name)
            and isinstance(value,dict) and value.get('location',[None])[0]==country)
        if not choices:
            raise ValueError('requested_independent_country_unavailable:'+country)
        selected.append(choices[0])
    return selected


def validate_job(payload,nodes):
    rid=payload.get('request_id','')
    if payload.get('ok')!=1 or not re.fullmatch(r'[A-Za-z0-9-]{1,64}',rid) or set(payload.get('nodes',{}))!=set(nodes):
        raise ValueError('measurement_job_mismatch')
    return rid


def main():
    out=Path('external-output');out.mkdir(exist_ok=True)
    report={'observed_at':datetime.now(timezone.utc).isoformat(),'run_id':os.getenv('GITHUB_RUN_ID'),
            'purpose':'independent_network_reachability_not_content_or_TLS_validation',
            'provider':BASE,'checks':[],'code_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    session=requests.Session();session.headers['Accept']='application/json'
    def read(path,params=None):
        r=session.get(BASE+path,params=params,timeout=20,allow_redirects=False)
        if r.status_code!=200:raise RuntimeError('provider_http_'+str(r.status_code))
        return r.json()
    try:
        metadata=read('/nodes/hosts')
        report['node_inventory']={name:value.get('location') for name,value in metadata.get('nodes',{}).items() if isinstance(value,dict)}
        nodes=choose_nodes(metadata)
        report['nodes']={n:metadata['nodes'][n] for n in nodes}
        jobs=[]
        for name,kind,target in TARGETS:
            try:
                p=read('/check-'+kind,[('host',target),('max_nodes',2)]+[('node',n) for n in nodes])
                rid=validate_job(p,nodes)
                item={'id':name,'kind':kind,'target':target,'request_id':rid,'report_url':BASE+'/check-report/'+rid,
                      'request_nodes':p['nodes'],'status':'pending'}
                report['checks'].append(item);jobs.append(item)
            except Exception as exc:
                report['checks'].append({'id':name,'status':'request_failed','error_type':type(exc).__name__,
                                         'reason':str(exc)[:120] if isinstance(exc,(RuntimeError,ValueError)) else 'provider_contract_or_transport_error'})
                # Do not repeatedly hit a rate-limited/refusing provider.
                break
            time.sleep(1)
        for attempt in range(8):
            pending=[j for j in jobs if j['status']=='pending']
            if not pending:break
            time.sleep(3)
            for j in pending:
                try:
                    p=read('/check-result/'+j['request_id'])
                    if set(p)!=set(nodes):raise ValueError('result_node_mismatch')
                    j['result']=p
                    if all(v is not None for v in p.values()):j['status']='completed'
                except Exception as exc:
                    j['status']='result_failed';j['error_type']=type(exc).__name__
    except Exception as exc:
        report['setup_error']={'type':type(exc).__name__,'reason':str(exc)[:120] if isinstance(exc,(RuntimeError,ValueError)) else 'nodes_or_provider_unavailable'}
    finally:
        report['finished_at']=datetime.now(timezone.utc).isoformat()
        (out/'independent.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
    print(json.dumps({'checks':len(report['checks']),'completed':sum(x.get('status')=='completed' for x in report['checks']),
                      'setup_error':report.get('setup_error')},ensure_ascii=False))

if __name__=='__main__':main()
