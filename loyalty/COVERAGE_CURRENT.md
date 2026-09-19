# Current coverage — practical discounts, 19 September 2026

## Latest accepted release: PR71, published and independently verified

Read **GREATLIST_PUBLICATION_ACCEPTANCE.md** for the completed release, actual destination, preservation checks and resolved queue incident. **GREATLIST_ALFA_ACCEPTANCE.md** records the detailed source/test acceptance; its pre-publication boundary is superseded by the publication report.

PR **71** merged at **5b3357040c867513f03b114e2df998eb2797e466** on **19 September 2026, 09:12:14 UTC**. The existing `loyalty/request.json` mechanism requested only `greatlist_alfa_only`; main run **35434092167:1**, execution **2c7ed78f56e31d71a86fcbaf6640d5d0a039c4e8**, completed collection and publication successfully. Final common-view readback completed **09:21:43 UTC**. Actual source observation: **2026-09-19T09:18:04.148389+00:00**.

The new public source reads GreatList's actual **Alfa Only** city tabs and every listed restaurant's own Alfa Only block. Same-origin city links, catalogue links and native restaurant IDs are rediscovered each run; restaurant inventory and benefit rates are not hardcoded. It reuses existing PublicSource robots/TLS checks, request budgets and daily collection. No bank session, new dependency, new recurring schedule or provider credit is needed.

| GreatList city/regional tab | Listed and parsed |
|---|---:|
| Moscow | 26/26 |
| Saint Petersburg | 11/11 |
| Yekaterinburg | 1/1 |
| Kazan | 0/0, valid empty section |
| Nizhny Novgorod | 0/0, valid empty section |
| Far East | 0/0, valid empty section |
| Total | **38/38, zero errors** |

Overlapping groups in those 38 source records: **12 cashback offers worded up to 10%; 3 explicit 10% discounts with concierge booking (Пафос, Зойка, Айна); 8 explicit compliments; 38 priority-booking privileges**. Do not sum these groups or call all 38 cashback offers. Ordinary cocktail/dessert menu descriptions are not gifts. Eva has no address in the reviewed contact block; Moscow membership and the privilege remain, with an explicit missing-address warning.

Source acceptance **35433752712:1** passed **1051 Python / 7 KEY tests, zero skips**, then main collection passed its regression steps and repeated the complete live source read. Independent artifact checks and source-field DOM replay reproduced all 38 records. Actual location and redemption instructions were verified in visible common-condition rows, not only raw JSON. No source date, cap, activation requirement or exact PDF rate was imported into a guide record where the guide did not state it.

## Current destination and lookup contract

Destination remains **скидки**, spreadsheet **1uFR7croj7p6RRNPcoTRYlVl06hKsurkIgyu1IdMMB-4**.

**2620 parser / 3268 unified records, verified/current, practical-offers-v1.** Before PR71 publication: 2582/3230. The 38 new parser rows are **2611–2648**; the one new coverage report is **row 1522**. Current common views contain **3268 records, 3795 benefit components, 9909 conditions/costs, 713 code/delivery components**. Counts are not unique merchants, usable discounts or coupon strings.

A genuine pre-publication export and a fresh post-completion export were independently compared. All **2582 previous source rows**, **1520 previous coverage data rows**, manual cells, source positions, original/history tabs, hidden 64-record document archive and **eight formulas** were preserved. All **964 managed new source/report fields** matched the actual production payload. Every current managed field in the four common views and manifest matched a full recomputation from the five source tabs; both before/after source fingerprints matched exactly. Old derived semantic content remained unchanged apart from expected generation identifiers. Four exported current-only filters and representative native current conditions were checked. No whole-workbook rendered-layout or ACL audit is claimed. Private exports were not committed or attached.

Source fingerprint: **ede0a7f16eed869df52f7c88f5b43c06e6fad7c6ee45a10436f1d38c3020d1b2**.
Generation: **509104e905b1d616edfacb401ced721af8f408a35b5c0be35478ae64d44b4fe8**.

Use `normalized_records`, `normalized_benefits`, `normalized_conditions` and `normalized_codes` only with **Статус нормализации = current**. API/export readers must apply this status themselves. Old derived rows remain as `retired_from_normalization`, not necessarily source-expired. Do not search the hidden document archive for ordinary practical offers. Search source partner/title/body/conditions as well; announcement text may be in `details.message_parts[].text`. Empty automatically recognised benefits do not prove no offer exists. Preserve exact partner/source/native identity, programme, region, tier, audience, transaction scope, code and dates. `current` denotes current normalization, not current coupon validity or personal eligibility.

## Alfa Only: separate public layers, no banking authentication

The stored public Alfa layers now contain **53 source records**: 38 GreatList records plus the 15 existing rules/PDF records below. This is **not 53 distinct usable discounts** and not a complete authenticated bank catalogue. Overlapping restaurants remain separate source evidence; do not silently combine a guide's up-to rate with another document's cap, expiry or transaction limit.

- **Public core rules:** `alfa_only_public_rules`, revision47, effective2026-05-01, nine practical records: taxi/transfer/carsharing, lounge reimbursement, airport restaurants, QR lounge access, RBC, concierge, SimplePrivé Silver, Smart Reading and travel insurance.
- **Public cashback limits:** `alfa_only_cashback_rules`, revision101, effective2026-05-25, one limits record. No personal category rates or customer tier are inferred.
- **Reviewed partner PDFs:** `alfa_only_partner_pdf_offers`, five documents: Betulla, Р14, Такахули, FRESA/other TSP of ООО «СОМ», Mama Tuta/Probka. Такахули is source-expired on2026-08-31, not a current September offer. The other stored periods are explicit source dates, not proof of activation or personal eligibility. FRESA expires2026-11-30; Mama Tuta/Probka2026-10-31. Keep first-transaction/month and all-transactions/month distinct, as well as exact TSP/legal identity. PR69/70 subsequently repaired clause fidelity and visibility in common conditions.
- **Exact requested bank catalogue:** `alfa_only_partner_offers`, `https://web.alfabank.ru/partner-offers/`, remains separate and unread. Its verified-TLS availability probe observed a302 redirect to bank authentication; it does not follow the redirect, read private bodies or claim collected cashback. CA-download failures remain distinct from fresh auth observations.

Persistent evidence: **ALFA_PUBLIC_RULES_ACCEPTANCE.md**, **ALFA_PARTNER_PDF_ACCEPTANCE.md**, **ALFA_CLAUSE_REPAIR_ACCEPTANCE.md**, **ALFA_PUBLIC_ACCESS_SPIKE.md**, **GREATLIST_ALFA_ACCEPTANCE.md**, **GREATLIST_PUBLICATION_ACCEPTANCE.md**. PR65/66 core-rule collection/publish dependencies, PR67/68 partner expansion and PR69/70 clause repairs are already released. Do not rebuild them from an obsolete branch/checkpoint.

The earlier anonymous spike tested direct verified bank TLS, ScrapingAnt datacenter/browser, one residential request, Google imports, Jina Reader and extended responses with challenge-cookie chaining. Public bank marketing pages still returned access challenges in those attempts. That does **not** mean all useful public paths are exhausted: the subsequent official CDN and GreatList routes worked. The residential attempt cost125 free credits and failed; do not repeat it automatically. PR71 used no ScrapingAnt credits.

## Priority rule and remaining high-value work

Prioritise **programmes with little useful coverage**, not a few unexplained residual URLs in otherwise readable catalogues. First establish what a normal user currently sees in the actual UI. An old sitemap URL, login page, obsolete document or unlisted entry is not automatically a missing current offer.

The earlier audit of **105 configured routes** found Alfa's exact bank catalogue was the only route that had never produced a record; no other route with a historical discovery of at least10 items had a best recorded parsing ratio below80%. Those are historical collector metrics, **not independent denominators for every programme**. The registry now has **109 routes**, not109 independent programmes. Latest failed alternate probes do not erase previous/alternate successful coverage. NORDWIND had successful7/7 visible-card runs despite later transport failures; RZD, Aeroflot and EKP have substantial alternate/public coverage.

**Next Alfa public frontier:** find source-owned, practically useful non-restaurant partner catalogues and a dependable current-PDF revision index. GreatList is complete only for the38 cards visible in its six same-origin Russian tabs at the accepted observation; foreign editions and all other restaurants were not claimed. Core/cashback PDF revisions remain exact-URL reviewed documents with explicit newer-revision-discovery warnings. No bank authentication is authorised by a generic continuation request. Do not suggest SMS forwarding or treat a transferable bank session as established infrastructure.

**Lower-priority historical residuals, not refreshed by PR71:**

- **HSE:** 55 listed,52 details/3 previews (`skyeng`, `skillcup`, `academiya`). The missing-anchor `mordapechat` error was fixed inPR64; printing-studio15%/HSEALUMNI and KubKvadrat10% are separate. Preserve expired MA-MA(2026-01-01), Gruzovichkof(2025-12-31), and Sila Vetra's10% SV20/HSExSilaSport10/end2026-12-31 separately from its August-only20%. Full payment100% is not a100% discount.
- **Mir/Privet:** accepted184/184 unique Moscow+SPb offers from four regional Mir/SBP catalogues. Not all regions or personal availability. **T2 Selection:** public programme/preview layers, not every account privilege.
- **Rostelecom:** `https://www.company.rt.ru/press/news_fill/d476187/` timed out at policy retrieval. Officially indexed `https://www.company.rt.ru/press/REGIONALNEWS/d476187/` remains an untested replacement candidate; existing two records retained.
- **Uralsib:** fresh success35378598217 followed by failure35379313650; intermittent, not permanently fixed.
- **RZD:** eight historical full-detail gaps with previews. Two Google-import failures also met provider423; six prior login/insufficient-content pages are not simple selector errors. Do not repeat unchanged whole catalogues. SacvoyagePR62 has own5% registration/10% referred first stay and separate RZD15% explicitly expired2025-12-31. Official-channel prize-winner announcements are not coupons.
- **EKP:** 110 protected observations/106 names distinct from935 historical public records among1045 entries. Region98 labelled All regions is not automatically equivalent to region78 announcements. iLockedPR61, ArtFlora/LitresPR60 and already-stored announcements are public alternatives, not authenticated recovery. FlyStation's public page was read but no offer adapter released. Independent partner sites are not exhaustively searched.
- **Coral:**69 listed offers reconciled using two separately dated reads(latest19/20 categories plus earlier successful Gadgets). Five missing from sitemap already stored. MegaFon/BookingCar expired2025-12-31. ALEF's public10% page was freshly read; UI-list absence/current code issuance remain unresolved. Do not repeat reconciliation or collect complete contracts.

## Scope, operation and privacy

The owner corrected the former document-completeness goal: «какие-то огромные документы с условиями включать не нужно, при практическом применении они нам не пригодятся никак». Answer **“Do I have a discount here, how much, and how do I use it?”**, not “Have all documents been archived?”

Keep benefit/scope, programme/partner, literal code or redemption instructions, membership/tier, material dates/region/minimum purchase/channel/non-combination, exact source and observation time. Unknowns stay unknown. Short relevant PDF clauses are allowed; whole contracts, parking manuals, exhaustive exclusions/pricelists, unrelated appendices and recursive OCR/document exhaustion are not routine coverage. Do not use canned rates, invented summaries or silently truncated terms. Measure useful offers and redemption information, not document pages or row inflation.

Use existing GitHub-controlled schedules, Free ScrapingAnt where needed, and Google WIF. No paid service, rented/administered server, always-on user computer or second provider account. Preserve source budgets, timestamps, native identities and shared serialized publication. Generic pipeline OCR installation is not a reason to use OCR for readable HTML/PDF text.

PR71's shared-validator merge incidentally started existing Aeroflot collection35434051076. It was stopped before any main publication, then its reserved public staging import cells were cleared and independently verified idle. One-time cleanup35434246971 and its temporary workflow are complete/removed; no durable permission/schedule change remains. See publication acceptance before touching this queue state again. Future shared-file releases should consider push-triggered unrelated collectors before scheduling a targeted publication.

Coral registration is complete; do not ask again or treat it as an EKP/RZD/bank session. Aeroflot parsing permission is owner-reported, not a global host-policy override. Read access does not authorise coupon issuance, activation, bookings, purchases or spending bonuses.

The repository is public. Earlier Sheet ACL was observed as `anyone:writer`, not re-audited or changed here. `private_complete` is a normalizer mode, not an ACL; hidden tabs are not private storage. Never publish tokens, OTP, sessions, auth cookies, private bank records, personal coupons or authenticated-only terms to public artifacts/link-accessible Sheets. Private exports stay local. Any future authenticated collection needs separate authorisation and private storage, not weaker TLS or identity checks.

## Accepted history and recovery

PR56 cleanup/PR57 offline filtering are complete:64 bulk records reversibly archived and source cells cleared without shifting rows; useful benefits and literal codes preserved. **Do not repeat the migration.** Aeroflot bulk linked-rules is a manual no-op without a schedule; practical Coral/lounge instructions, RZD tour clauses/bank links, EKP linked HTML and Utair privileges remain in scope.

PR64 source repairs were verified inSOURCE_REPAIR_ACCEPTANCE.md, main35380667200:1 at e976005f3e5b44bf2ca90c3efff164a8592dcd53, common readback18September18:35:51UTC. Its2567/3215 counts are historical, superseded by the current2620/3268. Older exact checkpoint before this update is preserved at **d335a37907a66a73eddf4f31e38aa348e763815e:loyalty/COVERAGE_CURRENT.md**, blob **d0e48f8e9f1baeeb1026a81faf5125fe61cb15d9**; the older PR61–63 recovery is ebc1a96c6c2a02a03210d073ecff9899c47a3bf1:loyalty/COVERAGE_CURRENT.md.

Other durable evidence: HSE_ALFA_ACCEPTANCE.md, ILOCKED_PUBLIC_ACCEPTANCE.md, PRACTICAL_SCOPE_ACCEPTANCE.md, PRACTICAL_FRONTIER_ACCEPTANCE.md, RZD_ANNOUNCEMENT_ALTERNATIVES.md, EKP_GATED_AUDIT.md, EKP_TARGETED_PUBLIC_AUDIT.md, RZD_EXTERNAL_ACCEPTANCE.md, RZD_PREVIEW_ACCEPTANCE.md, AEROFLOT_ACCESS_STATUS.md, AIRLINE_COVERAGE.md and historical SAMSON/AEROFLOT/EKP/CORAL linked acceptances. Historical bulk-document evidence is not a mandate to resume it. Actions artifacts expire; accepted source/run/code identities persist in Markdown. Interrupted chat output is not a rollback: inspect main, runs and actual destination before rebuilding.
