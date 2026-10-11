"""One-call source-first JSON probe; raw input/output remain immutable.

Only the experimental output schema/prompt differ from direct_sampling.py.
Text-span checks are provenance checks, not a semantic accuracy oracle.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import sys
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
BASELINE_SHA256 = "f6da311be861ca002ac7802de0224beabb3fa8d2749d53c3514961362f999da2"
SOURCE_INSTRUCTION = (
    "\n\nПервым полем JSON выведи target_blocks: дословные непрерывные фрагменты "
    "полного текста с заголовком целевой программы и её условиями. Не включай "
    "заголовки и условия соседних программ. Не пересказывай и не объединяй "
    "несмежные фрагменты в одну цитату. Затем заполни offers только по этим "
    "фрагментам: каждое действие how_to_get должно подтверждаться именно ими. "
    "Каждый фрагмент сохрани отдельной строкой массива в порядке источника. "
    "Не добавляй никакого "
    "текста вне JSON."
)


def source_schema(schema: dict) -> dict:
    result = copy.deepcopy(schema)
    if "target_blocks" in result["properties"]:
        raise ValueError("target_blocks_already_present")
    result["properties"] = {
        "target_blocks": {
            "type": "array",
            "items": {"type": "string", "minLength": 1},
            "description": "Дословные непрерывные блоки полного текста, относящиеся к TARGET.",
        },
        **result["properties"],
    }
    result["required"] = ["target_blocks", *result["required"]]
    jsonschema.Draft202012Validator.check_schema(result)
    return result


def source_request(baseline: dict, target: dict, text: str) -> dict:
    result = copy.deepcopy(baseline)
    schema = source_schema(result["format"])
    result["format"] = schema
    result["messages"][0]["content"] += SOURCE_INSTRUCTION
    result["messages"][-1]["content"] = (
        "TARGET: " + json.dumps(target, ensure_ascii=False)
        + "\nSCHEMA: " + json.dumps(schema, ensure_ascii=False)
        + "\nВсе изображения идут по порядку страниц. Полный текст:\n" + text
    )
    return result


def normalized(text: str) -> str:
    # Layout whitespace alone is normalized; words/punctuation/case are not repaired.
    return " ".join(text.split())


def check_blocks(raw: dict, text: str) -> dict:
    blocks = raw.get("target_blocks")
    if not isinstance(blocks, list) or any(not isinstance(b, str) or not b.strip() for b in blocks):
        raise ValueError("invalid_target_blocks")
    if raw.get("has_offer") != bool(raw.get("offers")):
        raise ValueError("offer_state_mismatch")
    if raw.get("offers") and not blocks:
        raise ValueError("offer_without_source_block")
    corpus = normalized(text)
    cursor = 0
    spans = []
    for block in blocks:
        quote = normalized(block)
        start = corpus.find(quote, cursor)
        if start < 0:
            raise ValueError("target_block_not_found_in_source_order")
        end = start + len(quote)
        spans.append({"start": start, "end": end})
        cursor = end
    return {
        "matching": "whitespace_normalized_contiguous_text",
        "normalized_spans": spans,
        "text_span_valid": True,
        "semantic_review": "pending",
        "publication_allowed": False,
    }


def to_legacy(raw: dict, legacy_schema: dict) -> dict:
    result = copy.deepcopy(raw)
    result.pop("target_blocks")
    for offer in result["offers"]:
        if "redemption" in offer:
            raise ValueError("ambiguous_acquisition_fields")
        offer["redemption"] = offer.pop("how_to_get")
    jsonschema.validate(result, legacy_schema)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--case", required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--ollama", type=Path, required=True)
    args = parser.parse_args()
    if args.out.exists():
        parser.error("output_exists")
    if hashlib.sha256((HERE / "direct_sampling.py").read_bytes()).hexdigest() != BASELINE_SHA256:
        parser.error("baseline_code_changed")
    sys.path.insert(0, str(HERE))
    import direct_sampling as baseline

    common = baseline.common
    frozen_io = baseline.frozen_io
    plan = json.loads((HERE.parent / "simple_thinking" / "plan.json").read_text())
    specs = {item["id"]: item for item in plan["cases"]}
    if args.case not in specs:
        parser.error("unknown_case")
    spec = specs[args.case]
    frozen = frozen_io.load_request(args.source, spec)
    target = json.loads(frozen["messages"][-1]["content"].split("\n", 1)[0])
    text = frozen_io.checked_bytes(args.source, spec["text"], spec["sha256"][spec["text"]]).decode("utf-8")
    legacy_schema = json.loads((HERE.parent / "prompt_ab" / "practical_schema.json").read_text())
    schema = copy.deepcopy(legacy_schema)
    offer = schema["properties"]["offers"]["items"]
    acquisition = offer["properties"].pop("redemption")
    acquisition["description"] = "Что пользователь должен или может сделать, чтобы получить эту выгоду. Не на что потом потратить баллы."
    offer["properties"]["how_to_get"] = acquisition
    offer["required"] = ["how_to_get" if name == "redemption" else name for name in offer["required"]]
    old_request = baseline.build_request(frozen, target, text, schema)
    request = source_request(old_request, target, text)

    args.out.mkdir(parents=True)
    common.save(args.out / "frozen-input.json", spec)
    (args.out / "visible-text.txt").write_text(text, encoding="utf-8")
    for i, name in enumerate(spec["images"], 1):
        (args.out / f"page-{i}.png").write_bytes(frozen_io.checked_bytes(args.source, name, spec["sha256"][name]))
    common.save(args.out / "comparison.json", {
        "baseline_run": 36998659984,
        "baseline_code_sha256": BASELINE_SHA256,
        "changed": ["system_append_source_instruction", "schema_target_blocks_first"],
        "unchanged": ["model", "options", "images", "full_text", "TARGET", "one_call"],
        "publication_allowed": False,
    })
    result = baseline.infer(request, args.ollama.resolve(), args.out / "direct", max_seconds=1800)
    result.update(case=args.case, stage="source_first_one_shot", publication_allowed=False, semantic_review="pending")
    if result.get("status") == "completed" and result.get("schema_valid"):
        raw = json.loads((args.out / "direct" / "extracted.json").read_text())
        try:
            review = check_blocks(raw, text)
            common.save(args.out / "source-block-check.json", review)
            common.save(args.out / "legacy-extracted.json", to_legacy(raw, legacy_schema))
            result.update(text_span_valid=True, legacy_schema_valid=True)
        except (ValueError, KeyError, jsonschema.ValidationError) as exc:
            result.update(status="failed", validation_error=str(exc), text_span_valid=False)
    common.save(args.out / "summary.json", result)
    print(json.dumps(result, ensure_ascii=False), flush=True)
    return 0 if result.get("status") == "completed" and result.get("legacy_schema_valid") else 2


if __name__ == "__main__":
    raise SystemExit(main())
