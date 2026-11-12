# Numeric and clause ownership follow-up

Base: `f61a0be8e97eff8b2a13e17244f9bcf7dc2c5b69`. Normalizer: **1.0.5**.

## Reproduced repairs

| Path | Failure | Corrected contract |
| --- | --- | --- |
| T2 SIM | The independent salon price duplicates a generic label and rejects the courier article. | Prices and the Selection free-delivery statement belong to the courier section; full article conditions remain. |
| Utair multiplier | `1,5-кратные` becomes 5; signed/ranged factors can donate a suffix. | Complete positive factors, consistent repetitions, unchanged worded factors. |
| Student/Utair counts | `21 года` and `1 рабочего дня` fail after changing the number. | Normal inflections, positive whole ages/durations and ordered age bounds. |
| GPB subscription | A paid introduction replaces the explicitly stated subsequent monthly price. | Separate literal introductory price/month count and ongoing monthly price/cost scope. |
| Percentage bounds | `не более` and `не менее` become exact percentages. | Upper/lower bounds, including `чем` and ordinary spacing; payment percentages remain conditions. |
| Literal source polarity | Phrase slicing discards a denial and creates a positive reward. | Full-sentence, per-occurrence interpretation; separate live rewards and product exclusions survive. |
| Monetary caps | A later cap erases a separate fixed discount; source-owned paths can promote the cap itself. | Only the owned cap is excluded from rewards; its amount, purchase stage and condition links stay local. |

## Actual collection failure

Nov10 run `42825924881`, artifact `13768954714`, records
`t2_sim_rules: sim_delivery_price_missing`. Archive SHA-256:
`6a0fc4814c7395b01cbbea1b9651e796d4afa06addc178db10707071f501b89a`.
The official public article was independently inspected on Nov12 and contains
both the salon price and a separate courier section. The new source-entrypoint
fixture preserves that relevant article structure and tests changed prices.

Nov11 T2's HTTP 504 is a separate access failure. HSE's three absent/empty detail
sections remain preview observations; all 57 catalogue cards are retained.
FlyStation's empty-page inventory guard remains unchanged. These access/content
states are not relabelled as successful extraction.

## Immutable public snapshot replay

Run `43023510344`, artifact `13856946598`, observed
`2026-11-11T12:50:05.440629+00:00`: **1,401 records**.
Archive SHA-256:
`dc6ced65dce00ecdddc716151ec19ff8971765a55ff30ffe9ca713de7c9d2fd4`.

The baseline serializer reconstructs stored-cell inputs once; both revisions
normalize exactly those inputs at assessment date `2026-11-12`. Original records,
observation times and the input snapshot remain unchanged. Version/content hashes
are expected to change. The replay is an immutable-data comparison, not a new
collection or publication of the historical snapshot.

The final replay has two changed semantic records: KARI's explicit
`не более 30%` remains an upper bound instead of an exact rate, and the historical
Aeroexpress wording `максимальная сумма кешбэка составляет 1 500 рублей` now
produces a 1,500 RUB cap condition with its unchanged full evidence. This is a
historical offer, not a claim that it is currently available. The reader grows
from **1,198 to 1,199** rows, with exclusions decreasing from 203 to 202: FOTOLAB's
10% service discount survives its separate product exclusion. This is not a new
commercial offer; it was previously hidden by the reader's whole-line guard.

The existing GPB original price evidence is accepted with the free first month
and later 399 RUB retained separately. Replaying retained student/Utair text
preserves the existing IDs and numerical fields; this is not a live HTML replay.

## Independent review and fix pass

A fresh read-only reviewer checked implementation tree `323eed0` and reproduced
four material failures beyond the first regression cases. All enter one test-first
fix pass:

- T2's legacy fallback is now available only for unstructured fragments. An
  unknown heading layout cannot flatten away service boundaries and borrow a
  following section's price.
- Utair fractional/ratio continuations (`1/2`, `1:2`, including spaces) cannot
  donate their trailing digit as a multiplier. An ordinary title colon remains
  a valid delimiter.
- A shared bounded monetary-cap grammar now handles ordinary punctuation,
  `сумма` and `выплата` consistently across exclusion and condition extraction.
- An explicitly payment-owned maximum remains an amount reference and cannot
  become or link as a reward cap merely because another sentence has a discount.

Two set-aside review examples were also graded material: an optional `чем`
in the cap prefix must not manufacture a positive reward, and an explicitly
denied cap must not become an active structured restriction. Equal denied/live
cap occurrences remain independent. Twelve final-review test methods cover these
repairs and compatibility controls; 28 failing assertions and two missing-cap
assertion errors were observed before the fixes.

## Verification and publication

Baseline: **2,431 Python tests and 7 Node tests passed**. Each repair has a public
entrypoint regression observed failing before implementation. Per-task full-suite
results, the independent whole-branch review and the exact CI/publication receipts
are recorded with the associated pull request.

Final fix-pass result: **2,473 Python tests passed in 93.581 seconds**, and
**7 Node tests passed**. This adds 42 test methods across the implementation and
review repairs without removing earlier regression tests. All 1,401 replay raw
records and their source fingerprint are unchanged; no existing reader row was
changed or removed.

The existing request bridge refreshes T2 SIM, student rules, Utair generations,
GPB rules, FlyStation and Ladoga. It uses existing source budgets and serialized
publication/readback, then recomputes all stored inputs with version 1.0.5.

## Limits

The repair covers the supported source templates and the tested phrase classes;
it does not claim arbitrary-prose understanding or universal numerical invariance.
New document identities, unsupported currencies and changed layouts remain review
boundaries. Unknown/conflicting values are not replaced by guessed facts. No LLM,
new dependency, schedule, authentication path or access-control change is included.
Alternative modifier placement such as `Максимальная скидка на повторные заказы
1000 ₽` or `Лимит на повторные заказы — 1000 ₽` remains literal evidence without a
new structured cap. Existing source-owned programme-rule projection is preserved.
