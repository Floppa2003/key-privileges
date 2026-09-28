"""Paired prompt-only test on frozen 1024px inputs; no publication or website reads."""
from __future__ import annotations
import argparse, base64, copy, hashlib, io, json, os, platform, sys
from pathlib import Path
from PIL import Image
import psutil

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parent/'local_visual'))
sys.path.insert(0,str(HERE.parent/'resolution'))
import run_cpu as old
import benchmark as runtime


def with_prompt(request: dict, variant: str) -> dict:
    if variant not in ('old','defined'):raise ValueError('unknown_prompt_variant')
    result=copy.deepcopy(request)
    if variant=='defined':
        result['messages'][0]['content']=(HERE/'defined_prompt.txt').read_text(encoding='utf-8')
    return result


def checked_bytes(root: Path, name: str, expected: str) -> bytes:
    path=(root/name).resolve()
    if not path.is_relative_to(root.resolve()):raise ValueError('source_path_escape')
    raw=path.read_bytes()
    if hashlib.sha256(raw).hexdigest()!=expected:raise ValueError('source_hash_mismatch:'+name)
    return raw


def load_request(root: Path, spec: dict) -> dict:
    raw={name:checked_bytes(root,name,sha) for name,sha in spec['sha256'].items()}
    request=json.loads(raw[spec['request']]);text=raw[spec['text']].decode('utf-8')
    if not text or not request['messages'][-1]['content'].endswith(text):raise ValueError('source_text_mismatch')
    if not 1<=len(spec['images'])<=8:raise ValueError('image_budget')
    images=[raw[name] for name in spec['images']]
    for image in images:
        with Image.open(io.BytesIO(image)) as im:
            if max(im.size)>1024:raise ValueError('image_exceeds_fixed_edge')
    request['messages'][-1]['images']=[base64.b64encode(x).decode('ascii') for x in images]
    return request


def runtime_status(result: dict) -> str:
    if result.get('returned_model')!=old.MODEL:return 'model_unverified'
    return 'cpu_verified' if result.get('vram_bytes')==[0] else 'needs_log_review'


def main() -> int:
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source',type=Path,required=True)
    p.add_argument('--out',type=Path,required=True)
    p.add_argument('--cases',nargs='+',required=True)
    p.add_argument('--execute',action='store_true')
    p.add_argument('--ollama',type=Path)
    a=p.parse_args()
    plan=json.loads((HERE/'prompt-ab-plan.json').read_text(encoding='utf-8'))
    specs={c['id']:c for c in plan['cases']}
    if len(set(a.cases))!=len(a.cases) or any(c not in specs for c in a.cases):p.error('unknown_or_duplicate_case')
    if a.out.exists():p.error('output_exists')
    if a.execute and (a.ollama is None or not a.ollama.is_file()):p.error('ollama_required')
    a.out.mkdir(parents=True)
    old.save(a.out/'host.json',{'platform':platform.platform(),'cpu_count':os.cpu_count(),
        'ram_bytes':psutil.virtual_memory().total,'fresh_process_per_attempt':True,
        'no_source_network':True,'publication_allowed':False})
    rows=[]
    for case in a.cases:
        spec=specs[case];request=load_request(a.source,spec)
        folder=a.out/case;folder.mkdir();old.save(folder/'frozen-input.json',spec)
        for i,name in enumerate(spec['images'],1):
            (folder/f'page-{i}.png').write_bytes(checked_bytes(a.source,name,spec['sha256'][name]))
        (folder/'visible-text.txt').write_bytes(checked_bytes(a.source,spec['text'],spec['sha256'][spec['text']]))
        for variant in spec['order']:
            out=folder/variant;out.mkdir();payload=with_prompt(request,variant)
            brief=copy.deepcopy(payload);brief['messages'][-1].pop('images')
            old.save(out/'request-without-image-bytes.json',brief)
            row={'case':case,'variant':variant,'publication_allowed':False,'status':'prepared'}
            if a.execute:
                try:
                    print('START',case,variant,flush=True)
                    with runtime.Server(a.ollama.resolve(),out/'ollama.log') as server:
                        old.save(out/'runtime.json',runtime.check_runtime(server))
                        result=old.infer(server.client,payload,out,server.process.pid)
                    row.update(result)
                    row['status']='completed' if result.get('schema_valid') else 'failed'
                    row['hardware_status']=runtime_status(result)
                except Exception as exc:
                    row.update(status='runtime_error',error_type=type(exc).__name__,error=str(exc)[:400])
            old.save(out/'measurement.json',row);rows.append(row)
            old.save(a.out/'summary.json',{'publication_allowed':False,'attempts':rows})
            print(json.dumps(row,ensure_ascii=False),flush=True)
    expected='completed' if a.execute else 'prepared'
    return 0 if len(rows)==2*len(a.cases) and all(r['status']==expected for r in rows) else 2

if __name__=='__main__':raise SystemExit(main())
