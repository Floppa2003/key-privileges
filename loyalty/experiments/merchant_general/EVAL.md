# General merchant researcher: evaluation contract, 2026-09-25

Input: known merchant homepage + programme and programme-level aliases. Discover source-owned pages, follow actual links and extract evidence-bound review candidates with one common policy. No merchant-specific CSS, regex, hand-picked offer paths or prompt hints. Preserve production sources, publisher, schedules and Google Sheets.

## Version and evidence boundaries

London Express is development evidence, not held-out success: the initial broad JSON extractor attributed a generic two-lesson gift to EKP and inferred offer dates from an image filename. The v1 runtime files did not survive context recovery; do not cite their earlier claimed test counts/freeze as accepted code. The visible original model response is an example of why quote checks and semantic verification must be separate.

v2 reduced the output to source quotations and added bounded link navigation. Its first ACADEMIA news read returned HTTP200/markdown but json=null with a provider-generated-schema error. A failing synthetic test also reproduced loss of multiline Markdown links; a separate test covered ambiguous encoded paths. v2.1 fixes these general issues and embeds an explicit typed JSON schema in the shared prompt, since the MCP schema argument was rejected before execution. This is not proof of provider-side constrained decoding. The common prompt is unchanged across v2.1 targets.

The eight input domains are absent from the existing partner_pages config but were selected from previous public leads. They are unconfigured domains, not an unbiased or model-unseen sample. London remains a development regression. Domain resolution from a bare merchant name is not evaluated. Preserve all attempted/failed/abstained/unrun targets; no internet-wide recall claim.

## Gates

1. Discovery: actual search result -> read page -> source-owned link -> read conditions; no snippet used as an offer.
2. At most three searched URLs and three pages per target; real same-host links only, depth2, no source account, issuing, forms, purchases or TLS override.
3. Schema, actual200, exact requested/final URLs, programme identity and exact source quotations. Codes must be literal or explicitly unavailable; dates retain roles. These checks do not prove entailment, completeness or user eligibility.
4. Separate semantic review records benefit mixups, material omissions, code/date errors and uncertainty. Automatic candidates are never certified discounts.
5. No publication adapter: every result has publication_allowed=false. Existing source adapters continue untouched.

## Reproducibility

CLI plan/ingest/report reuses the exact common requests. The optional REST executor uses the same planner with durable reservations before each request; ambiguous requests need reconciliation, not blind retry. MCP success does not certify REST/GitHub unattended operation. REST may use the documented keyless endpoint; API-key billing is not assumed free. Network/source policy and source redirects are controlled partly by the provider, not independently certified by lexical URL checks.

Report requests and actual credit metadata separately from estimates/account balance. No paid upgrade/new subscription/recurrence. A branch-only regression job may test one bounded keyless REST target and must report failure independently of passing tests. Do not publish private workbook snapshots, cookies, tokens or source-account data.

Acceptance pending actual CI/live results. A test count is not a coverage metric.
