"""Scale the short one-stage think=true JSON extractor to frozen 1024px captures.

Reads page PNGs and visible text from prior review artifacts. One local Qwen call.
No intermediate description, no repair, no source network access, no publication.
"""
from __future__ import annotations
import argparse, base64, copy, json, re, sys
from pathlib import Path
from PIL import Image

HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE.parent / p) for p in ("local_visual", "resolution", "prompt_ab", "simple_thinking")]
import run_cpu as common
from probe import infer
from direct_json import SYSTEM

PLAN = HERE.parent / "local_visual" / "expanded-plan-20260928.json"
SCHEMA = HERE.parent / "prompt_ab" / "practical_schema.json"

def load_case(source: Path, case: str) -> tuple[dict, dict]:
    plan=json.loads(PLAN.read_text())
    specs={x["id"]:x for x in plan["cases"]}
    if case not in specs: raise ValueError("unknown_case")
    spec=specs[case]
    root=source/"results"/case
    if not root.is_dir(): raise ValueError("missing_case_root")
    text=(root/"visible-text.txt").read_text(encoding="utf-8")
    if not text.strip() or len(text)>30000: raise ValueError("text_budget")
    pages=sorted(root.glob("page-*.png"), key=lambda p:int(re.search(r"(\d+)$",p.stem).group(1)))
    if len(pages)!=spec["pages"]: raise ValueError(f"page_count:{len(pages)}!={spec['pages']}")
    if len(pages)>8: raise ValueError(f"page_budget:{len(pages)}>8")
    images=[]
    for p in pages:
        raw=p.read_bytes()
        with Image.open(p) as im:
            if max(im.size)>1024: raise ValueError("image_too_large")
        images.append(base64.b64encode(raw).decode("ascii"))
    manifest=json.loads((root/"input.json").read_text())
    if manifest.get("all_pdf_pages_sent") is not True or manifest.get("max_image_edge")!=1024:
        raise ValueError("source_manifest")
    schema=json.loads(SCHEMA.read_text())
    target={"partner":spec["merchant"],"program":spec["program"],"as_of":plan["as_of"]}
    request={
      "model":common.MODEL,"stream":False,"think":True,"keep_alive":"5m","format":schema,
      "options":{"temperature":0,"seed":1,"num_ctx":16384,"num_predict":8192,"num_thread":4,"num_gpu":0},
      "messages":[
        {"role":"system","content":SYSTEM},
        {"role":"user","content":"TARGET: "+json.dumps(target,ensure_ascii=False)
          +"\nSCHEMA: "+json.dumps(schema,ensure_ascii=False)
          +"\nВсе изображения идут по порядку страниц. Полный текст:\n"+text,
         "images":images}
      ]
    }
    return request, {"case":case,"target":target,"pages":len(pages),"source_artifact_layout":"expanded_1024_v1",
                     "publication_allowed":False}

def main()->int:
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--source",type=Path,required=True)
    p.add_argument("--case",required=True)
    p.add_argument("--out",type=Path,required=True)
    p.add_argument("--ollama",type=Path,required=True)
    a=p.parse_args()
    if a.out.exists(): p.error("output_exists")
    a.out.mkdir(parents=True)
    request,meta=load_case(a.source,a.case)
    brief=copy.deepcopy(request); brief["messages"][-1].pop("images")
    common.save(a.out/"request-without-images.json",brief)
    common.save(a.out/"input-meta.json",meta)
    result=infer(request,a.ollama.resolve(),a.out/"direct",max_seconds=1800)
    result.update(case=a.case,stage="expanded_direct_json_think_true",publication_allowed=False)
    common.save(a.out/"summary.json",result)
    print(json.dumps(result,ensure_ascii=False),flush=True)
    return 0 if result.get("status")=="completed" and result.get("schema_valid") else 2

if __name__=="__main__": raise SystemExit(main())
