"""Bounded review-only expansion at the user-selected 1024px long edge.

Inputs are previously accepted public snapshots, never fetched again here.
The original three-case prompt/schema and the verified local CPU runtime are reused.
"""
from __future__ import annotations
import argparse, hashlib, io, json, os, platform, re, sys
from pathlib import Path
import fitz
from PIL import Image
import psutil
import run_cpu as old
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'resolution'))
import benchmark as runtime

DEFAULT_MAX_IMAGE_EDGE=1024
MAX_PAGES=8
PLAN=Path(__file__).with_name('expanded-plan-20260928.json')


def prepare_case(root: Path, spec: dict, out: Path, edge: int=DEFAULT_MAX_IMAGE_EDGE):
    case=spec['id']
    if not re.fullmatch(r'[a-z0-9_]+',case):raise ValueError('case_id')
    if edge not in (0,1024):raise ValueError('image_edge_must_be_1024_or_original_control')
    source=root/'captures'/case
    names=('reading.pdf','visible-text.txt','capture.json')
    raw={name:(source/name).read_bytes() for name in names}
    for name in names:old.verify(raw[name],spec['files'][name])
    capture=json.loads(raw['capture.json']);text=raw['visible-text.txt'].decode('utf-8')
    if not text or len(text)>24000:raise ValueError('text_budget')
    images=[];infos=[]
    with fitz.open(stream=raw['reading.pdf'],filetype='pdf') as pdf:
        if not 1<=len(pdf)<=MAX_PAGES:raise ValueError(f'page_budget:{len(pdf)}>{MAX_PAGES}')
        for i,page in enumerate(pdf,1):
            original=page.get_pixmap(matrix=fitz.Matrix(96/72,96/72),alpha=False).tobytes('png')
            small=runtime.resized_images([original],edge)[0]
            (out/f'page-{i}.png').write_bytes(small);images.append(small)
            with Image.open(io.BytesIO(original)) as before,Image.open(io.BytesIO(small)) as after:
                infos.append({'page':i,'original_size':list(before.size),'size':list(after.size),
                              'original_sha256':hashlib.sha256(original).hexdigest(),
                              'sha256':hashlib.sha256(small).hexdigest()})
    (out/'visible-text.txt').write_bytes(raw['visible-text.txt'])
    manifest={'case':case,'source_files_sha256':spec['files'],
              'source_url':capture.get('final_url'),'source_observed_at':capture.get('observed_at'),
              'source_warnings':capture.get('warnings',[]),'all_pdf_pages_sent':True,
              'max_image_edge':edge,'render_dpi':96,'images':infos,
              'publication_allowed':False,'gold_labels_sent':False}
    old.save(out/'input.json',manifest)
    target={'partner':spec['merchant'],'program':spec['program'],'as_of':'2026-09-27'}
    return old.payload(target,text,images),manifest


def classify(result: dict) -> str:
    if result.get('error_type') in ('ReadTimeout','Timeout'):return 'timeout'
    if not result.get('schema_valid'):return 'failed'
    if result.get('returned_model')!=old.MODEL or result.get('vram_bytes')!=[0]:return 'runtime_unverified'
    return 'completed'


def main() -> int:
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source',type=Path,required=True)
    p.add_argument('--out',type=Path,required=True)
    p.add_argument('--cases',nargs='+',required=True)
    p.add_argument('--ollama',type=Path)
    p.add_argument('--execute',action='store_true')
    p.add_argument('--edge',type=int,default=DEFAULT_MAX_IMAGE_EDGE,choices=(0,1024))
    a=p.parse_args()
    plan=json.loads(PLAN.read_text());specs={s['id']:s for s in plan['cases']}
    if len(set(a.cases))!=len(a.cases) or any(c not in specs for c in a.cases):p.error('unknown_or_duplicate_case')
    if a.out.exists():p.error('output_exists_use_new_path')
    if a.execute and (a.ollama is None or not a.ollama.is_file()):p.error('ollama_binary_required')
    a.out.mkdir(parents=True)
    old.save(a.out/'host.json',{'platform':platform.platform(),'cpu_count':os.cpu_count(),
        'ram_bytes':psutil.virtual_memory().total,'edge':a.edge,'model':old.MODEL,
        'expected_model_digest':runtime.DIGEST,'inference_requested':a.execute,
        'policy':'fresh_model_process_per_case; no_retry; no_publication; no_source_network_reads',
        'publication_allowed':False})
    rows=[]
    for case in a.cases:
        out=a.out/case;out.mkdir();row={'case':case,'publication_allowed':False,'edge':a.edge}
        try:
            request,info=prepare_case(a.source,specs[case],out,a.edge)
            row['pages']=len(info['images']);row['source_warnings']=info['source_warnings']
            brief=json.loads(json.dumps(request));brief['messages'][-1].pop('images')
            old.save(out/'request-without-image-bytes.json',brief)
            if not a.execute:
                row['status']='prepared_not_inferred'
            else:
                print('START',case,flush=True)
                with runtime.Server(a.ollama.resolve(),out/'ollama.log') as server:
                    old.save(out/'runtime.json',runtime.check_runtime(server))
                    result=old.infer(server.client,request,out,server.process.pid)
                row.update(result);row['status']=classify(result)
        except Exception as exc:
            row.update(status='preparation_or_runtime_error',error_type=type(exc).__name__,error=str(exc)[:400])
        old.save(out/'summary.json',row);rows.append(row)
        old.save(a.out/'summary.json',{'publication_allowed':False,'attempts':rows})
        print(json.dumps(row,ensure_ascii=False),flush=True)
    target='completed' if a.execute else 'prepared_not_inferred'
    return 0 if all(r['status']==target for r in rows) else 2

if __name__=='__main__':raise SystemExit(main())
