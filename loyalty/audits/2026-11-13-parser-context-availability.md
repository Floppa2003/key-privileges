# Component context, cancellation and retained availability

## Scope

Normalizer `1.0.8` repairs eight reproducible classes of deterministic parsing
errors. Source adapter version `2.9.6`, public/common schemas and the practical
catalogue format remain unchanged. Examples below are synthetic; this document
contains no workbook rows, private coupons or record identifiers.

| Class | Synthetic example | Required result |
| --- | --- | --- |
| Cancelled benefit | `Скидка 16% отменена. Скидка 9% действует на меню.` | Only the live 9% component supplies a benefit and reader headline. The original cancellation remains source evidence. |
| Replaced coupon | `Промокод OLD10 отменён и заменён на промокод NEW10.` | Retain NEW10 only. Explicit causal/parenthetical cancellation and replacement instructions have the same ownership rule. |
| Source availability | Source status `cancelled`/`finished` or the owned boolean `enabled=False`, with a future date | Exclude the record from the practical catalogue. Unknown statuses and nonboolean lookalikes do not imply disabling. |
| Date purpose | `Зарегистрируйтесь до 20.12.2026` alongside an explicit offer period | The registration condition does not expire the offer. Recompute retained Konsierge validity from its verified original item. |
| Monetary cap | `Скидка 21% онлайн (максимальная скидка 650 ₽), скидка 12% офлайн (максимальная скидка 430 ₽).` | Each discount links only to its own limit. A plain coordinated list with one shared limit keeps that limit shared. |
| Denied minimum | `Первый заказ от 2700 ₽ не требуется.` | No affirmative minimum term or benefit link, at either the source lexical or common-model boundary. |
| Wrapped conditional | `Если заказ отменён,\nпромокод NEW10 аннулирован.` | The condition is not unconditional cancellation. A native audience quotation retains the original antecedent and audience. |
| Coupon stage | Separate first-order and repeat-order coupon occurrences | Each literal receives its own stage, including two occurrences of the same literal with different stages. |

## Implementation boundaries

- Shared reward polarity distinguishes inherently negative predicates from
  their negation. Partial product exclusions and independent positive siblings
  remain valid. Purchase minima reuse the existing requirement-denial helper.
- Coupon context retains a wrapped conditional antecedent, while completed
  sentences, empty paragraphs, coupon instructions and independent sibling
  lines stop ownership. Specialized source labels keep their existing guards.
- Purchase-stage ownership is shared by benefit and coupon occurrences. A
  plural quoted coupon list is one component. Native audience/table ownership
  takes precedence over an unscoped lexical alias.
- Parenthesized labelled caps are boundaries within their owning benefit,
  rather than separate discounts. Existing plain-list and standalone-cap
  semantics remain intact.
- Konsierge customer expiry requires an explicitly named offer period or the
  record's principal benefit. Registration, booking, payment and an extra
  component's date stay conditions. Historical compatibility accepts only the
  reproducible former date projection and the original item's verified hash.
  Corrected validity and warnings belong to normalized fields; `raw` is intact.

## Tests and controls

New end-to-end modules:

- `test_parser_context_ownership.py`
- `test_promo_context_continuations.py`
- `test_source_availability_dates.py`

They exercise source adapters, publication preparation, retained cells, common
normalization and the practical reader. Assertions compare literal expected
benefits, code scopes, resolved condition IDs, availability, periods, source
identity, observation time and preserved raw input. Controls include changed
integers/decimals, currency spellings and whitespace, statement order, equal
values with different owners, partial exclusions, negated cancellation,
unrelated negative instructions and conditional neighboring coupons.

The source API's existing horizontal whitespace folding was accounted for in
the test harness before implementation; retained raw is compared with the
actual adapter snapshot, not a differently spaced test input.

| Pre-repair receipt | Reproduced semantic failures |
| --- | ---: |
| Corrected ownership/minimum/cap/stage RED | 52 |
| Coupon continuation RED | 34 |
| Retained specialized coupon projectors RED | 5 |
| Native audience conditional RED | 2 |
| Source availability RED | 4 |
| Date-purpose and historical reprojection RED | 19 |
| Additional component-date ownership RED | 3 |

The focused combined ownership/coupon/cap gate passed 118 tests. The separate
coupon and source-date affected gates passed 171 and 221 tests respectively.
These are overlapping checks, not additive totals.

## Independent review corrections

The first candidate passed all 2,661 Python and seven Node tests, but independent
review rejected it for additional context cases. Those test results remain
execution evidence, not acceptance of that candidate.

| Finding | Correction / independently specified control |
| --- | --- |
| Repeated activation text | An unqualified repeat of a first-order coupon cannot create an unrestricted alias. Both direct text and retained native arrays are checked. |
| Excluded purchase stage | `Промокод FIRST16 не действует на первый заказ` keeps the code without inventing first-order applicability. |
| Conditional benefit cancellation | An `если`/`при`/`после` antecedent keeps its conditional component. A complete neighboring benefit cannot lend that antecedent to a separately cancelled benefit. |
| Plural benefit cancellation | Shared `аннулированы`/`недоступны`/`отменены` applies to the entire plain mixed list. The same list under a conditional antecedent remains conditional. |
| Completed coupon main clause | A preceding coupon's complete affirmative statement closes its conditional scope at an independent next line. An open `Если промокод … действует` antecedent remains open. |
| Reconciled native spelling | Removing an instruction tail from an old native value must also retain the corrected literal's stage. |
| Scoped expiry suffix | A date followed by a specific service/audience cannot expire a record-wide offer, including equal-valued live siblings. |
| Opaque coupon literal | `REPEAT16`, `FIRST ORDER` and `REPEAT CUSTOMER` are literal values; words inside them never establish a purchase stage. |

The root review cases reproduced 21 semantic failures before repair. A shared
conditional mixed-list control reproduced three further failures. Their affected
gates passed 181 and 76 tests, respectively. The completed-coupon main-clause
cases reproduced 15 failures and then passed an affected gate of 122 tests.

Follow-up review closed two boundaries of conditional benefit ownership: an
earlier benefit's trailing condition cannot rescue a cancelled sibling, and
one genuine line wrap cannot destroy an open antecedent. Offset-preserving
context masking joins only an open antecedent immediately before its benefit;
the original evidence keeps the newline. Empty paragraphs and completed
statements remain boundaries. The full-input replay also found a coupon in a
roundup borrowing a stage from a later offer. Single-coupon fallback now reads
only the immediately preceding sentence, not the entire field. These controls
first reproduced seven failures; the integrated affected gate passed 207 tests.

The scoped date-suffix controls reproduced five failures. Their final affected
gate passed 224 tests, including retained-row repair and genuine global expiry.

## Fixed-input replay correction

The complete real-input replay rejected one further side effect: conditional
eligibility wording ending in `не предоставляется` had become an affirmative
discount. The conditional preservation rule now applies only to inherently
negative cancellation/availability predicates; negated provision retains the
existing exclusion behavior. The same replay found two headings absorbed into
preceding instructions. A line is now joined only when its own text contains
the cancellation continuation, not merely a discount heading.

Four corrected synthetic failures reproduced these cases before the production
edit; the affected gate then passed **209 tests**. Source rows and detailed
comparison evidence remain private.

## Validation before the final replay correction

Frozen implementation `ea9cd020592a80f55208767afd145071949f570d` passed the
complete Python suite: **2,675 tests in 132.762 seconds**, exit 0, `OK`.
All **seven Node tests** passed. Production/test files were unchanged throughout
these gates and compared against the frozen commit afterward.

Independent review repeated the same 27 coupon/benefit closure checks and the
two original scoped-date cases: **29 passed, zero failed**. All reported
implementation findings were accepted before the additional real-input
correction described above. This is bounded semantic review, not a
claim that every possible future wording is supported.

Remote CI and final publication readback are separate release gates; their
actual commit/workflow receipts belong in the pull request. Local tests alone
do not establish deployment.

## Final implementation and retained-input acceptance

Accepted frozen local implementation:
`e3b0858fa3b5a517700087966895127b07991740`.

- Complete Python gate: **2,677 tests in 139.184 seconds**, exit 0, `OK`.
- Node gate: **seven passed, zero failed**.
- Independent final-diff gate: **41 tests passed**, with direct readback of the
  cancelled sibling, wrapped antecedent and eligibility-exclusion cases.
- Production/test files stayed unchanged during these gates. The documentation
  acceptance successor does not change any tested production or test blob.

The baseline was independently reconstructed from all five supported source
datasets and matched the live publication before the repair. Two complete
native reads established a stable frozen input. The accepted implementation
then processed all **4,311 records** from that same input.

Every substantive difference was assessed against its own source: **10 records,
11 coupon terms**, each changing only its justified purchase stage. The prior
roundup borrowing error is corrected. All three rejected replay side effects
are byte-equivalent to baseline again. The other **4,301 records** differ only
in version-derived technical fields. Entire raw inputs, source identities,
provenance, observation times, evidence pointers and condition references pass
the invariant checks.

The full practical reader output is byte-equivalent to baseline: **3,350 rows,
961 exclusions**. All 72 baseline artifact hashes and candidate code/output
hashes were verified before sealing the private acceptance evidence. No private
rows, identifiers, coupon values, fingerprints or detailed diffs are published.
This acceptance is limited to the tested code and frozen inputs. Release CI and
post-publication verification remain independent gates recorded in the PR.

## Limits

The grammar remains finite. Unrecognized or ambiguous prose retains its source
evidence for review. These checks establish the listed defects and controls,
not correctness for every future natural-language construction. Explicit source
availability is authoritative only for its own source record; no personal
eligibility or live availability is inferred. A retained source-level Konsierge
JSON bundle must be regenerated from its original capture before adapter
validation; historical spreadsheet rows use the compatible common projection.
