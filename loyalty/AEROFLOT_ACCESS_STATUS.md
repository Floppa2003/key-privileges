# Aeroflot original catalogue: implemented public-company scope — 2026-09-16

## Current decision

Requested source: `aeroflot`, https://www.aeroflot.ru/ru-ru/afl_bonus/partners .

**Operational status: `implemented_and_published_for_current_company_catalogue`.** Production run **35094999686:1** read all **229 distinct company partners in 15 categories**, obtained a separate current import calculation for every detail, and completed the existing publisher and unified normalization. The new rows and final manifest were independently read back from the actual destination. This supersedes the earlier `blocked_by_source_crawl_policy` operational decision; it does not claim that the public robots file changed.

The owner reports receiving Aeroflot's email approval for the previously discussed parsing method and explicitly requests continuation. Searches of the three connected Gmail accounts did not locate that approval. Permission is therefore recorded as **owner-reported**, not an independently read email. No email contents, account identifiers, SMS, cookies or tokens were put into the repository or catalogue. The exception is limited to this public catalogue and the public category/detail endpoints; it is not a global robots override, a Googlebot identity claim or authorization for account/private areas.

The pre-permission policy investigation is retained unchanged in Git history at commit `1aa98dd2eb39155f1e83923f755d596b103c4565`. It was a scoped prerequisite blocker, never proof that arbitrary GitHub code could not read the catalogue.

## Released implementation and source scope

PR41 merged at `dd9ffb8c5b73eea4af30367ec7ec5c8e27ece821`. The accepted production run used commit `1aa98dd2eb39155f1e83923f755d596b103c4565`; its extra change was a workflow dispatch comment after the first release run was cancelled in the shared pending queue before source execution.

GitHub controls Google IMPORT calculations in the separate public-only staging tab `af_public_fetch`. It uses the existing short-lived Sheets-scoped WIF identity and the existing literal-record publisher for the SAME discount workbook. **No ScrapingAnt credits, new paid service, server, source login or extra API key is used.**

The original root returned its company-catalogue link and a separate airline-catalogue link. The source frontend's category/detail API contract was inspected during implementation. Each normal run imports the root, current categories and each discovered company ID anew; no stored partner answers or diagnostic capture is a runtime fallback. Current category membership and names are not fixed in code. The company category response uses `lang=ru`, which is a source-language parameter, not a verified eligibility region.

Source fields keep separate roles: short description, earning conditions, spending conditions, award fields, special-offer references and outgoing links. A successful source-text extraction is not a claim that all conditions are understood, still valid or applicable to the owner. Existing partner-side records are not semantically merged with the new official catalogue records.

The parser uses bounded, explicit IMPORTDATA delimiters and typed-cell validation rather than silently repairing damaged CSV/JSON. The delimiter/locale behavior was observed and tested; do not assume undocumented import behavior is a permanent vendor contract. Every request verifies workspace identity, clears prior formula state, writes a new generation and exact formula, requires two stable typed reads, and verifies cleanup. Source errors do not become catalogue rows.

## Completed production evidence

Run: https://github.com/Floppa2003/key-privileges/actions/runs/35094999686

- Collection started `2026-09-16T12:18:51.756594+00:00` and finished `2026-09-16T12:46:05.400491+00:00`.
- 232 import observations: one policy, one original-root discovery, one category response and 229 separate detail responses. No duplicate company IDs; all category IDs received matching detail records; zero source/mapping errors.
- Regression, collection and publisher job **104799253783** all completed successfully. This is an actual source-to-destination run, not the earlier four-detail diagnostic.
- Public artifact **10446862972** ZIP SHA256: `8115d22022397e2b64a671d7e6521b9dcbe7206c0b2db42806072be5d9c6499e`.
- Test artifact **10444859633** ZIP SHA256: `a8a3a533ab7949a2ad3f1fc02605d7392633862ad4ffcbd80092d63c928383cc`.
- Both ZIP digests and CRCs were checked. All229 records were independently reconstructed exactly from their own typed observations, JSON-schema/application validated and prepared by the real publisher. Observation ordering, uniqueness and bounded times were checked. The complete bundle validator also passed in an offline replay at the original completion time; this replay is not a new source observation or permission to republish stale output.
- Actual Actions logs show **704 Python tests and 7 KEY tests passing**, no skips. The 23 Aeroflot tests and seven KEY tests were repeated locally and passed. No repeated full local suite is claimed.
- Executed critical file Git blob identities match the runtime commit: collector `c71f1fb14a39fb27c4ddd9f8e220746705755d56`, mapper `2691ebfed5a8c7989705ae3ef500b53aa4747b6e`, workflow `ba26cc73342147045959682195dd9982663fce95`.

## Independent destination readback after the final write

- **229 new rows:** `parser_offers!A2225:Y2453`. All229 native content hashes in column X were compared programmatically with the reconstructed source records and matched. The newline-joined native hash projection SHA256 is `eeb93000109f73417628dc610c1c1e65e459d986b7cf81cd430852142f900cbe`.
- Native search of `Y2225:Y2453` scanned229 rows and matched229 run markers `35094999686:1`; its displayed result was limited to two rows, not the scan.
- Actual first/last IDs, partner names, record kinds and dates were read back. The full public conditions for Chefmarket at2339 and Askona at2390 were inspected natively: earning and spending are separate, and Askona's online-store exclusions remain present. Manual-column samples were blank, not overwritten with output.
- `parser_coverage!A1276:N1276`: `ok`,229 discovered/229 normalized/0 errors, complete observed company-category scope, with airline/linked/personal-eligibility flags false.
- `normalization_audit!A7:J7`: **verified/current**, **3100** unified input/output records, **2452** retained parser records. These retained totals are not all freshly read by this run.
- Final source fingerprint: `6658ee94c83bf9c639f39aba4564a62d7f88c950800002734998b5da28c12e89`; generation: `e5b0443314e2d698fe28b15462c44d65ceeb0e82bfd883bc44505007f8ad2cde`.
- Existing EKP2153 and RZD2224 sentinels retain their own prior hashes, dates and run IDs. Native normalized samples retain top/wrap/10pt formatting. This is all-new-hash/run verification plus declared literal/report/manifest samples, not an exhaustive independent private-workbook or rendered-format audit. The existing publisher performs its full output readback.
- Both complete staging rectangles were read: `af_public_fetch!A1:D4096` and `public_fetch!A1:D2048`. Only headers and their respective idle markers remained; no import formula or old result was left running.

## Regular operation and remaining limits

Weekly **Thursday08:47 UTC /11:47 Moscow**, plus manual and reviewed-main release execution, in `.github/workflows/aeroflot-import.yml`. The next scheduled execution is not yet observed. RZD retains its Wednesday schedule; its ordinary code-push path is now regression-only to avoid an unrelated crawl when the shared normalizer changes. Other collector schedules and provider budgets are unchanged.

Bounds:260 company details,263 imports,3000seconds, at least five seconds between import requests; three consecutive failures stop the source. If the current response later exceeds260 IDs, the selected subset rotates and coverage is explicitly partial. The current229-response result was not truncated by this bound.

**Not covered:** the separate airline-partner catalogue, special-offer pages or rules reached by outgoing links, PDFs/image-only clauses, actual redemption, and individual eligibility. Human-facing detail URLs are not claimed verified: the preserved direct source URL is the actual public API detail endpoint. Public offers can contain login/redemption requirements without any personal account being used by the collector.

Google imports expose parsed calculation results, not origin HTTP status, redirect history or origin-cache age. Observation time is the import request/calculation interval, not independently certified uncached origin retrieval. A successful production pass does not guarantee future network/cron availability.

The destination's existing sharing settings were not changed; only public source data was added. Do not place account-only results or personal codes into it without separately resolving access scope. If the reported permission is revoked or materially narrower than represented, stop the affected source and review the scope rather than broadening the exception.
