# Numeric and Clause Ownership Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Preserve supported numerical values and their service, period and sentence owners.

**Architecture:** Keep existing source adapters and common model. Validate complete
tokens only after establishing their local owner; use the shared polarity parser
on full source sentences. Preserve literal evidence and existing fail-closed gates.

**Tech Stack:** Existing Python standard library, BeautifulSoup and unittest; Node KEY tests.

**Spec:** `docs/superpowers/specs/2026-11-12-parser-numeric-followup.md`

## Global Constraints

- No LLM processing, new dependencies, schedules or access-control changes.
- Preserve raw evidence, stable IDs, observation timestamps and private data.
- Do not commit private workbook rows, codes, identifiers or credentials.
- Preserve reviewed source URL/document identity gates and fail-closed guards.
- Normalizer 1.0.5 changes the derived generation for identical input and date.
- Use `/tmp/key-parser-1112-venv/bin/python`; retain full test logs in the plan workspace.

## Review Focus

- A matching label in a neighbouring service section must not supply a missing price; Task 1 tests section isolation and duplicate courier labels.
- Decimal signs, grouping and ranges must not donate a valid multiplier suffix; Task 1 tests malformed tokens and conflicting repetitions.
- Introductory and ongoing paid fees must not exchange periods; Task 1 tests independently changed prices and duration, malformed later values and unsupported ambiguity.
- Denied and live rates with equal numbers must be distinguished by occurrence; Task 2 tests both orders, coordinated denials and product exclusions.
- Sentence boundaries around decimal money, abbreviations and URLs must keep local cap scope; Task 3 tests literal evidence and condition links.

### Task 1: Own source prices, multipliers and whole counts

**Files:**
- Create: `loyalty/tests/test_source_numeric_followup.py`
- Modify: `loyalty/known_rules.py`
- Modify: `loyalty/unified_normalization.py` (GPB cost projection only)

**Interfaces:**
- Consumes: `parse_known_rule(source, raw, url, observed_at)`, existing `whole_count`, `literal_number`, `normalize_record`.
- Produces: unchanged source record shape; optional `introductory_subscription` on a mileage option with `monthly_rub`, `months`, `evidence`; ongoing `monthly_subscription_rub` remains compatible. Common costs use explicit introductory/ongoing scope when this object exists.

- [ ] Step 1: Add failing public entrypoint tests with literal expectations: T2 salon 100 vs delivery 200 and changed 149.75 vs 299.5; Utair `1,5-кратные` -> common `1.5`, `2.5-кратные` -> `2.5`; student age 21 and delay 1; Utair ages 21/61/62. Reject negative/fractional counts, reversed intervals, malformed/duplicate owned values. GPB intro 99/month for 1 month then 399/month, and 49.5 for 3 months then 599.75; both costs keep periods and source evidence.
- [ ] Step 2: Run `python -m unittest discover -s loyalty/tests -p test_source_numeric_followup.py -v`.
  Expected: failures reproduce wrong suffix, lost inflections, T2 duplicate price rejection and GPB wrong ongoing price.
- [ ] Step 3: Implement scoped T2 service extraction; complete positive multiplier validation; year/day inflections with integer/range checks; owned GPB subscription phases and common cost projection. Preserve old plain source fixtures and all raw conditions.
- [ ] Step 4: Run the focused file, then `python -m unittest discover -s loyalty/tests -v`.
  Expected: all pass. Inspect every failure before proceeding.
- [ ] Step 5: Commit source fixes and tests; close task with the full suite via `task-done`.

### Task 2: Preserve percentage bounds and full-sentence polarity

**Files:**
- Create: `loyalty/tests/test_literal_polarity_followup.py`
- Modify: `loyalty/normalized.py` (`percent_spans`)
- Modify: `loyalty/content_discovery.py` (`literal_benefits`)
- Modify: `loyalty/catalogue_clauses.py` (reader denial guard; end-to-end finding recorded in ledger)

**Interfaces:**
- Consumes: `normalize_rates(value, with_spans=True)`, `percent_spans(value)`, `literal_benefits(body)`, FlyStation inventory -> source -> common -> reader.
- Produces: same rate/term shapes and original full-sentence fragments; qualifiers `up_to`/`at_least` for explicit bounds; denied occurrences removed individually.

- [ ] Step 1: Add failing tests: discount `не более 12,5%` -> `up_to`, cashback `не менее 7,25%` -> `at_least`; whitespace and changed numbers; `Скидка 10% не предоставляется` and `Кешбэк 10% не начисляется` produce no positive source/common/reader claim. Denied 10 plus live 5 retains only 5; denied and live equal 10 retain exactly one. Product exclusion and payment 50% preserve only the owned live reward. Keep full original conditions.
- [ ] Step 2: Run `python -m unittest discover -s loyalty/tests -p test_literal_polarity_followup.py -v`.
  Expected: current exact qualifiers and false positive source rewards fail.
- [ ] Step 3: Expand complete bound recognition and use full-sentence parsed occurrence positions to filter phrase-owned rewards, without whole-sentence suppression or derived savings.
- [ ] Step 4: Run focused tests and full Python suite.
  Expected: all pass, no rate/payment ownership regressions.
- [ ] Step 5: Commit and close task with the full suite via `task-done`.

### Task 3: Keep monetary caps local and release the corrected generation

**Files:**
- Create: `loyalty/tests/test_money_cap_ownership_followup.py`
- Modify: `loyalty/unified_normalization.py`
- Modify: `loyalty/normalized.py` (owned monetary cap filter; source-entrypoint finding recorded in ledger)
- Modify: `loyalty/UNIFIED.md`, `loyalty/request.json`
- Create: `loyalty/audits/parser-numeric-followup-20261112.md`

**Interfaces:**
- Consumes: Task 1 structured cost terms, Task 2 validated literal spans, existing `_component_context` and original evidence pointers.
- Produces: first-order discount 500 RUB plus repeat-order cap 1000 RUB with correct condition linkage; normalizer version 1.0.5 and existing refresh request.

- [ ] Step 1: Add failing tests for `Скидка 500 ₽ на первый заказ. Максимальная скидка 1000 ₽ на повторные заказы.`: benefit 500/first, cap 1000/repeat, no link from first reward to repeat cap. Change values, reverse sentences, use decimal/grouped money and `руб.`; retain original raw, cap-only exclusion, same-sentence controls and current percentage behavior. Pin generation inequality against 1.0.4 without changing input/date.
- [ ] Step 2: Run `python -m unittest discover -s loyalty/tests -p test_money_cap_ownership_followup.py -v`.
  Expected: current missing benefit/mixed cap scopes and old generation fail.
- [ ] Step 3: Bind cap classification and scope to its own monetary occurrence using existing component context and local sentence boundaries. Bump version and document precise coverage.
- [ ] Step 4: Run focused tests, full Python suite and `node --test key/refresh.test.mjs`; replay immutable Nov11 public artifact through baseline/current code, accounting for only reviewed deltas and expected version/hash changes. Prepare existing request refresh for changed source adapters, no schedule change.
  Expected: all tests pass; every semantic replay delta explained and no private data committed.
- [ ] Step 5: Commit, close task with full suite via `task-done`, generate whole-branch review package and dispatch one fresh reviewer. Apply material findings in one TDD fix pass; then exact-tree CI, merge, workflow publication and independent native readback.
