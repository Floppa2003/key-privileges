# Coral free Google-import coverage — accepted 2026-09-16

## Completed result, not a diagnostic-only claim

PR43 merged at `7e3810daba74619228651aef9c85d6c33a7de4f2`. Trusted-main run **35119476496:1** used that exact commit. Regression, collection and publisher job **104878403157** completed successfully. The SAME discount workbook received **87 source records: one new record and 86 updates to existing records**. No ScrapingAnt credits, source account, new key, paid service, rented machine or personal computer were used.

| Source scope | Discovered | Accepted records | Explicit store exclusions | Unresolved |
|---|---:|---:|---:|---:|
| Club sitemap pages under the current 20 categories |101|64|35|2|
| Current promo-index links |23|23|0|0|
| Total |124|87|35|2|

The 87 records comprise 63 `partner_offer`, 23 `campaign` and one `source_observation` for the gift-certificate information page. They are not 87 new or necessarily active discounts. The 35 exclusions are ordinary merchandise pages whose purchase structure was actually read; the failed blue umbrella page is not counted as a verified exclusion.

The only newly added identity is **ALEF**, `https://coralbonus.ru/klub-privilegii/odezhda-i-aksessuary/alef/`, source title `Скидка 10% на верхнюю одежду от фабрики "ALEF"!`. Its page says the offer applies in the online store and can be combined with other promotions; obtaining the code requires sign-in. These are source clauses, not independently tested checkout eligibility. No expiry was stated or inferred, and no code was issued.

## Discovery and interpretation boundaries

Each run reads the current robots document, club root, promo index and advertised `https://coralbonus.ru/sitemap/`. The current root returned 20 categories. Only same-host three-segment detail URLs belonging to those actual category paths are selected from the sitemap. Promo pages come from the current index, not the sitemap's archive. There is no fixed partner list or old page fallback.

**Sitemap presence is not proof that an offer appears in today's interactive catalogue or is active.** Club records explicitly preserve `active_catalogue_listing_verified=false` and `sitemap_presence_does_not_prove_active_catalogue_listing`. Parsed conditions and dates remain source evidence; eligibility, external documents and actual redemption are not inferred. The source owns category membership; unrelated sitemap areas are not crawled.

Seven previously stored club pages are absent from the current sitemap: Megafon, BookingCar, Name Skin Care, Maridzhental, Geltek, Feedback and Styx Silk Body. The previous records are retained with their prior observation times, not deleted or automatically expired. Some have explicit historical expiry dates, but absence itself is not expiry evidence. The existing provider collector remains enabled because its current interactive catalogue can cover pages omitted by this sitemap path. It was not replaced or given a smaller quota in this release.

Both unresolved reads returned `cg_import_timeout_or_error`:
- `https://coralbonus.ru/klub-privilegii/nedvizhimost/blue-zone-yalikavak/`
- `https://coralbonus.ru/klub-privilegii/suvenirnaya-produkfiya/zont-sinii/`

This is not an origin HTTP status, deletion finding or permanent-access verdict. All 23 current promo pages were read successfully in this pass; the old 24th promo remains historical unless another source path updates it.

## Implementation and privacy

Only three files were added: `loyalty/coral_import.py`, `loyalty/tests/test_coral_import.py` and `.github/workflows/coral-import.yml`. The reader reuses the released Coral HTML mapper and sanitizer, existing short-lived Google WIF authorization, literal parser upserts and unified publisher. It uses only its exact public scratch tab `coral_public_fetch` in the existing public staging workbook, never the original private source tabs.

Every import checks workbook/tab/dimensions/marker, idle state, literal formula, generation and two stable typed-string reads. Numeric coercion, unexpected columns, altered formulas, wrong canonical identity and out-of-scope URLs fail. Cleanup is performed and read back after each request, including exceptions; per-observation checkpoints retain diagnostic evidence. Source robots and applicable delays are checked. Limits are 164 imports, 160 candidate details, 2700 seconds and at least five seconds between imports. Future larger/slower catalogues can remain partial; finite bounds are not completeness guarantees.

The publisher reconstructs every accepted record and the source count/scope/exclusion summaries before obtaining destination credentials. Public artifacts contain sanitized HTML or sanitized sitemap URLs, not raw scripts, forms, session inputs or source-account responses. `typed_lines_sha256` records the pre-sanitization calculation hash; those exact raw lines are not archived and cannot be independently regenerated from the sanitized artifact.

Google imports expose calculation results, not origin HTTP status, redirect history or origin cache age. Observation timestamps identify the import request/calculation interval, not independently certified uncached origin downloads. Two stable local reads do not remove Google's source-cache uncertainty.

No account authentication, personal coupon issuance, bonus spending, purchase, source-permission expansion or Google permission change was performed. The destination's earlier `anyone:writer` finding remains a boundary: account-only data must not be added without resolving destination sharing. `private_complete` is a normalization mode, not an ACL.

## Actual execution and tests

Source calculation interval: **2026-09-16T16:04:54.066827+00:00 to 16:17:44.099702+00:00**. There were 128 import attempts: four controls and 124 candidate details. Source accounts=false; ScrapingAnt credits=0; final cleanup=true.

**736 Python tests and seven KEY tests passed in both final branch run35119039065 and main run35119476496, without skips.** Seventeen new tests cover source changes, exact discovery and canonical identity, store exclusions, real typed-cell polling/cleanup through an in-memory HTTP boundary, coercion/wide-spill rejection, source-to-bundle reconstruction and rejection of inflated coverage. Thirteen local reader/mapping tests passed; a full successful local suite is not claimed because Protego was unavailable.

Both final test ZIPs and the production ZIP were downloaded, SHA256 and ZIP CRC checked. The actual three changed files in the main archive match the reviewed branch files:
- `loyalty/coral_import.py`: `1aec9849c6f54e5d1be46922a524b1660d746a2e3ad0a07808406d1174b1aaba`
- `loyalty/tests/test_coral_import.py`: `52e6a09c633d8484d1fcfccb0582c5bbb3be9f1dbca1347617ec4ea18254d8fa`
- `.github/workflows/coral-import.yml`: `442d17a7d451cefac663b949da4574fb8fee5b4fdaab0d5aac1eb0aad54555f0`

| Artifact | ID | SHA256 |
|---|---:|---|
| Public production |10457895053|741a4ef73250cd513d307728c197dc2a6d8e3009d0569049ad3d5de0211807a8|
| Main tests |10456802843|40ab78d10eb30fe5d413a58ddc645f7fa641d20163faa4e55f73ac0f8910d303|
| Final branch tests |10456867177|0aa175c9543a2d812047d0c47c607c769e8772a23fba7695166cde923619662c|

Run: https://github.com/Floppa2003/key-privileges/actions/runs/35119476496

## Independent destination verification after the final write

Destination remains `1uFR7croj7p6RRNPcoTRYlVl06hKsurkIgyu1IdMMB-4`, title `скидки`.

The final destination was exported after the publisher completed. A read-only independent OOXML comparison reconstructed all 87 accepted records from the sanitized current observations and compared all 25 managed fields per source record plus all 14 fields in the two new coverage rows: **2203 managed fields matched**. All other parser rows, their old dates/text and manual cells were unchanged; old coverage rows were preserved. Every accepted record was present in the current unified generation. This does not certify the semantic truth of every source clause or every cell of the private workbook.

Native Sheets checks additionally read:
- **`parser_offers!A2460:J2460` and `W2460:Z2460`**: ALEF title, source terms, login requirement, ID, hash, observation time and run. New manual cell remains blank.
- **`parser_coverage!A1278:N1279`**: club101/64/2 partial and promo23/23/0 ok, with the exact two failed URLs.
- **`normalized_records!A3108:F3108` and `AA3108:AC3108`**: the same new record identity/current generation and normalizer's existing top/wrap/10pt style.
- **`normalization_audit!D7:J7`**: `verified/current`, **2459 retained parser records / 3107 unified records**. Overall current terms:3605 benefits,10121 conditions,117 costs,651 code records. These are retained totals, not all freshly read in this run.

ALEF ID: `c4e8f5d9e45a4b3c7f3f6e83ca0aabada491a4845b2348ae9a950b5b9e92e061`.
ALEF source hash: `e8be0978e5a7a26d94014c08fa8f015f273196784c3dda959886bdf9e53ac921`.
Final source fingerprint: `3544f73909ddbd005754d872b6cff5e9a7146360ada9132f7c40402269d10785`.
Final generation: `88fe7aa48d0d09d00f8475380e39193856bcb503168fd011442ac2e373e23a6c`.

A local artifact_tool render attempt timed out while importing the workbook; no rendered visual audit is claimed. Native formatting/structure samples were checked; the existing workbook was not restyled. No private workbook export is attached to public evidence.

The complete Coral scratch rectangle was read after collection: only its header and `idle:35119476496:1` remained. Temporary discovery and RZD gate-probe tabs were removed and final workbook metadata read back. Existing RZD/Aeroflot scratch tabs were not altered.

## Regular free operation

The new supplementary workflow runs **Wednesday and Saturday09:17UTC /12:17Moscow**. It traverses the current sitemap-selected pages across all current categories, rather than alternating halves. It uses **zero ScrapingAnt credits**. Existing provider, direct-source, EKP, RZD and Aeroflot schedules and budgets remain unchanged. This accepted run was a trusted-main push; future cron reliability is not proved by one completed pass.

## RZD: six formerly generic failures are now identified login responses

No new RZD discount conditions were published in this continuation; accepted terms remain66/74. A public raw-HTML read of the Sakvoyazh impressions offer returned a main-content login form, not merely a global header login link. Five scoped public IMPORTXML reads then extracted only the main form's action, its return path and its `Вход в РЖД Бонус` heading. In all six observations both form paths matched the exact requested offer URL:

| Offer page | Source path |
|---|---|
| Sakvoyazh impressions |/promo/skidka-15-na-prozhivanie-v-otele-sakvoyazh-vpechatleniy/|
| Admiralteyskaya |/promo/skidka-18-na-prozhivanie-v-gostinitse-admiralteyskaya-pri-bronirovanii-na-ofitsialnom-sayte/|
| Hilton Garden Inn Volgograd |/promo/skidka-15-po-promokodu-na-prozhivanie-v-otele-hilton-garden-inn-4-gorod-volgograd/|
| Chekhoff |/promo/15-skidka-v-chekhoff-hotel-moscow-curio-collection-by-hilton-g-moskva_2026/|
| Station Hotels |/promo/skidka-16-na-prozhivanie-v-seti-oteley-station-hotels-v-sankt-peterburge/|
| Airo |/promo/1500-ballov-rzhd-bonus-i-skidka-25-na-pervyy-zakaz-ot-airo-ru_summer_2026/|

The robots document was read again, and separate RZD source requests respected its20-second delay. Forms were only inspected, not submitted. No credential, account session, issued code or private term was collected. The inference is limited: **the observed anonymous response requires sign-in to proceed to those conditions**. This is not permanent technical impossibility and not a successful authenticated read. Production RZD's earlier coverage rows were not rewritten to masquerade as a new full run.

The other two failed pages, Renaissance Smart Plus4000points and Grand Karat Sochi2026, were not retried here. Their earlier Google `Resource at url not found` messages remain unresolved, not proof of origin404/deletion/expiry. Repeating HTML selectors against the six login responses is not the next useful step; permitted account access and safe destination handling would have to be investigated separately.
