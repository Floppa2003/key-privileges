# Current coverage — practical discounts, PR82 checkpoint

## Latest deployed release: PR82; source collection and publication independently verified

Read **DURABLE_COLLECTION_PUBLICATION.md** for actual run/code/payload identities, all-source outcomes, independent destination comparison and the unresolved GitHub health-job metadata. **DURABLE_COLLECTION_ACCEPTANCE.md** preserves the reproduced cancellation failure, runtime contract and accepted regression; its pre-publication boundary is superseded. Do not repeat the full crawl or publication merely to restore context.

PR82 merged at **2026-09-22T20:39:21Z**, merge **cb70bbebbdfc301b64cfb65b72cf1678e9f4510f**, reviewed head **24af5efc6231f0ef332fe9c96e1192a0091ea368**. Final feature **35781070515** at **60331bcde874566f804d50bef6086705be3f292d** passed **1252 Python +7 KEY tests**, no skips, with real pinned dependencies. All112reports/1286records from older daily35714017362 were replayed through the new orchestration with exactly unchanged managed publication rows and original timestamps; that replay made zero live website requests. Only acceptance documentation and temporary-workflow removal followed accepted code before merge.

Actual main **35781773598:1**, execution **96275a709b896ed3296ad518bb163cdb4773be53**, observed **2026-09-22T20:41:30.767057+00:00**. The complete registered scope was selected: **115/115 workers completed in702.036seconds**,1497records,106ok/1partial/8failed reports. No missing/unfinished reports or worker exceptions. All85production Python hashes match the accepted full archive. Main regression repeated successfully. This collection timestamp is not a source-written date or cache-age claim.

**collect106928779546 and publish106933441441 both completed/success.** Publication/readback ended20:57:22UTC; publisher job ended20:57:25. **source-health106933441399 still reports in_progress/conclusion=null although all its steps, including Complete job, report completed/success at20:53:28.** This persisted through named-tool and separate raw repository-jobs reads. The actual health application step succeeded; actual payload execution-health and all3strict reward health checks were independently replayed successfully. Do not claim the parent health job or whole workflow is completed/green until a later read establishes it. Cause unknown; no rerun/cancellation was used to force the metadata. A later continuation should re-read this metadata, not recollect all sites.

| Source | Latest accepted batch observation | Coverage boundary |
|---|---:|---|
| Backit /backit_public | **178**,2026-09-22T20:41:30.767057+00:00 |916unique listings/23pages/189eligible detail attempts accounted for;738excluded. No product-level marketplace offers. |
| Club Avolta /club_avolta_public | **17**,same PR82 batch |17Russian cards/sixcategories:16full cards plus DragonPass restaurant-only component. No asserted lounge fee or restaurant redemption method. |
| Mantera /mantera_moments | **16**,same PR82 batch |5programme tiers +11named accommodation properties, not16hotels/all group businesses. Property-specific redemption confirmed only for3. |
| Konsierge /konsierge_public | **159**,same PR82 batch |Public catalogue, not the complete user's Only Assist entitlement. |

All four reported zero source errors. The three public reward integrations also passed their stricter inventory/health contracts. Other named source failures remain below; execution completeness does not mean every site was successfully read.

**Current verified destination:3022 parser /3670 normalized /3056 clean reader records, unchanged counts.** PR82 refreshed1497existing source IDs, added0offer IDs, applied0holds and appended115history reports (1994 ->2109report IDs). Every source managed field matched the independently simulated update plan. Independently recomputed102760normalized-record fields,97306benefit fields,171904condition/cost fields,8904code/delivery fields and70audit fields all matched the final Sheet, including old-row positions and manual columns. Full reader3056rows/51952fields and visible3056rows/42784fields matched. Original8formulas,9175untouched-tab cells, native A10search/A7count, B3:B5/B4validation, C6freshness note, programme-list formula and two-tab visibility remain;0formulaerrors. Private exports stayed local; no full rendered-layout or ACL audit claimed.

Current generation: **db0a56885e1866d167f231a334d7e907766e8ba5434187872b5cd2164c629e1f**.
Source fingerprint: **2d37ac379ea3139f6e5cdb7d9f157b55491f14c8e8330c6bb53e84072a193c38**.
Reader digest: **60f874a5eb3a60c33f4e3f3188dbeeaa0360328cf7b48b80cea207318b2f62f9**.
Future verified publication can change these: inspect live manifests, never restore stale chat counts.

## Full-collection durability, new in PR82

The old collector saved its bundle only after every gather worker and browser.close finished. Controlled main-entry cancellation after one valid source result reproduced loss of that result. The historical daily baseline itself succeeded; do not invent a historical incident.

collection_runtime.py atomically checkpoints completed-source batches with flush/fsync/replace. A failed serialization/write preserves the earlier complete JSON. Every selected source is represented; unfinished reads remain failed/interrupted or not_started, zero invented offers. No historical snapshot is relabelled fresh. Code hashes are saved before browser work. Cancellation propagates; cleanup/disk errors are not hidden.

Existing4worker concurrency and individual source budgets remain. Longer permitted budgets enter earlier, while report order/IDs remain configured. Queue waiting does not consume source timeout. Per-source queue_seconds/execution_seconds are additive diagnostics. This heuristic is not a guaranteed optimum or measured causal speed improvement.

A1000second soft collection deadline reserves intended headroom in the existing20minute job. Completed results remain publishable on graceful deadline; unfinished sources stay unhealthy. No actual timeout/cancellation was needed in the PR82 main run. Not guaranteed: SIGKILL/runner loss/disk loss/blocked event loop, artifact upload after hard timeout, unusually slow setup, or individual records inside a still-unfinished source. No remote per-source checkpoint architecture was added.

The health CLI now checks execution/report completeness for ALL selected configurations, separately from the3reward semantic/inventory checks. Missing/duplicate/foreign/unfinished reports and unexpected worker exceptions cannot silently pass execution health. Ordinary historical-route failures retain their explicit source reports and are not globally reclassified. Successful-source publication remains independent of stricter source-health failures. No source adapter, URL, rate, TLS/access policy or schedule changed in PR82.

## Current unresolved source outcomes and next priorities

These same8routes failed in both inspected full batches; none was fixed by the runtime change:

| Route | PR82 actual failure |
|---|---|
| nordwind | robots TimeoutError |
| coral, coral_promo | http_403 |
| rzd | http_403 |
| aeroflot | robots_not_readable |
| ekp | robots TimeoutError |
| af_primbank_rules | ERR_CERT_AUTHORITY_INVALID |
| alfa_only_partner_offers | alfa_bank_authentication_redirect |

HSE55records remains partial: skyeng, skillcup, academiya have missing/empty detailed sections. Do not confuse a failed spare route with programme-wide absence: RZD/Aeroflot/EKP/Coral have separate collector/history paths, and NORDWIND previously had successful7/7accordions. Inspect those actual alternate executions before choosing the next coverage target. Preserve their last successful observations; don't pretend PR82 revalidated each alternate path.

Next useful work: resolve health-job metadata with a read; inspect alternate-source freshness for the currently failed routes, then address a demonstrably missing useful offer or access/readiness regression. Do not inflate totals with advertisements, technical placeholders, general contracts or bank-acquisition ads. Repeated unchanged Backit marketplace redirects are not progress. Only Assist still waits for the authorized device session.

## Retained scoped lifecycle, freshness and operation

**Mantera lifecycle /PR81:** only a complete same-time named roster with valid record identities/hashes and one coherent roster/resort evidence pair can reversibly withhold its own absent public_partner cards. Match exact native ID/name, not the shared URL. Roster absence is not programme-wide departure. Five FAQ tiers and independently sourced Congress are outside that retirement scope. Empty/wholly removed/failed/partial/duplicate/mixed-version rosters cannot mass-retire cards. Source text/time, positions and manual notes remain; checked_at/run metadata is separate. Fresh return restores the same row; older evidence cannot overwrite a newer observation/hold. Health and reconciliation share the validated snapshot. PR81 tests and PR82 refresh applied0real holds. See MANTERA_LIFECYCLE_PUBLICATION.md/ACCEPTANCE.md.

**Backit/Avolta holds /PR79:** only complete successful same-time inventories accounting for every URL can withhold old excluded/absent cards. Failure/partial reads cannot prove disappearance. Original rows, source text/time and notes remain; return/old-write/concurrent-value guards remain. These are source-local rules, not a global retirement policy for older programmes.

**Freshness:**7calendar-day observation-age limit applies only to Backit, Club Avolta and Mantera parser records. It is not an offer expiration date. Clean materialization and native TODAY predicate both enforce it; original evidence remains. API readers must apply freshness at their own lookup date. Native filtering depends on Sheets recalculation, not a promise of exact unattended midnight execution. No global timezone/recalculation setting changed.

**Avolta transport:** ordinary same-origin HTTP replaced the source-local headed renderer in PR79; full traversals also succeeded in PR82. Successes do not guarantee future uptime. Verified TLS, source scope, bounded retries and access stops remain. No proxy/header rotation/authentication or Browserbase dependency was introduced.

**Operation:** existing daily05:23UTC/08:23Moscow, same shared serialized publisher. PR82 was a controlled workflow_dispatch with full daily scope, not a timer-triggered execution. The first later timer run has not been observed. No additional ChatGPT task, recurring workflow or notification setting. Do not mistake preserved normalized current status for source freshness/eligibility.

## Public programme boundaries retained from PR79–81

**Mantera roster:** https://sochiparkhotel.ru/about/programma-loyalnosti/ names11properties while its separate counter says6. Use named identities and retain the discrepancy. Hosting the roster does not prove Sochi Park Hotel itself participates. Congress retains its independently sourced ID/page.

Names: Мантера Resort & Congress5*; Сочи Марриотт Красная Поляна5*; Риксос Красная Поляна Сочи5*; Новотель Резорт и спа Красная Поляна5*; Новотель Фит Красная Поляна4*; Кортъярд Марриотт Сочи Красная Поляна4*; Долина9604*; Ибис Стайлс Красная Поляна; Панорама by Mercure Красная Поляна; Апартаменты Курорта Красная Поляна; Апарт-отель «Бонус»3*. Use actual source spelling/spacing for identity, not this compressed inventory.

https://krasnayapolyanaresort.ru/loyalty separately confirms earning/spending at Долина960, Кортьярд, Марриотт. Exact reviewed mappings attach spending only to those full roster names, never substring-match Marriott into Courtyard. Other named properties get earning with individual redemption unknown. Preserve tier/annual-spend scope, pre-booking registration,18+, free participation,12month status,24month bonus validity, non-cash rules/exclusions. Both public tier tables must agree; unknown aliases or missing critical terms fail closed. The private /app/partners route was not entered; FAQ calendar-versus-business accrual discrepancy remains. Failed participant pages do not relabel old evidence fresh. See MANTERA_PARTNERS_PUBLICATION.md/ACCEPTANCE.md.

**Backit:**178accepted/916inventory in PR82,738excluded:677source-disabled,50acquisition ads,10expired promotions,1detail replaced by catalogue. Three previously uncertain promotion periods were accepted with year inferred from matching current page-title month/year (Все Инструменты, Xcom-Shop, Плати по всему миру). Keep the explicit promotion_year_inferred_from_current_page_month warning: not a source-written year or guarantee against stale copy. Preserve fixedRUB/ranges/customer scopes/zero-rate exceptions/public coupons; cash back is not an upfront discount.

**Backit marketplace:** old Ozon/Wildberries compilations and mixit-ozon redirected to the catalogue; Roborock-Ozon explicitly disabled cashback. PR80 additionally tested the source-linked /ru/cashback/shops/ozon/products once:302to/ru/cashback/shops. No product-level marketplace offers were imported from cached search. These separate failed routes were not reprobed by PR82. Do not repeat unchanged probes on restart.

**DragonPass:**31USDheadline/28USDbody still conflicts for lounge entry. Only independently consistent restaurant discount up to25% is retained as partial. Lounge fee and restaurant redemption method remain withheld/unknown; lounge app instructions are not restaurant activation. Country/tier/frequency and personal eligibility stay distinct.

## Everyday lookup and reader quality

Destination **скидки**, spreadsheet **1uFR7croj7p6RRNPcoTRYlVl06hKsurkIgyu1IdMMB-4**.

- Visible Скидки, sheetId2026092001: B3keyword/code, B4programme, B5category. No junk/expired return switches. Empty filters show accepted records subject to scoped freshness.
- Hidden _ui_catalog!A:Q: partner, programme, benefit, code/retrieval, activation, conditions, source period, category, observation, source link, comment, record type, validity status, ID, input tab, input row, original title. It is an as-of materialization; API readers honor freshness too.
- _ui_catalog!Y1:Z8: Z2verified,Z5=normalization_audit!J7; normalizationE7verified,I7current. Z4is materialized count, potentially above later freshness-filtered results.
- Visible О таблице retains instructions/programme list. Only2tabs visible; hiding is not access control.

parser_offers/normalized_* are provenance layers, not everyday offers. Current normalization is not proof of current validity, practical acceptance or user access. Preserve programme/source/nativeID, branch, region, tier, customer type, payment channel, literal code and dates. Unknowns stay unknown. Never restore raw posts/polls/placeholders/corporate advertising/whole contracts to increase apparent coverage.

PR77source-owned cleaning remains in the same publisher;5original datasets and14original technical/history tabs remain. Do not delete/shift old source rows because legacy IDs depend on them. ObsoleteR:Xhelper stays cleared. XLSXDUMMYFUNCTION/cached spill formulas are not nativeUIformulas; read CellData to verify search.

## Earlier sources, privacy and recovery

Konsierge/PR75 now freshly reconfirmed159public records in PR82; see KONSIERGE_RECURRING_ACCEPTANCE.md, KONSIERGE_CATALOG_ACCEPTANCE.md, KONSIERGE_PUBLICATION_ACCEPTANCE.md. Its owner-approved robots exception is source-local. It is not the full user's Only Assist catalogue. Completed APK/emulator/device work is separate; no authenticated app content has been collected. Do not repeat it while awaiting the authorized Android session.

Alfa/GreatList/TSUM,HSE,Mir,RZD,Aeroflot,EKP,Coral and other earlier adapters were not modified by PR82. The full main refresh exercised registered routes and preserved failures; separate alternate collectors were not all rerun. Prioritize practically missing programmes/conditions, not route counts or bulk document archiving.

The complete pre-PR82checkpoint remains byte-for-byte at **96275a709b896ed3296ad518bb163cdb4773be53:loyalty/COVERAGE_CURRENT.md**, blob **ce8b260d77e740b8beb2a57ea81ba6f7f4bbb8e6**. It preserves PR81, the pre-PR81checkpoint3f5fb995c21b886b1971d1219927c0ee3a40a865/blob e638e2ef13d3d5b616bb6710afa826f769692ec0, and the recovery chain through PR80–78 to earlier full source checkpoint22241f9a964f9af84e48ee730f583289c4c9d034. Older no-Mantera-retirement or raw-reader instructions are superseded. PR56/57migration and earlier Aeroflot cleanup are complete; do not repeat them.

The repository is public. Never commit/upload private workbook exports, bank data, personal coupons, tokens/cookies/OTP or authenticated-only terms. Hidden tabs and private_complete are not ACLs. Private exports remain local; only public evidence and aggregate audits may be shared. Existing Free ScrapingAnt/GoogleWIF/shared queue remain; no paid provider, extra account, rented server or always-on user computer.

Public reading does not authorize registration, issuance, activation, booking, purchases or bonus spending. Artifacts expire; exact run/code/payload identities persist in acceptance/publication documents. Interrupted chat output is not rollback: inspect main, actual jobs and live destination before rebuilding.
