# Normalized loyalty sources (schema v2, adapter 2.2.0)

The canonical run output is `loyalty-output/normalized.json`: `schema_version`, `run_id`, `observed_at`, `records`, `sources`. `offers.jsonl` is one normalized record per line. `coverage.json` and `summary.md` distinguish discovered, normalized and failed observations.

## Scope and source routes

The registry `sources_normalized.json` includes all programs in the live loyalty source audit, the additional Loyals source, existing KEY collector and explicitly labelled partner-page fallbacks. Multiple URLs/program tiers/campaigns are **not** counted as different unique partner programs.

- S7: public `__NEXT_DATA__`; deduplicate native offer codes, follow the actual `priorityRulesUrl`, extract only that partner's `priorityDetails`. The page H1 is not a partner name. `otherOffers`, auth state, client state and tracking `outLink` are never copied.
- Mir/Privet: observe the anonymous regional catalogue JSON request and replay only its same-origin read-only filter pagination; fetch `promoDetail.promo.promoAction`. Preserve dates, payment badges, source flags and named conditions templates. The default region and catalogue count are reported. Do not treat this as every offer in every Russian region or as a personalized-account catalogue.
- Ural Wings: public partner array from the observed `ajax=partners&action=default` endpoint; fallback to actual `li#partner_*` blocks. Preserve each partner's separate text, category, city IDs and tier tables.
- Moskvich: `.lpp-card` name and terms in the same block.
- No Name: native record/element IDs and aligned card geometry, not DOM text order. Ambiguous pairings fail rather than moving the next partner's benefit onto this one.
- RGO: exhaust its span-based load-more control, then parse individual pages. The full `.section-text__inner.text` content is preserved, not merely contact/summary sections. The Beeline image-PDF uses a separately declared digest-bound visual-review profile; changed bytes require a new review.
- AZIMUT: status-table columns retained separately from summary cards. Image-coded unavailable amounts are not guessed. A summary card does not make a platinum privilege universal.
- Museum Friends: published plan names/prices and corresponding benefits; membership plans remain a distinct record kind. The three explicitly named external partners are also represented separately with eligible plan names; their 10% discounts never inherit the 15% museum-program rate.
- MEDI / Neva Travel: named partner-page fallbacks. These do not certify completeness of the EKP or SOGAZ catalogues.
- Promo Miles: distinguish campaign announcements and archived sections from current partner offers.
- KEY: run the existing `key/refresh.mjs` live, check the resulting observation timestamp and adapt its structured snapshot. Do not relabel a checked-in old snapshot as a fresh scrape.
- Other registry URLs: bounded anonymous access probes. Failure/status and `adapter_not_yet_implemented` remain explicit; no generic whole-page extractor invents normalized partner records.

## Additional reviewed routes (2.1.0)

`partner_pages.json` defines **14 exact public partner URLs** with reviewed selectors, program identity checks and stable partner-name mappings. Eleven are Aeroflot partner pages, two are RZD hotel pages and one is the EKP/Rostelecom announcement. These are not an extraction of the blocked main program catalogs. Every such record has `details.source_scope=reviewed_partner_page_not_program_catalog`. The coverage registry retains the blocked main sources separately.

Utair's accessible `media.utair.ru/status` partner panel is parsed by each rate-bearing anchor's own destination, not by nearby advertising legal-entity names or global text order. Five known destination domains identify the partners; an unknown domain fails closed pending identity review. The public tier-specific Otello rate sentences remain distinct in `details.tier_rates`. Only that partner panel is covered, not Utair's full rules or all status benefits.

Mileage normalization supports `13% милями`, an intervening accrual verb, and reversed `За каждые 60 руб начисляется 1 миля` wording. Percentages used for spending miles are not reclassified as earned-miles percentages. Inline bold/link markup does not split a spending denominator from its mileage value. The source spelling `милz` is deliberately retained and not silently corrected to a typed mileage rate.

Askona's base earning rule and explicitly dated multiplier are separate records. A past temporary multiplier is marked expired while the base offer has no invented overall expiry. MEDSI/Taivas/Grether labelled periods are extracted separately from publication dates. EKP/Rostelecom new/existing customers are separate records; the article publication date is metadata, not an offer deadline, and the new-customer lifetime claim is not copied into the existing-customer benefit.

Transient read-only 502/503/504 requests get at most three attempts with bounded backoff. Authorization failures, 429, CAPTCHA and a server `Retry-After` instruction are not immediately retried. Queue waiting no longer consumes a source's 420-second network budget. Robots/network/TLS/access failures are still not interpreted as empty catalogs.

## T2 and source-quality corrections (2.2.0)

- T2's normal browser loader can return an initial HTTP 503 and then replace the main document with HTTP 200. The transport observes the **final main-document response**, with a finite wait only on the reviewed T2 host. It does not click challenges, activate offers, sign in, provide SMS codes, alter TLS verification, or use external proxies.
- Robots are parsed with pinned Protego 0.6.2, including wildcard rules, longest-match Allow handling and crawl/request-rate intervals. A failed robots request still fails closed. Query-card URLs are not crawled around a wildcard restriction.
- T2 «Больше» records come from the allowed public root page's **own anonymous catalog response**. No additional API query is sent by the production adapter. IDs, company display names, complete agreement text, explicit expiration timestamps, categories and eligibility flags remain separate. This is the Moscow/Moscow Oblast anonymous response, not every regional/personal catalog. Direct card URLs are not fabricated or marked independently verified.
- The public MiXX M help page is divided into prepared choices, selectable replacements, automatic inclusion and fixed benefits. Its six selection slots do not make every listed service simultaneously available. Selection's short Premium card remains a summary rather than an invented full benefit catalog. Speaker bundle terms and the archived powerbank campaign retain their own periods.
- RGO's older fixture omitted the actual content wrapper. Real captured DOM regression fixtures now check the full benefit and conditions. Etnomir's explicit 31.12.2025 deadline is recognized. The fresh Paddock page currently states only the room discount; a gift from an older cached page is **not** carried forward without live evidence.
- The Beeline PDF is image-based. `reviewed_pdf.py` contains a human-readable visual-review profile locked to the full PDF SHA256 and exact URL. It publishes only after each live download matches; a replacement PDF stops publication of this record pending review. This is not general-purpose OCR and not automatic understanding of arbitrary future PDFs. Monthly prices, included tethering and the separately priced option are distinct; the filename date is not an offer expiry.
- One exact Domina Pulkovo partner-owned page adds limited NORDWIND CLUB coverage without claiming that the blocked airline catalog is collected.
- `details.lexical_conditions` contains only recognized minimum-purchase, maximum-benefit, first-purchase/new-customer references and stacking clauses, each with its complete evidence clause. These are **references**, not a complete global eligibility decision: exceptions in the same clause and all original conditions remain authoritative. Tariff/subscription prices are not purchase minima or discount amounts.

Public fixtures include only reviewed source blocks/objects, never personal sessions or the destination spreadsheet. Existing data boundaries, WIF credentials and disabled scheduling gates are unchanged.

## Record contract

`id` is SHA256 of `source_id + newline + native_id`. Prefer a native offer/card ID; same S7 offer under `/city/` and `/partners/` is one identity. Missing source-native identities use a documented stable name/text key, never the observed discount amount as a key for a known partner.

Useful fields: `program`, `partner_name`, `record_kind`, `title`, `category`, `benefit_text`, `conditions_text`, `redemption_text`, `benefit_types`, `rates`, `promo_codes`, `valid_from`, `valid_until`, `validity_status`, `source_status`, `source_url`, `benefit_url`, `link_kind`, `locator`, `tables`, `details`, `warnings`, `observed_at`, `adapter_version`, `content_sha256`.

- `partner_name` is null when a display name is not safely obtained; its native code/source description remains available.
- Every extracted numeric rate includes its exact local evidence clause, kind, decimal-string value, unit and qualifier. Mileage rates preserve the spending denominator. A purchase minimum is not a discount amount. **Rates are lexical extractions, not a complete pricing/eligibility engine; never sum unrelated rates or convert miles into cash.** Full conditions remain authoritative.
- Dates are typed only from explicit structured source date fields or a reviewed labelled interval within the precise partner terms block. A year in a copyright, campaign URL, display banner or unrelated card does not become an offer expiry. `null` means unknown/not stated, not unlimited validity.
- `source_status` records publication flags; `validity_status` is a separate date comparison. Neither confirms the user's eligibility or checkout success.
- Shared-page blocks have `benefit_url=null` plus the real `source_url` and a block locator. Actual anchors and source-published individual URLs are retained; unique URLs are not invented for cosmetic completeness.
- `tables` and source-specific `details` keep information that must not be flattened into a universal percentage. Unknowns remain explicit.
- `content_sha256` covers the normalized record including source text/conditions, excluding observation time, hash itself and run ID. This is an integrity check, not cryptographic proof of website authorship. Source markup is reduced to relevant public card fields; no whole-page sessions are exported.

## Publication / existing data

The current workflow automatically upserts **only** `parser_offers` (A:Y managed, Z manual comments) and `parser_coverage` (A:N managed, O manual comments) in the existing configured spreadsheet. The curated benefits, source audit, Yandex/VG and old v1 `parser_inbox` / `parser_runs` are not rewritten. Those old v1 tabs are retained as historical diagnostic evidence, not the current normalized feed.

Writes use literal `stringValue`, are ID-idempotent, retain missing observations, reject unknown sheet schemas and read back after the final write. Missing/failed scraping does **not** expire or delete prior offers. Consumers must inspect observation date and latest source coverage before using an older row. Manual comments are outside managed columns.

The existing WIF/service account configuration is reused. Collection has no Google credentials; publication is isolated to trusted main and explicit enable flags. Schedule remains opt-in and is not activated by this code. Request-file dispatch now uses a 200-detail-page per-source cap; successful count-reconciled sources are distinguished from capped or partial ones.

## Run / verify

```sh
python -m pip install -r loyalty/requirements.txt
python -m unittest discover -s loyalty/tests -v
node --test key/refresh.test.mjs
python -m playwright install --with-deps chromium
python loyalty/collect_normalized.py --limit 200
python loyalty/sheets_normalized.py --input loyalty-output/normalized.json
```

The last command is a dry run. Live publication adds `--publish` and requires the existing short-lived Google token environment. Do not send tokens, personal browser state, spreadsheet exports or private corporate offers to the public repository/artifacts. Public artifacts expire after seven days; persistent history beyond the sheet's retained rows is not implemented.

Tests use small hand-checked fixtures of observed source structures, with synthetic negative canaries. They cover shifted partners, ambiguous No Name geometry, mixed mileage/discount units, purchase thresholds, archived headings, duplicate rows, tampering, readback mismatches and preservation of trailing manual columns. Local tests do not prove live source accessibility or completeness; use concrete Actions artifacts and independently read the destination after each production change.
