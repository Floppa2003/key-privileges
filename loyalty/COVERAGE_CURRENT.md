# Current coverage — practical discounts, 19 September 2026

## Latest accepted release: PR72, published and independently verified

Read **ALFA_FRONTIER_PUBLICATION_ACCEPTANCE.md** for actual main execution, destination, preservation checks and completed readback. **ALFA_PUBLIC_FRONTIER_ACCEPTANCE.md** preserves source/test acceptance and the still-unread Only Assist investigation; its pre-publication boundary is superseded by the publication report.

PR72 merged as `a2c74317d2be23390d47839597d1cae50ff17040` at **2026-09-19 12:22:38 UTC**. The existing request mechanism selected only `alfa_only_tsum,alfa_only_announcements`. Main **35442711304:1**, execution **a40d90fdb9592fce24ae8b503c28bf31fd52f129**, completed collection and publication/readback successfully. Actual source observation: **2026-09-19T12:24:37.237375+00:00**. An independent post-completion export and native-cell checks confirmed the results; do not confuse an intermediate `publishing` manifest with completion.

| New public source | Accepted result | Material boundary |
|---|---|---|
| TSUM / DLT merchant page | **2 tier records**, zero errors | **8% Orange / 20% Black are merchant loyalty credits**, not bank cash or miles. Eligibility and dates remain unverified/unknown where the source does not establish them. |
| Alfa Only public announcements | **18 records**, zero errors | 180-day public-caption window, not 18 unique/current usable offers or the full bank/app catalogue. |

TSUM preserves practical payment/card/courier exclusions, activation, returns, accrual timing, conversion and tier rules. The common-view projection emits exactly one `earn_points` benefit per tier, reward unit `TSUM_DLT_loyalty_credit`, linked to complete practical conditions and activation. Baseline 5%/10% and another card tier remain conditions, not extra rewards. Required missing/duplicate clauses, card/FAQ rate disagreement and rehashed scope tampering fail validation.

Announcements remain `announcement` / `announced_unverified`; publication date is not expiry. Source-owned captions/album parts are preserved; forwarded posts, plain yield/lifestyle statistics, polls, lotteries and the random privilege wheel are excluded. Multi-merchant posts are not assigned to one guessed partner. The channel self-describes as Alfa-Bank's lifestyle channel, but an extra bounded search did not independently establish bank-publisher attribution. Verify material redemption terms on a bank/merchant source before claiming a usable benefit.

Verification runs **35442088448** and **35442472548** passed **1069 Python + 7 KEY tests, no skips**, on identical production bytes; actual main regression steps also succeeded. A temporary helper in **35442309775** incorrectly combined a one-row slice with whole-source counters after successful collection/dry-run. Corrected verification replayed the exact artifact rather than changing data or needlessly repeating the catalogue. Temporary probe/installation workflow and helper are removed.

## Current destination and lookup contract

Destination remains **скидки**, spreadsheet **1uFR7croj7p6RRNPcoTRYlVl06hKsurkIgyu1IdMMB-4**.

**2641 parser / 3289 current unified records, verified/current, practical-offers-v1.** The genuine pre-state was **2621/3269**, not the older PR71 checkpoint's2620/3268: a later Mir MEOLLO record was already present. New source rows **2650–2669**, source reports **1632–1633**. Current common views contain **3289 records, 3817 benefit components, 9950 conditions/costs, 714 code/delivery components**. These are not unique merchant, discount or literal-code counts.

Independent before/after comparison preserved all previous source values/formulas at their original positions, manual cells, original/history tabs, hidden archive and eight formulas. All **528 new managed source/report fields** matched the main payload; all **1436 new common semantic fields** matched recomputation from actual source rows. Existing common semantic fields remained unchanged except generation identifiers. Every current common row matches the verified generation. No whole-workbook rendered-layout or ACL audit is claimed. Private exports remain local and are not committed or attached.

Source fingerprint: **589adf3a346b3835ddea29df28bffa130a07713a8e512a5a5b9604f205b73507**.
Generation: **3df875fa34a6f4f8cad24b5a01781c6d086a431caa82eec20541123362c2482b**.

Use `normalized_records`, `normalized_benefits`, `normalized_conditions`, `normalized_codes` only with **Статус нормализации = current**; API/export readers must filter explicitly. Old derived rows remain `retired_from_normalization`, not necessarily source-expired. `current` means current normalization, not current coupon validity or personal eligibility. Search original partner/title/body/conditions too; announcements may retain text in `details.message_parts[].text`. Preserve exact programme, merchant/source/native identity, tier, region, audience, payment channel, code and date scope. Empty automatic benefit extraction does not prove no source offer exists. Do not search the hidden document archive for ordinary practical offers.

## Alfa layers: public expansion, not banking/app authentication

There are now **73 public Alfa-related source records**: 38 GreatList, 9 core rules, 1 cashback-limits record, 5 partner PDFs, 2 TSUM tiers and 18 announcements. Counts overlap; never silently merge a guide's rate with another PDF's cap/date or an announcement's code.

**GreatList / PR71:** historically accepted **38/38** visible cards across six Russian tabs: Moscow26, SPb11, Yekaterinburg1; Kazan/Nizhny Novgorod/Far East valid empty. Overlapping groups:12 up-to-10% cashback,3 explicit10% concierge-booking discounts(Пафос, Зойка, Айна),8 compliments,38 priority-booking privileges. Do not add those group counts or call all38 cashback. Eva has an explicit missing-address warning. Actual city/card links are rediscovered, not a fixed restaurant list. Foreign editions/all restaurants are not claimed. See GREATLIST_ALFA_ACCEPTANCE.md and GREATLIST_PUBLICATION_ACCEPTANCE.md.

**Existing rules/PDFs:** `alfa_only_public_rules` remains core47/effective2026-05-01 with9 practical records; `alfa_only_cashback_rules` remains rev101/effective2026-05-25 with1 public limits record. No personal rates, tier or eligibility are inferred. `alfa_only_partner_pdf_offers` contains Betulla, Р14, Такахули, FRESA/other TSP of ООО «СОМ», Mama Tuta/Probka. Такахули expired2026-08-31; FRESA ends2026-11-30, Mama Tuta/Probka2026-10-31. Keep exact TSP/legal identity and first-transaction versus all-transactions monthly scope. PR65–70 collection/dependency/clause fixes are already released; do not rebuild an obsolete branch.

**Bank catalogue:** exact `https://web.alfabank.ru/partner-offers/` remains unread. Its earlier verified-TLS HEAD probe observed a302 bank-authentication redirect, without following it or reading private bodies. CA failure is not a fresh auth observation. Public alternatives are not equivalent to this catalogue.

**Only Assist:** package `com.konsierge.assist.only`. RuStore HTML and all26 public JavaScript assets were read in35441034826; they exposed store/deep links, not a discount-feed API. The developer origin timed out at robots; its www alias redirected. APK distribution follow-up35441372055 reached403 on the actual target after correcting an overly strict robots403 check. No APK was successfully inspected or executed; no app endpoint/catalogue was recovered. Generic `konsierge.com/benefits` was not proven equivalent to the Alfa plan and was not relabelled as Alfa Only. Detailed attempted routes and evidence are in ALFA_PUBLIC_FRONTIER_ACCEPTANCE.md. Do not repeat unchanged failed requests or claim app parsing works.

The earlier anonymous bank spike covered direct TLS, ScrapingAnt datacenter/browser, one residential request, Google imports, Jina and extended responses. The failed residential request cost125 free credits; do not repeat automatically. Later public CDN/GreatList/TSUM/channel routes worked. **PR72 used no scraping-provider credits and no source account authentication.**

## Priorities and concrete remaining work

Prioritise **programmes with little useful coverage**, not isolated unexplained URLs in well-covered catalogues. Establish what a normal user sees. Old sitemap entries, login pages, obsolete PDFs and unlisted cards are not automatically missing current offers. Registry now has **111 routes**, not111 independent programmes. The earlier105-route historical audit found Alfa's exact bank route the only never-positive route; no historically10+-item route had a best normalization ratio below80%. Those are not independent complete programme denominators. Failed alternate probes do not erase successful coverage; NORDWIND previously had7/7 visible cards, and RZD/Aeroflot/EKP substantial alternate/public coverage.

**Highest-value Alfa remainder:** a genuinely distinct readable app/bank catalogue route; source-owned practical non-restaurant merchant conditions discovered from the announcement leads; and a dependable current-PDF revision index with reviewed migration. **Automatic new-PDF revision discovery is not implemented by PR72.** Preserve exact-URL revision warnings. Generic continuation does not authorize bank authentication/SMS forwarding or private session publication.

**Other historical residuals, not re-audited by PR72:**
- HSE55 listed/52details/3previews:skyeng,skillcup,academiya. PR64 fixed mordapechat ownership; studio15%/HSEALUMNI remains separate from KubKvadrat10%. Preserve expired MA-MA2026-01-01/Gruzovichkof2025-12-31 and Sila Vetra10% SV20/HSExSilaSport10/end2026-12-31 separately from its August-only20%. Full payment100% is not a100%discount.
- Mir/Privet previously184/184 unique Moscow+SPb offers across four regional catalogues; later observations can add rows, including MEOLLO. Not all regions/personal offers. T2 Selection public layers do not include every account privilege.
- Rostelecom `press/news_fill/d476187/` timed out during policy retrieval; indexed `press/REGIONALNEWS/d476187/` remains an untested replacement. Existing two records retained. Uralsib success35378598217 then failure35379313650 remains intermittent.
- RZD eight historical full-detail gaps with previews; two import failures also met provider423 and six prior login/insufficient-content pages are not simple selector bugs. SacvoyagePR62 own5% registration/10% referred stay is separate from RZD15% expired2025-12-31. Prize-winner announcements are not coupons. Do not repeat unchanged whole catalogues.
- EKP110 protected observations/106names versus935 historical public records among1045entries. Region98/All regions is not automatically region78. iLockedPR61, ArtFlora/LitresPR60 and stored announcements are public alternatives, not authenticated recovery. FlyStation public page read, no released adapter; independent merchant sites not exhaustively searched.
- Coral69 listed offers reconciled across separately dated reads(latest19/20categories plus earlierGadgets); five sitemap omissions already stored. MegaFon/BookingCar expired2025-12-31. ALEF public10% page read, UI-list absence/current issuance unresolved. Do not repeat inventory reconciliation or expand into full contracts.

## Operation, privacy and recovery

The practical task is **“Do I have a discount here, how much, and how do I use it?”**, not exhaustive document archiving. Keep benefit/scope, literal code/redemption, programme/partner/tier, material restrictions, exact URL and observation time. Unknown stays unknown. Short useful PDF clauses are allowed; full contracts/manuals/pricelists, unrelated appendices and recursive OCR are not routine scope. No canned rates, invented summaries, silent truncation or row-count inflation.

Use existing GitHub schedules, Free ScrapingAnt where needed, Google WIF and shared serial publication. No paid service, rented/admin server, always-on user computer or second provider account. Preserve budgets, timestamps and native IDs. Generic OCR installation is not a reason to OCR readable text. Shared validator/normalizer pushes can launch unrelated source workflows: PR71's Aeroflot incident and cleanup35434246971 are already resolved; PR72 avoided that push-triggered crawl without disabling schedules. Do not redo the cleanup.

Coral registration is complete, not an EKP/RZD/bank session. Aeroflot permission is owner-reported, not a global host-policy override. Reading does not authorize coupon issuance, activation, booking, purchase or bonus spending. The repo is public; earlier Sheet ACL was anyone:writer, not re-audited here. `private_complete` is a normalizer mode, not access control; hidden tabs are not private storage. Never put tokens, OTP, sessions, auth cookies, private bank data, personal coupons or authenticated-only terms into public artifacts/link-accessible Sheets. Authenticated collection requires separately authorized access and private storage.

PR56/57 practical cleanup is complete:64 bulk records reversibly archived, source cells cleared without moving rows, useful benefits/codes retained. **Do not repeat this migration.** Aeroflot bulk linked-rules is a manual no-op; practical Coral/lounge, RZD tour/bank, EKP HTML and Utair clauses remain in scope.

The complete preceding PR71 checkpoint is preserved byte-for-byte at **a40d90fdb9592fce24ae8b503c28bf31fd52f129:loyalty/COVERAGE_CURRENT.md**, blob **74bd430ddf10779ca600c506e528dfa4bc0e14b2**. It retains earlier exact PR64/71 evidence and recovery links. Durable acceptance files also include SOURCE_REPAIR_ACCEPTANCE.md, HSE_ALFA_ACCEPTANCE.md, ILOCKED_PUBLIC_ACCEPTANCE.md, PRACTICAL_SCOPE_ACCEPTANCE.md, PRACTICAL_FRONTIER_ACCEPTANCE.md, RZD_ANNOUNCEMENT_ALTERNATIVES.md, EKP_GATED_AUDIT.md, EKP_TARGETED_PUBLIC_AUDIT.md, RZD_EXTERNAL_ACCEPTANCE.md, RZD_PREVIEW_ACCEPTANCE.md, AEROFLOT_ACCESS_STATUS.md and AIRLINE_COVERAGE.md. Historical bulk evidence is not a mandate to resume it. Artifacts expire; source/run/code identities persist in Markdown. Interrupted chat output is not rollback: inspect current main, runs and destination before rebuilding.
