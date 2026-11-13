# Retained formula, exclusion and local-threshold regressions

## Scope and evidence

This audit describes synthetic examples for normalizer `1.0.7`, using invented
program/partner labels. It contains no workbook rows or retained private data.
The public schema is unchanged. Replays, independent review, remote CI and
publication acceptance remain separate controller gates.

The focused module is `loyalty/tests/test_retained_production_regressions.py`.
It constructs literal `parser_offers` cells, passes them through `make_input`
and `normalize_record`, validates grounded evidence and resolves condition IDs.
Reader assertions use `benefit_claim`, `meaningful_claim`, `record_row` and
`build_catalogue`. The native row, raw source, identity and observation time are
compared with independent copies after normalization.

## Repairs

| Class | Synthetic input | Independently specified result |
| --- | --- | --- |
| Reverse monetary denominator | `За каждые потраченные 200 ₽ - 4 мили «Пример Клуб».` plus the same complete native earning rule | One complete `4 miles / 200 RUB` benefit; no denominator-free lexical duplicate. |
| Subordinate exclusion | `В программе «Орбита» скидки не распространяются на товары, на которые предоставляется скидка во время распродажи.` followed by a separate live `8%` discount | The live statement supplies the headline; the exclusion remains in conditions. Adding `13%` or `17,5%` inside the excluded-product relative clause does not create a common benefit. |
| Local minimum | `Оформите первый заказ в разделе «Дом» на сумму от 1 700 ₽. Получите скидку 28% на ваш первый заказ.` | The conditions-derived discount links to its own explicit minimum. A qualified headline with its own minimum keeps that separate local link. |
| Basket variant | `Оформите первый заказ в разделе «Техника», сложив в корзину товары на сумму от 2 300 рублей. Получите скидку 33% на ваш первый заказ.` | The intervening basket wording does not discard the `2300 RUB` threshold. |

The reverse formula matcher accepts an adjacent dash/colon in place of an
earning verb only for a monetary denominator. It uses the existing literal
number validator, bounds and denial handling. Complete structured signatures
remain intact: equal numbers alone never authorize suppression. Multiple equal
formulas additionally require a uniquely represented native channel; statement
order cannot choose the owner. Independent surviving formulas retain local
source quotations and their original clause's shared rules. The comparison
uses the owned original clause, so horizontal whitespace folding in the lexical
API cannot create an additional complete duplicate.

The shared exclusion helper identifies the relative clause attached to an
explicit excluded object. Its contents remain references even when they contain
numbers. Sentence, comma and independent sibling boundaries stop that ownership.
Both common numeric projection and reader claim selection use the same spans.
A primary numeric discount with a partial product exclusion remains a benefit.

The added minimum grammar requires an explicit purchase noun, a bounded
channel/category/basket qualifier and `на сумму от` followed by a validated RUB
amount. It cannot cross another reward, purchase, amount, negation or sibling
clause. Quoted category names may themselves contain numbers; a bounded list of
up to four quoted alternatives is one qualifier. Existing adjacent
minimum extraction and cross-field propagation rules remain unchanged. A new
standalone minimum sentence can link only to one unambiguous component with the
same explicit stage in that same field and compatible explicit channel/category
qualifiers. A condition for A alone does not constrain a benefit for A or B.
An owned prefix or closing postfix denying the requirement does not create an
affirmative minimum.
Ambiguous owners remain unlinked.

## Controls and limits

- Changed integers, decimals, `₽`/`руб.`/`рублей`/`RUB`, a narrow nonbreaking
  separator, dash variants, colon, range and upper-bound wording.
- Independent equal-valued mileage formulas with different denominators;
  native channel scope, forward ordering, denied awards, zero/malformed bases
  and an unrelated monetary statement.
- Numeric and nonnumeric positive reader siblings, reordered statements,
  quantified primary discounts with partial exclusions, and a positive clause
  after `но` without a comma.
- Different and equal purchase stages, distinct local minima, reversed
  instruction order, numbered category labels and conflicting amounts in
  different fields. A missing local minimum is not borrowed from a qualified
  headline. Delivery, mileage, wallet top-up and negative requirement statements
  cannot become the new purchase threshold.
- Existing reward, denial, catalogue and purchase-ownership suites are included
  in affected validation. Original evidence remains unchanged; numeric evidence
  continues to be validated against its source pointer.

The grammar is deliberately finite. An unfamiliar or ambiguous construction
remains source evidence requiring review. The checks do not establish coverage
of every possible future sentence, nor do they establish release acceptance.

## Initial candidate test receipts

The following receipts belong to candidate `c708327`, which the independent
review rejected for four additional ownership/polarity findings. They remain
historical execution evidence, not an acceptance verdict. The fix-round section
below records the replacement work.

All commands use `/tmp/parser-audit-nov12-venv/bin/python` and
`PYTHONPATH=loyalty:loyalty/tests` for Python tests.

| Receipt | Actual result |
| --- | --- |
| Initial focused RED, before production edits | 11 tests; exit `1`; 27 failing subcases. One harness assertion incorrectly treated app code delivery as absent; that assertion was corrected and the original receipt retained. |
| Corrected semantic RED, still before production edits | 11 tests; exit `1`; 26 failing subcases, covering all three defect classes. |
| First implementation run | 11 tests; exit `1`; 2 failing subcases exposed the nonbreaking-space quotation mismatch and the lexical API's existing space-folding contract. |
| Common numeric-reference RED | 12 tests; exit `1`; 4 failing subcases: the quotation mismatch plus three independently asserted excluded-percentage outcomes. |
| Focused GREEN | 12 tests; exit `0`; `OK`. |
| Initial affected suites | 168 tests; exit `0`; `OK`. |
| Relative-clause sibling control RED | 14 tests; exit `1`; 1 failure, an independent positive clause after `но`. |
| Threshold sibling control RED | 1 targeted test; exit `1`; 1 failure, an unrelated wallet top-up after `, а`. |
| Affected suites after boundary repairs | 170 tests; exit `0`; `OK`. |

Full gates ran once after the implementation self-review and production/test
freeze. Every frozen SHA-256 value was identical before and after both gates.
`git diff --check` also passed. The full Python log includes expected fixture
diagnostics and asyncio timing notices; its actual unittest result was `OK`.

```text
PYTHONPATH=loyalty:loyalty/tests /tmp/parser-audit-nov12-venv/bin/python -m unittest discover -s loyalty/tests -q
Ran 2597 tests in 116.025s
OK
exit: 0

node --test key/refresh.test.mjs
tests: 7
pass: 7
fail: 0
exit: 0
```

These local receipts cover the tested implementation. Independent review,
unchanged-input replays, exact-revision remote CI and publication readback have
not been performed by this implementation task.

## Fix round 1: review findings I1–I4

| Finding | Repair and synthetic control |
| --- | --- |
| I1: incompatible local qualifiers | A threshold explicitly in an app cannot constrain a separately qualified website discount. Quoted category/app/site names participate in compatibility. The benefit's explicit set must be covered by the condition's set; partial overlap is insufficient. Matching qualifiers and an unqualified local continuation remain valid. |
| I2: prefix requirement denial | `Не требуется оформлять первый заказ в приложении на сумму от 1 700 ₽` remains source evidence and creates no affirmative minimum. `Не нужно` is covered too. A separate denial about a card or another order does not cancel a live minimum. |
| I3: independent equal formulas | One native online `4 miles / 200 RUB` rule consumes only the explicitly online occurrence, including when offline comes first. The offline formula survives with its own unchanged quotation. Unqualified ambiguous native ownership cannot choose either occurrence; two separately qualified native rules can own their respective occurrences. |
| I4: quoted-name alternatives | `Оформите первый заказ в разделах «Север» или «Юг», сложив в корзину товары на сумму от 2 600 рублей — введите промокод при оформлении заказа — получите скидку 27% на ваш заказ.` retains the minimum in `/conditions`. An independent `или` action/reward remains a boundary. |

The same occurrence qualifiers also constrain retained-rule reconciliation of
denials and bounds. A denied online award cannot borrow the offline award's
positive context. The explicit `а за каждые …` sibling boundary stops denial
leakage. Reverse denominator matching starts at the nearest explicit reverse
opener, preventing a textual `RUB` in the preceding formula from being consumed
as part of the next basis.

The round-1 focused module had 23 tests. Added controls include changed decimal
numbers, narrow nonbreaking spaces, `руб.`/`RUB`, reversed channel and instruction
order, quoted names with digits, named app/site conflicts, A versus A-or-B scope,
own denials/bounds, ambiguous owners and shared nonnumeric restrictions.

| Fix-round receipt | Actual result |
| --- | --- |
| `round1-red.log`, before round-1 production edits | 21 tests; exit `1`; 18 failing subcases; all four findings reproduced. |
| `round1-focused-01.log` | 21 tests; exit `1`; 2 failures in the decimal/textual-currency reverse ratio controls. |
| `round1-affected-01.log` | 177 tests; exit `0`; `OK`. |
| `round1-red-owned-qualifiers.log` | 22 tests; exit `1`; 7 failures for named app/site conflicts and native-owned denial/bound controls. |
| `round1-affected-02.log` | 178 tests; exit `0`; `OK`. |
| `round1-focused-final.log` | 22 tests; exit `0`; `OK`, including the additional A/A-or-B controls. |
| `round1-red-shared-restriction.log` | 1 targeted test; exit `1`; the narrowed formula quotation initially lost its shared-clause restriction link. |
| `round1-affected-final.log` | 179 tests; exit `0`; `OK` after preserving original-clause rule membership. |

All prior receipts remain preserved. The expected fixture/asyncio diagnostics
noted by review as M1 are outside this parser repair; no unrelated test-harness
cleanup or blanket output suppression was added.

The fix-round full gates ran once after self-review and the production/test
freeze. All five frozen hashes matched before and after both gates;
`git diff --check` passed. Actual receipts:

```text
PYTHONPATH=loyalty:loyalty/tests /tmp/parser-audit-nov12-venv/bin/python -m unittest discover -s loyalty/tests -q
Ran 2606 tests in 108.823s
OK
exit: 0

node --test key/refresh.test.mjs
tests: 7
pass: 7
fail: 0
exit: 0
```

These results establish the local fix-round test outcome. The replacement
candidate still requires independent review, unchanged-input public/private
replays, exact-revision remote CI and publication readback by the controller.

## Fix round 2: I5 owned postfix requirement denial

I1–I4 were addressed by `740a2fd`; review identified one remaining polarity gap.
The extended-threshold guard now also checks an adjacent closing negative
predicate after the amount. It retains the prefix behavior and does not cancel
a true minimum when the subsequent negative instruction has its own argument,
such as `не требуется предъявлять карту` or `не нужно вводить промокод`.
No other production path was changed in this round.

| Synthetic source construction | Independently asserted actual result |
| --- | --- |
| `…от 1 700 ₽ не требуется. Скидка 28% на первый заказ.` | No minimum term or link; the live `28%` discount and source text remain. |
| `…от 1 700 ₽ не нужно. Скидка 28% на первый заказ.` | No minimum term or link; the live discount remains. |
| `Не требуется оформлять…от 1 700 ₽. Скидка 28%…` | Existing prefix-denial behavior remains unchanged. |
| `Оформите…от 1 700 ₽ — не требуется предъявлять карту. Скидка 28%…` | The actual `1700 RUB` minimum remains linked; the unrelated card instruction cannot cancel it. |

Three added tests preserve all 23 earlier focused tests. They cover both postfix
predicates, changed integers/decimals, narrow nonbreaking spaces,
`₽`/`руб.`/`RUB`, an intervening dash, separate and same-clause card/code
instructions, and a different denied order requirement in both statement orders.
Native rows, raw evidence, the live benefit and resolved condition IDs are
asserted through the real common-model entrypoints.

- Pre-edit semantic RED: 26 tests; exit `1`; 14 failing subcases.
- Affected GREEN: 182 tests; exit `0`; `OK`.
- The four exact behavior cases above were independently read back with literal
  assertions after the repair; every assertion passed and raw text was unchanged.

Round-2 full gates ran once on the frozen code/tests. All five before/after
hashes matched, and `git diff --check` passed.

```text
PYTHONPATH=loyalty:loyalty/tests /tmp/parser-audit-nov12-venv/bin/python -m unittest discover -s loyalty/tests -q
Ran 2609 tests in 108.830s
OK
exit: 0

node --test key/refresh.test.mjs
tests: 7
pass: 7
fail: 0
exit: 0
```

These receipts establish the I5 implementation/test outcome. Review, exact-code
unchanged-input replays, remote CI and publication readback remain controller
acceptance gates; no release acceptance is inferred from the test counts.

## Fix round 3: I5 modified requirement denial

Review confirmed the round-2 bare predicates but reproduced the same owned
negative requirement with `больше` and `уже`. Those modified forms still created
an affirmative minimum. This round reuses the existing shared modifier
vocabulary instead of maintaining a separate bare requirement expression.

`purchase_requirement_denied` in `reward_context.py` now classifies the local
prefix or closing postfix around the already recognized purchase threshold.
The shared vocabulary remains bounded to three modifiers per position and is
unchanged for its existing benefit/reward consumers. The requirement predicate
also recognizes the corresponding `требоваться` form after `будет`, perfective
`потребуется`, fused `необязательно` and short `нужен`/`обязателен` forms. A negative
instruction with its own argument, such as `больше не требуется предъявлять
карту`, cannot close the purchase phrase and therefore preserves its minimum.
Threshold extraction, qualifier ownership and cross-field linking are unchanged.

| Synthetic source construction | Independently asserted actual result |
| --- | --- |
| `…от 1 700 ₽ больше не требуется. Скидка 28% на первый заказ.` | No minimum term or link; the live `28%` discount and raw source remain. |
| `…от 1 700 ₽ уже не нужно. Скидка 28% на первый заказ.` | No minimum term or link; the live discount remains. |
| `…от 2 750,50 руб. не нужно сейчас. Скидка 12,5%…` | No minimum term or link; changed numeric formatting and the live discount survive. |
| `Не нужно сейчас оформлять…от 3.600,25 RUB. Скидка 33%…` | The same modified prefix denial creates no minimum. |
| `…от 1 700 ₽ вам больше не будет требоваться. Скидка 28%…` | The ordinary auxiliary/modifier combination creates no minimum. |
| `…от 1 700 ₽ вам больше не потребуется. Скидка 28%…` | The same future requirement denial creates no minimum. |
| `Вам сейчас необязательно оформлять…от 3.600,25 RUB. Скидка 33%…` | The fused negative predicate has the same absence-of-requirement meaning. |
| `Первый заказ…от 2 750,50 ₽ не обязателен. Скидка 12,5%…` | The short predicate creates no minimum or link. |
| `Оформите…от 1 700 ₽ — больше не требуется предъявлять карту. Скидка 28%…` | The true `1700 RUB` minimum remains linked to its local discount. |
| `Оформите…от 2 750,50 ₽ — не нужно сейчас вводить промокод. Скидка 12,5%…` | The true `2750.5 RUB` minimum remains linked. |

Six added tests preserve all 26 prior focused tests. Their literal expectations
cover the existing temporal modifiers before/after the predicate, auxiliary and
personal forms, prefix modifiers next to the purchase action, affirmative
requirements, independent card/code instructions, and a different denied order
requirement in both statement orders. The real native/common boundaries assert
source preservation, live benefits, condition terms and resolved links.

| Round-3 receipt | Actual result |
| --- | --- |
| `round3-red.log`, before production edits | 31 tests; exit `1`; 45 semantic failing subcases. |
| `round3-affected-green.log`, first implementation attempt | 187 tests; exit `1`; 9 failures for the `требоваться` form, all retained despite the initial filename. |
| `round3-affected-final.log`, after completing the same predicate family | 187 tests in 2.043s; exit `0`; `OK`. |
| `round3-actual-behavior.json` | Seven independently asserted actual source/benefit/minimum cases passed; raw source remained unchanged. |
| `round3-red-predicate-family.log`, before extending the remaining same-family forms | 32 tests; exit `1`; 23 semantic failing subcases for `не потребуется`, fused and short predicates. |
| `round3-affected-predicate-final.log`, final affected gate | 188 tests in 2.110s; exit `0`; `OK`. |
| `round3-actual-final.json` | Fourteen actual-output cases passed, including the initial modified forms, added predicate-family forms, affirmative counterparts and unrelated instructions; raw source remained unchanged. |

The full gates each ran once on the final frozen code/tests. All five hashes
matched before and after both gates; `git diff --check` passed. No code/test edit
or blind retry occurred during the frozen gates.

```text
PYTHONPATH=loyalty:loyalty/tests /tmp/parser-audit-nov12-venv/bin/python -m unittest discover -s loyalty/tests -q
Ran 2615 tests in 113.316s
OK
exit: 0

node --test key/refresh.test.mjs
tests: 7
pass: 7
fail: 0
exit: 0
```

M1's expected fixture/asyncio diagnostics remain visible; no unrelated harness
cleanup or suppression was added. These receipts establish the local repair
outcome. Independent review, exact-code unchanged-input replays, remote CI and
production readback remain controller gates.


## Controller implementation acceptance

Independent cumulative review accepted the complete follow-up from production
base `2dc70b9d7da43220b4bed1c14de95128a7e3d4d1` through code commit
`b8bd3dd885062a1afe00bb38d16d2ffc542b2ba4`, tree
`81af145196e3175c40838a2d822f6f220360a3d3`. Findings I1–I5 are closed; no
Critical/Important implementation finding remains. The original requirement
matrix, all fourteen actual-output cases and all failed/intermediate/final
receipts were assessed explicitly. M1 remains a nonblocking test-output
reliability/clarity observation; it was not suppressed or silently discarded.

The controller independently read the final local gates and verified the five
production/test hashes against the frozen and committed files: 2,615 Python
tests and seven Node tests passed without an unchanged-code retry.

The exact-code public replay passed on both unchanged corpora: 1,620 normalized
records and 1,416 reader rows, including the complete normalized, catalogue and
identity payloads, are byte-identical to both reviewed R1 and R2 outputs. All
previously assessed baseline-relative changes remain valid. Original inputs,
reference outputs, raw/source values, identities, provenance and observation
times were preserved; the replay verified all 109 top-level loyalty Python
blobs against the accepted commit.

A separate private complete-input replay also passed on the original frozen
snapshots. Complete deterministic payload equality to both reviewed references
preserves every original failure closure, accepted correction and previously
assessed source-update effect. The controller read the full private assessment
and final checksum/clean-code receipt. No private rows, identifiers, coupons,
fingerprints or detailed comparison artifacts are included here.

This acceptance covers implementation and retained-input verification. The
remaining release gates are exact-revision remote CI before integration, fresh
source outcomes, and native readback after the last material publisher. Their
actual execution receipts belong in the follow-up PR. A documentation-only
acceptance successor does not change any tested production or test blob.
