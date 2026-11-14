# Deterministic parser completion audit — 14 November 2026

This change repairs confirmed extraction and ownership defects in the retained
4,344-record source corpus. It changes deterministic source/common parsing only.
The common schema, retained raw inputs, source identities, original observation
times, LLM processing, credentials and publication workflow remain unchanged.

The audit baseline is `e839bf076e9af365a09faf8e70ea24b97d1295d7`.
The retained input SHA-256 is
`5e527b13065c135aff67642201b1d303339218b1879aeb3d7e1cf9187c6a8a17`;
the evaluation date is 2026-11-14. The input consists of 3,696 collected records,
495 curated records, 96 Yandex records, 45 community records and 12 inbox records.
Private exports and detailed per-record review ledgers are deliberately excluded
from the public repository. Public regressions contain retained public source
objects or minimal actual source excerpts; private provenance and personal codes
are excluded. No new regression source wording was invented.

## Original findings

| Finding | Implemented behavior | Regression evidence |
| --- | --- | --- |
| Otello/Utair 3,000/2,000-mile limits treated as awards | Keep 10%/8% earning rates and attach the per-order ceiling to its own status group | `test_observed_reward_completion.py` |
| Utair 1 mile = 1 ruble redemption treated as earning | Preserve the redemption statement without inventing a mileage award | `test_observed_reward_completion.py` |
| Vkusomania exchange minimum treated as an award | Keep the 1,200-point/100-mile minimum as exchange evidence | `test_observed_reward_completion.py` |
| HSE first/repeat discounts lose ownership | Preserve DROP20 first/later stages; collapse repeated Много Лосося instructions into two offers with their own codes and rule sections | `test_hse_native_purchase_stages.py`, `test_observed_hse_full_block_instructions.py` |
| Coral AURA gifted 150,000 bonuses omitted | Type the literal point award with its qualifier and source evidence | `test_observed_reward_completion.py` |
| Coral calendar range using «до» omitted | Carry both actual calendar bounds into source and retained-input normalization | `test_observed_campaign_periods.py` |
| Magnit/T2 range with Latin `c` omitted | Recognize the actual date separator without confusing observation and offer dates | `test_observed_campaign_periods.py` |

## Additional repairs found in the full corpus

The review continued beyond the initial findings. Positive rewards, spending,
conversion references, worked examples, purchase minima and reward ceilings are
classified separately. Decimal quantities, ranges, units and literal denominators
are preserved. A bare dollar is not silently assigned a country currency.
Night/month/year/package denominators remain attached to their own awards.

Native source projections now retain omitted benefits from Gorod, X5, Magnit,
Mantera, Avolta, Backit, Konsierge and Tsvetnoy. Complete native objects are tested
alongside the common projection. Coupon discounts stay separate from cashback;
native prices and exchange costs do not become earned rewards. Declared legacy
privilege packages retain their own explicit discounts and named membership tiers.

First/repeat stages and audiences are local to their benefit component. Qlean's
first, second and subsequent cleaning discounts stay distinct. Bereg adult and
child offers keep their own first-service restrictions. MEZZO's second/third
renewal discount does not become an unlimited repeat discount. A trial offer does
not inherit a sibling's first/repeat scope. Full HSE blocks preserve activation
instructions, minimum orders and limits with the corresponding promo code.

Caps in the same reward clause remain linked despite abbreviations such as
«макс.». Other merchants' limits cannot cross that boundary. Explicit cashback
refund wording and fixed cash rewards are retained; qualifying tour spend and
aggregate campaign funds remain separate. The conditional Finpodushka top-up
bonus keeps its literal ruble denomination, top-up requirement and personal demo
deadline; it is not labelled withdrawable cash. The virtual demo balance is not
an award. An explicitly typed closed list of
welcome bonuses can share its stated final point unit without converting its
total ceiling into a guaranteed award.

Dates distinguish campaign intervals, participation periods, offer availability,
code validity, reward lifetime, membership duration and observation dates.
Conflicting native dates are exposed as conflicts. An expired acquisition phase
does not invent the customer's remaining service period. Draws and unavailable
offers retain evidence without being presented as guaranteed ordinary offers.

## Coverage and review method

Every domain began with the full retained input, followed by an explicit candidate
inventory and source-level disposition. Counts below overlap and must not be
added or described as an error rate.

| Review | Coverage |
| --- | --- |
| Whole input replay | 4,344 input/output records; exact raw/provenance/ID preservation |
| Nominal reward roles | 949 literal occurrences, individually dispositioned |
| Missing percentage candidates | 99 records; reward and discount ownership reviewed separately |
| Redemption candidates | 101 records; native source restrictions checked |
| Literal monetary reward screen | 224 occurrences in 120 records; cashback, caps, balances and bonus credits reviewed separately |
| Orphan reward ceilings | 87 terms; 7 linkage defects and 4 missing owning benefits repaired; 76 legitimate record/channel limits retained |
| Promo literals and delivery | 145 initial candidates; 155 delivery groups and 1,017 source occurrences reviewed |
| Purchase requirements and ownership | 136 prior candidates; 457 additional mentions in 198 records |
| Calendar/native lifecycle fields | 4,344 record bounds and 773 applicable native field groups checked |
| Gorod | All 221 native records: 133 partners and 88 coupons; 1,694 tier-award values, 3 redemption fields, 38 coupon cashback fields |
| HSE | All 58 retained blocks/observations; source/common parity checked |
| Avolta | All 20 retained native objects |
| Mantera | All 19 retained native records, including source exclusions for other hotels |
| X5 and Magnit | All 71 native objects, with literal cost/benefit direction preserved |

Actual source regressions were observed failing before the corresponding repair
and passing afterward. Full input replays compare every semantic term group and
reader row, preserve raw/provenance exactly, and bind outputs to code and input
hashes. An independent reviewer checks concrete residual findings and closure
receipts. Passing tests alone is not treated as proof of semantic completeness.

## Representation boundaries

The closure claim concerns confirmed defects in this input snapshot and the
documented parsing contract. It is not a claim that all future source wording,
personal eligibility or every sentence of the source has been understood.

- All terms still require contextual review, and
  `semantic_completeness=not_certified` remains in the unchanged schema.
- The 76 reviewed record/global/channel ceilings without explicit per-benefit
  ownership remain typed parent conditions plus complete raw rules. The parser
  does not guess an owner across unrelated fields.
- Native service packages and game/social currencies keep their literal partner
  privilege and spend-cost evidence. They are not coerced into money or points.
- Three native exchange menus each have five exactly equivalent ratios. All 15
  options were independently checked with exact fractions. One canonical ratio
  is typed; complete choices, minima and increments remain in raw.
- Eight ticket redemption-price mentions, twelve supplementary document/inbox/
  catalogue-preview mentions, one noncash bonus-ruble conversion reference and
  three native point/cash reference occurrences remain source evidence. This
  release does not claim a complete typed ticket-cost or conversion model.
- General Mantera redemption wording does not override the source's explicit
  restriction to its named hotels. Unconfirmed hotels do not gain a redemption
  benefit by inference.
- Existing full-rule preservation does not imply that every eligibility threshold
  or PDF table has a common numeric projection. Unknown availability or source
  conflicts remain explicit.

## Validation and publication

Source adapter version: **2.9.8**. Common normalizer version: **1.0.12**.
Retained raw source versions and timestamps are not rewritten; the common
normalizer recomputes the derived views from their original evidence.

Final verification results and exact CI/publication links accompany the pull
request. Required gates are the complete Python suite, KEY Node tests, all four
Chromium regression scripts, unchanged-schema validation, complete retained-input
replay, every semantic/reader delta reviewed, and independent final review.

Publication uses the existing trusted `normalize.yml` workflow. It fingerprints
all stored inputs before and after normalization, preserves manual columns,
publishes literal derived values, and reads back every managed expected value
after the last write. The native audit journal and representative repaired cells
are independently read afterward. Repeated claims in distinct source fields remain evidence components of the same
record; their values are not summed. A green job without resulting-state
verification is not a completion claim.

Reproduction commands for the public regression gates:

```sh
python -m unittest discover -s loyalty/tests -v
node --test key/refresh.test.mjs
python diagnostics/test_merchant_evidence_browser.py
python diagnostics/test_source_parsing_browser.py
python diagnostics/test_capture_geometry_browser.py
python diagnostics/test_verified_capture_browser.py
```
