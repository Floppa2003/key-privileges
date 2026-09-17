# RZD external partner conditions — accepted 2026-09-17

## Completed source-to-destination release

PR49 merged as `f21dcbd7e361d2666f3314fb70ae15d25a136a5e`. A one-line follow-up, `c6bc13f0bce9ff2630a0d08131ffc959cfaad5cd`, includes both external test modules in the workflow's push selector. It did not change collection, credentials, the schedule or publication logic.

Trusted-main run **35227462966:1** completed regression, collection and publisher **105224771705**. Every final publisher step and job was independently read as completed/success. Actual source interval: **2026-09-17T13:31:33.331169+00:00–13:36:11.693511+00:00**.

| Scope | Source objects checked | Published records | Exclusions / final errors |
|---|---:|---:|---|
| Cruise-tour pages discovered from the RZD Tour homepage and linked cruise category |35 tour details|34 tour-specific offers|One inspected page without an RZD clause in its owned pricing block; zero errors|
| Exact catalogue-linked UniCredit CASH&BACK page |1 page|1 evidence-only product reference|Zero errors; RZD exchange not confirmed|
| Reward-rule PDFs linked by that bank page |1 actual PDF,12 native-text pages|4 numbered text parts|Zero extraction or download errors|

**39 new source identities were published, not39 additional monetary discounts.** No old tour list, rate, PDF answer text or fixed page count is the runtime input. URLs and rule labels are re-discovered from current source responses within the declared scope. There were **41 ordinary HTTPS requests and zero provider credits**.

### What the tour records mean

Each of the34 accepted pages independently contains its own RZD Bonus5% clause and the requirement to buy through the RZD Tour sales office or submit a website application with a card number. Most also explicitly state that discounts do not combine; the exact per-page wording is retained rather than added to pages that omit it. The complete owned pricing text and table cells remain attached to that tour. Other child discounts, prices, airfare exclusions or neighbouring navigation are not automatically advertised as RZD benefits.

The inspected exclusion is `https://rzdtour.com/kruiznyie-turyi/kruiznyie-poezda/dva-serdcza-kavkaza`. It is not a failed download or proof that no discount can ever apply to that tour: no RZD clause was present in the selected owned pricing block. Booking availability, current departure applicability and personal eligibility were not checked. This is the homepage/cruise-category-linked selection, not every product or route sold by the tour operator.

### What the bank records mean

The bank target is the exact public product path previously linked by the RZD catalogue. Its present text and the linked reward document do not substantiate the older catalogue's1:1RZD exchange claim. Neither cancellation nor personal ineligibility is inferred. The product page remains a `source_observation`; the PDF parts are `program_rules`, with no automatic benefit/code projection from unrelated cashback, penalties or examples.

The PDF URL is dynamically discovered from the source's reward-rule download row. Its12 pages were downloaded as actual HTTP200/application-pdf bytes: **240902bytes**, SHA256 **`c9db3bc59fea0645579888f4d1a453c1b5089a7accf601878c66ebfc155f2610`**. The main binary matches the exact candidate binary whose12 pages were locally rendered and inspected. All12 yielded native text; no OCR or manual transcription. Table relationships and legal interpretation are not certified by text extraction. The title comes from the source download label when PDF metadata is empty/numeric, not a hardcoded document title.

## Recovered implementation and two demonstrated repairs

An interrupted earlier turn had already written the external collector on `loyalty/rzd-external-20260917`. It was recovered rather than replaced. Initial run35217733868 passed821Python/7KEY tests and collected26 tour offers, but ignored the source's HTML base tag, inventing21 nested navigation URLs and missing real links. A failing regression reproduced this. The source-root base correction removed those false targets and discovered35 real tour URLs, including nine absent from the initial selection.

Run35225236034 passed828Python/7KEY tests and collected34 tour offers, one bank reference and four PDF parts. Its remaining tour error was a second H1 inside the owned pricing block, not a second tour identity. Two new tests failed before the correction; the mapper now retains that heading as a condition and uses the unique heading outside the pricing block as identity. It can correctly inspect/exclude that no-RZD-clause page rather than hide a layout failure.

Final branch35226300040 passed **830Python/7KEY tests**, then obtained the same39-record, zero-error selected scope. Its production mapping, normalization and security tests vary source slugs, labels, titles, rates, PDF content, base tags, ownership, missing clauses, refusals and tampered receipts. No publication occurred on the branch.

The first merge-triggered external run35227125225 was cancelled in the existing shared concurrency queue before any job/source read. A failed-jobs rerun was refused. The follow-up selector fix triggered only the external workflow, whose real main acceptance is35227462966; cancelled queue state is not counted as a source failure or successful collection. The shared publication exclusion mechanism and all old schedules were preserved; no broad reliability guarantee follows from this one accepted run.

## Independent source and destination verification

All downloaded candidate/final/main archives passed GitHub SHA256 metadata and ZIP CRC checks. Main artifacts:

| Artifact | ID | ZIP SHA256 |
|---|---:|---|
| Actual main source responses and output |10500191892|7634495defd88743594794435f3da48757fca6afd05e50a777e48a34b368e82f|
| Exact main code and test logs |10499058804|371a9c53d96e40d2d8180cd1cef2340a7d331b414e902712a0146ca25a0afaa2|

The main test log confirms **830Python/7KEY passed, zero skipped**. All six changed file blobs in the archive matched reviewed bytes, accounting for the explicit one-line workflow selector change. Every source record was independently reconstructed from the archived actual responses using exact executed code, then JSON-schema validated. Offline replay explicitly supplied the source completion time as a historical validation clock; it is not a new fetch or assertion that archived data passes a future freshness gate. The real publisher independently validated its live bundle before obtaining Google credentials.

Destination is still **`1uFR7croj7p6RRNPcoTRYlVl06hKsurkIgyu1IdMMB-4`**, title **`скидки`**. A fresh baseline was read before publication and another read-only export after the final write:

- **1017 managed fields matched:**39records×25 +3reports×14.
- The39 new identities are at **parser_offers2481–2519**:34tours2481–2514, bank reference2515, PDF parts2516–2519. All39 hashes, source times and run markers were also read natively.
- **parser_coverage1392–1394** reports all three scopes `ok`, zero final errors. PDF record counts mean four parts of one file, not four files.
- Common rows **3129–3167** were checked against the actual per-record projection, including IDs, titles, source rows, dates, counts, current generation, and all current benefit/condition/code component IDs and evidence text. The34tour records each have one benefit and one condition; the bank reference projects zero automatic terms; each PDF part has one condition and zero benefits/costs/codes.
- All **2479 pre-existing parser rows**, their manual comments, **1390 old coverage rows**, and values/formulas in six other original input/audit tabs were unchanged against the baseline. Private exports were not published or committed.
- Final manifest: **verified/current;2518 retained parser records /3166 unified records**. The baseline was2479/3127, not the previous user-reported2477/3125: an independent earlier scheduled collector had added two source rows before this release. This external release adds exactly39.
- Source fingerprint:`82d3e40e51bcb91889cdeafe395fa6c80c34ca512b260723b68050506d1b32c5`.
- Generation:`47a0164a42d59386a66976fc1df30f058cb650339c0ff002235915fdcdece0a0`.

Native common-view samples retain top alignment, wrapping and10pt text. An attempted artifact-tool import for rendered checking failed at daemon startup; no rendered whole-workbook audit is claimed. This does not affect the exact value/structure/native-style readback. No workbook restyling or permission change was performed.

## Recurring operation and limits

New external refresh: **Wednesday09:57UTC /12:57Moscow**, under GitHub, writing the same destination. Existing source workflows keep their schedules. No ScrapingAnt/other provider key, source account, paid service or new Google scope is used. The existing conservative provider allowance6454/31days is unchanged, excludes manual diagnostics/other account usage, and is not a current balance measurement.

Bounds:80tour details,4PDF files,90requests,900seconds,2MBHTML/6MBPDF, minimum5seconds between same-host requests and source-declared delay/rate checks. No redirects, login, coupon issuance, purchases, bonus spending or unlimited retries. Collection has no Google credentials; only validated output reaches the separate existing WIF publisher. Discovery is bounded rather than every hyperlink on either domain.

## Remaining maximum-coverage boundary

This closes the demonstrated reachable RZD external selection, not the entire programme. RZD's eight own-host full-detail gaps remain66/74; EKP's110 gated observations, region equivalence and linked/image-only conditions remain unverified. Further external documents across other programmes are not exhausted. Read permission and destination privacy must be resolved before authenticated conditions or personal codes can enter the last-inspected link-editable Sheet. No such privacy change or account connection was attempted here.

Do not repeat the old proxy feasibility probe or reimplement this adapter in the next turn. Prioritize a concrete missing scope, preserve source ownership/dates, and require successful publication/readback for additional release claims.
