# Parser Semantic Ownership Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox syntax for tracking.

**Goal:** Repair the seven confirmed parser defect groups and apply the verified result to the working catalogue.

**Architecture:** Keep the existing source adapters and schemas. Repair occurrence-level polarity/bounds, coupon boundaries and monetary-condition ownership at their existing parsing seams; keep catalogue decisions consistent with those facts. Reconcile contradictory retained fields against their original source evidence.

**Tech Stack:** Python 3.12, unittest, existing pinned BeautifulSoup/pypdf runtime, Node tests, GitHub Actions, existing Sheets publication/readback.

**Spec:** `docs/superpowers/specs/2026-11-13-parser-semantic-ownership.md`

## Global Constraints

- Change deterministic parsing, normalization and catalogue projection only; do not change LLM behavior, providers, schedules, authentication, access controls or dependencies.
- Do not hardcode business amounts, coupon literals, record IDs or partner exceptions for these fixes. Existing source-template identity checks remain valid.
- Preserve source text, evidence, raw record identity, observation timestamps, stable IDs and private/manual data. No private workbook exports or identifiers, credentials or browser data in public git/artifacts.
- Resolve each numeric/coupon occurrence in its own clause/component; an unrelated denial or sibling offer must not erase a live benefit.
- Preserve actual product exclusions, real reward caps, payment amounts, valid multiword/quoted codes, existing source-specific scopes and supported number formats.
- Re-normalization of retained source rows must not resurrect a contradicted stale structured field or cancelled/malformed code when the complete original evidence is present. Do not guess missing source facts.
- Use regression tests observed failing before code edits, real source/publication/common/catalogue entrypoints, and literal independently derived expectations.
- Ship with normalizer `1.0.6`; public record schema stays compatible.
- Final acceptance requires green Python and Node suites, reviewed replay differences on an immutable public corpus, independent scoped and whole-branch review, CI on the final revision, and readback of the last production publication.

## Runtime and work boundaries

Worktree: `/workspace/scratch/9cc5ddd90dec/key-parser-semantics-nov13`.
Interpreter: `/tmp/parser-audit-nov12-venv/bin/python` (requirements already installed).
Test command: `PYTHONPATH=loyalty:loyalty/tests /tmp/parser-audit-nov12-venv/bin/python -m unittest discover -s loyalty/tests -q`.
Node command: `node --test key/refresh.test.mjs`.
Implement one task at a time. Do not dispatch worker subagents. Reports and logs belong to this plan's ignored workspace. Root owns replay, CI and publication. Do not publish or change workflows from implementation tasks.

## Review Focus

1. Denied/live equal-value occurrences within one source sentence must remain distinguishable (Task 1 and Task 2 tests).
2. Historical structured fields/codes with truncated evidence must not bypass corrected text parsing (Task 2 and Task 3 tests).
3. Uppercase prose after an unquoted code versus an explicitly quoted multiword code must produce different boundaries (Task 3 tests).
4. Equal purchase minima in first/repeat components and ruble abbreviations must preserve ownership, not just values (Task 4 tests).
5. Partial product exclusions and complete closure must remain distinct regardless of source field placement (Task 1 tests).

---

### Task 1: Shared benefit denial and catalogue activity

**Files:** Modify `loyalty/reward_context.py`, `loyalty/catalogue_clauses.py`, `loyalty/catalogue_view.py`; create `loyalty/tests/test_semantic_denial_reader.py`.

**Interfaces:** Preserve `benefit_denied(text, start, end, *, amounts=(), gift=False)`, `benefit_claim(s, raw=None)` and `record_row(n, as_of)`. Later tasks reuse the shared polarity helper. Add only small responsibility-specific helpers if required; document any new public helper signature in the report.

- [x] **Step 1: Add failing public-chain regressions.** Use `make_offer` and the existing `test_dom_card_boundaries.project` helper before `record_row`. Assert no positive benefit and no catalogue offer for `Скидка 10% больше не действует.`, `Скидка 10% временно не предоставляется.` and the already-recognized simple `Скидка 10% не предоставляется.`. Assert a visible 10% row for `Скидка 10% на меню. Акция не действует на алкоголь.` in both benefit and conditions placement. Include full closure control and mixed denied/live equal and different rates. Vary numeric amounts; preserve raw text.
- [x] **Step 2: Run the new module and capture expected failures** in the task report before production edits.
- [x] **Step 3: Fix occurrence-level denial and reader decisions.** Extend supported modifier grammar, preserve product exclusions, and prevent an inactive-only literal from being promoted by a generic benefit-word match. Complete-offer closure must be scoped to a whole-offer statement, not a category exclusion. Keep live nonnumeric gifts/perks working; do not filter every row with an empty numeric benefit list.
- [x] **Step 4: Run focused denial/catalogue suites, then the complete Python and Node commands.** Record all failures/warnings; investigate baseline versus introduced failures without hiding them.
- [x] **Step 5: Self-review and commit** only this task's files. Report RED/GREEN evidence, exact commands, API changes and limitations.

### Task 2: Source-owned mileage semantics and retained-field reconciliation

**Files:** Modify `loyalty/known_rules.py`, `loyalty/unified_normalization.py`, `loyalty/normalized.py`, and `loyalty/reward_context.py`; create `loyalty/tests/test_source_mileage_semantics.py`. Reuse Task 1's polarity helper. The two shared-file additions were approved after a reproduced postfix-denial gap: the source parsed the complete mileage formula, but lexical normalization stopped before its denominator and resurrected a positive rate. Shared forward-basis/span recognition resolves that discrepancy without a separate common-only filter.

**Interfaces:** Preserve `mileage_multiplier(value)`, `earning_rules(value)`, `parse_known_rule` and `normalize_record(raw, *, as_of)`. `earning_rules` can add compatible qualifier/minimum metadata. Shared projection must retain that metadata and full evidence. No schema-breaking fields.

- [x] **Step 1: Add failing source-entrypoint tests** by altering the existing Utair/Bootwood HTML fixtures. `двойные мили больше не начисляются` and `Не начисляется 1 миля за каждые потраченные 70 руб.` must create no positive multiplier/earning. `До 2 миль за каждые потраченные 70 руб.` must have only upper-bound semantics; `От 1 до 2 миль за каждые потраченные 70 руб.` only range semantics. Assert through source record -> `prepare` -> common normalization, with original text unchanged. Include changed factors/bases, product exclusion, mixed live/denied formulas and a retained raw row carrying the old truncated structured fields.
- [x] **Step 2: Run new regressions against Task 1 HEAD and retain RED output.** Existing literal exact mileage controls must pass.
- [x] **Step 3: Read each full owned quantitative expression before structured projection.** Preserve qualifier/lower bound and full sentence evidence. Reconcile retained contradictory fields with their original complete source text; preserve existing native fields when no contradiction is established. Reuse occurrence/polarity and number parsing rather than partner-specific constants. Prevent a source-owned exact amount from contradicting the same bounded lexical occurrence.
- [x] **Step 4: Run focused known-rule/source/common tests and complete Python/Node suites.** Report affected registered source IDs for release refresh.
- [x] **Step 5: Self-review and commit** the task. Record retained-data behavior and any ambiguity handling.

### Task 3: Coupon cancellation, instruction boundaries and retained codes

**Files:** Modify `loyalty/promo_codes.py`, `loyalty/unified_normalization.py`, `loyalty/catalogue_clauses.py`, `loyalty/konsierge_catalog.py`, and `loyalty/hse_alumni.py`; create `loyalty/tests/test_coupon_semantic_boundaries.py`. The source-owned projection and validation additions were approved after reproduced failures: retained Konsierge arrays were rejected before evidence-based repair, and the HSE fallback restored cancelled literals. Preserve source validation and supported label contracts, using occurrence ownership from initial extraction through retained projection.

**Interfaces:** Preserve `candidate(value, position, prefix)`, `extract_promocodes(value, tables=None)`, source `make_offer` and common `normalize_record` shape. Full source text remains in raw. No code activation or live checkout calls.

- [x] **Step 1: Add failing public source -> publication -> normalization -> catalogue tests.** `Промокод OLD10 больше не действует. Примените промокод NEW10.` must expose only NEW10; also test `Не используйте промокод OLD10` and `Промокод OLD10 отменён`. For uppercase `НА САЙТЕ`, `ПРИ ЗАКАЗЕ`, `ДЛЯ ЗАКАЗА` after NEW10, expect only NEW10. Include stale retained `codes=['OLD10','NEW10']` and `codes=['NEW10 НА САЙТЕ']` with complete original evidence. Controls: `MOSKVICH MAG`, quoted `«NEW10 НА САЙТЕ»`, lowercase instructions, `Промокод NEW10 не действует на алкоголь`, same-value denied/live occurrences and independent scoped source table codes.
- [x] **Step 2: Run new tests and capture expected RED assertions.** Use literal expected codes and reader cells, not helper-derived expected output.
- [x] **Step 3: Parse cancellation per complete owned occurrence; bound unquoted extension before instruction words.** Keep explicitly quoted literals intact. Reconcile contradictory retained native codes against the complete text so republishing stored rows applies the fix. Preserve code evidence and scopes; avoid suppressing a live occurrence merely because another occurrence of the same value is denied.
- [x] **Step 4: Run coupon/multiline/table/common/catalogue regressions and full Python/Node suites.** Explain any code-scope changes in report.
- [x] **Step 5: Self-review and commit** this task's files.

### Task 4: Monetary condition ownership and release version

**Files:** Modify `loyalty/unified_normalization.py`; create `loyalty/tests/test_purchase_condition_ownership.py`; update public audit `loyalty/audits/parser-semantic-ownership-20261113.md` with implementation evidence available at task completion (root adds replay/release receipts later).

**Interfaces:** Preserve common normalized schemas, benefit `condition_ids` and existing money helpers. Use `maximum_amount_reference` for explicit purchase upper limits rather than adding a new required condition kind. Set normalizer `VERSION = '1.0.6'` for release.

- [x] **Step 1: Add failing actual-normalizer tests.** For `Скидка 20% на первый заказ от 5000 ₽, скидка 10% на повторный заказ от 2000 ₽.` assert each benefit's referenced minima is exactly its own amount. Repeat with period, semicolon, newline, equal amounts, changed amounts and `руб.`. For `Скидка 10% при сумме заказа не более 5000 рублей.` assert no `benefit_cap`; retain 5000 as a purchase-owned amount reference. Cover `заказ`, `покупка`, `чек` alongside real `лимит скидки на заказ` and independent prepayment controls.
- [x] **Step 2: Run new tests and retain RED output.** Verify failures concern semantics rather than fixture/import errors.
- [x] **Step 3: Bind each minimum and maximum to its own local component.** Use existing occurrence/sentence/component boundaries, preserve decimals and shared conditions, and avoid whole-line reward borrowing. Monetary values themselves cannot decide ownership. Update the release version and concise audit.
- [x] **Step 4: Run money/purchase-stage/compound suites and full Python/Node tests.** Inspect integration with the earlier source/coupon changes.
- [x] **Step 5: Self-review and commit** this task's files. Root then runs immutable-corpus replay, independent whole-branch review, final CI and production readback.
