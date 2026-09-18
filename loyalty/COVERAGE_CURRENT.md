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

## Implementation state of this correction

**This commit changes the requirements/handoff only.** No collector code, workflow schedule, Sheet contents, sharing or keys were changed. Existing full-document collectors and stored document rows have NOT yet been disabled, compacted, hidden or deleted. Do not claim otherwise from this policy update.

The next implementation should first prevent bulk-document additions/republication, while preserving actual offer collectors and brief redemption conditions. Then remove standalone bulk texts from normal practical lookup, retaining source links, provenance and manual comments. Inspect actual records before changing them; do not blindly discard every `program_rules` record, every PDF or every record with zero automatically parsed benefits. Prefer a scoped reversible migration over deleting useful source data. Read back the resulting code/configuration and affected destination after the final write.

Do not start another broad crawl, new API integration, account flow or document parser just to acknowledge this correction.

## Remaining work, under the corrected goal

1. Apply the practical-only scope to existing collection/publication and lookup. The old external-document backlog is no longer a priority or a prerequisite for completion.
2. RZD has eight historically unread offer-detail pages, with previews retained. Revisit only missing benefit/redemption information: two prior transient imports were Renaissance Life Smart Plus and Grand Karat Sochi; six other pages showed login forms. Targeted retry mode was not implemented at the preceding checkpoint. Do not reread the whole catalogue just to chase two imports.
3. EKP has 110 historically gated observations. Establish whether useful offer information is actually missing before starting an account-dependent project. No source-account session is connected; authentication and safe publication remain separate boundaries.
4. Check catalogue discovery only where it can reveal missing offers, including Coral interactive/sitemap differences. General attached regulations do not contribute to this denominator.
5. Preserve the existing source-validation and queue/retry reliability improvements. Search partner/title/offer text and practical conditions, not only derived benefit rows; a missing automatic benefit match is not proof of no discount.

## Technical baseline and recovery references — historical, not newly verified here

The complete preceding checkpoint, including every accepted scope, schedule, bound, digest, limitation and recovery instruction, is preserved at:

`b118c4425a010992c5b71e30bc4b94176c292c25:loyalty/COVERAGE_CURRENT.md`

Latest accepted code release remains PR55 (Samson extension), main run `35315811926:1`, execution commit `f3f27c1187b40133ce940d3a58bb44ee06b49094`. Its source-to-Sheet acceptance is in `SAMSON_LINKED_ACCEPTANCE.md`. Previous recorded destination totals were 2558 retained parser records / 3206 common records, `verified/current`; those include now-out-of-scope documents and are **not practical-offer counts**. No fresh Sheet read was made for this requirements-only correction.

Other persistent evidence: `AEROFLOT_LINKED_ACCEPTANCE.md`, `EKP_LINKED_ACCEPTANCE.md`, `RZD_EXTERNAL_ACCEPTANCE.md`, `CORAL_PDF_ACCEPTANCE.md`, `CORAL_LINKED_RULES_ACCEPTANCE.md`, `CORAL_RETRY_ACCEPTANCE.md`, `RZD_PREVIEW_ACCEPTANCE.md`, `AEROFLOT_ACCESS_STATUS.md`, `AIRLINE_COVERAGE.md`. These are historical implementation evidence, not a mandate to keep collecting every document. Interrupted chat output is not a rollback; inspect main/branches/runs/destination before reimplementing accepted work.

## Unchanged operating and privacy constraints

Destination: `скидки`, spreadsheet `1uFR7croj7p6RRNPcoTRYlVl06hKsurkIgyu1IdMMB-4`. Recurring GitHub-controlled updates, no paid service, rented/administered server or always-on user computer. Existing free ScrapingAnt and Google WIF; no extra provider account. Coral registration is already complete; do not ask for it again. Aeroflot parsing permission is owner-reported and does not waive other hosts' policies or authorize private-account access, coupon issuance, bookings, purchases or spending bonuses.

The last ACL inspection noted `anyone:writer`; it was not rechecked or changed here. `private_complete` is a normalizer mode, not access control. Source sessions and personal coupons must not enter public artifacts or a link-accessible Sheet. Private exports stay private. Existing queue serialization, source identity, timestamps, bounded requests and no-canned-answer requirements remain in force.
