# Normalized loyalty sources (v2)

The canonical run output is `loyalty-output/normalized.json`: `schema_version`, `run_id`, `observed_at`, `records`, `sources`. `offers.jsonl` is one normalized record per line. `coverage.json` and `summary.md` distinguish discovered, normalized and failed observations.

## Scope and source routes

The registry `sources_normalized.json` includes all programs in the live loyalty source audit, the additional Loyals source, existing KEY collector and explicitly labelled partner-page fallbacks. Multiple URLs/program tiers/campaigns are **not** counted as different unique partner programs.

- S7: public `__NEXT_DATA__`; deduplicate native offer codes, follow the actual `priorityRulesUrl`, extract only that partner's `priorityDetails`. The page H1 is not a partner name. `otherOffers`, auth state, client state and tracking `outLink` are never copied.
- Mir/Privet: observe the anonymous regional catalogue JSON request and replay only its same-origin read-only filter pagination; fetch `promoDetail.promo.promoAction`. Preserve dates, payment badges, source flags and named conditions templates. The default region and catalogue count are reported. Do not treat this as every offer in every Russian region or as a personalized-account catalogue.
- Ural Wings: public partner array from the observed `ajax=partners&action=default` endpoint; fallback to actual `li#partner_*` blocks. Preserve each partner's separate text, category, city IDs and tier tables.
- Moskvich: `.lpp-card` name and terms in the same block.
- No Name: native record/element IDs and aligned card geometry, not DOM text order. Ambiguous pairings fail rather than moving the next partner's benefit onto this one.
- RGO: exhaust its span-based load-more control, then parse individual pages. A linked PDF is reported separately and is not silently counted as parsed HTML.
- AZIMUT: status-table columns retained separately from summary cards. Image-coded unavailable amounts are not guessed. A summary card does not make a platinum privilege universal.
- Museum Friends: published plan names/prices and corresponding benefits; membership plans remain a distinct record kind.
- MEDI / Neva Travel: named partner-page fallbacks. These do not certify completeness of the EKP or SOGAZ catalogues.
- Promo Miles: distinguish campaign announcements and archived sections from current partner offers.
- KEY: run the existing `key/refresh.mjs` live, check the resulting observation timestamp and adapt its structured snapshot. Do not relabel a checked-in old snapshot as a fresh scrape.
- Other registry URLs: bounded anonymous access probes. Failure/status and `adapter_not_yet_implemented` remain explicit; no generic whole-page extractor invents normalized partner records.

## Record contract

`id` is SHA256 of `source_id + newline + native_id`. Prefer a native offer/card ID; same S7 offer under `/city/` and `/partners/` is one identity. Missing source-native identities use a documented stable name/text key, never the observed discount amount as a key for a known partner.

Useful fields: `program`, `partner_name`, `record_kind`, `title`, `category`, `benefit_text`, `conditions_text`, `redemption_text`, `benefit_types`, `rates`, `promo_codes`, `valid_from`, `valid_until`, `validity_status`, `source_status`, `source_url`, `benefit_url`, `link_kind`, `locator`, `tables`, `details`, `warnings`, `observed_at`, `adapter_version`, `content_sha256`.

- `partner_name` is null when a display name is not safely obtained; its native code/source description remains available.
- Every extracted numeric rate includes its exact local evidence clause, kind, decimal-string value, unit and qualifier. Mileage rates preserve the spending denominator. A purchase minimum is not a discount amount. **Rates are lexical extractions, not a complete pricing/eligibility engine; never sum unrelated rates or convert miles into cash.** Full conditions remain authoritative.
- Dates are typed only from explicit structured source date fields. A year in a copyright, campaign URL, display banner or unrelated card does not become an offer expiry. `null` means unknown/not stated, not unlimited validity.
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
