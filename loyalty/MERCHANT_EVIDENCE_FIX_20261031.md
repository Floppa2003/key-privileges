# Merchant source-evidence fix — 31 October 2026

## Approved scope

Fix the observed collector → LLM information loss in the existing daily queue. Keep one model call receiving original evidence and returning JSON. No model web search/tools, intermediate summaries, hardcoded merchant benefits, paid fallback, purchases, billing changes or automatic Sheets publication. Existing seven providers, limits, schedule and state writer lock are preserved.

Base main was `1860e95378c34af7ed11549c73af16e08715bf57`; work branch `loyalty/merchant-evidence-fix-20261031`. The historical four-case regression is a diagnostic sample, never a production partner allowlist.

## Root cause and actual UI

Discovery retained only the partner/program/source URL and discarded complete collector records, including `details.public_item` and `native_id`. For Konsierge, all these URLs were the common catalogue. Generic capture returned a loader or unrelated first-page teasers. Empty extraction JSONs were cached as successful work.

Read-only live browser investigation found the native objects for Memo, Hide, El Copitas Bar and Po’mestam through normal public category navigation/pagination. Clicking their teaser cards does not open a detailed offer. The full conditions are in the public responses used by the page, not in a hidden detail modal. No fictitious detail URL or screenshot has been invented.

## Implementation

- All distinct collector records for each stable target identity are retained by deep copy. Registry seeds do not shadow actual catalogue evidence. Temporary catalogue absence does not erase previously saved source records.
- Ordinary page inputs retain explicitly dated collector snapshots with their complete original data; normalized fields are labelled as such, not passed off as verbatim source quotations. Original snapshot sidecars and native objects have verified hashes.
- The Konsierge capture adapter obtains fresh browser-owned native responses, locates the current target by its original ID, corroborates title/label, and captures the complete target card(s). All PNG tiles are retained. Exact native public fields, including the full description, and the acquired page text go to the same model call. Old catalogue snapshots remain an audit attachment, not a fabricated live fallback.
- Missing target data becomes `needs_source`, not `has_offer=false`. Explicitly unresolved input is not sent to a model or hidden by an older cached response. Other queue items continue normally.
- Old negative answers lacking the new evidence contract are requeued once; previous response history remains in Git. Valid positive results are not erased. Fresh successful evidence clears the recovery flag.
- Native JSON serialization is deterministic. The cache ignores only collector bookkeeping (`observed_at`, `details.source_run`, `details.capture_sha256`) inside our explicit snapshot appendix, not source dates/conditions or the actual page. The stored and sent input retains those metadata fields. Changed actual terms still invalidate the cache.
- The original prompt also said to stop at a heading for a separate benefit. This could drop additional benefits inside the same target. The boundary is now another program/card/partner; all monetary and non-monetary benefits inside the target belong in `offers`. This is a general scope clarification, not merchant-specific output repair. It changes the prompt fingerprint, so earlier cache results are not falsely considered generated under the new instruction.

## Verification ledger

1. RED run `41204709724`: seven source-loss tests reproduced six failures and one error against the original queue. Diagnosis intentionally continued to collect browser evidence; its green job did not mean the regression was green.
2. Read-only UI probe `41204928537`: all four native objects and exact teaser DOM nodes acquired. No model calls or production-state mutations.
3. Build `41205532299`: **1566 Python tests + 6 real-Chromium HTTP-fixture tests + 7 KEY tests passed**. Tested source transformation committed as `48aff69a7b3f22ee171ced7a9ef7333c08995089` and read back. Artifact `13043468418`, ZIP SHA256 `02787f2850b5ebb923c42e2e449d1a4d8eac89338f00c6792a0a7b6062a8bfcc`.
4. Cache boundary RED→GREEN build `41205970623`: initial four cache tests showed two failures and one error. After refinement, **1570 Python tests + 6 browser tests + 7 KEY tests passed**, no skips. Tested source commit `1dcdba775c43e4633752c64250b6c8d273400c10` read back. Artifact `13043778478`, ZIP SHA256 `ac8fb7b7de8ba28eb5aa25d37f8b3c34649b982a90d69628038408baafadbf3a`.
5. First live extraction `41205750809` used current native objects and four original target-card PNGs: four Experiential `:free` requests, four completed JSONs, 38,603 total tokens, reported cost zero. All four discounts and concierge-booking instructions were recovered; **Hide and El Copitas lost the additional priority-seating benefit**. This was not a full semantic pass. Artifact `13044468348`, ZIP SHA256 `03910360b3be1ee8a4cf1907a9bccd01000b4cf2e9222f9e7eddf2458cd6a312`; independent job `124551529629` verified all 71 hashes and printed the original answers.
6. Final acceptance additionally requires all three priority-seating benefits, and first checks that the stronger assertions reject the saved earlier omission without another model call. Final CI/live results and rollout readback will be recorded in the PR; they are not claimed by this pre-rollout note.

## Decisions and limits

Source-adapter selection is based on the catalogue protocol, never on a finite list of partner names or discount percentages. Shared catalogue detail acquisition for other sites is not automatically solved by the Konsierge adapter, though the generic source-record handoff is fixed for all records. Renderer changes may still require adapting a source protocol.

`completed` remains transport/JSON completion; semantic approval/publication is separate. Tests with original data are a small familiar regression, not a blind accuracy estimate across every source or model. Provider reasoning settings are unchanged in this source fix. Quota refusals and provider outages remain possible.

The generic prompt clarification deliberately invalidates the old prompt cache on subsequent reads. No bulk deletion of historical outputs or quota-ledger reset is used. Corrected source lookup requires page loads; the 300-target limit is still a workload ceiling, not guaranteed daily throughput.

Tests ran in GitHub Actions because local container/Python execution returned ClientError. Sources and results were independently read through the connected GitHub app. Review is author self-review, not an independent reviewer.
