# Numeric parsing generalization

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove reproduced accidental numeric constants without weakening source ownership or numeric validation.

**Architecture:** Extract literal parameters in the existing source adapters; share only the value rules needed to re-project stored evidence. Keep source identity/layout checks. Generalize reader decisions by semantic context, never by a previously observed amount or year.

**Tech Stack:** Python unittest, existing HTML/PDF adapters, common projection, reader catalogue, GitHub Actions and managed Sheets publication.

**Spec:** `docs/superpowers/specs/2026-11-08-numeric-parsing.md`.

## Global Constraints

- No changes to brand/source identities, access controls, collection budgets, personal eligibility, LLM processing or schedules.
- Preserve original records, literal evidence, source timestamps and private data.
- Do not commit private workbook rows, codes, identifiers or credentials.
- Exercise real parsers/projections; mock only external PDF decoding/transport where required by existing fixtures.
- Base: `f3569391bb34b6ebfa4fe149bdbafc27caaeca8d`; existing common version 1.0.2.
- Reuse the immutable 1387-record public snapshot and inspect every semantic delta.
- Merge and publication remain authorized parts of this continuing repair task.

## Review Focus

- A valid changed amount must not rescue a malformed numeric suffix or range.
- Cached structured metadata must not override changed literal source evidence.
- Relative dates and start-only dates must not become invented absolute expiries.
- Percent payment conditions and ordinary prices must not turn into discounts.
- Known source formats/identities and immutable raw/evidence must survive the changes.

### Task 1: Generalize known rule values and cached projection

**Files:** Modify `loyalty/known_rules.py`, `loyalty/unified_normalization.py`; create `loyalty/known_rule_terms.py`, `loyalty/tests/test_known_rule_value_changes.py`.

**Interfaces:** `retail_redemption_basis(text: str) -> str | None` derives only explicitly stated discount/delivery treatment. Existing redemption keys remain; GPB fees add `notifications_from_month` (positive int) and `notifications_monthly_rub` (decimal string), retaining `notifications_after_first_month_rub` only when the start month is 2. Student `entitlement_expiry_text` remains literal with no absolute year.

- [x] Add real source/common tests for delivery included/excluded/unspecified/conflicting, and stale cached basis; assert unchanged raw and corrected typed scope/source-value.
- [x] Add fee start-month substitutions 1, 3, 12 with changed prices, decimal prices and invalid/nonpositive/nonintegral month controls; preserve existing second-month compatibility.
- [x] Add student expiry substitutions 2 September, 15 October, 29 February; reject impossible dates and retain relative academic year.
- [x] Run new file and observe the expected failures before production edits.
- [x] Implement shared literal basis extraction, source fee/day parameters and common cached-basis correction without mutating raw.
- [x] Run focused tests and existing known-rule/product/common tests; expected PASS.
- [x] Commit; task-done runs `/tmp/key-privileges-venv/bin/python -m unittest discover -s loyalty/tests -q`; expected PASS.

### Task 2: Extract Alfa PDF numerical terms

**Files:** Modify `loyalty/alfa_partner_rules.py`; create `loyalty/tests/test_alfa_partner_value_changes.py`.

**Interfaces:** Existing `parse_document`, `partner_rates`, `validate_partner_record`, `project_common` remain. Rates and generated titles are dynamic; cap and payout remain linked literal conditions, with no new required cached fields.

- [x] Add source-to-common tests changing rate/cap/days together and separately (7.5%, 2750, 21 days; 12%, 9000, 3 days); current fixture remains equivalent.
- [x] Cover grouped/decimal numbers, parenthesized cap words, title/operative-rate disagreement, malformed/range/negative/out-of-domain rates and invalid caps/days.
- [x] Run new file and observe expected failures.
- [x] Capture and validate current numeric tokens; build the title from the parsed operative rate, retaining document identity and clause ownership checks.
- [x] Run focused and existing Alfa/common tests; expected PASS.
- [x] Commit; task-done runs the full Python suite; expected PASS.

### Task 3: Generalize reader numeric decisions

**Files:** Modify `loyalty/catalogue_view.py`, `loyalty/catalogue_clauses.py`; create `loyalty/tests/test_catalogue_value_changes.py`.

**Interfaces:** Preserve `owned_source_text(raw)` and `record_row(n, as_of)`; preserve original raw. Calendar decisions use explicit source completion/end context and the supplied date, never a fixed list of years.

- [x] Add flight-count substitutions (`двух`, `трёх`, `2`, `17`) and ensure the same material qualification clause survives.
- [x] Add past/current/future campaign dates across 2025, 2026, 2027, and 2031; a start-only date cannot establish expiry.
- [x] Add payment/prepayment percentages 25, 50, 75 and 100 with a positive neighboring discount control; payment alone must remain excluded.
- [x] Add nominal promotional-price substitutions with an ordinary-price negative control; use source context rather than a one-ruble constant.
- [x] Run new file and observe expected failures.
- [x] Implement bounded semantic reader rules and run existing catalogue tests; expected PASS.
- [x] Commit; task-done runs the full Python suite; expected PASS.

### Task 4: Version, full replay and release

**Files:** Modify `loyalty/unified_normalization.py`, `loyalty/UNIFIED.md`; add source/common substitution integration tests as needed.

**Interfaces:** Common version 1.0.3 identifies changed semantics for immutable stored inputs. Existing schema, publication and source snapshots remain unchanged.

- [x] Add a regression proving changed semantics do not reuse the preceding generation; observe RED, then bump version/document the contracts.
- [x] Run all Python and KEY tests. Replay all immutable public inputs through common/reader views; separately validate source-derived changes. Inspect every delta.
- [x] Commit and complete task-done with the full Python suite.
- [x] Obtain one fresh whole-branch review; fix material findings with RED-to-GREEN regressions and a green full suite.
- [ ] Run branch CI, merge exact verified head, complete existing normalization publication and independently read back the receipt/native manifest.

Release completion is verified in the merged PR, workflow receipt and native publication manifest; it is not pre-marked by this code commit.
