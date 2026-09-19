# Konsierge public catalogue: 159 reconciled records, 19 September 2026

## Scope and result before publication

The owner supplied `https://konsierge.com/benefits?rubric_id=24` and requested continuing the website-first collection approved in PR73. This release adds a **tested offline capture parser and source-owned common-view projection**, not a new schedule or an authenticated app integration. Publication is not claimed by this pre-publication section; append the actual main execution and independently checked destination below after it completes.

The exact category URL works. A fresh ordinary Playwright browser loaded the website's own catalogue responses successfully, despite the earlier **direct anonymous API request returning401**. No request headers, cookies, source client constants, account sessions or OTP were extracted/replayed. No direct API request was made by the capture script. The browser simply opened public pages and scrolled them; non-read methods and account/auth routes were blocked. Only an explicit allowlist of public offer fields was retained.

**The main-origin robots transport remains unresolved.** Its GET returned ReadTimeout in35463505666, and Exa's separate robots fetch also timed out. These user-requested one-off public-page inspections do not change the existing production gate. `konsierge_public` is intentionally **not in sources_normalized.json or any recurring collector**. Do not advertise a complete scheduled integration, substitute subdomain robots for main-origin policy, or repeat app/API credential investigation. No provider credits were used.

## Independent denominators

Accepted source capture **35463931323:1**, execution `80136a3a1f3f4da7ea0c7860ba6eba8893cbef4f`, observed **2026-09-19T19:18:49.862699+00:00**. All pages returned200; response observation times remain in the report. The source's cache age is not reported.

| Public view | rubric_id | Native total / parsed DOM | Pages |
|---|---:|---:|---:|
| Whole catalogue | none | **159 / 159** | 14 |
| Рестораны | 23 | 93 / 93 | 8 |
| Услуги и покупки | 26 | 15 / 15 | 2 |
| Отели и курорты | 24 | 13 / 13 | 2 |
| Красота и здоровье | 25 | 35 / 35 | 3 |
| Сочи | 29 | 4 / 4 | 1 |
| Недвижимость | 77 | 1 / 1 | 1 |

All six IDs/names were discovered from the live site's rubric response, not guessed ranges. Root plus categories produced31 accepted page responses. Pagination requires consecutive page numbers, consistent total_count/total_pages, exact page lengths, a terminal null next_page and matching DOM names/offer labels. Temporary scroll inactivity is not completion. A first pass35463701025 captured all159 root items but navigated away after only48/93 restaurants; it was rejected for category completeness. The corrected pass waits for the declared last page and accepted all six views.

The six category counts sum to161, not159: four Sochi rows also belong to restaurants, while **Такахули(id2347) and Insider(id2343) occur only in the root and not in the six current tabs**. Their native non-menu rubric IDs are retained; they are not dropped or assigned a guessed public category. Native rubric order differs across responses, but sorted membership is identical. All other public fields match across root/category observations. Four restaurant/Sochi overlaps plus two root-only records explain the denominator exactly.

## Preserved offer semantics

All159 records retain their native benefit ID, name, original short offer label and full public description. There are **107 numeric discount labels and52 unspecified privilege labels**, not159 universal percentage discounts.157 descriptions include identifiable redemption paragraphs; those paragraphs are copied whole, with the complete original conditions retained separately. Unknown instructions remain empty.

The common view deliberately emits one headline component per record and links it to all owned conditions. Hotel breakfast/upgrades, room-category-dependent restaurant credits, department-specific discounts and non-customer commission percentages are **not expanded into unconditional numerical benefits**. Rich details stay searchable. At Atlas, a headline up-to20% is not silently reconciled with departmental10% clauses or physician25%/0% text; scope-review warnings remain.

Common projection:159 headline components,316 condition/redemption components,19 code/delivery components. The latter comprise9 literal-code occurrences,9 code-word occurrences and one app-delivery instruction with **no issued code**. Case and Cyrillic code words are retained. OSKELLY's instruction to request a code is not a collected/personal code. Generic public GMS/Dropp/other code literals came from public offer descriptions, not account storage or activation.

Every native card has enabled=true, but that does not establish current validity. Three native expiry timestamps have elapsed. Grand Hotel Polyana's description explicitly ends30.12.2023 and is marked expired. Atlas Serpukhovsky Val has description end31.12.2026 versus native expiry2025-12-30T21:00:00Z: its common status is `source_date_conflict`, not an inferred current offer. YUG22 Moscow has elapsed native expiry without a literal customer period, preserved as uncertainty. date_of_release/created_at/updated_at are never inferred as offer start. UTC metadata is retained verbatim; a one-day date boundary is not treated as evidence of a year-scale conflict.

The site supplies no valid direct detail URL for these records:158 links are null and Mandarin Oriental's is literally `Some url`. Source URLs are the real root, with stable public-native-ID locators and exact category URLs in details. No constructed detail links or imported Alfa/PDF conditions. No bank/customer eligibility is inferred.

## Code, tests and evidence

New module `loyalty/konsierge_catalog.py` parses and validates a saved sanitized capture and projects owned common terms. Two surgical hooks in normalized.py/unified_normalization.py register identity validation and the scoped projection. No source registry, shared transport, permission or recurring workflow changes.

Verification **35464404712:1**, execution `6456c652c1af53a99032410e1221b27b7b5e8bab`, passed **1090 Python tests +7 KEY tests, no skips**. The21 new tests cover missing/duplicate pages, count drift, early-scroll stops, wrong partner despite equal count, DOM hashes, native category ordering/drift, root-only retention, complete terms, quoted code words, unissued codes, hotel/department scope, expired/conflicting dates, source identity and rehashed field tampering. An initial local assertion differed only on normalized nonbreaking spaces; the test now uses the established source text normalizer, while raw description remains retained in public_item. No data/rate exception was added to silence a failed test.

Validated feature commit **f864bbf1e9af6ed549aae84df4f2060612271ada** persisted the reviewed hooks and source-derived fixture after all tests and full159-row replay/common checks passed. Temporary UI/check files were removed after verification; their exact historical execution commits remain recoverable. No production parser bytes changed during cleanup.

Persistent evidence identities:
- Full source capture artifact10589993853: ZIP SHA256 `54ee476f6713710cf24baa65beb6b4cde09502df57e9bf9d848a094aaa78656e`.
- Parser acceptance artifact10590009353: ZIP SHA256 `81521cb24f290317bc0221e85aeac205ee12ccb8fc064efa43f91b6c92390ec5`.
- Both ZIP digests/CRCs, full capture contracts, fixture provenance and tested code hashes were checked locally. The14-item checked-in fixture preserves real descriptions/lifecycle fields; test pagination is synthetic, while acceptance separately replays actual DOM and all31 real pages.
- Module SHA256 `a32f20b2251de1e2e460d0c78ff1ab1a45e28cab102deece6704eb83e4102a99`; normalized.py `e3c118af3f157145e0a3a6c14b3ddfc64d61574ea486529c8bc60e3cca067102`; unified_normalization.py `a6cd63a6aa506dacab7c93f425810ad1adf1b964835a3e1211e6ac96358ad671`.

The genuine private destination export before publication contains2641 parser /3289 current unified records and eight formulas. Its source fingerprint is `3c42fed6ada6bed54855d5eb4a1bde44b137ced3364dcb35dd96db6448d45d4f`, newer than PR72's earlier fingerprint. A read-only XML audit matched all3289 per-record input hashes and the manifest after normalizing exported empty parser strings to the API's absent-value representation. The private export is not committed or attached.
