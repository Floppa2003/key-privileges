# Coral recovery and combined destination check — 2026-09-16

## Completed execution

The interrupted continuation was resumed from actual main state rather than the older airline handoff. PR43 had already published its first Coral Google-import run; PR44's RZD publication was still running. No collector was rebuilt or new paid/source-account service introduced.

Coral collect job104873556708 was explicitly rerun after both prior failed URLs produced usable source HTML in a separate public diagnostic tab. **Run35119476496:2**, still using its original tested main commit `7e3810daba74619228651aef9c85d6c33a7de4f2`, completed collection and publisher **104944330712** successfully. Every final publisher step was read after completion. RZD run35135328617:1 also completed; its separate acceptance is in RZD_PREVIEW_ACCEPTANCE.md.

Coral's new source calculation interval was **2026-09-16T19:15:20.492414+00:00 to19:28:05.486838+00:00**. It attempted128 imports, used zero ScrapingAnt credits and no source account, and verified scratch cleanup.

| Scope | Current candidates | Latest accepted | Verified ordinary products excluded | Latest errors |
|---|---:|---:|---:|---:|
| Club sitemap URLs under20 current categories |101|63|36|2|
| Current promo-index URLs |23|23|0|0|

**Latest result:86 records, not88.** The club remains `partial`; promos are `ok` within the current index. The previous errors for Blue Zone Yalikavak and the blue umbrella no longer occur in this run: Blue Zone mapped to its own source conditions and existing identity, while the umbrella was correctly excluded as an ordinary product. Blue Zone already existed at parser row1081, so refreshing it did not add a new row.

Two different URLs failed in the latest pass:
- https://coralbonus.ru/klub-privilegii/razvlecheniya/muzei-opticheskikh-illyuzii/
- https://coralbonus.ru/klub-privilegii/servisy/gruzovichkof/

Both retain `cg_import_timeout_or_error`, not an invented origin404 or permanent-access verdict. Their successful earlier records from35119476496:1 remain in rows1034 and1098 with the earlier16:04:54.066827UTC observation time. They were not re-dated to the new pass.

## Aggregate versus fresh coverage

The exact source URL identities, not merely the counts, are identical between the two passes. Their combined accepted set is **88 records:65 club records and23 promos**, plus36 inspected ordinary-product exclusions. These account for the101 selected club URLs and23 promo URLs across the two observation intervals. This is **not a single fully successful fresh pass**, nor proof of completeness or current eligibility in the interactive catalogue.

The earlier pass's only new discount-record identity was ALEF at row2460; its full acceptance is in CORAL_IMPORT_COVERAGE.md. The latest rerun added zero new parser IDs. Relative to the last airline checkpoint, the destination gained **nine records total: one ALEF offer and eight incomplete RZD catalogue observations**. Do not label that nine newly verified discounts or count Blue Zone as another new row.

Sitemap presence still does not establish active catalogue membership. Seven earlier club records missing from this sitemap remain outside this method's current selection and retain their prior dates. The separate interactive/provider collector remains enabled. Current terms, expiry clauses, product exclusions and account requirements retain their existing evidentiary roles; no personal code was requested or issued.

## Source and publication checks

The latest public artifact **10465385383** has SHA256 `e2d37f7959e7f7fc0ce5582c2f38b7bb2670f03ab85222aff4e49105bea26992`. It was downloaded and checked against GitHub metadata and ZIP CRCs. All86 records were independently reconstructed from their saved sanitized observations and passed JSON Schema, application validators and production publisher preparation. The36 ordinary-product exclusions were reproduced by the existing mapper.

After the final publisher completed, the SAME destination workbook was exported and independently read without changing it. The exact comparison covered:
- RZD74 records:1850 managed fields, plus14 report fields.
- Latest Coral86 records:2150 managed fields, plus28 report fields.
- The two retained earlier Coral records:50 managed fields, including their original dates and run markers.

**All4092 fields matched.** Every selected record was present in the latest current normalization generation. All eight RZD previews retained zero automatically projected benefit/condition/cost/code components and explicit evidence-only warnings.

Comparing the final workbook with the snapshot immediately before this Coral rerun also confirmed2381 non-incoming parser rows unchanged, every old parser ID retained, all parser manual-comment values preserved,1279 previous coverage rows unchanged, and unchanged values in the six other original input/audit tabs. This comparison is about stored values, not a rendered or exhaustive native-formula/style audit. The existing publisher separately performs its full destination readback.

Native Sheets reads after final completion verified Blue Zone's actual conditions/hash/run at row1081; the old dates/hashes of museum1034 and Gruzovichkof1098; ALEF2460; exact new coverage rows1281–1282; the final normalization manifest; and an unchanged evidence-only RZD record's current-generation marker. Native common-view formatting samples retained top/wrap/10pt styling. No unrelated restyling occurred.

Final destination: `1uFR7croj7p6RRNPcoTRYlVl06hKsurkIgyu1IdMMB-4`.
Final manifest: **verified/current**, **2467 retained parser records /3115 unified records**.
Source fingerprint:`e66236872c9afab1875ebfae9a69cd98eb800f393f8da7b0b3809f1935f3e093`.
Generation:`215096f3696cdc2763357006711f189bf21b9e7d22ca3831937e5409e191aa63`.

Both production scratch rectangles for RZD and Aeroflot were read and contained only headers/idle markers. Coral's full scratch rectangle was read after this collection and contained only headers and `idle:35119476496:2`. The separate coral_remaining_probe tab was deleted and metadata read back. Private destination exports were not committed or included in public evidence.

## Code, schedules and remaining work

No new parser-code patch was needed for this recovery. PR43's released Coral implementation had passed736 Python and7 KEY tests; its rerun regression job also completed successfully. PR44/current collector code passed753 Python and7 KEY tests, with its downloaded logs and archive checked. The complete local policy/bundle validator was not rerun because Protego is unavailable locally; no substitute policy implementation was injected. Actual GitHub collection and publisher validations succeeded.

Supplementary Coral Google import remains **Wednesday/Saturday09:17UTC /12:17Moscow**, traversing sitemap-selected pages across all20 current categories rather than alternating halves. RZD remainsWednesday08:37UTC /11:37Moscow. Other schedules, provider budgets and Google permissions are unchanged. This recovery used zero ScrapingAnt credits, no paid service, new key, second account or user computer. No current provider balance is claimed.

A read-only reconciliation of90 configured source routes with destination coverage history found at least one positive report for each. This includes supplementary URLs, not90 independent programmes, and is a historical availability check rather than proof of simultaneous fresh or complete coverage. The most recent reports can still be failed or partial.

The next reliability candidate is bounded failed-import retry inside the existing read/time limits, with tests and exact repeat-observation handling; it is not implemented or claimed tested here. Do not run unchanged full crawls indefinitely to chase transient errors. RZD's eight full-detail gaps and account/privacy boundaries remain, as do external/PDF/image conditions and personal eligibility. Google cache age remains unknown: observation timestamps identify import request/calculation, not certified uncached origin downloads.

For merchant lookup, search the original parser_offers title/conditions/source fields as well as derived views. Evidence-only previews can have no automatic benefit terms and no resolved partner name; an empty normalized-benefits search is not proof that no offer exists.
