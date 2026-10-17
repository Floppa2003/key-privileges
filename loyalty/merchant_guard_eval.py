"""Replay conservative semantic guard on frozen block-extraction observations."""
from __future__ import annotations
import argparse, json
from pathlib import Path
import merchant_blocks as b
import merchant_general as core
import merchant_semantic_guard as g

def parse_answer(raw: str) -> dict:
    return core.model_output({"answer": raw})

def evaluate(path: Path) -> dict:
    data=json.loads(path.read_text(encoding="utf-8"))
    rows=[]
    for trial in data["trials"]:
        s=trial["source"]
        doc=b.build(s["markdown"],url=s["url"],observed_at=s["observed_at"],completeness=s["completeness"])
        if doc["source_sha256"] != s["source_sha256"]:
            raise ValueError("frozen_source_sha_mismatch")
        pred=parse_answer(trial["raw_answer"])
        checked=b.check(trial["target"],doc,pred)
        guarded=g.assess_result(trial["target"],checked)
        rows.append({
            "id":trial["id"],
            "block_status":checked["status"],
            "guard_status":guarded["status"],
            "guard_reasons":[o["reasons"] for o in guarded["offers"]],
            "publication_allowed":False,
        })
    # These are frozen expectations decided from the source context, not model outputs.
    by={r["id"]:r for r in rows}
    expected={
        "elcom":"review_required",      # excerpt provenance still blocks auto acceptance
        "academia":"review_required",   # extractor omitted explicit audience field
        "teplohod":"review_required",   # past event is not a reusable cardholder entitlement
    }
    passed=all(by[k]["guard_status"]==v for k,v in expected.items())
    return {"version":"merchant-semantic-guard-eval-v1","passed":passed,
            "publication_allowed":False,"expected":expected,"results":rows}

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--input",type=Path,required=True);p.add_argument("--out",type=Path,required=True)
    a=p.parse_args();result=evaluate(a.input)
    a.out.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding="utf-8")
    raise SystemExit(0 if result["passed"] else 1)

if __name__=="__main__":main()
