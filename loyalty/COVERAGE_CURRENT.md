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

## Accepted implementation — do not repeat the migration

**The correction is implemented and destination-verified**, not requirements-only. Detailed evidence and verification limits: **PRACTICAL_SCOPE_ACCEPTANCE.md**.

- PR56 released the provenance-based practical filter, collection restrictions and reversible archive migration. Main execution `11fd53fc2153137e8986ece9e5df81c052997b8a`, run **35324821738:1**, migration job **105535582920**, completed successfully on 18 September 2026 at 08:35:46 UTC.
- **64 bulk records** moved to hidden `parser_documents_archive`, retaining their 26 native source cells, original row positions and archive times. Their former source values are blank; rows were not deleted or shifted. Retained derived history is marked `retired_from_normalization`, not source-expired.
- Fresh independent readback confirms **2494 parser records / 3142 unified records, verified/current**. Before migration: 2558/3206. All **3644 benefit components** remain; all **294 components containing literal codes** retain their IDs and values. The two retired code/delivery components had no literal codes. Counts are not unique merchants, personal usable-discount totals or distinct coupon strings.
- The four current derived views contain 3142 records, 3644 benefits, 9652 conditions/costs and 651 code/delivery components. Every managed current field was recomputed and matched to a fresh export. Archive reconstruction also matched retained historical managed content; it is not an independently preserved old workbook export.
- PR57 fixed a missed offline entrypoint: `unified_publish.py --offline-input` now applies the same practical filter and provenance audit as live publication. The real CLI regression failed before and passed after; replay of 3206 reconstructed historical inputs produces the identical 3142 practical records. **912 Python / 7 KEY tests plus schema validation passed** in run **35327225254:1**. A local all-suite attempt lacked dependencies and is not counted as passing.
- PR57 main merge **37a9617572d03aeb9de260f82a2d4c1bba60974e** has the exact tested branch tree `d7d847313f44c48cea6116ea0b2813caddfda8ca`. Push-triggered migration/publication was skipped for that merge only to avoid rewriting an already verified Sheet. No schedule or live publisher behavior changed in PR57.

The bulk Aeroflot linked-rules workflow is retired to a manual no-op without a schedule. Other released practical collectors remain: Coral offers and short lounge instructions without full contracts/PDF stage; RZD tour clauses and bank links without the general bank PDF; EKP practical linked HTML without full appendices; Utair short privileges without the full programme contract. Existing source-bundle validation remains before practical publication filtering. Do not blindly discard every `program_rules`, every PDF or every zero-rate record.

Current source fingerprint: `84b18d0b76b5a2dca26913d5853cfa3fa392c8175e9d3be18abe47704abd5797`.
Current generation: `f19389fda3fe508244b8b34b031e4173de07556523867f781815d70970cae325`.
These are accepted stored-state identities, not universal source freshness. Post-PR57 native readback still matched both.

## Practical lookup contract

Use `normalized_records`, `normalized_benefits`, `normalized_conditions` and `normalized_codes` only where **Статус нормализации = current**. Their native filters are configured, but API/export readers must explicitly honor the status rather than treating all retained rows as current. Do not use `parser_documents_archive` in normal discount lookup.

Search partner/title/offer text and practical conditions in `parser_offers` as well as the derived views; a missing automatically recognized benefit is not proof of no discount. `current` means current normalization, **not** current validity. Before answering, inspect the matched offer's source/validity status, original observation time, membership requirement, geography and redemption channel. Do not infer the owner's eligibility or combine different programme rates.

## Remaining work, under the corrected goal

1. RZD has eight historically unread offer-detail pages, with previews retained. Revisit only missing benefit/redemption information: two prior transient imports were Renaissance Life Smart Plus and Grand Karat Sochi; six other pages showed login forms. Targeted retry mode was not implemented at this checkpoint. Do not reread the whole catalogue just to chase two imports.
2. EKP has 110 historically gated observations. Establish whether useful offer information is actually missing before starting an account-dependent project. No source-account session is connected; authentication and safe publication remain separate boundaries.
3. Check catalogue discovery only where it can reveal missing offers, including Coral interactive/sitemap differences. General attached regulations do not contribute to this denominator.
4. Preserve source-validation and queue/retry reliability. The correction and offline repair did not re-fetch source offers, refresh all timestamps or verify every future scheduled run.

Do not start another broad crawl, new API integration, account flow or document parser merely to continue from this checkpoint. First resolve a concrete missing practical offer or demonstrated defect.

## Historical recovery references

The preceding exhaustive-document checkpoint is preserved at `b118c4425a010992c5b71e30bc4b94176c292c25:loyalty/COVERAGE_CURRENT.md`. The subsequent requirements-only checkpoint is preserved in `11fd53fc2153137e8986ece9e5df81c052997b8a:loyalty/COVERAGE_CURRENT.md`; its “not implemented” status is now superseded.

Other persistent evidence: `SAMSON_LINKED_ACCEPTANCE.md`, `AEROFLOT_LINKED_ACCEPTANCE.md`, `EKP_LINKED_ACCEPTANCE.md`, `RZD_EXTERNAL_ACCEPTANCE.md`, `CORAL_PDF_ACCEPTANCE.md`, `CORAL_LINKED_RULES_ACCEPTANCE.md`, `CORAL_RETRY_ACCEPTANCE.md`, `RZD_PREVIEW_ACCEPTANCE.md`, `AEROFLOT_ACCESS_STATUS.md`, `AIRLINE_COVERAGE.md`. These are historical implementation evidence, not a mandate to keep collecting every document. Interrupted chat output is not a rollback; inspect main/branches/runs/destination before reimplementing accepted work.

## Unchanged operating and privacy constraints

Destination: `скидки`, spreadsheet `1uFR7croj7p6RRNPcoTRYlVl06hKsurkIgyu1IdMMB-4`. Recurring GitHub-controlled updates, no paid service, rented/administered server or always-on user computer. Existing free ScrapingAnt and Google WIF; no extra provider account. Coral registration is already complete; do not ask for it again. Aeroflot parsing permission is owner-reported and does not waive other hosts' policies or authorize private-account access, coupon issuance, bookings, purchases or spending bonuses.

The last ACL inspection noted `anyone:writer`; it was not rechecked or changed in this continuation. `private_complete` is a normalizer mode, not access control; a hidden archive is not private storage. Source sessions and personal coupons must not enter public artifacts or a link-accessible Sheet. Private exports stay private. Existing queue serialization, source identity, timestamps, bounded requests and no-canned-answer requirements remain in force.
