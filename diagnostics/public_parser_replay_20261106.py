"""Replay public stored rows through both real deterministic consumers."""
from __future__ import annotations
import copy
import hashlib
import json
from pathlib import Path
import socket
import sys


def load(path):
    p = Path(path)
    if p.is_symlink() or p.stat().st_size > 64 * 1024 * 1024:
        raise SystemExit("invalid_replay_input")
    return json.loads(p.read_text(encoding="utf-8"))


def save(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, sort_keys=True), encoding="utf-8")


def fingerprint(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                    separators=(",", ":")).encode()).hexdigest()


def emit(kind, value):
    print(kind + " " + json.dumps(value, ensure_ascii=False, sort_keys=True), flush=True)


def no_network(*args, **kwargs):
    raise AssertionError("network_forbidden_in_saved_public_replay")


def prepare_inputs(code_root, bundle_path, output, expected_run, expected_count):
    sys.path.insert(0, str(Path(code_root).resolve() / "loyalty"))
    from sheets_normalized import prepare
    from unified_inputs import HEADERS, inputs_from_tables
    from unified_normalization import INPUT_TABS
    socket.create_connection = no_network
    socket.socket.connect = no_network
    bundle = load(bundle_path)
    if bundle.get("run_id") != expected_run or len(bundle.get("records", [])) != int(expected_count):
        raise AssertionError("source_bundle_identity_or_count_mismatch")
    before = copy.deepcopy(bundle)
    values = prepare(bundle)["parser_offers"]
    tables = {
        tab: [[] for _ in range(header - 1)] + [[{"value": name} for name in HEADERS[tab]]]
        for tab, (header, _) in INPUT_TABS.items()
    }
    tables["parser_offers"].extend(
        [[{"value": value} for value in cells + [""]] for cells in values]
    )
    inputs, _ = inputs_from_tables(tables)
    if bundle != before or len(inputs) != int(expected_count):
        raise AssertionError("source_bundle_mutated_or_rows_lost")
    save(output, inputs)
    emit("REPLAY_INPUT", {"run_id": expected_run, "records": len(inputs),
                          "input_sha256": fingerprint(inputs)})


def normalize(code_root, input_path, output):
    sys.path.insert(0, str(Path(code_root).resolve() / "loyalty"))
    from unified_normalization import normalize_inputs, validate_normalized
    socket.create_connection = no_network
    socket.socket.connect = no_network
    inputs = load(input_path)
    before = copy.deepcopy(inputs)
    result = normalize_inputs(inputs, as_of="2026-11-06")
    if inputs != before or len(result["records"]) != len(inputs):
        raise AssertionError("consumer_mutated_inputs_or_lost_records")
    for row, raw in zip(result["records"], inputs):
        validate_normalized(row)
        if row["raw"] != raw or row["id"] != raw["id"]:
            raise AssertionError("consumer_changed_raw_or_identity")
        if row["provenance"]["observed_at"] != raw["observed_at"]:
            raise AssertionError("consumer_changed_observation_time")
    save(output, result)
    emit("REPLAY_OUTPUT", {"records": len(result["records"]),
                           "terms": result["audit"]["terms"],
                           "result_sha256": fingerprint(result)})


def compact_term(term):
    fields = ("kind", "value", "unit", "qualifier", "basis_value", "basis_unit", "reward_unit")
    item = {key: term.get(key) for key in fields}
    item["evidence_path"] = term.get("evidence", {}).get("path")
    return item


def compare(label, old_path, new_path):
    old = load(old_path)
    new = load(new_path)
    previous = old["records"]
    current = new["records"]
    if [r["id"] for r in previous] != [r["id"] for r in current]:
        raise AssertionError("consumer_reordered_or_changed_source_identities")
    changed = []
    for left, right in zip(previous, current):
        if left["raw"] != right["raw"] or left["provenance"] != right["provenance"]:
            raise AssertionError("consumer_changed_raw_or_provenance")
        if left == right:
            continue
        groups = ("benefits", "conditions", "costs", "codes")
        item = {"record_id": right["id"], "source_id": right["provenance"]["source_id"],
                "changed_fields": sorted(key for key in set(left) | set(right) if left.get(key) != right.get(key))}
        for group in groups:
            old_terms = {x["id"]: x for x in left[group]}
            new_terms = {x["id"]: x for x in right[group]}
            removed = [compact_term(x) for key, x in old_terms.items() if key not in new_terms]
            added = [compact_term(x) for key, x in new_terms.items() if key not in old_terms]
            if removed or added:
                item[group] = {"removed": removed, "added": added}
        changed.append(item)
    if len(changed) > 50:
        raise AssertionError("replay_semantic_delta_requires_larger_review")
    emit("REPLAY_COMPARISON", {"dataset": label, "records": len(current),
                               "old_terms": old["audit"]["terms"], "new_terms": new["audit"]["terms"],
                               "changed_records": len(changed),
                               "raw_and_provenance_unchanged": True})
    for item in changed:
        emit("REPLAY_DELTA", item)


if __name__ == "__main__":
    mode, *args = sys.argv[1:]
    if mode == "prepare":
        prepare_inputs(*args)
    elif mode == "normalize":
        normalize(*args)
    elif mode == "compare":
        compare(*args)
    else:
        raise SystemExit("unknown_replay_mode")
