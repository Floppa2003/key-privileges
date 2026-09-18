# Practical-offer scope — accepted 18 September 2026

The owner changed the goal from exhaustive documents to practical discounts: partner, benefit, how to claim, material short restrictions and source link. `COVERAGE_CURRENT.md` defines the operative scope. This acceptance replaces its earlier requirements-only implementation status; it does not certify fresh source eligibility.

## Released change and actual destination

PR56 merged as `6e4127c28aa470913a29f4c178fcbc58264db9e9`. Main migration run **35324821738:1**, execution commit `11fd53fc2153137e8986ece9e5df81c052997b8a`, completed successfully. The migration job **105535582920** ended at **08:35:46 UTC on 18 September 2026** with `practical_scope_migration_verified` and `unified_views_published_and_readback_verified`.

Destination is still `скидки`, spreadsheet `1uFR7croj7p6RRNPcoTRYlVl06hKsurkIgyu1IdMMB-4`.

| Stored scope | Before migration | Accepted current |
|---|---:|---:|
| Parser source records | 2558 | 2494 |
| Unified records | 3206 | 3142 |
| Benefit components | 3644 | 3644 |
| Conditions and costs in the conditions view | 10340 | 9652 |
| Code/delivery components | 653 | 651 |
| Components containing a literal code | 294 | 294 |

These are records/components, not unique merchants, currently usable discounts, or distinct coupon strings. The two retired code/delivery components contained no literal code.

**64 bulk records** were copied to hidden `parser_documents_archive`: 27 bulk-document parts, 6 general-contract records, 3 bulk appendices, 28 exclusion-list pages. The migration copied all 26 source cells, including the manual-comment column, plus original row number and archive time; it verified the archive and source before clearing selected source values. It did not delete or shift source rows. All 2494 retained source rows were reported unchanged by the completed migration. Existing derived history remains stored as `retired_from_normalization`; all four derived views have a `current` filter. The archive is reversible and is not part of normal practical lookup.

Released collection/publication behavior: Aeroflot bulk linked-rules workflow is a manual no-op without a schedule; Coral full-document PDF stage and general contracts are excluded while practical offer/lounges instructions remain; RZD external collection keeps tour clauses and bank links, not the general bank PDF; EKP full appendices and Utair's full contract are outside practical scope. Short PDF privileges and specifically parsed PDF offer clauses are not banned by format. Existing bundle validation precedes practical projection.

## Independent readback in the continuation

A fresh native metadata/cell read and read-only XLSX export were checked independently of the migration job. Every managed current view field was recomputed from the five actual input tabs and matched. The archive's 64 classified IDs are absent from active parser inputs; their original source positions are blank. All four current filters and the archive's hidden flag were checked. The private export was not committed, attached as a deliverable or uploaded as a public artifact.

Historical inputs were reconstructed from the current source rows plus the archive at its recorded original positions. Their 3206 normalized records and all historical managed component content match retained derived history. All 294 literal-code component IDs and values are identical before/after. **This reconstructed baseline is not an independently preserved pre-migration workbook export**; no new whole-workbook formatting or ACL comparison is claimed.

Post-code-release native readback again returned `verified/current`, `publication_scope=practical-offers-v1`, 2494 parser/3142 unified records and the same manifest:

- Source fingerprint: `84b18d0b76b5a2dca26913d5853cfa3fa392c8175e9d3be18abe47704abd5797`.
- Generation: `f19389fda3fe508244b8b34b031e4173de07556523867f781815d70970cae325`.

The migration's exact code/test artifact **10538187155**, SHA256 `6d74e845f83d8ae81c3ad32303fdf7a5c04a01aaddadff0c00ec9b881d644c02`, matched GitHub metadata and ZIP CRC; 911 Python and 7 KEY tests passed in that main run.

## Additional offline defect fixed in this continuation

The live publisher applied practical filtering, but `unified_publish.py --offline-input` did not. A real subprocess test reproduced three output records instead of two, including a bulk exclusion list. PR57 reuses the existing `select_inputs` and live scope/provenance audit fields in the offline path, retaining the short PDF and synthetic legacy code; no live publisher, collector, schedule or credential behavior changed.

Branch run **35327225254:1**, test job **105543001400**, at `c564690ac8dda86740819f9b659601d59b9176f4` passed **912 Python tests, 7 KEY tests and JSON-schema validation, zero test skips**. Branch publication was intentionally skipped. Eleven focused tests passed locally; a separate local all-suite attempt lacked project dependencies, notably `protego`, and is not claimed as passing.

The actual repaired CLI also replayed all 3206 reconstructed historical inputs: it excluded the same 64 bulk records and produced exactly the same 3142 practical records, including JSONL output, as current Sheet reconstruction. Private input bytes remained unchanged. No source requests, OCR or provider credits were used for this verification.

PR57 merged as **37a9617572d03aeb9de260f82a2d4c1bba60974e**. Its independently read tree **d7d847313f44c48cea6116ea0b2813caddfda8ca** exactly equals the tested branch tree. The merge's push-triggered jobs were intentionally skipped to avoid repeating the already accepted Sheet migration; schedules were not edited. Executable SHA256: `unified_publish.py` = `bf4fd4cefe4c1bb219819c423c22aa4647a876bcc50b473f4973d2f0c8b6f50e`.

## Limits

This completes the scope cleanup and offline guard, not every missing practical source offer. Historical RZD missing details, EKP gated observations and Coral discovery boundaries remain separate. `current` means current normalization, not current validity or a new source fetch. Rates, eligibility, geography, dates and redemption channels must still be checked per matched offer. Hidden sheets are not access controls; the earlier `anyone:writer` ACL observation was not re-audited or changed. No paid service, source login, permission change, private export or coupon issuance was introduced.
