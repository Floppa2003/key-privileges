# PR77 reader catalogue — published and independently verified

This supersedes the pre-release verification boundary in CATALOGUE_QUALITY.md.
The owner rejected merely hiding advertising with a checkbox. The actual generated working catalogue has now been rebuilt; returning raw/expired entries via checkboxes is no longer supported.

## Execution

PR77 merged at 2026-09-20T12:04:38Z as `22241f9a964f9af84e48ee730f583289c4c9d034`; merged state was independently read back. Feature regression35509465102 executed `eabb05501832f74e3a1d6f83bda8296c023ae295` and passed **1133 Python +7 KEY tests**, including31 new focused tests. Artifact10604494289 ZIP SHA256 `ada94f1a26e3a98da9239159f6da679c8f6c84948d3165a7ba6875285d9e95da` and CRC were independently verified. Exact tested code was replayed locally against the real source snapshot and matched the reviewed projection.

Actual main run **35509595600** executed the merge commit. Both test job106075070116 and private publication job106075184175 completed successfully, including full regression and destination readback. It ran the existing normalize.yml process; no new recurring schedule or unrelated source crawl was added. The temporary feature verification workflow was removed before merge.

## Result in the live workbook

Destination: spreadsheet `1uFR7croj7p6RRNPcoTRYlVl06hKsurkIgyu1IdMMB-4`, reader tab Скидки, sheetId2026092001. `_ui_catalog!A:Q` is now literal cleaned data, not a formula projection of raw posts. `_ui_catalog!Y1:Z8` holds its verified version, count, generation and fingerprints. The obsolete raw-text helper R:X is empty.

**3448 source records ->2852 working catalogue records;596 excluded.**

| Exclusion reason | Count |
|---|---:|
| Unprocessed announcements/pages/source observations |250|
| No concrete benefit |170|
| No meaningful offer name / technical heading |5|
| Document instead of an offer |31|
| Unreviewed OCR document |1|
| Established expiry |64|
| Archived by source |4|
| Explicitly inactive offer |5|
| Exact duplicate |3|
| Exact manual/live catalogue mirror |63|

**2475 retained records** have cleaned benefit or condition fields. The internal rewritten counter2541 is measured before duplicate consolidation and must not be described as2475+66 additional independent offers. Unknown deadlines and user eligibility are not inferred. Different programmes, branches, card tiers and material restrictions remain separate.

Source-owned examples tested: KIBERone's parent-success statistic is not a benefit and its actual card-scoped free weeks survive; RZD/Yota programme points are separate from unrelated merchant marketing; Coral/Litres' two-book gift is separate from generic free-book inventory. Mir caps/payment exclusions/currency-change clauses, HSE full-prepayment restrictions, and retained literal codes remain.

## Independent post-publication audit

After successful main publication, native-cell tests checked combined search/programme/category filters:4 exact GMS results including the code and client restriction. The rejected weekend-route advertisement returned0 results. Search inputs were reset to blank, then a fresh full export was read and compared. Read-only audit completed2026-09-20T12:10:39.195871+00:00.

- All **48,484 generated catalogue cells** (2852x17) matched the exact reviewed projection.
- All **39,928 visible result fields** (2852x14) matched the catalogue, allowing native Sheet sort order.
- **413,893 original nonempty values/formulas across14 original tabs** were unchanged; zero cell differences and all8 original formulas preserved.
- **309 literal-code components on retained records**, zero lost.
- Zero formula errors; no obsolete raw helper cells.
- B6/B8 return-junk controls removed. B3:B5 remain search/programme/category; final inputs blank.
- Main UI requires both verified states and matching normalization/catalogue generation. Current-normalization status alone is not acceptance as a practical offer.

Before export SHA256 `bd03efba9e78e5d71b5a6262364caeca1cf1d50318518b25aadc9825d7f0509e`.
After export SHA256 `9042e06b963131ee8a2984f3126b320f978d1fc8c61c9fbc575fcd1a9ace3b85`.
Catalogue SHA256 `c6ba02474c59be9eb0a54a1108e43e63e83a81b48f5d2ec99538c36f367dc846`.
Generation `77a6c8bb336b4fb553d17d8a4797956802438fc01db214998467c922950caa07`.
Source fingerprint `be1c43161520bfb56e3d3cf470e80986c722a949ff0b6bb39040106eba9dfe7e`.

## Scope and recovery

A separate native Drive backup was created and independently confirmed unshared/owner-only before changes. Its private ID and the full private exports are not committed here. The14 original tabs remain hidden ingestion/provenance data; they were not physically destroyed. They are outside the working catalogue and no UI switch returns them as discounts. Existing collectors retain their source data and regenerate the cleaned catalogue inside the same serialized private publication stage.

This is complete traversal of the stored dataset with reviewed quality rules, not a fresh crawl of every merchant or proof that every possible new wording is semantically understood. Counts are not guaranteed current personal entitlements. Raw technical data must not be used to reintroduce rejected advertisements, placeholders, generic documents or repeated mirror records into ordinary discount search.
