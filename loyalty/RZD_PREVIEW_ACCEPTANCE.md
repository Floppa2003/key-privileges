# RZD catalogue-evidence release: accepted 2026-09-16

## Verified outcome

PR44 is merged at `4ca372cd798845d5b953e5ad75339d08c589747d`. Trusted-main run **35135328617:1** used that exact revision. Regression, collection and final publisher job **104938549763** completed successfully; every publisher step was independently read after completion.

The new run returned **74 source records: 66 full detail records and eight separate catalogue observations**. The existing 66 detail identities were updated. The eight new `catalogue:<path>` identities were added at **parser_offers rows2461–2468**. They do not overwrite a previously read full detail, infer a code or represent eight fully verified discounts. The source report remains **partial**, with eight unresolved detail reads and `all_discovered_details_read=false`.

Source calculations: `2026-09-16T18:36:17.903769+00:00` to `2026-09-16T19:11:05.452072+00:00`. There were99 import attempts and97 preserved successful observations: robots, home,23 catalogue states and72 detail responses. Six of those detail responses lacked usable conditions; two further imports returned errors. The23 category-pager states disclosed74 same-host detail URLs; source-owned pagination was exhausted. The26 recorded external-link occurrences were not fetched and are not asserted to be26 distinct missing offers.

## What the eight observations preserve

| Source-linked offer | Full-detail result | Retained information |
|---|---|---|
| Renaissance Smart Plus |Google import error|The actual catalogue summary and its own more-information text|
| Grand Karat Sochi2026 |Google import error|The actual catalogue summary and its own more-information text|
| Admiralteyskaya |Insufficient detail content|Same-card public summary and body|
| Hilton Garden Inn Volgograd |Insufficient detail content|Same-card public summary and body|
| Sakvoyazh impressions |Insufficient detail content|Same-card public summary and body|
| Chekhoff Moscow |Insufficient detail content|Same-card public summary and body|
| Station Hotels |Insufficient detail content|Same-card public summary and body|
| Airo |Insufficient detail content|Same-card public summary and body|

These are labels for this observed run, not hardcoded runtime membership. Each run discovers the catalogue again. A card's `.article__item` ownership, own link, source element ID, category, summary and `.more__inf` body are bound to its sanitized catalogue observation. Neighboring offers are never substituted for missing conditions.

A material source inconsistency is retained: the Renaissance card advertises4000 points in its summary and final step but4545 in another sentence. Neither figure is selected as a verified reward. All eight records use `source_observation`, empty benefit fields and no inferred rates or codes; common normalization marks them `evidence_only_no_automatic_benefits`. Full source text and the unread detail URL remain available for human review.

The earlier separate login-form investigation is recorded in CORAL_IMPORT_COVERAGE.md: six corresponding anonymous detail pages showed a main-content sign-in form with their own return path. That is evidence of the observed login boundary, not a successful authenticated read. The two Google import errors are not proof of origin404, deletion, expiry or technical impossibility. This run did not use an account, submit forms or issue coupons.

## Independent source and destination checks

Public artifact **10464307885**, SHA256 `84a9e1a7526da45cca7d637ffd0b618c6de509b86edecd03343eb2a0595619b3`, was downloaded and checked against GitHub metadata and ZIP CRCs. Every typed observation passed its existing source contract. All74 records were independently reconstructed from those observations, including the catalogue-page ownership and failure-to-preview mapping, then passed JSON Schema, application validation and production publisher preparation. No old answer fixture or alternate policy implementation was substituted.

An export of the SAME destination after publisher completion was read without modifying it. **All1850 managed source-row fields and14 coverage fields matched** the newly collected payload. The output IDs were unique and all74 records were present. The exported workbook includes private legacy inputs and was not attached to public artifacts or committed.

Native destination checks after the final publication also read:
- `parser_offers!A2461:F2468` and `W2461:Z2468`: all eight new evidence-only IDs, categories, hashes, observation dates and run markers; trailing manual cells remain blank.
- `parser_coverage!A1280:N1280`:74 discovered/74 retained/8 errors/partial, explicitly66 accepted full details and8 catalogue previews.
- `normalized_records!S3109:W3116`: all eight new records have zero automatic benefit/condition/cost/code projections and explicit evidence-only limitations. Existing top-aligned wrapped10pt formatting remains in the native common-view samples.
- `normalization_audit!D7:J7`:verified/current, **2467 retained parser records and3115 unified records** at this checkpoint. These totals include the earlier Coral ALEF addition and are not all fresh RZD observations.

Checkpoint source fingerprint: `afd08619d530932d500d55af7ff54aec5467dfe244d2df3cc3c85877d7707df9`; generation:`523676b0700b1165d5c61bf99d42a031ac9cdf5d61d1e5347682c50f3ba60e47`. A later valid publication can change these aggregate values; per-record RZD provenance remains its own run.

The main test archive **10462228397**, SHA256 `95756b44c2eed6e6d111d661dd3af2cf24ff1496c1601484e942affcafa808e3`, was downloaded and CRC checked. Its logs record **753 Python tests and7 KEY tests passing without skips**. The full local policy/bundle validator was not rerun because its optional policy dependency is absent locally; the actual GitHub collection and publisher both passed that complete validation. Local verification is source reconstruction and application/schema validation, not a fabricated replacement for the source-policy check.

## Operation and limitations

The existing **Wednesday08:37UTC /11:37Moscow** schedule,20-second source delay, Google WIF authorization and destination writer are retained. This path uses **zero ScrapingAnt credits**. Limits remain32 catalogue states,100 rotating details,135 imports and3300seconds. No paid service, second account, server, new permission or source authentication was introduced.

Google imports expose parsed calculation results, not origin HTTP status, redirect chain or cache age. Import timestamps are not proof of uncached origin downloads. Eight full details, external links, image-only/PDF terms and personal eligibility remain unverified. Catalogue evidence does not close these gaps. The link-accessible destination must not receive account-only material or credentials without resolving sharing first.

The temporary Coral probe used during acceptance was a separate tab and was removed with metadata readback; the production RZD scratch area was not edited manually. The completed collector reported verified cleanup. Future scheduled success must be observed, not inferred from this single accepted run.

Run: https://github.com/Floppa2003/key-privileges/actions/runs/35135328617
