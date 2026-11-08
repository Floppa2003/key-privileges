# Literal reward parsing repairs

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Repair the reproduced reward parsing defects and continue through adjacent failing cases until a targeted audit has no unresolved demonstrated defect.

**Architecture:** Bind each quantity to its local earning, spending, denial or reference context before projection. Keep numeric validation, explicit source structures and original evidence intact; extend only literal supported wording. Reuse the same local action ownership for miles and points and apply equivalent denial boundaries to percentages and gifts.

**Tech Stack:** Existing Python unittest pipeline, normalized source adapters, common projection, reader catalogue and GitHub Actions.

**Spec:** `loyalty/UNIFIED.md`, the six reproduced findings reported to the user, and the user's instruction to repair adjacent deterministic parser defects. No LLM work.

## Global Constraints

- Preserve source IDs, raw fields, exact evidence, dates, observation times, source access controls and collection budgets.
- No private source rows, codes, spreadsheet identifiers or credentials in repository or CI artifacts.
- No LLM processing/configuration changes or model calls.
- Exercise real `normalize_rates`, `normalize_record`, `normalize_inputs`, `prepare_views` and reader projection; no mocks for semantic parsing.
- Keep unsupported/ambiguous meaning in raw; never invent eligibility, award probability, exchange valuation or missing terms.
- Branch baseline: `31993a692b992bb8cc7fad6c5f6c1148c6c7149b`; 2244 Python tests pass.
- Public replay baseline: run `42478152200`, 1387 source records. Inspect every semantic delta, not merely aggregate counts.
- Complete branch CI, merge and existing publication workflow; independently read back final external state.

## Review Focus

- Shared amount lists and postfix actions must not borrow a sibling's denial or expense.
- A balance requirement, exchange denominator or replaced amount must not become an earned reward.
- Limited applicability and unrelated negative conditions must preserve a positive benefit.
- A sibling gift's first-visit restriction must not limit a permanent discount.
- Chance-to-win campaigns must not pass the ordinary-offer reader filter; promotional use of the word chance alone must remain harmless.

### Task 1: Bind reward actions to literal amounts

**Files:** Create `loyalty/reward_context.py`, `loyalty/tests/test_reward_action_ownership.py`; modify `loyalty/normalized.py`, `loyalty/unified_normalization.py`.

**Interfaces:** `reward_role(text, start, end, *, amounts=())` returns `earn`, `spend`, `denied`, `reference` or `unknown` for an original-text span. `normalize_rates` retains its public signature; common projection keeps its schema.

- [x] Add entrypoint tests: `Не начисляем 500 миль` produces no miles; a neighbouring positive 100 remains. Cover prefix/suffix and shared lists in both units.
- [x] Add mixed-action tests: `Потратьте 500 баллов и получите 100 баллов` and `Списывайте 500 баллов и получите 100 баллов` yield only earned 100; reversed action order retains only the affirmative amount.
- [x] Add references: `Получите 500 баллов, если у вас на счете менее 100 баллов` yields only 500; `Начисляем 500 баллов, а не 100 баллов` and `Вы получите 500 баллов вместо 100 баллов` yield only 500.
- [x] Test exact raw/evidence preservation and the real common view rows. Keep affirmative `не менее/не более/не только`, unrelated denied receipt, positive postfix and shared-list controls.
- [x] Run `python -m unittest discover -s loyalty/tests -p test_reward_action_ownership.py -v`; expected: assertions FAIL on current production code.
- [x] Implement the bounded local action classifier; remove whole-clause expense vetoes that erase positive neighbours. Keep bare literal mileage rates supported and point amounts dependent on their own earning context.
- [x] Run the focused test and existing `test_unified_points_negation.py`; expected: PASS. Run the full Python suite; expected: PASS.
- [x] Commit the repair and complete the task with the full Python suite as its gate.

### Task 2: Preserve literal amounts, bounds and exchange bases

**Files:** Modify `loyalty/normalized.py`, `loyalty/unified_normalization.py`, `loyalty/reward_context.py`; create `loyalty/tests/test_reward_amount_terms.py`.

**Interfaces:** Preserve normalized `value`, `value_min`, `qualifier`, `basis_amount`/`basis_value` and `basis_unit`. Reuse Task 1 ownership; do not reinterpret a denominator as an award.

- [x] Add tests for `Начисляем не более 500 баллов` -> upper bound 500, `Получите не менее 500 бонусов` -> lower bound 500, `Получите от 100 до 500 баллов` and `Получите 100–500 баллов` -> range 100..500. Malformed or reversed ranges must not leak a numeric suffix.
- [x] Add tests for `Начислим 500 бонусных баллов`, `Заработайте 500 баллов` and `Скидка до 51% на первый заказ + 500 баллов` with exact positive amounts. Check denied/spending/reference versions of the added wording.
- [x] Add source/common tests for `20 миль за каждые 500 баллов`: 20 miles with basis 500 points, no earned 500 points. Preserve existing RUB mileage bases and malformed-number rejection.
- [x] Run `python -m unittest discover -s loyalty/tests -p test_reward_amount_terms.py -v`; expected: FAIL before implementation.
- [x] Extend literal amount/qualifier/base recognition and retain exact evidence. Keep unsupported phrases unstructured.
- [x] Run focused and full Python suites; expected: PASS. Commit and complete the task using the full suite.

### Task 3: Keep compound benefits and denials local

**Files:** Modify `loyalty/normalized.py`, `loyalty/unified_normalization.py`, `loyalty/reward_context.py`; create `loyalty/tests/test_compound_benefit_context.py`.

**Interfaces:** `normalize_rates(..., with_spans=True)` retains original percentage indexes. `_rate_scope` and gift projection bind source context only to the owned component.

- [x] Add source/common tests for `10% (постоянной скидки)` -> exact discount 10, including the public Bionika wording. Check nearby untyped tax/payment percentages cannot borrow the label.
- [x] Add scope tests: `Скидка 10% + комплиментарная процедура на первое посещение` yields an unrestricted discount and a first-visit gift; reverse component order is equivalent. Preserve shared purchase stages across coordinated percentages.
- [x] Add denied discount/cashback/gift tests with positive neighbours. Preserve `Скидка 10% не действует на акционные товары`, `Кофе в подарок, если вы не оформляли заказ ранее`, and restrictions on cash-equivalent payment of an existing gift.
- [x] Run `python -m unittest discover -s loyalty/tests -p test_compound_benefit_context.py -v`; expected: FAIL before implementation.
- [x] Add bounded postfix labels, component ownership and explicit denial checks. Do not equate arbitrary `комплементарная` wording with a free gift.
- [x] Run focused and full Python suites; expected: PASS. Commit and complete with the full suite.

### Task 4: Keep chance-only campaigns out of ordinary offers

**Files:** Modify `loyalty/catalogue_view.py`; create `loyalty/tests/test_campaign_chance_filter.py`.

**Interfaces:** Preserve the existing reader `record_row`/catalogue interface and exclusion reason. Raw campaigns remain auditable.

- [x] Add real-entrypoint tests for the public PromoMiles wording `получите шанс стать одним из 10 обладателей 50 000 миль` and `получите шанс выиграть 50 000 миль`: both must follow the existing draw-campaign exclusion.
- [x] Preserve a campaign stating `Не упустите шанс: скидка 10% каждому участнику` and the existing explicit draw controls.
- [x] Run `python -m unittest discover -s loyalty/tests -p test_campaign_chance_filter.py -v`; expected: FAIL before implementation.
- [x] Extend the existing explicit draw-campaign recognizer without matching every occurrence of `шанс`.
- [x] Run focused and full Python suites; expected: PASS. Commit and complete with the full suite.

## Verification and continuation

- [x] Replay all 1387 public inputs through the real common pipeline, validate schemas, and inspect every delta against source text.
- [x] Repeat targeted independent adversarial probes; add a RED-to-GREEN regression for each newly reproduced in-scope defect. Record any scope ambiguity and its consequence in the ledger.
- [x] Document the resulting contracts in `loyalty/UNIFIED.md`.
- [ ] Run final full Python, KEY and required CI/browser gates. Obtain one fresh whole-branch review; fix material findings with failing tests and a green suite.
- [ ] Merge the verified branch, complete publication and read back its final receipt and native sheet manifest.
