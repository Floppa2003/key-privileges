# Regional catalogue expansion — 2.4.0

The source set and schema version remain unchanged. This release expands two previously Moscow-only sources to two explicit anonymous listing regions: Moscow/region and Saint Petersburg/region. It does not turn regional listing membership into user eligibility or an all-Russia coverage claim.

## T2 «Больше»

`loyalty/t2_regions.py` observes the ordinary public GET response `/api/loyalty/offers` separately on `msk.t2.ru` and `spb.t2.ru`. Each region has a fresh anonymous context and its own rules check. The SPb page's ordinary 503-to-200 document reload is handled exactly as Moscow's; no challenge is clicked or solved.

Normalize each object with the existing reviewed mapper and native ID. Compare all normalized source semantics before merging a shared ID, excluding only observation/provenance fields. Identical terms give one stable record and multiple `details.catalog_regions` entries. A same-ID terms conflict is reported, not silently overwritten or turned into common eligibility. The primary record remains without the conflicting regional membership.

SPb-only records keep the actual SPb root URL. `benefit_url` stays null because this adapter observes the public catalog object, not a separately verified query-based card. Raw program flags and complete agreement/info text remain authoritative. No activation, registration, personal promo-code request, credentials or session export occurs.

Verified T2 branch run `34773439059` yielded 103 unique records: Moscow76, SPb95, 68 identical shared observations. This adds 27 SPb-only offers to the prior Moscow snapshot, not 95 new offers. All 103 records passed schema, identity/evidence and publisher preparation checks. ZIP artifact10323160697 SHA256: `bd817e7a654ff5de048a46d9e558865e7838f8e321912dfb723eebd6584e7e26`.

## «Привет!» / Мир / СБП

`loyalty/mir_regions.py` runs the existing full public browser UI collector in independent Moscow and SPb contexts. The actual visible region selector is clicked. A new page-one response whose title matches the selected region is required; an old Moscow response cannot establish SPb provenance. Both payment profiles and all observed pagination are handled by the existing collector; each accepted card's details are read and matched in that region before unioning.

`details.catalog_listings` is the per-region relationship: region key/label, observed payment profiles, original page titles and `detail_checked`. Preserve the previous `catalog_profiles` / `catalog_region` as provenance of the primary observation; consumers of the union must use `catalog_listings` rather than form a Cartesian product between regions and payment types.

Stable identity plus matching normalized source terms is required to merge. Transport attempt counters and regional listing labels are not substantive terms. Conflicting terms remain an explicit report and do not expand a primary record's region list. A failed regional read retains successfully completed other regions. Unique discovered URLs are counted separately from normalized records, including failed detail reads. The requested record limit is applied after union, with an explicit truncation diagnostic.

Public UI contract inspection34773755508 confirmed Moscow97/SPb90 cards in the SBP profile; these first-page counts are not a claimed final all-payment union. Complete release counts must come from the corresponding full collection and main publication report.

## Integration and tests

Regression tests cover original native identity, literal regional sources, duplicate IDs, conflicts, input immutability, missing-region retention, post-union limits, new-response region selection and source-dispatch integration. The initial Mir test exposed a stale production import through the compatibility module: direct wrapper tests passed, but the main dispatcher called the old collector before any rules initialization. A failing test at `one()` now covers the actual route, which imports the regional wrapper directly.

The complete local suite after this fix has 257 Python tests plus 7 unchanged KEY tests. Passing tests do not certify live regional completeness: inspect the concrete fresh source reports and independent destination readback.

## Unresolved access and preserved boundaries

Three cold GitHub discovery trials34772857216 tried the already-observed EKP public endpoint and explicit catalog page. All three timed out on both reads, with no native JSON objects captured. The earlier successful diagnostic saved paths/short excerpts, not a complete payload contract. No speculative EKP mapper was registered. The eight known inaccessible primary URLs remain separate from alternative sources and these regional expansions.

Google WIF, permissions, disabled periodic schedule, stable IDs, curated tabs and manually edited columns remain unchanged. Only parser_offers A:Y and parser_coverage A:N are managed; Z/O remain manual. Missing previous observations are not deleted or relabelled freshly observed. Public repository/artifacts contain no private spreadsheet export, destination ID or credentials. Temporary discovery/review workflows are removed from the production diff before merge.
