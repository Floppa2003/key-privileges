# Current coverage goal — practical discounts, 18 September 2026

## Owner correction: this supersedes the previous document-completeness goal

The owner explicitly clarified: «какие-то огромные документы с условиями включать не нужно, при практическом применении они нам не пригодятся никак».

The objective is to answer **“Do I have a discount here, how much, and how do I use it?”** from regularly updated offers in the SAME Google spreadsheet. It is not to archive every programme contract, PDF page or product-exclusion catalogue. Previous work drifted from useful-offer coverage into document completeness. Do not continue that expansion merely to increase counts.

### Keep in a useful offer

- Programme, partner and the actual benefit, including amount/rate and what it applies to.
- Promo code, or concise instructions for obtaining/using it; required card, account or membership tier.
- Dates, region, minimum purchase, online/offline restriction, non-combination and other material redemption restrictions when the source states them.
- Direct offer/source link and actual observation time. Unknown facts remain unknown.

A source's brief offer-specific terms remain necessary. The correction does **not** authorize deleting all conditions or assuming universal applicability.

### Exclude from routine coverage and the practical answer dataset

- Full programme contracts, general legal/regulatory documents, parking-use manuals and similar long texts saved in page-sized parts.
- Exhaustive product-exclusion lists, complete price lists and unrelated appendices as independent records. Working interpretation: keep a short “exclusions apply” note and the exact source link instead of hundreds of product names, unless a concrete purchase question later requires checking one item.
- Recursive document traversal or OCR performed merely to exhaust attachments.

**Format is not the criterion:** an offer available only in PDF may still be in scope. Extract the relevant benefit and material practical terms; do not publish the whole document by default. Do not replace source facts with invented summaries, canned values or silently truncated clauses.

Measure progress by covered partners/offers and usable redemption information, not PDF pages, document parts, exclusion products, field-check counts or total retained rows. An intentionally omitted general document is **out of scope**, not an unresolved coverage gap, source failure or proof of GitHub impossibility.

## Accepted scope cleanup — historical checkpoint, do not repeat the migration

**The correction is implemented and destination-verified**, not requirements-only. Detailed evidence and verification limits: **PRACTICAL_SCOPE_ACCEPTANCE.md**.

- PR56 released the provenance-based practical filter, collection restrictions and reversible archive migration. Main execution `11fd53fc2153137e8986ece9e5df81c052997b8a`, run **35324821738:1**, migration job **105535582920**, completed successfully on 18 September 2026 at 08:35:46 UTC.
- **64 bulk records** moved to hidden `parser_documents_archive`, retaining their 26 native source cells, original row positions and archive times. Their former source values are blank; rows were not deleted or shifted. Retained derived history is marked `retired_from_normalization`, not source-expired.
- That checkpoint's independent readback confirmed **2494 parser records / 3142 unified records, verified/current**. Before migration: 2558/3206. All **3644 benefit components** remained; all **294 components containing literal codes** retained their IDs and values. The two retired code/delivery components had no literal codes. Counts are not unique merchants, personal usable-discount totals or distinct coupon strings.
- That generation's four derived views contained 3142 records, 3644 benefits, 9652 conditions/costs and 651 code/delivery components. Every managed current field was recomputed and matched to a fresh export. Archive reconstruction also matched retained historical managed content; it is not an independently preserved old workbook export.
- PR57 fixed a missed offline entrypoint: `unified_publish.py --offline-input` now applies the same practical filter and provenance audit as live publication. The real CLI regression failed before and passed after; replay of 3206 reconstructed historical inputs produced the identical 3142 practical records. **912 Python / 7 KEY tests plus schema validation passed** in run **35327225254:1**. A local all-suite attempt lacked dependencies and is not counted as passing.
- PR57 main merge **37a9617572d03aeb9de260f82a2d4c1bba60974e** has the exact tested branch tree `d7d847313f44c48cea6116ea0b2813caddfda8ca`. Push-triggered migration/publication was skipped for that merge only to avoid rewriting an already verified Sheet. No schedule or live publisher behavior changed in PR57.

The bulk Aeroflot linked-rules workflow is retired to a manual no-op without a schedule. Other released practical collectors remain: Coral offers and short lounge instructions without full contracts/PDF stage; RZD tour clauses and bank links without the general bank PDF; EKP practical linked HTML without full appendices; Utair short privileges without the full programme contract. Existing source-bundle validation remains before practical publication filtering. Do not blindly discard every `program_rules`, every PDF or every zero-rate record.

Historical PR57 source fingerprint: `84b18d0b76b5a2dca26913d5853cfa3fa392c8175e9d3be18abe47704abd5797`; generation: `f19389fda3fe508244b8b34b031e4173de07556523867f781815d70970cae325`. Later automatic refreshes legitimately changed them; use the current checked state below rather than treating these historical identities as permanent.

## Latest practical frontier — verified outcomes, 18 September

Full run/artifact/independent-check evidence: **PRACTICAL_FRONTIER_ACCEPTANCE.md**. EKP exact public references and regional limits: **EKP_GATED_AUDIT.md**.

### RZD: targeted retry exists, but no full card recovered

PR58 is released. Main **35339529804:1**, execution **0b20a8e05517951f41a47c5d9a72fa3cca01ed9a**, ran `frontier_checks.py`: fresh membership followed by the two prior transient-error details (Renaissance Life Smart Plus and Grand Karat Sochi). Both were still listed, both again failed with `rzd_import_error_cell`; **5 imports, 0 full records, 2 source errors**, 11:26–11:29 UTC. Workflow completion means an audited attempt; source coverage is failed. The publication job was correctly skipped and all eight previews remain stored. Six historical login/insufficient-content pages were not retried as transient errors.

Separate same-URL title-only and raw-HTML import probes also returned Google “Resource at url not found.” This does not expose origin HTTP status or prove removal/expiry. The temporary staging tab was removed and original staging metadata read back. Do not rerun a complete catalogue or change an XPath merely to chase the same two unavailable imports.

### EKP: all 110 gated observations audited, zero protected details recovered

The stored region-98 catalogue contains 110 gated observations / 106 distinct displayed partner names. All were inspected. Fourteen native IDs have exact references in the bounded official-announcement set; the other 96 lack such a reference in that set, not necessarily on the whole web. Only SberAuto has a quantified own benefit in the exact matched announcements (5% servicing/tyres), already in the Sheet; its code and complete terms remain gated. Neva Travel's public supplementary offer is also already stored.

All matched announcement links use region 78, while the catalogue query used region 98, whose UI label was “Все регионы”. Same ID is a useful reference, not regional-term equivalence. No protected values were copied from anonymous API fields, no source session was connected and no new gated detail was published. See the audit for exact links and dates. Do not equate fourteen references with fourteen resolved offers.

### Coral: observed catalogue reconciled; all 69 URLs already stored

The Google-only stage read root/sitemap and 20 category templates; all 20 category lists correctly failed as unrendered, not empty. PR59 uses the existing free browser for inventory only, no offer-detail or document expansion.

Main **35341044020:1**, execution **4c01ac48de58f4576afff07c485b259de6ca21db**, read **19/20 categories**, 68 unique offer URLs, with an explicit Gadgets `access_challenge`, 11:44–11:47 UTC. **202 recorded free credits** used within the 222 ceiling. Latest-run `complete=false` remains unchanged.

Gadgets was independently reconstructed from successful same-day normal run **35335174051:1**, observed **10:36:28–10:36:34 UTC**. Combining those separately timestamped observations covers **all 20 categories / 69 unique offer URLs**, every one already in the Sheet. This is a time-window union, not a simultaneous snapshot or fresh read of all detail conditions.

Five observed offers absent from sitemap—NAME SKIN CARE, Мариджентал, GELTEK, Feedback, Styx Silk Body—already reach the Sheet through the complementary normal collector. The earlier seven-URL discrepancy also included MegaFon and BookingCar, both stored with expiry 2025-12-31 and already expired. **ALEF remains in the sitemap but was absent from the observed interactive list**; its existing 10% record has unknown expiry. Do not delete it or infer cancellation; verify before practical use. Sitemap ordinary merchandise entries are not missing discounts.

### Current destination and code checks

Fresh before/after exports of this frontier turn have identical values across all 14 tabs and all eight formulas unchanged. Native manifest remains **2498 parser / 3146 unified records, verified/current, practical-offers-v1**. The four-record increase versus PR57 happened in normal refreshes before this turn's baseline, not from the gap checks. No new offer rows were added by PR58/59 or the EKP audit. Archive64 remains hidden. No whole-workbook visual or byte-identical formatting claim.

Current checked source fingerprint: `75f7e08fba1647cbc9c5abac6e401b9a1e077dcbb5f75cf38b98a84198d49973`.
Current checked generation: `d02d29c3d62bd678b7595ab37154517ee211a0e4d8d5ffb43fdeea7cda9a3f09`.
These are stored-state identities at the check, not universal source freshness.

PR58 branch/main tests: **922 Python / 7 KEY**. PR59 branch/main: **927 Python / 7 KEY, zero skips**. Downloaded main code/test archives matched GitHub SHA256/CRC and reviewed executable bytes. Both added workflows are on-demand; existing recurring schedules and serial queue remain unchanged. The static inventory and RZD stages used no provider credits; the separate rendered Coral check used the 202 credits above. No new provider, paid service, source account or Google sharing change.

## Practical lookup contract

Use `normalized_records`, `normalized_benefits`, `normalized_conditions` and `normalized_codes` only where **Статус нормализации = current**. Their native filters are configured, but API/export readers must explicitly honor the status rather than treating all retained rows as current. Do not use `parser_documents_archive` in normal discount lookup.

Search partner/title/offer text and practical conditions in `parser_offers` as well as derived views; a missing automatically recognized benefit is not proof of no discount. Official announcement bodies may be in `details.message_parts[].text` even with empty `conditions_text`; match explicit linked-card IDs and preserve programme/region boundaries. `current` means current normalization, **not** current validity. Inspect the matched offer's source/validity status, original observation time, membership requirement, geography and redemption channel. Do not infer the owner's eligibility or combine different programme rates.

## Remaining work and anti-loop rules

1. RZD's eight full detail gaps remain. The implemented targeted retry has already been exercised and did not recover the two transient-error targets. Six other historic pages require authorized access or a genuinely independent public source. Existing previews remain usable as limited evidence, not full conditions.
2. EKP's 110 protected details remain gated, with the exact public references now audited. Source authentication and safe private storage are separate boundaries. Do not request Coral registration again or assume it supplies an EKP session. No exhaustive independent-site crawl of all 106 partner names has been done.
3. Coral's observed same-day catalogue has no offer missing from the Sheet. Preserve the latest Gadgets challenge and the earlier successful category timestamp separately. ALEF is the specific unresolved listing-versus-sitemap discrepancy; do not repeat a 20-category crawl merely to increase a completion counter.
4. New live practical offers or demonstrated parser defects may justify further work. These checks do not certify future cron execution, uncached source age, personal eligibility, coupon availability or booking stock. General attached regulations remain outside the completion denominator.

Do not start another broad crawl, new API integration, account flow or document parser merely to continue from this checkpoint. First resolve a concrete missing practical offer or demonstrated defect. Read actual main/runs/destination before reimplementing interrupted work.

## Historical recovery references

The preceding exhaustive-document checkpoint is preserved at `b118c4425a010992c5b71e30bc4b94176c292c25:loyalty/COVERAGE_CURRENT.md`. The requirements-only checkpoint is preserved in `11fd53fc2153137e8986ece9e5df81c052997b8a:loyalty/COVERAGE_CURRENT.md`; its “not implemented” status is superseded. The PR57 cleanup checkpoint is preserved at `f45ffb8bdf547f6752b0a41a3274d28a583abbaa:loyalty/COVERAGE_CURRENT.md`.

Other persistent evidence: `SAMSON_LINKED_ACCEPTANCE.md`, `AEROFLOT_LINKED_ACCEPTANCE.md`, `EKP_LINKED_ACCEPTANCE.md`, `RZD_EXTERNAL_ACCEPTANCE.md`, `CORAL_PDF_ACCEPTANCE.md`, `CORAL_LINKED_RULES_ACCEPTANCE.md`, `CORAL_RETRY_ACCEPTANCE.md`, `RZD_PREVIEW_ACCEPTANCE.md`, `AEROFLOT_ACCESS_STATUS.md`, `AIRLINE_COVERAGE.md`. These are historical implementation evidence, not a mandate to keep collecting every document. Interrupted chat output is not a rollback.

## Unchanged operating and privacy constraints

Destination: `скидки`, spreadsheet `1uFR7croj7p6RRNPcoTRYlVl06hKsurkIgyu1IdMMB-4`. Recurring GitHub-controlled updates, no paid service, rented/administered server or always-on user computer. Existing free ScrapingAnt and Google WIF; no extra provider account. Coral registration is already complete; do not ask for it again. Aeroflot parsing permission is owner-reported and does not waive other hosts' policies or authorize private-account access, coupon issuance, bookings, purchases or spending bonuses.

The last ACL inspection noted `anyone:writer`; it was not rechecked or changed in this continuation. `private_complete` is a normalizer mode, not access control; a hidden archive is not private storage. Source sessions and personal coupons must not enter public artifacts or a link-accessible Sheet. Private exports stay private. Existing queue serialization, source identity, timestamps, bounded requests and no-canned-answer requirements remain in force.
