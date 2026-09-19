# PR71 GreatList publication — independently verified 19 September 2026

This is the completed release/destination acceptance. It supersedes the pre-publication boundary in **GREATLIST_ALFA_ACCEPTANCE.md**, which remains the detailed source/parser/test acceptance. Do not repeat publication or earlier migrations merely because the conversation was interrupted.

## Released and actually published

PR **71** was independently read as `merged: true`, merged **2026-09-19T09:12:14Z** at **5b3357040c867513f03b114e2df998eb2797e466**. The five production/test/configuration files are the exact files tested in source-acceptance run **35433752712:1**; temporary discovery code/workflow were removed before merge.

The existing request mechanism was used, not a new recurring workflow:
- `loyalty/request.json` request **2026-09-19-greatlist-alfa-71**;
- `source_ids` contained only **greatlist_alfa_only**, with publication enabled;
- request/execution commit **2c7ed78f56e31d71a86fcbaf6640d5d0a039c4e8**;
- production run **35434092167:1**;
- collect job **105874154618** and publish job **105874375124** both completed with **success**;
- **1051 Python tests / 7 KEY tests**, zero skips, passed in the reviewed acceptance run and the main collection completed its regression steps successfully;
- actual production observation **2026-09-19T09:18:04.148389+00:00**;
- parser publication reported `normalized_published_readback_verified` at **09:19:05 UTC**;
- full common-view publication reported `unified_views_published_and_readback_verified` at **09:21:43 UTC**.

Production artifact **10582192122** (`loyalty-public-35434092167-1`) was independently downloaded. SHA256 **a0db23139af1752e0bada5f270ba8a8f4640cfbafb2459ce6693a386f01d5af8** and ZIP CRC matched. Its code hashes matched the tested executable bytes, its source report had **38 discovered / 38 normalized / 0 errors**, and its records had the same source semantics as the acceptance run, apart from real timestamps and response hashes.

## What the source adds

This source reads actual public GreatList Alfa Only tabs: **Moscow 26, Saint Petersburg 11, Yekaterinburg 1; Kazan, Nizhny Novgorod and Far East 0**. All six catalogue containers and all 38 listed detail pages were read. Empty sections are not source failures. City/restaurant discovery comes from the public UI, not a hardcoded inventory of restaurants.

The 38 source records contain overlapping groups:
- **12** published cashback offers worded **up to 10%**;
- **3** published **10% discounts with concierge booking**, distinct from cashback: **Пафос, Зойка, Айна**;
- **8** explicit restaurant compliments;
- **38** priority-booking privileges via concierge.

There are 24 cards without a numerical cashback/discount. The group counts overlap and must not be summed. Ordinary menu descriptions are not interpreted as complimentary gifts. Eva's address is absent from the reviewed contact block and is explicitly unknown; its Moscow membership and source offer remain readable.

This is public partner-guide evidence, not a bank authentication integration or a certification that any given customer qualifies. Missing caps, validity dates, activation requirements and stacking restrictions are not copied from unrelated PDFs. Existing Alfa PDF evidence stays separate, including overlapping restaurants.

## Independent destination comparison

Destination remains the same **скидки**, spreadsheet **1uFR7croj7p6RRNPcoTRYlVl06hKsurkIgyu1IdMMB-4**.

A real pre-publication read-only XLSX export and a fresh post-completion export were compared independently of Actions. Both stayed private and were not committed or attached to the user. Native CellData reads separately confirmed the published coverage row, representative new source rows, actual visible common-condition rows, old source cells and the final manifest.

| Current stored scope | Before | After |
|---|---:|---:|
| Parser source records | 2582 | **2620** |
| Unified current records | 3230 | **3268** |
| Current benefit components | 3765 | **3795** |
| Current conditions/costs components | 9833 | **9909** |
| Current code/delivery components | 713 | **713** |

Exact checks passed:
- **38 new source rows**, at `parser_offers!A2611:Y2648`, and **1 new coverage row**, at `parser_coverage!A1522:N1522`, matched **all 964 managed fields** of the actual production payload;
- all **2582 prior parser rows**, all **1520 prior coverage data rows**, their positions and manual cells were preserved;
- the other seven original/history/input/archive tabs retained identical values and formulas;
- all **14 sheet names/order/hidden states** and all **eight original formulas** were preserved;
- all existing derived IDs, managed semantic fields and manual columns were preserved; current generation identifiers changed as expected;
- the hidden 64-record document archive was unchanged;
- all five input tabs were reconstructed with their source value types, and **every current managed field in all four common views plus the manifest matched a fresh recomputation**, for both the before and after exports;
- both recomputed source fingerprints exactly matched their stored manifests;
- all four derived-view filters still select **current** in the exported workbook; native representative common-condition rows also showed `current`;
- all **15 previous public Alfa PDF/rules records** remain unchanged.

The standalone export reader initially represented integral Excel date serials as floats and materialized empty export cells as empty strings, unlike the publisher's native atoms. After correcting those read-only representation differences, the full hashes and every managed field matched. No production data/code was changed to force this verification, and the initial mismatching replay is not claimed as passing.

Current source fingerprint: **ede0a7f16eed869df52f7c88f5b43c06e6fad7c6ee45a10436f1d38c3020d1b2**.
Current generation: **509104e905b1d616edfacb401ced721af8f408a35b5c0be35478ae64d44b4fe8**.
Final manifest: **verified / current / practical-offers-v1**.

## Incidental queue work, resolved before unrelated publication

Merging the shared validator also triggered the existing push-based Aeroflot import **35434051076**, which occupied the serialized queue. Its source collection had started using the reserved public staging sheet; it was not a GreatList dependency and no main destination publication had started.

Because no direct cancellation action was exposed, a narrowly scoped one-time cleanup workflow verified the exact run ID, merge SHA, event, workflow path and absence of started publication before requesting cancellation. Cleanup run **35434246971** succeeded. Independent readback confirmed Aeroflot collection cancelled and its publication job cancelled **with no executed steps**. The temporary cleanup workflow was deleted at **d335a37907a66a73eddf4f31e38aa348e763815e**; no enduring permission or schedule change remains.

The interrupted reader left one public import formula in its reserved staging tab. The same bounded cleanup contract cleared `af_public_fetch!A2:D4096` and set the generation to `idle:35434051076:1`. Full native readback of `A1:D4096` confirmed only the four original header cells and no remaining import formula/results. The main before/after comparison confirmed no old Aeroflot records were changed.

## Continuing boundaries

The existing daily catalogue now includes GreatList; future city/card inventories are discovered again from that site's public UI. A newly incompatible layout/pagination reports a failure rather than inventing coverage.

**38 guide records + 15 existing Alfa rules/PDF records = 53 public source records**, not 53 distinct usable discounts or a complete bank catalogue. The exact authenticated `web.alfabank.ru/partner-offers/` source remains unread. Newer core/cashback PDF revision discovery and broader non-restaurant public partner coverage are still open. No fresh universal audit of every other programme is claimed.

No banking session, OTP, personal account data, booking, purchase, privilege activation, new provider account, paid service, new recurring schedule or ScrapingAnt credit was used. Existing generic pipeline installation of OCR tools is not OCR use: this source reads HTML. Whole-workbook rendered-layout and ACL audits were not performed or claimed.
