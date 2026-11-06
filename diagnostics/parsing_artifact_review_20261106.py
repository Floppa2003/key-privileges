"""Inspect two fixed saved artifacts locally; no requests or project imports."""
from __future__ import annotations

import json
from pathlib import Path
import re
import sys

SOURCE_RUN = "42131727166:1"
CI_COMMIT = "c9f080c9d1b53ae435e13bf916497f89b9da8316"
SOURCE_IDS = ("rgo", "hse_alumni", "af_vtb_rules", "flystation_public")
LOG_NAMES = (
    "python.log", "browser.log", "source-browser.log",
    "geometry-browser.log", "tls-browser.log", "key.log",
)
SUMMARY = re.compile(
    r"(?:Ran \d+ tests? in [0-9.]+s|"
    r"OK(?: \([^)\r\n]{1,200}\))?|FAILED(?: \([^)\r\n]{1,200}\))?|"
    r"(?:#|ℹ) (?:tests|suites|pass|fail|cancelled|skipped|todo|duration_ms) [0-9.]+)"
)


def emit(kind, value):
    rendered = json.dumps(value, ensure_ascii=False, sort_keys=True)
    if len(rendered) > 65536:
        raise SystemExit("bounded_diagnostic_output_exceeded")
    # JSON escaping keeps artifact strings on one inert log line.
    print(kind + " " + rendered, flush=True)


def read_bounded(root, name, limit):
    path = root / name
    if path.is_symlink() or not path.is_file():
        raise SystemExit("expected_artifact_file_missing_or_symlink")
    if not path.resolve().is_relative_to(root.resolve()):
        raise SystemExit("artifact_path_outside_root")
    if path.stat().st_size > limit:
        raise SystemExit("artifact_file_size_bound_exceeded")
    return path.read_text(encoding="utf-8")


def list_files(root):
    entries = []
    for path in root.rglob("*"):
        if path.is_symlink():
            raise SystemExit("artifact_symlink_rejected")
        if path.is_file():
            if len(entries) >= 2000:
                raise SystemExit("artifact_file_count_bound_exceeded")
            entries.append({"path": str(path.relative_to(root)), "bytes": path.stat().st_size})
    entries.sort(key=lambda entry: entry["path"])
    emit("SOURCE_FILES", {
        "file_count": len(entries),
        "total_bytes": sum(entry["bytes"] for entry in entries),
        "listed": entries[:80],
        "omitted_count": max(0, len(entries) - 80),
    })


def main():
    if len(sys.argv) != 3:
        raise SystemExit("expected_source_and_ci_directories")
    source_root, ci_root = map(Path, sys.argv[1:])
    list_files(source_root)
    bundle = json.loads(read_bounded(source_root, "normalized.json", 64 * 1024 * 1024))
    if bundle.get("run_id") != SOURCE_RUN:
        raise SystemExit("source_run_identity_mismatch")
    emit("SOURCE_META", {key: bundle.get(key) for key in ("schema_version", "run_id", "observed_at")})
    reports = bundle.get("sources")
    if not isinstance(reports, list):
        raise SystemExit("source_reports_missing")
    for source_id in SOURCE_IDS:
        matches = [report for report in reports
                   if isinstance(report, dict) and report.get("source_id") == source_id]
        if len(matches) != 1:
            raise SystemExit("source_report_missing_or_duplicated")
        # These are collector reports, not bundle["records"] or offer evidence.
        emit("SOURCE_REPORT", matches[0])

    commit = read_bounded(ci_root, "commit.txt", 128).strip()
    if commit != CI_COMMIT:
        raise SystemExit("ci_commit_identity_mismatch")
    emit("CI_COMMIT", {"commit": commit})
    for name in LOG_NAMES:
        content = read_bounded(ci_root, name, 8 * 1024 * 1024)
        lines = [line.strip() for line in content.splitlines()
                 if SUMMARY.fullmatch(line.strip())]
        if not 1 <= len(lines) <= 32:
            raise SystemExit("ci_summary_missing_or_count_bound_exceeded")
        emit("CI_SUMMARY", {"file": name, "lines": lines})


if __name__ == "__main__":
    main()
