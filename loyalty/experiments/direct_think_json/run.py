"""One-stage direct visual JSON extraction with think=true on frozen inputs."""
from __future__ import annotations
import argparse, base64, copy, hashlib, io, json, os, sys, time
from pathlib import Path
from PIL import Image
import jsonschema, requests

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parent/'local_visual'))
sys.path.insert(0,str(HERE.parent/'resolution'))
import run_cpu as common
import benchmark as runtime

MODEL=common.MODEL
PROMPT=(HERE/'direct_prompt.txt').read_text(encoding='utf-8')

def checked(root:Path,name:str,sha:str)->bytes:
    p=(root/name).resolve()
    if not p.is_relative_to(root.resolve()): raise ValueError('path_escape')
    raw=p.read_bytes()
    if hashlib.sha256(raw).hexdigest()!=sha: raise ValueError('hash_mismatch:'+name)
    return raw

def load_case(source:Path,spec:dict,schema:dict)->dict:
    req=json.loads(checked(source,spec['request'],spec['sha256'][spec['request']]))
    text=checked(source,spec['text'],spec['sha256'][spec['text']]).decode('utf-8')
    images=[]
    for name in spec['images']:
        raw=checked(source,name,spec['sha256'][name])
        with Image.open(io.BytesIO(raw)) as im:
            if max(im.size)>1024: raise ValueError('image_too_large')
        images.append(base64.b64encode(raw).decode('ascii'))
    target=json.loads(req['messages'][-1]['content'].split('\nСхема:\n',1)[0])
    return {
      'model':MODEL,'stream':False,'think':True,'keep_alive':'5m','format':schema,
      'options':{'temperature':0,'seed':1,'num_ctx':16384,'num_predict':8192,'num_thread':4,'num_gpu':0},
      'messages':[
        {'role':'system','content':PROMPT},
        {'role':'user','content':json.dumps({'TARGET':target,'schema':schema,'full_text':text},ensure_ascii=False),
         'images':images}
      ]
    }

def main()->int:
    ap=argparse.ArgumentParser()
    ap.add_argument('--source',type=Path,required=True)
    ap.add_argument('--plan',type=Path,required=True)
    ap.add_argument('--schema',type=Path,required=True)
    ap.add_argument('--case',required=True)
    ap.add_argument('--ollama',type=Path,required=True)
    ap.add_argument('--out',type=Path,required=True)
    a=ap.parse_args()
    plan=json.loads(a.plan.read_text())
    spec=next(x for x in plan['cases'] if x['id']==a.case)
    schema=json.loads(a.schema.read_text())
    a.out.mkdir(parents=True)
    request=load_case(a.source,spec,schema)
    brief=copy.deepcopy(request); brief['messages'][-1].pop('images')
    common.save(a.out/'request-without-images.json',brief)
    with runtime.Server(a.ollama.resolve(),a.out/'ollama.log') as server:
        common.save(a.out/'runtime.json',runtime.check_runtime(server))
        start=time.monotonic()
        r=server.client.post(runtime.BASE+'/api/chat',json=request,timeout=(5,1800))
        seconds=time.monotonic()-start
        (a.out/'response.json').write_bytes(r.content)
        row={'case':a.case,'http_status':r.status_code,'seconds':seconds,'publication_allowed':False,
             'think':True,'num_predict':8192,'schema_valid':False,'status':'failed'}
        try:
            r.raise_for_status(); data=r.json()
            row.update(done=data.get('done'),done_reason=data.get('done_reason'),
                       eval_count=data.get('eval_count'),prompt_eval_count=data.get('prompt_eval_count'))
            thinking=data.get('message',{}).get('thinking')
            row['thinking_chars']=len(thinking) if isinstance(thinking,str) else 0
            if data.get('done') is not True or data.get('done_reason')!='stop': raise ValueError('incomplete')
            obj=json.loads(data['message']['content']); jsonschema.validate(obj,schema)
            if obj['has_offer']!=bool(obj['offers']): raise ValueError('offer_state_mismatch')
            common.save(a.out/'extracted.json',obj)
            row['schema_valid']=True; row['status']='completed'
        except Exception as exc:
            row['error_type']=type(exc).__name__; row['error']=str(exc)[:500]
        common.save(a.out/'measurement.json',row)
        print(json.dumps(row,ensure_ascii=False),flush=True)
        return 0 if row['status']=='completed' else 2
if __name__=='__main__': raise SystemExit(main())
