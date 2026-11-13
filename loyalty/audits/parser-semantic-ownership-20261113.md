# Parser semantic ownership repair — implementation audit

Assessment date: 2026-11-13. Normalizer version: `1.0.6`; public normalized schema remains version 1.

This document records deterministic implementation, independent task-review and immutable-public-corpus evidence. It is not a live production-status indicator or a certification of current merchant availability. Final whole-branch review, revision-specific CI and publication/readback receipts belong to the associated release pull request and GitHub Actions runs. No native workbook identifiers or exported data are included here.

## Implemented surface

The branch repairs modified benefit denials and product exclusions, source-owned mileage bounds, cancelled/malformed coupons, and monetary condition ownership. This task changes only `unified_normalization.py`, adds purchase-condition regression tests and this audit; accepted earlier tasks are retained.

Monetary minima now use the existing literal component anchors and original sentence boundaries. The same numeric value can occur in different first/repeat branches without collapsing their scope. Explicit separators associate local minima and monetary caps with local benefits through existing `condition_ids`. Plain coordinated rate lists and explicit shared purchase prefixes retain shared minima. Shared non-numeric conditions keep their existing linkage. Decimal punctuation and the sentence-ending period of `руб.` are preserved.

Purchase upper limits use existing `maximum_amount_reference`, not a reward cap. Local purchase/payment owners take precedence over unrelated reward text. Explicit discount/cashback limits and compensation remain reward-owned, including when an order or receipt names their basis. Independent payment, prepayment and fee references remain unlinked to rewards. No required schema fields, money-token grammar, source text, raw identities or observation timestamps are changed.

## TDD and integration evidence

- Initial tests ran against the accepted parent before production edits: 9 test methods, 15 failing subtests. Actual `normalize_record` output linked both first/repeat minima to both benefits, collapsed equal minima under `multiple_stages`, misclassified purchase maxima as reward caps and treated compensation as a payment limit. The real source → publication preparation → common normalization → reader path reproduced minimum cross-linking.
- A second RED with corrected abbreviation punctuation reproduced the same 15 semantic failures before implementation.
- A focused intermediate run exposed two abbreviation-boundary failures; the monetary occurrence window now handles a currency token whose final period also ends the sentence.
- Added sibling-maxima controls produced 3 failing subtests before their fix. A shared purchase-prefix control separately failed before preservation was added.
- Final focused run: 70 tests passed, including 14 new test methods and existing money-cap, follow-up-review, purchase-stage and compound-benefit suites. Assertions compare each benefit's complete linked numeric condition values, not mere occurrence of those values in the record.
- Full Python and Node gate receipts are appended after completion. No production/test changes are permitted during that gate.

## Public evidence boundaries

The implementation was informed by a read-only selection of 12 public records / 17 clause blocks, with exact source text, analyst interpretation and observed baseline separated. Business amounts in tests are fixture data, never parser constants.

- VTB restaurant compensation per receipt is a reward limit, whereas its transaction-size bound concerns eligible spending. The selected baseline did not type either amount; this repair does not claim to newly parse every `до` phrase.
- X5 monthly aggregate purchases remain within their full owned programme rule container. They are not converted into a per-order reward cap.
- HSE ordered first/repeat instructions already reside in a full owned partner rule container. Its baseline had no separate numeric minima/cap; preserving that container is different from approving cross-linked numeric conditions. Source/prepare/common compatibility tests confirm no numeric terms are invented there.
- Aeroflot receipt tiers retain their source-owned evidence. Missing typed tier detail is not reconstructed from matching numbers. EX bags' overlapping bracket endpoint remains source ambiguity.

## Открытия, нюансы и допущения

Ownership uses a finite grammar, not unrestricted prose understanding. When no local benefit anchors or explicit component separator exist, existing explicit-scope linkage is retained; uncertain cross-sentence business facts are not invented. Monetary references remain conservative references rather than proof of eligibility. Source-owned projectors and rich rule containers retain their existing contracts.

The complete suite can emit known fixture JSON and asyncio diagnostics; only actual assertion/error receipts determine pass/fail. Immutable corpus review and release checks remain necessary, particularly for effects on historical records outside the literal regression matrix. No private workbook exports, identifiers, credentials or browser data are included here.

## Frozen full gate receipts

After the final production/test edits, both commands completed once with exit 0:

```
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=loyalty:loyalty/tests /tmp/parser-audit-nov12-venv/bin/python -m unittest discover -s loyalty/tests -q
Ran 2568 tests in 117.747s
OK

node --test key/refresh.test.mjs
7 tests; 7 pass; 0 fail; duration 214.021288 ms
```

Production/test file hashes matched before and after the gate; `git diff --check` passed. Known fixture JSON and asyncio timing diagnostics appeared, with no assertion failures or runtime warnings. These local results do not replace independent review, corpus replay, CI or production readback.

## Review correction — round 1

The independent scoped review found that an explicit cashback limit with the basis “за одну покупку” became an unlinked purchase maximum. The independent replay of the provisional candidate also found that a minimum in a repeated activation discount no longer constrained its matching headline discount. Both findings required changes despite the original green suites and unchanged reader rows.

Explicit reward owners now survive singular/count purchase-basis modifiers; an explicit spending phrase such as “при сумме заказа” still takes precedence. Cross-field minimum linkage is restored only for a uniquely restated offer with the same full semantic signature and explicit scope, a single constrained source representation, and one original occurrence per field. This applies across benefit, activation and conditions fields. A finite plain rate/stage/minimum statement is required at the originating occurrence; unmodelled product/channel qualifiers, competing minima and ambiguous duplicate components are not assigned new cross-field ownership. Gifts, miles, payments and different rates/stages remain separate.

Round-1 TDD: 19 tests initially produced 10 failing subtests covering both review findings and activation/conditions mirrors. Two additional self-review regressions failed before their fixes: conflicting source minima and borrowing a plain sibling statement to authorize a product-specific minimum. Final focused run passed 77 tests. The exact frozen public Flowwow record was also normalized alone: both 17% discount representations link only the 1500 RUB minimum, while miles/gift do not; raw identity/text/timestamp, condition array and reader row are unchanged. This targeted check is not a replacement for the controller's updated full immutable-corpus replay.

At this implementation checkpoint, the earlier gate results belonged to the previous candidate. The corrected candidate therefore required new frozen gates and an updated independent review and replay; unchanged reader rows were not accepted as proof of structured correctness.

Corrected round-1 frozen gate, first execution: Python `Ran 2575 tests in 118.028s`, `OK`, exit 0; Node 7/7 passed, 237.17249 ms, exit 0. Production/test hashes matched before/after and `git diff --check` passed. Known fixture JSON/async timing output remains deferred test-harness noise; there were no assertion failures. No implementation/test edits occurred during this gate. These receipts were followed by the independent task acceptance and full replay below.

## Complete implementation acceptance

All four implementation tasks passed independent specification and quality review. The historical four-task implementation checkpoint is `2b14b5c3fa734fc223253c581b96c46ea3eb554d`; its normalizer is `1.0.6`. Release preparation incorporated the unrelated automatic KEY data refresh from main. The replay below belongs to that checkpoint; the later combined whole-branch repair is recorded separately below.

| Required outcome | Verification boundary | Regression module |
| --- | --- | --- |
| Modified denial cannot become a usable benefit | Shared parser, source/publication/common projection and reader; live gifts/delivery and independent siblings remain valid | `test_semantic_denial_reader.py`, `test_source_mileage_semantics.py` |
| Mileage retains upper/range bounds and complete denominator evidence | Actual known-rule sources and retained structured fields, including changed values, branded units and channel scopes | `test_source_mileage_semantics.py` |
| Cancelled coupons stay cancelled | Fresh generic/HSE sources, retained source projectors, scoped audience/table occurrences and reader | `test_coupon_semantic_boundaries.py` |
| First/repeat minima belong to their own benefits | Exact linked-condition matrices across separators, equal/changed values, decimals and abbreviations; repeated-field constraints and ambiguity controls | `test_purchase_condition_ownership.py` |
| Purchase maxima, reward caps and payments retain their owners | Actual normalizer; explicit singular/count reward bases, compensation, fees, shared/sibling limits | `test_purchase_condition_ownership.py` |
| Product exclusions preserve an otherwise live offer | Actual reader with the exclusion in benefit or conditions; complete closure controls | `test_semantic_denial_reader.py` |
| Uppercase instructions cannot extend unquoted codes | Fresh and retained code paths; quoted literals and actual multiword-code controls | `test_coupon_semantic_boundaries.py` |

Test expectations are literal and independent of production helper outputs. Source/raw identity and timestamps are asserted through real boundaries. Source-specific HSE label patterns and Konsierge validation remain explicit source contracts, with a fabricated-code rejection control; these repairs add no coupon-literal, record-ID or business-amount exceptions.

### Test-harness observation retained

One intermediate Task 3 full run executed 2,548 tests and failed the 50 ms deadline fixture's `cancelled.is_set()` assertion. The unchanged isolated test passed, followed by one explicitly authorized unchanged-hash full retry that passed all 2,548 tests. Later Task 3 and final Task 4 frozen gates passed on their first execution. Inspection supports a scheduling/admission timing explanation, but does not establish a failure on the old baseline. No runtime behavior or test assertion was changed or suppressed. The failed execution, successful retry and noisy fixture diagnostics remain review observations, separate from parser semantic acceptance.

## Immutable public replay and independent assessment

Baseline: `23c5e7da30c1f96c6a9d700c948836587e8f28df`, normalizer `1.0.5`. Treatment: `2b14b5c3fa734fc223253c581b96c46ea3eb554d`, normalizer `1.0.6`. Both use assessment date `2026-11-13` and the same inputs serialized once by the baseline. No practical-scope filtering, cross-artifact deduplication, treatment-side input regeneration or baseline refreeze was used.

| Public artifact | Records | Version/hash only | Semantic changes | Unchanged reader rows | Changed / added / removed reader rows |
| --- | ---: | ---: | ---: | ---: | --- |
| [Loyalty run 43231214298](https://github.com/Floppa2003/key-privileges/actions/runs/43231214298) | 1,382 | 1,380 | 2 | 1,179 | 0 / 0 / 0 |
| [Aeroflot run 43265384786](https://github.com/Floppa2003/key-privileges/actions/runs/43265384786) | 238 | 238 | 0 | 237 | 0 / 0 / 0 |

Every actual semantic change was reviewed against complete retained source evidence:

- **Tripster:** the lexical formula gains the explicitly stated `100 RUB` basis for `3 miles`. Its source-owned structured formula already held this basis. Values, qualifiers, scopes and condition links remain unchanged.
- **i’way:** source-owned earning terms retain their original `direct` and `travel_agent` channel scopes, with the respective `50 RUB` and `90 RUB` bases. These channels already existed in the raw earning-rule containers; no rate or payment interpretation was invented.
- **Flowwow regression check:** all benefits and conditions now exactly match baseline, including the minimum-purchase reference on both descriptions of the first-order discount. It is classified as version/hash only.

All 1,618 metadata-only records were individually checked for differences restricted to normalizer version and content hash. Across all 1,620 records, raw inputs, record IDs, complete provenance/observation timestamps, validity, availability, quality, relationships and complete condition/cost/code arrays remain equal. Both complete reader catalogue files are byte-identical to baseline, including removed rows/reasons and counts. Every frozen input and original artifact hash was rechecked after processing.

| Fingerprint | Loyalty | Aeroflot |
| --- | --- | --- |
| Original public artifact JSON SHA256 | `80c40b7ab189b62e00ff7fd43e83597a23ab39534f189a23d3b0bb57edb877d1` | `802722b40a3ff1d04bfe162c1027d0b66adfd2200f026a4627d9ce033971498f` |
| Canonical mapped-input snapshot SHA256 | `19469c88d78aa1d7386d5a1fc15407232fe2bd85ffe3a9b89f1921db466dc7a3` | `42bd8b043ddad7618bef2e6431c96174d604d07611bcb134eb406e4ff5ed3867` |
| Identical baseline/treatment reader SHA256 | `f2854c8ed6ccbf5689190d00666a4a091a5cc5f4bbd786f3b70fa6be77e6d18f` | `81f0d90755565c7e08015c6e30ca82581abfcd7d74dfe6f165d210ca135bedd0` |

This is a full replay of retained public normalization and reader inputs observed on 2026-11-12, not a fresh website collection or a complete adapter replay. Most saved records lack original full HTML. In particular, the corpus does not contain an observed public whole-code cancellation transition; synthetic real-entrypoint regressions supply that coverage. Successful replay does not prove arbitrary future prose or replace final CI and destination readback.

## Release scope

The existing request bridge refreshes `utair_generations_rules`, `af_bootwood_rules`, `af_wolford_rules`, `af_iway_rules`, `af_skyshop_rules`, `af_tripster_rules`, `af_comfort_rules`, `af_vipzal_rules` and `hse_alumni`, then applies version `1.0.6` to retained inputs using the existing serialized publication workflow. The release changes no providers, LLM behavior, schedules, authentication, access controls or dependencies. Source access failures must retain their actual status. Completion requires final-revision CI and native publication/readback receipts after the last material publisher.

## Combined whole-branch repair after final review

The independent whole-branch review of `32c8ae2d485e234d8ed228b4dc55c05ae6e56539` found two remaining supported-grammar gaps: whole-offer closure with `сейчас`/`пока`, and cancellation of the already-supported quoted plural coupon list. Earlier task acceptances and replay results did not waive these failures.

The anchored complete-offer predicate now recognizes the existing temporal modifier set (`уже`, `больше`, `временно`, `сейчас`, `пока`). Product/calendar exclusions retain their statement continuation, and a denied benefit component cannot close an independent live sibling.

Coupon extraction and retained reconciliation share a bounded occurrence map for the existing licensed quoted list. The terminal predicate applies to every mapped member; plural cancellation predicates and explicit negative instructions remove the cancelled occurrences. Each literal retains its own spelling and source evidence boundary. Independently live occurrences of the same value, quoted multiword literals, conditional/product/calendar restrictions, and independent table/audience evidence remain preserved.

A concrete source-path dependency required the existing HSE fallback to consume the same mapping: after generic extraction removed both cancelled list members, the fallback restored the first. This narrow caller correction follows the existing HSE source-contract scope. Only canonical `Промокоды` with its existing whitespace/delimiter form licenses plural continuation; generic code-word extraction is unchanged. Production changes are limited to `catalogue_clauses.py`, `promo_codes.py` and `hse_alumni.py`; regression additions are in the existing denial-reader and coupon-boundary modules. Version remains `1.0.6`; the source-refresh request and unrelated KEY data are unchanged.

TDD receipts: before production edits, the two affected modules ran 66 tests with 30 failing subtests reproducing closure and fresh/common/retained coupon leakage. Before the HSE caller edit, a focused three-test run produced 27 failing HSE subtests across source, common and retained-reader boundaries; the independent table/audience and quoted-multiword controls passed. After the repair, 234 affected regression/compatibility tests passed in 8.606 seconds. Expectations are literal outputs through real source → publication preparation → common normalization → reader paths, with raw/source identity and observation evidence retained.

Frozen combined-repair gates, first execution: Python `Ran 2583 tests in 114.151s`, `OK`, exit 0; Node 7/7 passed, 237.034994 ms, exit 0. The three production and two test file hashes matched before and after; `git diff --check` passed. No production/test edits occurred during the gates. Expected fixture JSON/async diagnostics appeared, with no assertion failures. These receipts certify the repaired working tree, whose exact commit and replay are recorded by the subsequent release evidence.

At this implementation checkpoint, the repair required a new exact-commit replay and final repair review. The corpus lacks the new closure/cancelled-list cases and cannot certify those behaviors; their literal real-entrypoint regressions provide that evidence. The earlier 50 ms deadline-fixture assertion failure and its single authorized unchanged-hash retry remain recorded above; no runtime or test-harness behavior was changed.

## Final exact-code replay

The combined repair was committed as `6a27f957827a7de98478314d62f9e199f0e81fbc`. A fresh full replay used this exact clean commit, the unchanged baseline `23c5e7da30c1f96c6a9d700c948836587e8f28df`, the same frozen input bytes and assessment date `2026-11-13`. The complete normalization and catalogue output files for both corpora, and their complete baseline-relative detailed record comparisons, are byte-identical to the independently reviewed four-task checkpoint above. This exact equality permits reuse of the two source-grounded semantic assessments; it is not an inference from equal counts.

The final comparison therefore contains 1,618 version/hash-only records and the same two intended Tripster/i’way semantic improvements, with all 1,416 reader rows unchanged. Flowwow's complete benefits, conditions and links remain equal to baseline. The fresh run independently checked all 1,620 raw records, stable IDs, source IDs, complete provenance/observation timestamps, input nonmutation, frozen/original file hashes and sizes, output JSON readback and exact clean commit identity. Both reader change files are empty; complete catalogues also equal baseline bytes.

| Final normalized output | SHA256 |
| --- | --- |
| Loyalty | `ce16a059a7fa6fd9dc42158d609283c23555541b5542a1c900c3c4d084a2dde6` |
| Aeroflot | `77b560aa4640edafa8e7f89df24b90d23ec5c07a892de592d0fac693134e29a7` |

The final local gate for this parser/test tree is **2,583 Python tests and 7 Node tests passed**, first execution. Subsequent audit-only commits preserve that tested and replayed tree. The scoped final re-review, exact final remote CI, affected-source refresh and native readback after the last material publisher remain release gates; their live status is recorded in the associated pull request and workflow runs. Neither immutable replay nor the local gate alone certifies production adoption.
