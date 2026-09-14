# Live extraction release review — 2026-09-14

## User acceptance criterion

Production output must be extracted from the current source response, not replaced by an answer transcribed for one known publication. A fixture is test input only. A new supported document URL, changed amount, page count or caption ID must be read without updating stored answer data. Unsupported semantic or layout changes must remain explicit failures, not yesterday's values.

## Recovered branch evidence

Run 34872914267 executed the actual production dispatcher for ten affected sources. It returned 107 records with ten successful source reports. Artifact 10358774321 SHA256: 80c8f494c898427e1aa9f386f06a0fc5d7212244be0ef79b8d030075fc9a6e5f. ZIP CRCs and all 90 archived runtime/test file digests were independently checked. The 107 records passed the JSON Schema, application evidence/identity validation and publisher preparation after download.

470 Python tests and seven KEY tests passed in that Actions run; both suites were rerun successfully in the recovery environment. The recovery environment has pypdf 5.9.0, while Actions uses the repository's pinned 6.18.1. The latter run is the exact production-dependency test evidence. No repeated network crawl or local repeat OCR was used for this recovery review.

## Findings and corrections

- Main 2.8.0 really contained an RGO/Beeline manual transcription gated by a PDF content digest. This is removed, not described as already generic. The compatibility entrypoint now calls live native-text/OCR extraction for discovered public RGO PDFs. Its old retained record is evidence-only in the common projection.
- Utair's checked-in shortlink/title/page-count inventory and sparse-page answer exception are removed. Links and labels are discovered again from each current landing page. Current files are fetched, and duplicate bytes are merged only within that run.
- Multi-caption Telegram media is recognized by DOM ownership and same-channel member permalinks. No production lookup targets the formerly failing post ID. Unowned or conflicting text is rejected.
- Direct same-host PDFs on the three recovered HTTPS pages are discovered from current scoped page content, fetched and bound to parent/document hashes. Unknown external hosts are not automatically followed.
- Fixed MiXX selection-slot and powerbank session-day output values are now read from clauses. Financial-PDF page and tier counts no longer require the previous snapshot's exact counts.

Mutation tests vary IDs, values, file names, document titles, page counts, caption content, listing membership and rule-tier counts. They test changed output, stable source identity where applicable, no invented fallback, and preservation of partial results. They do not prove correctness for every future layout.

## Deliberate remaining boundaries

Site adapters still contain source routes, selectors, identity aliases, required semantic markers and explicit supported clause grammars. A repository-wide static scan is not a proof of universal semantic generality. New websites, new storage hosts, wholly new service categories or unsupported wording can require an adapter change and must not be silently guessed. Security CA digests and finite resource limits are not stored benefit answers.

OCR was inspected against a rendered RGO source page. It has recognition errors and omissions, including small/colored text; no manual repairs were injected. Exact machine text and OCR uncertainty remain visible. An extraction job with no runtime errors does not certify full transcription, table semantics or current offer eligibility.

Publication, normalization, preservation checks and final run counts must be recorded in the release PR after the main run. This document is a code/branch review, not proof that Sheets publication has already happened. Existing schedule flags and Google permissions remain unchanged.
