# Retained production regressions implementation plan

Specification: `docs/superpowers/specs/2026-11-13-retained-production-regressions.md`.

Base: merged PR125, `2dc70b9d7da43220b4bed1c14de95128a7e3d4d1` (normalizer1.0.6). One implementer owns the combined repair because the mileage, clause and monetary paths share normalization invariants.

## Combined implementation task

- [x] Add literal synthetic regressions for all three failures and observe their intended semantic assertion failures before production edits.
- [x] Repair complete reverse-mileage basis handling and grounded duplicate reconciliation; preserve independent source/channel/bound cases and genuine denial.
- [x] Repair exclusion-only headline selection with subordinate discount mentions; preserve numeric and nonnumeric positive siblings and partial-exclusion semantics.
- [x] Repair explicitly owned local minima across intervening channel/category/basket wording, without broad cross-component fallback.
- [x] Add changed-number/format/ordering and negative ownership controls through actual entrypoints.
- [x] Bump normalizer to1.0.7 and write a public audit containing only synthetic examples and public validation receipts.
- [x] Self-review, freeze changed production/tests, run affected suites and the complete Python/Node gates; verify hashes and commit the repair with an exact report.

Allowed production files: `loyalty/normalized.py`, `loyalty/reward_context.py`, `loyalty/catalogue_clauses.py`, `loyalty/unified_normalization.py`. Add one focused regression module under `loyalty/tests/`; extend existing related tests only if this makes the assertion clearer. A concrete dependency report is required before other production-file changes.

## Review fix round 1

Candidate `c708327` was rejected by independent review. Preserve its receipts
and repair all four findings together before the next acceptance attempt.

- [x] I1: require compatible owned channel/category qualifiers, including named alternatives and coverage rather than partial overlap.
- [x] I2: reject an owned prefix denial of a purchase minimum without cancelling independent positive siblings.
- [x] I3: require actual occurrence ownership in addition to the full signature; retain independent equal formulas in both orders and the native owner's own denial/bound.
- [x] I4: permit bounded quoted-name alternatives inside the qualifier, preserving independent `или` action/reward boundaries.
- [x] Observe semantic RED before repairs, retain failed receipts, pass focused/affected controls, and self-review shared restriction links and raw/provenance preservation.
- [x] Freeze the replacement code/tests, run full Python/Node once, verify unchanged hashes, commit and append the exact fix-round report.

## Review fix round 2

I1–I4 were addressed on `740a2fd`; I5 remained an owned postfix requirement
denial in the extended threshold grammar.

- [x] Observe both postfix variants as semantic RED, including changed numbers/formats and unrelated-negative ownership controls.
- [x] Extend only the local requirement-polarity guard; preserve prefix behavior, true minima, live discounts and source evidence. Verify actual outputs and affected tests.
- [x] Freeze code/tests, run full Python/Node once, verify hashes, commit and append the exact round-2 report without altering prior evidence.

## Review fix round 3

Round 2 repaired the bare I5 predicates, but review retained I5 for the same
owned denial with ordinary modifiers such as `больше` and `уже`.

- [x] Observe modified prefix/postfix forms as semantic RED before production edits, with changed numbers and independent positive/negative ownership controls.
- [x] Reuse the existing bounded modifier vocabulary in one local requirement-polarity helper; cover ordinary word positions, present/future requirement forms, fused `необязательно` and the same families' short predicates without traversing a separate argument or instruction.
- [x] Preserve all 26 prior focused tests, retain every failed receipt, pass the affected suites and independently assert actual source/benefit/minimum results.
- [x] Freeze code/tests, run full Python/Node once, verify unchanged hashes, commit and append the exact round-3 report without altering prior evidence.

## Controller acceptance and release

- [x] Independent task/code review of the complete repair and original constraints.
- [x] Public immutable replay on the exact accepted code; review all changes, preserve original inputs/baseline.
- [x] Private frozen-input replay: all three blocker classes closed and every remaining semantic/reader difference justified from original evidence; no private artifacts in GitHub.
- [ ] Reconcile current main; publish exact accepted tree in a PR; obtain green exact-revision remote CI.
- [ ] Merge through the existing authorized release flow; observe relevant publishers and independently verify the final native version, generation, source snapshot and reader state.

Do not replace the frozen inputs or discard earlier failed receipts. Any fresh concrete defect remains blocking. No broad optimization, source enrichment or future-language guarantee is implied by this plan.
