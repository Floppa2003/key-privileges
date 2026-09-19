# GreatList Alfa Only public directory — 19 September 2026

## Scope and provenance

The owner authorized continuing public Alfa Only collection, prioritizing programmes with little useful coverage rather than residual cards in nearly complete catalogues. This source opens a different public layer: GreatList's actual Alfa Only city tabs and the Alfa Only section of each listed restaurant detail page. It does not access the bank account, authenticated partner-offers catalogue or A-Club privileges.

Primary partnership context: Alfa-Bank's 16 April 2026 release, `https://alfabank.ru/news/t/release/alfa-bank-i-greatlist-rasshiryayut-partnyorstvo-do-2029-goda/`. Actual collection starts at `https://greatlist.ru/spb/alfa-only/`; same-origin city links and each `data-id="alfa-only"` tab are discovered from the public UI. Cards are not enumerated from arbitrary URLs, guessed files or search snippets. International GreatList editions are outside this source.

Source ID: **greatlist_alfa_only**. Existing PublicSource transport, robots checks, source budget and publication pipeline are reused; no new dependency, schedule, credential or provider credit is required.

## Live inventory accepted

Run **35433752712:1**, job **105872816434**, execution **c9269bae495213a1e521b1c17f137e1efa97ab1f** completed successfully. Actual observation **2026-09-19T09:06:49.286964+00:00**.

| Source's city/regional tab | Listed | Detail pages parsed |
|---|---:|---:|
| Moscow | 26 | 26 |
| Saint Petersburg | 11 | 11 |
| Yekaterinburg | 1 | 1 |
| Kazan | 0 | 0 |
| Nizhny Novgorod | 0 | 0 |
| Far East | 0 | 0 |
| Total | **38** | **38** |

All six valid catalogue containers were read, including the three empty ones; zero source errors. Source robots returned HTTP 200 / rules_loaded. The source made 50 scoped HTML reads (12 city/catalogue pages, 38 detail pages), separately from robots.

The 38 records contain:
- **12** explicit cashback offers, each worded **up to 10%**, not guaranteed exact 10%;
- **3** explicit **10% booking discounts**, not cashback: Pafos, Zoyka and Ayna;
- **8** explicit restaurant compliments;
- **38** priority-booking privileges via the concierge service.

These groups overlap and must not be added together. The other 24 records contain no numeric discount/cashback. Ordinary wording about a signature cocktail or dessert being on the menu is retained as context, not relabelled as a complimentary gift.

## Extraction and validation

Only a unique canonical page, expected city/restaurant path, native WordPress post ID, matching restaurant heading and the owned Alfa Only block are accepted. Duplicate IDs/URLs, wrong programmes, unexplained pagination controls, unrelated/ambiguous containers and foreign redirects fail closed.

Two observed presentations are supported: an Alfa Only heading followed by list items, and a paragraph beginning with the source's Alfa Only eligibility wording. Normal expandable UI sections are readable; actual hidden attributes, scripts, forms and comments do not supply benefit values. Rate values are extracted, not hardcoded. All original source fields and the full short Alfa Only block remain available.

`details.activation` carries the exact booking/redemption wording and `details.limitations` carries the source's city and extracted address. They are independently checked as visible common-condition components, not merely as raw JSON. Stable IDs are city plus native post ID. Every row retains the full-page response hash and public-guide provenance, with personal eligibility unverified and authenticated-catalogue equivalence false.

One detail page, **Eva**, has no address in the reviewed contact block. Its actual Moscow catalogue membership and privilege are retained; no address is invented. The row and coverage report carry the missing-address warning.

## Tests and independent replay

The accepted run passed **1051 Python tests and 7 KEY tests**, zero skips. Nineteen new tests cover source identity, owned benefit sections, valid empty catalogues, discovery limits, rate-limit stopping, list/paragraph and quoted-heading variants, absent addresses, source-derived rates, booking-only benefits, discounts distinct from cashback, hidden-content rejection, rehashed evidence mutations and visible common conditions.

Artifact **10582096562**, SHA256 **a0773e0781698daf6727f15db919c302a2834396c09fbee31407fb55fe97e25f**, was downloaded and independently checked against GitHub metadata and ZIP CRC. The executed five production/test files matched the reviewed local bytes exactly. All 50 minimized source-field DOM snapshots passed their stored byte hashes; independent replay reproduced every field of all 38 records after restoring each original full-page digest. All 38 visible location and redemption components matched; eligibility_verified remained null. Minimized DOM snapshots are not claimed to be complete copies of every original page asset or script.

Executed SHA256:
- `loyalty/greatlist_alfa.py`: **5efdf793db3141fecb1520083162fd4fd0b1bdf99ed01f8d1f3437b3dcb1053c**
- `loyalty/tests/test_greatlist_alfa.py`: **131be99683e0b4ed12839f45a3f1afd08df102a795c36d2f4b899bf221150943**
- `loyalty/normalized.py`: **81209863e491f1d6949ff1152bfebc655ef32efb38f0a1e21fa67a0748ce515b**
- `loyalty/collect_normalized.py`: **e673e3c91f181213283411600fb9f55dd0989036c80de8bbffc434b29185cde5**
- `loyalty/sources_normalized.json`: **3e854684ec0b5087b80519c3d63855a70b60e0ce8964836e95af1f202cc64456**

Earlier run **35433333623** fetched all 38 pages but its first adapter accepted only 28 and failed ten observed layout/address cases. Its final validation failed correctly and it is not release acceptance. The subsequent fix and four additional tests produced the successful run above. An initial local all-suite invocation exceeded its execution timeout; it is not claimed as passing. Full-suite acceptance is the pinned GitHub run.

The two temporary exploration/acceptance files were removed before PR creation. The tested executable files were unchanged by that cleanup.

## Publication boundary at this checkpoint

This document currently certifies source/test acceptance, not completion of a Google Sheets write. Before publication, native Sheet readback and a private read-only workbook export confirmed the existing **2582 parser / 3230 unified** state, 14 sheets and eight formulas. The exporter baseline is retained privately for the post-publication comparison.

Release and actual destination verification will be appended only after the main-branch collection/publication completes and independent readback matches. Do not rerun old migrations or refresh unrelated sources simply because a chat was interrupted.

## Remaining limits

This is complete coverage of the **38 cards visible in six reviewed same-origin GreatList Alfa Only tabs at that observation**, not of every bank offer, every GreatList restaurant or every international edition. Booking, cashback and compliments are different benefits. Public guide wording does not establish cashback caps, end dates, card-specific activation, stacking or the owner's eligibility where these are not stated. Do not copy missing conditions from an unrelated bank PDF or apply an exact PDF rate to a guide's up-to rate automatically.

The existing 15 public Alfa PDF/rules records remain separate. Overlapping restaurants are separate source evidence, not automatically new unique offers. The authenticated `web.alfabank.ru/partner-offers/` source remains unread. Newer core/cashback PDF-revision discovery is also still unresolved. These results disprove the earlier suggestion that useful public routes were exhausted, but do not justify a new universal completeness claim.

No bank login, OTP, authenticated cookies, personal financial records, discount activation, booking, purchase, new provider account, paid service or ScrapingAnt credit was used.
