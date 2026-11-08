# Deterministic parsing boundary repairs

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Repair reproduced parser defects on current main while preserving source evidence and the existing publication contract.

**Architecture:** Validate explicit source identities at the native-cell input boundary, before normalization or writes. Bind explicit points-award negation to the corresponding amount in common projection. Keep source-specific parsing and common projection separate; add other repairs only after a concrete failing reproduction.

**Tech Stack:** Python 3.12, unittest, the existing Sheets cell adapter and in-memory publication integration client.

**Spec:** `loyalty/UNIFIED.md` (unchanged public IDs, explicit legacy row locators, reject invalid input before publication), plus the user's continuation request restricted to deterministic parsing.

## Global Constraints

- No LLM processing/configuration changes or model calls.
- Preserve original source fields, formulas, observation times, access controls and collection budgets.
- No private source rows, codes, spreadsheet identifiers or credentials in repository/artifacts.
- Test real input-to-publication behavior; isolate external I/O at the existing fake client.
- Current main baseline: `627c7ffae3316cca651039729e257121ec70275e`, 2231 Python tests pass.
- Public replay baseline: run `42478152200`, 1387 records; all common records pass their schema.

## Review Focus

- A blank ID in a populated parser input must not acquire the identity of its row position.
- Whitespace-only, numeric and boolean IDs must not be accepted as explicit parser identities.
- A formula with a valid cached string ID must preserve its original formula and identity.
- Truly empty/styled parser rows must remain ignorable.
- Legacy sheets without an ID column must keep their existing row-locator identity.
- Literal prefix/suffix denials must not produce earned points, including shared lists.
- Neighbouring affirmative awards and unrelated negated conditions must remain distinct.
- Raw source text and exact evidence must remain unchanged; normalized views must contain only the affirmative amount.

### Task 1: Preserve explicit parser identities

**Files:**
- Modify: `loyalty/unified_inputs.py`, `loyalty/UNIFIED.md`
- Create: `loyalty/tests/test_unified_source_ids.py`

**Interfaces:**
- Consumes: `atom_from_cell(cell)`, `inputs_from_tables(tables, public_records=None)`, `publish_all(as_of=..., client=...)`.
- Produces: unchanged canonical records for valid inputs; `ValueError` before publication for a populated `parser_offers` or `parser_inbox` row without a nonblank string `ID`.

- [x] Write tests for both parser inputs with absent, blank, whitespace-only, numeric and boolean IDs. Assert `ValueError` and unchanged source tables.
- [x] Add valid literal/formula ID controls, empty-row controls, and exact legacy row-locator comparisons.
- [x] Add an actual `publish_all` integration regression using `FakeUnified`; invalid ID must leave all source/destination tables unchanged and perform no non-GET request.
- [x] Run `/tmp/key-privileges-venv/bin/python -m unittest discover -s loyalty/tests -p test_unified_source_ids.py -v`; expected: new invalid-ID checks FAIL before the repair.
- [x] Require nonblank string IDs only for the two known ID-bearing parser schemas before any fallback. Preserve valid ID text verbatim; retain row-based identities for legacy inputs.
- [x] Run the same focused command; expected: all checks PASS. Document the explicit ID contract.
- [x] Run the full Python suite and public publisher/reader replay; expected: no regressions and byte-identical complete outputs for the 1387 valid public records.
- [x] Commit this independently reviewable repair.

### Task 2: Keep denied points awards out of benefits

**Files:**
- Modify: `loyalty/unified_normalization.py`, `loyalty/UNIFIED.md`
- Create: `loyalty/tests/test_unified_points_negation.py`

**Interfaces:**
- Consumes: `normalize_record`, `normalize_inputs` and real common view projection with literal source text.
- Produces: no earned-points benefit for an explicitly denied amount; neighbouring positive awards, exact evidence and raw input stay intact.
- Shares the public replay gate with Task 1; no change to native ID handling.

- [x] Add failing production-entrypoint tests for prefix and suffix denials of ordinary points, bonus amounts and existing additional-point wording.
- [x] Cover neighbouring positive awards in both orders, same-sentence conjunctions, shared negated lists, and separate fields/sentences; verify evidence and raw preservation.
- [x] Add affirmative controls, including wording with `не менее`, `не более`, `не только` and independent negated conditions.
- [x] Run `/tmp/key-privileges-venv/bin/python -m unittest discover -s loyalty/tests -p test_unified_points_negation.py -v`; expected: denied rewards currently FAIL.
- [x] Add a small amount-owned negation check before creating point benefits, retaining existing quantity and exchange/price parsing.
- [x] Repeat focused tests; expected: PASS. Document the deterministic negation boundary.
- [x] Replay all 1387 public records; inspect every delta and reject unexplained changes. Run full Python suite and KEY tests.
- [x] Commit this independently reviewable repair and run the task completion gate.

## Integration verification

- [x] Review the complete branch with a fresh independent reviewer.
- [ ] Run required Python, KEY and existing CI/browser gates on the final tree.
- [ ] Read back the published branch/PR state and the final merged code; verify any triggered publication only after its last material write.
