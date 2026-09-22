# Current coverage — practical discounts, 22 September 2026

## Latest accepted release: PR79, published and independently verified

Read **RELIABILITY_PUBLICATION.md** for actual main execution, exact code/payload identities, destination comparisons and remaining limits. **RELIABILITY_ACCEPTANCE.md** preserves diagnostics, implementation contracts and final regression; its pre-publication boundary is superseded by the publication report. Do not repeat completed probes or start another crawl just to restore context.

PR79 merged at2026-09-22T16:41:38Z as **d8143b362256512f9b10ffe651f33194447b9ede**, reviewed head **bbd42c261e46f498b72db8e7bda45b22caea1329**. Merged state was independently read back. Final regression **35755005927**, implementation **ec63a34a709bd51eb0dd979d86233828d5ced050**, passed **1206 Python +7 KEY tests**, no skips, and all201 actual-record replays. Only the acceptance document and removal of temporary files followed accepted production bytes before merge.

Actual main **35755985550:1**, execution **73175279fd8c43e18c4e6306346613b010e4c9d9**, freshly collected at **2026-09-22T16:44:49.142888+00:00**. The three jobs collect106841762779, source-health106845143475 and publish106845143596 all completed successfully. Each source outcome and the final destination were independently read; green collection alone was not treated as source completeness. All82 actual Python manifest hashes match the accepted implementation.

| Source | Accepted current observation | Coverage boundary |
|---|---:|---|
| **Backit — денежный кешбэк** /backit_public | **178**, zero errors |916 unique listings/23pages/189 eligible details accounted for.738 exclusions:677 source-disabled,50 acquisition ads,10 expired promotions,1 detail replaced by catalogue. No product-level marketplace data. |
| **Club Avolta** /club_avolta_public | **17**, zero errors |17 source-linked Russian cards/six categories.16 full cards plus a partial DragonPass restaurant-only component; no asserted lounge fee or restaurant redemption instructions. |
| **Мантера Моменты** /mantera_moments | **6**, zero errors |Five public FAQ tiers plus one confirmed hotel, Mantera Resort & Congress. Not six hotels or the full six-partner inventory; hotel redemption is not confirmed. |

**Current destination:3012 parser /3660 current common /3046 cleaned reader records.** True pre-state was3007/3655/3041. Five IDs added,196 refreshed;201 source upserts;zero real holds needed in this refresh. All3046 visible rows/42644fields matched the cleaned catalogue. Source/report5067fields, common20128fields and source-reader3417fields were independently checked. Previous unrelated source/history positions, manual annotations and semantics, eight original formulas and visibility were preserved;zero formula errors. The native A10 search formula and C6 explanation were intentionally upgraded and separately read back.

Current generation: **d1a66a14bf1606612dc931b98d85af92ecdc7c26dbff7f9ab195fb5e8226969c**.
Source fingerprint: **83780c2233bc5096809218942124d6f9e8782fe1f7f8790fdca0d0b3514d414a**.
Reader digest: **faa0422fa7d92e2fac1bad4dcbd7d5b10baef65e397803b1b305af5f0d31e9a1**.
Future verified publication can change counts and hashes: read live manifests instead of restoring an old chat checkpoint.

## Reliability and interpretation contracts

**Avolta transport:** ordinary same-origin HTTP replaced its source-local headed browser. Feature35753691428 and main35755985550 independently completed the full catalogue without source errors. This is two successful traversals, not guaranteed long-term uptime. Shared scope, verified TLS, bounded transient retries and access-refusal stops remain. No proxy, credentials, header rotation or Browserbase dependency was introduced.

**Reversible source holds:** Backit/Avolta publish a bounded exact inventory with named exclusions. Only a successful complete same-time inventory accounting for every unique URL can withhold an old excluded/absent card. Empty/failed/partial reads cannot prove disappearance. Original row, source text and offer observation time remain; operational checked_at/run metadata is separate. Fresh accepted evidence removes the hold. Older incoming evidence cannot overwrite newer observations/holds. Concurrent managed-value checks and trailing manual fields are preserved. Zero real holds happened in this publication; test transitions are not claimed real source changes.

**Freshness:** the reader and native search apply an internal **7-calendar-day observation-age limit only to Backit, Club Avolta and Mantera parser records**. It is not a source expiration date. Source evidence remains available in technical storage, but stale observations must not be offered as current. Native TODAY filtering works when Sheets recalculates even if CI does not publish. Global recalculation settings/timezone were not changed; no exact unattended midnight recalculation is claimed. A read-only counterfactual against196 genuine old records confirmed retention at7days and withholding at8days without changing real Sheet dates.

**Health:** the existing loyalty.yml now has a read-only source-health job evaluating the actual artifact for these three integrations. It makes the overall run fail on unhealthy selected sources; the publisher still depends on collect, not source-health, so other successful sources may publish. No ChatGPT notification task or user-notification setting was configured. Do not confuse health failure with failure to publish every successful source.

**Schedule:** existing daily **05:23UTC /08:23Moscow**, shared serialized publication, no new recurring workflow or rented/always-on server. First future timer-triggered execution after PR79 has not yet been observed. Controlled production runs succeeded. No paid provider, source login, issuance, activation, booking or purchase was added.

## Coverage findings and unresolved boundaries

**Backit promotions:** three of13 formerly withheld panels cover the observation date: Все Инструменты, Xcom-Shop, Плати по всему миру. Ten are already expired. DD.MM dates lack a written year; use only the matching current month/year in the page title and visibly flag **promotion_year_inferred_from_current_page_month**. This is a disclosed inference, not a site-written year or a guarantee against stale site copy. Preserve fixed RUB, ranges, customer/order scopes, zero-rate restrictions, coupon clauses and conditional confirmation. Never revive crossed-out base rates or present cashback as an upfront discount.

**Backit marketplace:** tested old Ozon/Wildberries compilation routes and mixit-ozon returned302 to the general catalogue; Roborock-Ozon returned200 with explicit temporary cashback unavailability. Do not import cached historic offers as current. Product-level marketplace coverage remains unavailable through those checked routes.

**DragonPass:** headline31USD and body28USD still conflict about lounge admission. Its consistent restaurant discount up to25% is independently retained as partial. Lounge fee and restaurant activation remain unknown/withheld; instructions for entering a lounge are not restaurant instructions. Country, tier, frequency and personal eligibility cannot be inferred from membership alone.

**Mantera:** the hotel-owned public page confirms Mantera Resort & Congress earns under the programme. Tier earning rates and qualification scopes are recorded; general programme spending caps do not establish that this particular hotel permits spending. Some objects only earn; some also redeem. The group landing says six partners without a complete named inventory; /app/partners redirects to sign-in and was not followed. The existing FAQ calendar-versus-business accrual-day discrepancy remains explicit. No account or personal entitlement was checked.

## Everyday lookup: clean reader, not raw technical records

Destination is **скидки**, spreadsheet **1uFR7croj7p6RRNPcoTRYlVl06hKsurkIgyu1IdMMB-4**.

- Visible **Скидки**, sheetId2026092001: B3 keyword/code, B4 programme, B5 category. No B6/B8 return-junk controls. Empty filters show accepted records subject to the current freshness predicate.
- Hidden **_ui_catalog!A:Q**: partner, programme, benefit, code/retrieval, activation, conditions, source period, category, observation time, source link, comment, record type, validity status, ID, input tab, input row, original title. Its materialization has an as-of date; consumers must also honor freshness at their own lookup date.
- **_ui_catalog!Y1:Z8**: require Z2=verified, Z5=normalization_audit!J7; normalization E7=verified,I7=current. Z4 is the materialized reader count, which may exceed a later freshness-filtered native search result.
- Visible **О таблице**: instructions and programme-list formula. Only these two sheets are visible; hidden tabs are not access control.

parser_offers, normalized_records, normalized_benefits, normalized_conditions and normalized_codes are ingestion/provenance layers. Their current normalization status is NOT source freshness, practical acceptance, current availability or user eligibility. Never restore raw posts, placeholders, polls, general advertising or whole contracts to inflate coverage. Preserve distinct programme, source/native identity, branch, region, tier, customer type, payment channel, literal code and dates. Unknown deadlines stay unknown. Partial benefits must keep their limitations.

PR77's source-owned clean-reader policy remains active: do not restore a checkbox for junk. The five original input datasets and14 original technical/history tabs are preserved; ingestion may add rows. Do not manually delete/shift old rows because legacy IDs depend on input row position. The obsolete R:X helper stays cleared. Original eight formulas remain intact; native XLSX DUMMYFUNCTION spill exports are not the actual search formulas.

## Earlier sources and recovery

**Konsierge /PR75** remains in daily collection, historical accepted159public records. See KONSIERGE_RECURRING_ACCEPTANCE.md, KONSIERGE_CATALOG_ACCEPTANCE.md and KONSIERGE_PUBLICATION_ACCEPTANCE.md. Its owner-approved source-local robots exception does not change other transports, TLS or access checks. Konsierge is not the entire user's Only Assist catalogue. The APK/emulator/device investigation is separate; do not repeat completed app diagnostics or pretend these public-source releases provide authenticated Only Assist content.

Alfa/GreatList/TSUM, HSE, Mir, RZD, Aeroflot, EKP, Coral and other older source implementations were not expanded or globally stabilized by PR79. Failed spare routes can coexist with successful programme coverage. Prioritise practically missing programmes and usable conditions, not route counts or whole-document archiving.

The complete **pre-PR79 checkpoint is preserved byte-for-byte at73175279fd8c43e18c4e6306346613b010e4c9d9:loyalty/COVERAGE_CURRENT.md**, blob **7cd2da859742282ff9c9cf59246848470a5bf83f**. Read it with AFFORDABLE_SOURCES_PUBLICATION.md and AFFORDABLE_SOURCES_ACCEPTANCE.md for PR78 provenance. Its former no-retirement statement,175/16/5counts and Avolta renderer boundary are superseded above.

The complete earlier source checkpoint remains at **22241f9a964f9af84e48ee730f583289c4c9d034:loyalty/COVERAGE_CURRENT.md**, blob **d341b85d7fde65dd07efe333f062f5851d92e750**. It links prior programme counts, incomplete paths, budgets and acceptance reports. Its old raw-normalization lookup guidance is superseded by the clean-reader contract. PR77 cleanup evidence remains CATALOGUE_QUALITY_ACCEPTANCE.md and CATALOGUE_QUALITY.md. PR56/57 bulk-record migration and earlier Aeroflot cleanup are complete; do not repeat them.

## Privacy and recovery

The repository is public. Never commit/upload private workbook exports, bank data, personal coupons, tokens, cookies, OTP or authenticated-only terms. Hidden sheets and private_complete normalization mode are not ACLs. Private exports remain local; only aggregate audit results and public source evidence may be shared. Existing Free ScrapingAnt/Google WIF/shared queue remain; no new paid services/provider accounts or always-on user computer.

Artifacts expire; accepted source/run/code identities in Markdown persist. Interrupted chat output does not roll back merged code or publication: inspect main, actual runs and live destination before rebuilding. Reading public offers does not authorize source registration, coupon issuance, activation, purchases or spending bonuses.
