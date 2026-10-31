"""One-off deployed-channel verification. Only dispatch issues a write API call.

It invokes the already merged daily workflow once, at most five generation
attempts total. Other operations are independent GETs / local artifact inspection.
No account mutation, extra generation, queue reset or Sheets publication.
"""
from __future__ import annotations
import argparse
from collections import Counter
from datetime import datetime, timezone
from decimal import Decimal
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import time
import urllib.request
import zipfile

REPO='Floppa2003/key-privileges'
EXPECTED='1f2167462c9f76b29f5470a4c3765fa4777ae6ac'
TESTED_MERGE='81e351a415a839cb6d9822f95e32fc005d3a84cb'
CHANNELS=('experiential','kilo','openrouter','vercel','gemini')
OUT=Path('verification-output')


def save(name,value):
    OUT.mkdir(exist_ok=True)
    (OUT/name).write_text(json.dumps(value,ensure_ascii=False,indent=2))


def api(path, payload=None):
    cmd=['gh','api',f'repos/{REPO}/{path}']
    if payload is not None:cmd += ['--method','POST','--input','-']
    return subprocess.check_output(cmd,input=json.dumps(payload).encode() if payload is not None else None,timeout=90)


def get(path):return json.loads(api(path))


def dispatch():
    assert get('git/ref/heads/main')['object']['sha']==EXPECTED
    actual=get('git/commits/'+EXPECTED); tested=get('git/commits/'+TESTED_MERGE)
    assert actual['tree']['sha']==tested['tree']['sha'], 'merged_tree_differs_from_tested_PR'
    workflow='actions/workflows/merchant-llm-daily.yml'
    before={r['id'] for r in get(workflow+'/runs?branch=main&event=workflow_dispatch&per_page=20')['workflow_runs']}
    started=datetime.now(timezone.utc).isoformat()
    inputs={'max_requests':'5','max_pages':'10','providers':','.join(CHANNELS),'per_provider_requests':'1'}
    # Exactly one dispatch; no retry on unknown dispatch outcome.
    api(workflow+'/dispatches', {'ref':'main','inputs':inputs})
    record={'expected_sha':EXPECTED,'tested_tree':actual['tree']['sha'],'started_at':started,'inputs':inputs}
    save('launch.json',record)
    run=None
    for _ in range(120):
        time.sleep(10)
        runs=get(workflow+'/runs?branch=main&event=workflow_dispatch&per_page=20')['workflow_runs']
        candidates=[r for r in runs if r['id'] not in before and r['head_sha']==EXPECTED]
        if run is None:
            if len(candidates)>1:raise RuntimeError('ambiguous_new_run_no_redispatch')
            if candidates:run=candidates[0];record['run_id']=run['id'];save('launch.json',record)
        if run is not None:
            run=get('actions/runs/'+str(run['id']))
            save('run.json',{k:run.get(k) for k in ('id','head_sha','event','status','conclusion','created_at','updated_at','html_url')})
            if run['status']=='completed':
                print(json.dumps(json.loads((OUT/'run.json').read_text()),indent=2));return
    raise RuntimeError('verification_window_exhausted_no_redispatch')


def readback():
    launch=json.loads((OUT/'launch.json').read_text());rid=launch['run_id']
    run=get('actions/runs/'+str(rid));assert run['head_sha']==EXPECTED
    artifacts=get(f'actions/runs/{rid}/artifacts')['artifacts']
    artifact=next(a for a in artifacts if a['name']==f'merchant-llm-daily-{rid}-1' and not a['expired'])
    raw=api(f"actions/artifacts/{artifact['id']}/zip")
    digest=hashlib.sha256(raw).hexdigest()
    if artifact.get('digest'):assert artifact['digest']=='sha256:'+digest
    before=json.loads(Path('state-before/state.json').read_text())
    after=json.loads(Path('state-after/state.json').read_text())
    report={'run_id':rid,'head_sha':run['head_sha'],'conclusion':run['conclusion'],
            'artifact_id':artifact['id'],'artifact_sha256':digest,
            'state_before_sha':subprocess.check_output(['git','-C','state-before','rev-parse','HEAD'],text=True).strip(),
            'state_after_sha':subprocess.check_output(['git','-C','state-after','rev-parse','HEAD'],text=True).strip(),
            'state_after_sha256':hashlib.sha256(Path('state-after/state.json').read_bytes()).hexdigest(),
            'queue_before':len(before['items']),'queue_after':len(after['items']),
            'accepted_before':sum('extracted' in v for v in before['items'].values()),
            'accepted_after':sum('extracted' in v for v in after['items'].values()),
            'main_current':get('git/ref/heads/main')['object']['sha'],'documents':[]}
    processed=set()
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        def read(name):return json.loads(archive.read(name))
        summary=read('results/summary.json');report['summary']=summary
        report['capture']=read('captures/capture-summary.json')
        manifest=read('captures/manifest.json');specs={d['id']:d for d in manifest['documents']}
        assert summary['http_attempts']<=5
        assert summary['publication_allowed'] is False
        for provider in summary['providers']:
            name=provider['provider'];assert name in CHANNELS
            assert provider['http_attempts']<=1
            for row in provider.get('results',[]):
                ident=row['id'];base=f'results/{name}/{ident}/direct/'
                detail=read(base+'summary.json')
                info={'id':ident,'provider':name,'status':row['status'],'detail':detail}
                if row['status']=='completed':
                    obj=read(base+'extracted.json');item=after['items'][ident]
                    assert item['extracted']==obj and item['inferred_provider']==name
                    assert item['publication_allowed'] is False
                    processed.add(ident);spec=specs[ident]
                    for relative,sha in spec['sha256'].items():
                        assert hashlib.sha256(archive.read('captures/'+relative)).hexdigest()==sha
                    text=archive.read('captures/'+spec['text']).decode()
                    quotes=[q for offer in obj.get('offers',[]) for q in offer.get('evidence',[])]
                    folded=' '.join(text.split())
                    info.update(target=spec['target'],extracted=obj,
                        evidence_quotes_found=sum(' '.join(q.split()) in folded for q in quotes),
                        evidence_quotes_total=len(quotes),images_verified=len(spec['images']),
                        full_text_chars=len(text),source_excerpt=text[:2500])
                report['documents'].append(info)
    # Preserve previous accepted content, including records not visited in this run.
    preserved=0
    for ident,item in before['items'].items():
        if 'extracted' in item and ident not in processed:
            assert after['items'][ident]['extracted']==item['extracted']
            assert after['items'][ident]['fingerprint']==item['fingerprint'];preserved+=1
    report['previous_accepted_preserved']=preserved
    report['providers_state']={p:after.get('providers',{}).get(p) for p in CHANNELS}
    report['status_counts']=dict(Counter(v.get('status','missing') for v in after['items'].values()))
    save('readback.json',report)
    print(json.dumps(report,ensure_ascii=False,indent=2))


def account(stage):
    result={'stage':stage,'checked_at':datetime.now(timezone.utc).isoformat(),'generation_requests':0}
    requests=[('vercel_credits','https://ai-gateway.vercel.sh/v1/credits','AI_GATEWAY_API_KEY'),
              ('experiential_credits','https://api.experientiallabs.ai/api/v1/credits','EXPERIENTAL_API_KEY')]
    if stage=='after':
        requests.append(('experiential_usage','https://api.experientiallabs.ai/api/v1/usage?limit=20','EXPERIENTAL_API_KEY'))
    for label,url,env in requests:
        key=os.environ.get(env,'')
        if not key:result[label]={'status':'missing_key'};continue
        try:
            request=urllib.request.Request(url,headers={'Authorization':'Bearer '+key,'Accept':'application/json'})
            with urllib.request.urlopen(request,timeout=30) as response:raw=response.read()
            if key.encode() in raw:raise ValueError('credential_echo')
            data=json.loads(raw)
            if label=='vercel_credits':data={k:data.get(k) for k in ('balance','total_used')}
            elif label=='experiential_credits':data={k:data.get('data',{}).get(k) for k in ('total_credits','total_usage')}
            else:
                data=[{k:v for k,v in row.items() if k in ('created_at','model','cost_usd','real_cost_usd','pricing_known','input_tokens','output_tokens','status')} for row in data.get('data',[]) if isinstance(row,dict)]
            result[label]=data
        except Exception as exc:result[label]={'error_type':type(exc).__name__}
    if stage=='after' and (OUT/'account-before.json').exists():
        before=json.loads((OUT/'account-before.json').read_text())
        try:result['vercel_usage_delta']=str(Decimal(result['vercel_credits']['total_used'])-Decimal(before['vercel_credits']['total_used']))
        except Exception:pass
    save('account-'+stage+'.json',result);print(json.dumps(result,ensure_ascii=False,indent=2))


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('mode',choices=('dispatch','readback','before','after'))
    mode=parser.parse_args().mode
    if mode=='dispatch':dispatch()
    elif mode=='readback':readback()
    else:account(mode)
