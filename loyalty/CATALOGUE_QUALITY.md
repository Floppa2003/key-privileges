# Practical reader catalogue — 20 September 2026

The owner rejected a checkbox-only fix: **remove junk from the complete working catalogue**, not just hide one Telegram post. The reader now has a separate deterministic publication, `catalogue_view.py` + `catalogue_clauses.py`, executed inside the existing private `unified_publish.py` queue. It replaces `_ui_catalog` completely and verifies every resulting cell; the public source adapters and their schedules are unchanged.

## Scope

The working catalogue excludes unprocessed posts/pages/previews, empty benefit placeholders, technical headings, expired or explicitly inactive offers, archive-only entries, generic rule documents and reviewed exact duplicate/mirror records. It extracts an actual source-owned offer clause and keeps practical activation, limits, eligible cards/tiers/cities, non-combination rules, codes and date conflicts. It does not invent rates, mark unknown dates expired, merge different programmes or claim user eligibility. A raw-source row is not itself an accepted reader offer.

Source-specific ownership handles RZD shopping panels, HSE partner sections, Mir structured conditions, Loyals card clauses, Coral programme blocks, Konsierge privilege sections and native PDF line wraps. Examples: KIBERone parent-success percentages are not discounts; RZD/Yota benefits are programme points, not Yota's unrelated household offer; Coral/Litres free inventory is not the two-book gift. Mir caps, payment exclusions and the October bonus-currency disclaimer remain.

Duplicate consolidation requires exact scoped content. The specifically reviewed manual/live mirrors for Moskvich/No Name match programme, merchant, headline, code, period and source URL, retaining unique practical/access/manual clauses. These are not cross-programme equivalences.

## Publication and privacy

Before changes the actual Google workbook was copied to a separate **owner-only, unshared Drive backup**. Five original input datasets and the original technical/audit sheets remain unchanged; they are ingestion evidence, not the working catalogue and are not offered by a return-raw-text switch. Deleting their rows would destroy provenance and the legacy row identities used by publishers.

`_ui_catalog!A:Q` contains only cleaned literal cells, `Y1:Z8` its version/state/count/generation/fingerprint. The obsolete raw-text helper in R:X is cleared. Publication prevalidates headers, dimensions, nonempty results and cell sizes, clears only this generated sheet, writes bounded batches, and verifies all rows, state and blank tail. It stays within the outer publishing/verified manifest and repeats readback after the final manifest write. Private contents are never logged or uploaded as public artifacts.

The main search must compare catalogue generation `Z5` to normalization manifest `J7` and require both verified states. Search, programme and category controls remain; switches returning raw/expired junk are removed. Unknown/ambiguous source validity remains visibly qualified. A count is not a count of guaranteed current personal entitlements.

## Verification boundary

31 focused synthetic/public regression tests cover content ownership, junk rejection, literal-code safety, scope, deduplication, immutability, full generated replacement and readback failure. Full fresh-checkout regression and actual main publication are required before claiming release. Initial local replay of the real 3448-row source snapshot produced 2852 working records, excluded596 and retained every literal code belonging to a kept record. These are pre-release observations, not a claim of publication. The initial incomplete local archive lacked dependency `protego` and workflow files; its full-suite failure was environmental and must not be called a passing release test.

This is content cleaning, not a new scrape of every merchant or proof of global semantic completeness. Recurring recomputation prevents rejected source kinds/known noise from returning, while new layouts or new ambiguous wording may require a reviewed rule update.
