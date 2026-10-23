"""Run the one-stage 9B think=true JSON extractor on fresh public visual captures.

Input: a merchant-visual-batch artifact with captures/<case>/reading.pdf,
visible-text.txt, and capture.json. No network reads and no publication.
"""
from __future__ import annotations

import argparse
import base64
import copy
import io
import json
import os
import re
import sys
from pathlib import Path

import fitz
import jsonschema
from PIL import Image

HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE.parent / p) for p in ("local_visual", "resolution", "prompt_ab", "simple_thinking")]
import run_cpu as common
import benchmark as runtime
from probe import infer
from direct_json import SYSTEM

PLAN = HERE.parent / "local_visual" / "expanded-plan-20260928.json"
LEGACY_SCHEMA = HERE.parent / "prompt_ab" / "practical_schema.json"
MAX_IMAGE_EDGE = 1024
MAX_PAGES = 8

SCHEMA_PROMPT_SUFFIX = """
SCHEMA уже согласована с инструкцией и содержит все нужные поля, включая how_to_get.
Не анализируй и не перепроверяй структуру SCHEMA и не обсуждай возможные противоречия в ней.
Используй SCHEMA как заданный формат; reasoning посвяти только содержанию источника и затем выдай финальный JSON.
"""


def model_schema(legacy: dict) -> dict:
    schema = copy.deepcopy(legacy)
    offer = schema["properties"]["offers"]["items"]
    field = offer["properties"].pop("redemption")
    field["description"] = "Что пользователь должен или может сделать, чтобы получить эту выгоду. Не на что потом потратить баллы."
    offer["properties"]["value"]["description"] = "Числовая величина основной выгоды. Для относительного увеличения вида «на N% больше баллов/кэшбэка» укажи N."
    offer["properties"]["unit"]["description"] = "Единица value. Для относительного увеличения в процентах используй «%»; для фиксированных баллов — «баллов»."
    offer["properties"]["how_to_get"] = field
    offer["required"] = ["how_to_get" if x == "redemption" else x for x in offer["required"]]
    return schema


def legacy_output(raw: dict, schema: dict) -> dict:
    out = copy.deepcopy(raw)
    for offer in out["offers"]:
        offer["redemption"] = offer.pop("how_to_get")
    jsonschema.validate(out, schema)
    return out


def capture_root(source: Path) -> Path:
    direct = source / "captures"
    if direct.is_dir():
        return direct
    matches = list(source.rglob("capture-report.json"))
    if len(matches) != 1:
        raise ValueError("capture_root_not_unique")
    return matches[0].parent


def load_case(source: Path, case: str, out: Path) -> tuple[dict, dict, dict]:
    plan = json.loads(PLAN.read_text())
    specs = {x["id"]: x for x in plan["cases"]}
    if case not in specs:
        raise ValueError("unknown_case")
    spec = specs[case]
    root = capture_root(source) / case
    capture = json.loads((root / "capture.json").read_text())
    if not str(capture.get("capture_status", "")).startswith("captured"):
        raise ValueError("capture_not_usable")
    text = (root / "visible-text.txt").read_text(encoding="utf-8")
    if not text.strip() or len(text) > 32000:
        raise ValueError("text_budget")

    pages: list[bytes] = []
    infos: list[dict] = []
    pdf_path = root / "reading.pdf"
    with fitz.open(pdf_path) as pdf:
        if not 1 <= len(pdf) <= MAX_PAGES:
            raise ValueError(f"page_budget:{len(pdf)}>{MAX_PAGES}")
        for i, page in enumerate(pdf, 1):
            original = page.get_pixmap(matrix=fitz.Matrix(96 / 72, 96 / 72), alpha=False).tobytes("png")
            small = runtime.resized_images([original], MAX_IMAGE_EDGE)[0]
            (out / f"page-{i}.png").write_bytes(small)
            pages.append(small)
            with Image.open(io.BytesIO(small)) as im:
                infos.append({"page": i, "size": list(im.size)})

    legacy = json.loads(LEGACY_SCHEMA.read_text())
    schema = model_schema(legacy)
    observed = str(capture.get("observed_at") or "")
    target = {
        "partner": spec["merchant"],
        "program": spec["program"],
        "as_of": observed[:10] if len(observed) >= 10 else None,
    }
    request = {
        "model": os.environ.get("DIRECT_MODEL", common.MODEL),
        "stream": False,
        "think": True,
        "keep_alive": "5m",
        "format": schema,
        "options": {
            "temperature": 0,
            "seed": 1,
            "num_ctx": 32768,
            "num_predict": 8192,
            "num_thread": 4,
            "num_gpu": 0,
        },
        "messages": [
            {"role": "system", "content": SYSTEM + SCHEMA_PROMPT_SUFFIX},
            {
                "role": "user",
                "content": "TARGET: " + json.dumps(target, ensure_ascii=False)
                + "\nSCHEMA: " + json.dumps(schema, ensure_ascii=False)
                + "\nВсе изображения идут по порядку страниц. Полный текст:\n" + text,
                "images": [base64.b64encode(x).decode("ascii") for x in pages],
            },
        ],
    }
    meta = {
        "case": case,
        "target": target,
        "pages": len(pages),
        "page_images": infos,
        "source_url": capture.get("final_url") or capture.get("url"),
        "source_observed_at": capture.get("observed_at"),
        "source_warnings": capture.get("warnings", []),
        "publication_allowed": False,
    }
    return request, meta, legacy


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--source", type=Path, required=True)
    p.add_argument("--case", required=True)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--ollama", type=Path, required=True)
    a = p.parse_args()
    if a.out.exists():
        p.error("output_exists")
    a.out.mkdir(parents=True)

    request, meta, legacy_schema = load_case(a.source, a.case, a.out)
    common.save(a.out / "input-meta.json", meta)
    brief = copy.deepcopy(request)
    brief["messages"][-1].pop("images")
    common.save(a.out / "request-without-images.json", brief)

    result = infer(request, a.ollama.resolve(), a.out / "direct", max_seconds=5400)
    result.update(case=a.case, stage="expanded_live_direct_json_think_true_9b", publication_allowed=False)
    if result.get("status") == "completed" and result.get("schema_valid"):
        raw = json.loads((a.out / "direct" / "extracted.json").read_text())
        legacy = legacy_output(raw, legacy_schema)
        common.save(a.out / "legacy-extracted.json", legacy)
        result["legacy_schema_valid"] = True
    common.save(a.out / "summary.json", result)
    print(json.dumps(result, ensure_ascii=False), flush=True)
    return 0 if result.get("status") == "completed" and result.get("schema_valid") and result.get("legacy_schema_valid") else 2


if __name__ == "__main__":
    raise SystemExit(main())
