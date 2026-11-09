# Remaining Numeric Invariance Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove reproduced numerical pins and partial-number parsing from supported loyalty sources after 1.0.3.

**Architecture:** Reuse strict numeric-token validation and source-owned clause boundaries. Keep counts distinct from decimal money/rates; preserve complete literal evidence and existing source identities.

**Tech Stack:** Python, unittest, BeautifulSoup, pypdf; existing KEY Node tests and GitHub publication workflows.

**Spec:** `docs/superpowers/specs/2026-11-09-numeric-invariance.md`

## Global Constraints

- No LLM processing, new dependencies, schedules or access-control changes.
- Preserve raw records, literal evidence, observation timestamps and private data.
- Do not commit private workbook rows, codes, identifiers or credentials.
- Source URL allowlists, document revision identity, section numbers and product names remain explicit; new document discovery is outside this repair.
- Use a feature branch; finish with tests, public-fixture replay, one independent whole-branch review, PR CI, merge, publication and independent native readback.

## Review Focus

- A malformed first number followed by a valid-looking suffix or repeated label must not be accepted; test in Tasks 2 and 4.
- Grouping/decimal separators and number-dependent inflections must preserve full values while rejecting fractional counts; test in Task 2.
- An unrelated price, negated bundle offer or N <= M must not become a reward; test in Task 3.
- Explicit long dates must remain distinct from inferred years and invalid/reversed periods; test in Task 1.
- Published citations, limits and old record identities must remain compatible after projection; test in Tasks 4 and 5.

## Verification Commands

Interpreter: `/tmp/key-privileges-venv/bin/python`.
Full suite: `/tmp/key-privileges-venv/bin/python -m unittest discover -s loyalty/tests -q`.
Each implementation task runs the full suite once before its commit; `task-done` reruns its focused regression after the commit. Redirect verbose output to this plan's workspace. This avoids repeating an unchanged two-minute suite while preserving both verification gates.

### Task 1: Explicit long promotion periods

**Files:** Modify `loyalty/promotion_period.py`; create `loyalty/tests/test_numeric_period_invariance.py`.
**Interfaces:** Consumes `promotion_dates(period, page_title, observed_on)` and `backit_source.parse_detail`; preserves their signatures and errors for invalid/inferred dates.

- [x] Write `test_explicit_long_periods_preserve_source_dates` using the Backit Kuper fixture: 01.09.2026–31.12.2026 and 01.09.2026–31.01.2027 must retain their literal endpoints through producer/common outputs. Add 93/94-day, yearless/mixed-year, reversed, expired and future controls.
- [x] Run `python -m unittest discover -s loyalty/tests -p test_numeric_period_invariance.py -v`; expected RED on explicit periods >93 days.
- [x] Apply the 93-day bound only when an endpoint's year was inferred; retain all calendar/current-period checks.
- [x] Run focused tests, then the full suite; expected zero failures.
- [x] Commit `fix: preserve fully dated long promotion intervals`.

### Task 2: Complete numeric values and inflected units

**Files:** Modify `loyalty/known_rules.py`, `loyalty/known_rules.json`, `loyalty/known_pdf.py`, `loyalty/tier_sources.py`, `loyalty/partner_pages.py`, `loyalty/x5_partners.py`; create `loyalty/tests/test_source_numeric_invariance.py`; update the old PDF test that incorrectly classified a fractional earning rate as an invalid count.
**Interfaces:** Consumes `NUMERIC_TOKEN`, `literal_number`, source fixtures and real entrypoints. Preserves existing scalar field types; adds `qualification.window_years` for Ural, retaining `window='calendar_year'` only for one year.

- [x] Write independent-value regressions: GPB fee199.5/base1500; SIM299.5; Family349.5; iway1.5 miles; Smartavia12.5%/249.5/349.5; Primbank1.5 miles; Finuslugi3 months; generations5 years; Domina1.5 miles; X5 one/two/decimal miles; Ural1500 flights and21 years; Utair1000000 RUB from1 000 thousand. Include malformed/range/negative/fractional-count controls and preserved common/reader evidence.
- [x] Run `python -m unittest discover -s loyalty/tests -p test_source_numeric_invariance.py -v`; expected RED on the reproduced lost/truncated values.
- [x] Replace integer-only or suffix-matching patterns with full validated tokens. Canonicalize money/rates, validate counts separately, and accept normal unit forms without changing source ownership.
- [x] Run focused tests, then the full suite; expected zero failures.
- [x] Commit `fix: preserve full numerical values across source adapters`.

### Task 3: Quantity-based Avolta offers

**Files:** Modify `loyalty/avolta_source.py` and `loyalty/catalogue_clauses.py`; create `loyalty/quantity_offers.py` and `loyalty/tests/test_avolta_quantity_invariance.py`.
**Interfaces:** Preserves `practical_text` and `source_fields`; emits the existing `partner_privilege` with literal evidence, no computed percentage. The shared quantity predicate also admits the same offer to the reader; current source-only recognition otherwise loses even the original two-for-one offer.

- [x] Write tests accepting `Три по цене двух`, `3 по цене 2` and larger valid digit counts; reject `Два по цене трёх`, equal/zero/negative/decimal counts, negation and malformed numeric continuations. Confirm an independent actual discount survives a bad bundle clause.
- [x] Run `python -m unittest discover -s loyalty/tests -p test_avolta_quantity_invariance.py -v`; expected RED on missing offers and false positive N<=M.
- [x] Replace the fixed `два по цене` marker with a validated owned quantity relation using a bounded explicit number-word lexicon and unrestricted valid digit quantities.
- [x] Run focused tests, then the full suite; expected zero failures.
- [x] Commit `fix: recognize changing Avolta bundle quantities`.

### Task 4: Alfa public document values

**Files:** Modify `loyalty/alfa_public_rules.py` and expose the supported count reader in `loyalty/quantity_offers.py`; create `loyalty/tests/test_alfa_public_value_invariance.py`.
**Interfaces:** Preserves `parse_core`, `parse_cashback`, record identities and document revision checks; parameterizes only source-owned numerical clauses and contact data.

- [x] Write the failing full-expense assertion: the restaurant evidence must contain `при списании 20 Альфа-Баллов`. Add independent substitutions for taxi/lounges/restaurants caps, days/hours, companions, RBC minimum, insurance expenses, participant labels, phone digits and cashback categories/caps. Include malformed first numbers, duplicate labels and wrong clauses.
- [x] Run `python -m unittest discover -s loyalty/tests -p test_alfa_public_value_invariance.py -v`; expected RED on value pins and truncated citations.
- [x] Extract complete numeric tokens with their units and validate owned clauses. Preserve parenthesized words literally and do not infer personal eligibility or monetary reward valuation.
- [x] Run focused tests, then the full suite and the immutable Alfa PDF controls; expected zero failures, unchanged values for original documents and complete expense evidence.
- [x] Commit `fix: derive Alfa public rule values from complete clauses`.

### Task 5: Version, replay, review and release

**Files:** Modify `loyalty/unified_normalization.py`, `loyalty/UNIFIED.md`, relevant generation test, the insurance expense-table reader guard and its regression, `loyalty/audits/numeric-invariance-20261109.md`, the existing `loyalty/request.json` release request and this plan.
**Interfaces:** Produces normalizer1.0.4 and a generation distinct from1.0.3 for the same input/date; preserves raw input.

- [x] Add a failing generation regression against the previous generation for a fixed public record; expected RED before bump.
- [x] Bump to1.0.4 and document the repaired numerical paths.
- [x] Run the complete Python suite and `node --test key/refresh.test.mjs`; compare base/current projections on immutable public fixtures or the prior public snapshot and inspect every delta.
- [x] Commit `fix: version numerical invariance repairs`.
- [ ] Obtain one fresh whole-branch review; fix material findings in one RED→GREEN pass and run the full suite.
- [ ] Publish a PR, verify final-head CI, merge the tested tree, use the existing request bridge to refresh the two Alfa PDFs whose lost clauses cannot be recovered from stored rows, wait for publication, and independently read native manifest/catalogue state. Record completion in release evidence after the final write.
