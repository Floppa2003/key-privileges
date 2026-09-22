# PR79 — coverage and reliability published, 22 September 2026

This report supersedes the pre-publication boundary of RELIABILITY_ACCEPTANCE.md. The implementation, source diagnostics, explicit assumptions and regression evidence remain in that document. No new crawl is requested by this documentation update.

## Release and actual main execution

PR79 merged at **2026-09-22T16:41:38Z**, merge **d8143b362256512f9b10ffe651f33194447b9ede**, reviewed head **bbd42c261e46f498b72db8e7bda45b22caea1329**. The connected GitHub app independently read back its merged status. Temporary probe, patch, installation manifest and verification workflow files were removed before merge; no production bytes changed after the final accepted test except the already verified DragonPass activation correction.

Actual main run **35755985550:1**, execution **73175279fd8c43e18c4e6306346613b010e4c9d9**, used the existing selected-source workflow. Fresh batch observation: **2026-09-22T16:44:49.142888+00:00**. This is the collection observation, not a source-written publication date or cache-age claim.

| Job | ID | Independently read final result |
|---|---:|---|
| collect | 106841762779 | completed / success |
| source-health | 106845143475 | completed / success |
| publish | 106845143596 | completed / success |

All three source reports were separately inspected: **178 Backit +17 Club Avolta +6 Mantera =201 accepted records; zero errors for each source**. The source-health result is not inferred solely from a green collection job. Every actual main record was independently reproduced from its own stored public evidence and original observation time. All82 Python hashes in the actual source manifest match the final accepted regression code archive.

Final feature regression **35755005927**, execution **ec63a34a709bd51eb0dd979d86233828d5ced050**, passed **1206 Python +7 KEY tests, no skips**. It replayed201 real records:200 unchanged, one DragonPass correction limited to removing the lounge-specific activation from the restaurant-only offer and recomputing its content hash. Actual main regression then passed again. The earlier full live feature run35753691428 and this main run constitute two successful complete HTTP traversals of Avolta, not evidence of guaranteed long-term uptime.

## Accepted coverage and residual limits

**Backit:** all916 unique listings across23 inventory pages and189 eligible detail attempts accounted for.178 accepted;738 excluded:677 explicitly disabled by the source,50 financial/acquisition advertisements,10 expired promotional periods,1 detail replaced by the general catalogue. Three previously withheld current-context promotional cards are now included: Все Инструменты, Xcom-Shop, Плати по всему миру. Dates come from the promotion panel. A missing year is inferred only from the matching current month/year in the page title and is visibly labelled as an inference; it is not represented as a source-written year. Old crossed-out rates are not revived.

**Club Avolta:**17 public cards in six source-linked Russian categories, read through ordinary same-origin HTTP rather than the source-local headed renderer. DragonPass is a partial restaurant-only record: the independently consistent discount up to25% is retained; conflicting lounge admission prices31USD/28USD remain withheld. Restaurant redemption instructions are unknown. The lounge-app instructions are not reused for restaurant activation. Country, tier and frequency restrictions remain with their own cards.

**Mantera:** five existing FAQ tiers plus one source-confirmed hotel, **Mantera Resort & Congress**, from https://manteracongress.ru/loyalty-program. Six records are not six hotels or the full partner inventory. Earning rates are scoped by annual-spend tier. Redemption at that specific hotel is not confirmed: the public page distinguishes objects that only earn from those that also redeem. Pre-booking registration, no-cash withdrawal and exclusions are preserved.

The tested old Backit Ozon/Wildberries compilation routes redirect302 to the general catalogue; Roborock-Ozon retains a rate table but explicitly says cashback is temporarily unavailable. They are not imported from stale search cache. Product-level marketplace coverage remains absent through those tested routes. Mantera's full partner-list route redirects to sign-in; that redirect was not followed and no account was used.

## Reliability deployed

Backit/Avolta now carry an exact inventory snapshot. Only a complete successful same-time inventory accounting for every unique URL authorizes reversible holds for previously accepted but now excluded/absent cards. Empty, malformed, failed and partial reads do not retire offers. Original rows, source text, source observation time and manual fields are preserved; operational checked_at/run metadata is separate. Fresh accepted evidence restores a held card. Older incoming observations cannot overwrite newer offers or holds, and concurrent managed-cell changes are checked before writing.

An internal **7-calendar-day freshness limit** applies only to these three public reward programmes. Over-age records are withheld from the cleaned reader without inventing a source expiration date. The native search formula has the same source/origin-scoped TODAY predicate, so it also filters stale observations when Sheets recalculates even when CI cannot publish. Global recalculation settings and timezone were not changed; exact unattended midnight recalculation is not promised.

A separate read-only source-health job reports failure for an unhealthy selected new source while allowing the other successful sources to publish. The existing daily **05:23UTC /08:23Moscow** schedule and serialized publisher remain. No additional recurring workflow or ChatGPT task, paid provider, source account, coupon issuance, purchase or activation was added. First future timer execution after this release has not yet been observed.

**No real record required a hold in this refresh.** The hold/restore pipeline was tested end-to-end with simulated source transitions and preserved manual notes. An additional local read-only counterfactual checked196 genuine previously stored records: retained at age7days, withheld at age8days. No production observation dates were modified for that test.

## Independent destination audit

Destination: скидки, spreadsheet **1uFR7croj7p6RRNPcoTRYlVl06hKsurkIgyu1IdMMB-4**. Genuine private pre-publication and post-publication exports were compared. Native CellData was separately read for formulas, search controls and effective values; exported DUMMYFUNCTION/cached spill formulas were not mistaken for native formulas. Final export modification metadata:2026-09-22T16:56:04.317Z, not an asserted exact final-read completion time.

| Check | Verified result |
|---|---|
| Parser records | 3007 ->3012 |
| Current common records | 3655 ->3660 |
| Clean reader | 3041 ->3046 |
| New / refreshed source IDs | 5 new,196 refreshed;201 total source upserts |
| Real holds applied | 0 |
| Exact source/report fields | 5067 matched |
| Exact common fields independently recomputed | 20128 matched |
| Exact source-reader fields independently recomputed | 3417 matched |
| Entire visible reader |3046 rows /42644 fields matched |
| Unrelated old common semantic fields |353578 preserved, apart from expected generation changes |
| Untouched-tab cells |9175 preserved |
| Manual-column positions |25323 checked and preserved |
| Source/history rows |4800 unrelated source/history rows preserved; not4800 discounts |
| Original formulas |8 preserved; zero formula errors |
| Native UI |A10 exactly equals guarded transformation of pre-state; C6 note matches; B3:B5 and B4 validation preserved |
| Visibility |Only Скидки and О таблице visible, unchanged |

Both manifests were verified/current and their generations matched. Native A7 displayed **Показано:3046 / Предложений в каталоге:3046**. Current components:4358 benefits,10626 conditions,98 costs,742 code/delivery components; these are not counts of unique usable discounts or literal codes.

Final generation: **d1a66a14bf1606612dc931b98d85af92ecdc7c26dbff7f9ab195fb5e8226969c**.
Source fingerprint: **83780c2233bc5096809218942124d6f9e8782fe1f7f8790fdca0d0b3514d414a**.
Reader digest: **faa0422fa7d92e2fac1bad4dcbd7d5b10baef65e397803b1b305af5f0d31e9a1**.

Main public artifact **10708552614**, loyalty-public-35755985550-1: ZIP SHA256 **95615c20ddf03b5a7d0bff935014dbb544e0d2c8f66165f660fafbf821cfd872**; normalized.json SHA256 **fae3e757c56fb7c0e8a00807bc0cc233c63f8f1da1d23dab9586d375b9c90914**. ZIP digest/CRC and actual payload were independently verified. Shareable aggregate audit SHA256 **09cc92e6719eb8f7575e30ef39c978d5362941a5badb765916aeab1585e23d59**. All private workbook exports stayed local and are not committed or attached to public artifacts.

This release improves the three new sources, not all historic programmes. Source health, current normalization, freshness and personal eligibility are distinct. Future failed reads must remain visible as failures; never relabel last-good observations as newly retrieved evidence.
