"""One declared image-resolution comparison after the full-resolution timeout."""
from __future__ import annotations
import argparse, base64, hashlib, io, json, os
from pathlib import Path
from PIL import Image, UnidentifiedImageError
import psutil
import requests
import run_cpu as core

DIGEST='2a654d98e6fba55d452b7043684e9b57a947e393bbffa62485a7aac05ee4eefd'


def reduce_images(images, edge):
    if type(edge) is not int or not 1<=edge<=2048:raise ValueError('invalid_image_edge')
    values=[]
    for raw in images:
        try:
            with Image.open(io.BytesIO(raw)) as image:
                image.load()
                if max(image.size)<=edge:values.append(raw);continue
                image.thumbnail((edge,edge),Image.Resampling.LANCZOS)
                out=io.BytesIO();image.save(out,format='PNG');values.append(out.getvalue())
        except (UnidentifiedImageError,OSError) as exc:
            raise ValueError('invalid_image') from exc
    return values


def main():
    p=argparse.ArgumentParser();p.add_argument('--source',type=Path,required=True)
    p.add_argument('--out',type=Path,required=True);p.add_argument('--server-pid',type=int,required=True)
    a=p.parse_args();a.out.mkdir(exist_ok=True,parents=True)
    client=requests.Session();client.trust_env=False
    version=client.get(core.BASE+'/api/version',timeout=10);version.raise_for_status()
    tags=client.get(core.BASE+'/api/tags',timeout=10);tags.raise_for_status()
    local=core.local_model(tags.json())
    if local.get('digest')!=DIGEST:raise ValueError('comparison_model_changed')
    show=client.post(core.BASE+'/api/show',json={'model':core.MODEL},timeout=10);show.raise_for_status()
    core.save(a.out/'model-show.json',show.json())
    if 'vision' not in show.json().get('capabilities',[]):raise ValueError('vision_not_supported')
    core.save(a.out/'runtime.json',{'ollama':version.json(),'local_model':local,'cpu_count':os.cpu_count(),
        'ram_bytes':psutil.virtual_memory().total,'no_cloud':os.environ.get('OLLAMA_NO_CLOUD'),
        'endpoint':core.BASE,'publication_allowed':False,'comparison':'same model/prompt/text/all pages; max image edge 768'})
    out=a.out/'nevsky';out.mkdir(exist_ok=True)
    request=core.prepare(a.source,'nevsky',out)
    raw_images=[base64.b64decode(x) for x in request['messages'][-1]['images']]
    reduced=reduce_images(raw_images,768)
    full=out/'full-resolution';full.mkdir(exist_ok=True)
    changes=[]
    for i,(before,after) in enumerate(zip(raw_images,reduced),1):
        (full/f'page-{i}.png').write_bytes(before);(out/f'page-{i}.png').write_bytes(after)
        changes.append({'page':i,'before_sha256':hashlib.sha256(before).hexdigest(),
            'after_sha256':hashlib.sha256(after).hexdigest(),
            'before_size':list(Image.open(io.BytesIO(before)).size),'after_size':list(Image.open(io.BytesIO(after)).size)})
    request['messages'][-1]['images']=[base64.b64encode(x).decode('ascii') for x in reduced]
    manifest=json.loads((out/'input-manifest.json').read_text())
    manifest['pdf_render_dpi_before_resize']=manifest.pop('render_dpi')
    manifest.update(image_sha256=[c['after_sha256'] for c in changes],image_transform=changes,max_image_edge=768)
    core.save(out/'input-manifest.json',manifest)
    result=core.infer(client,request,out,a.server_pid);result['case']='nevsky';result['max_image_edge']=768
    core.save(a.out/'summary.json',[result]);print(json.dumps(result,ensure_ascii=False),flush=True)
    return 0 if result['schema_valid'] else 2

if __name__=='__main__':raise SystemExit(main())
