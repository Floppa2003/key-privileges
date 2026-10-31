# Confirmed-channel integration — 31 October 2026

## Binding scope

The user explicitly approved enabling the five routes verified on 30 October in the existing daily GitHub queue. Preserve OrcaRouter and Token Harbor, durable state, full text and all original PNGs, the extraction prompt/schema, and review-only JSON. No Sheets publication, model web search, purchases, paid fallback, account changes, source-specific parsing rules, or unrelated scraping gates.

Base main: `9f9ec635f98e3940f82fad1d70a68fc7eeeebf39`. Implementation branch: `loyalty/confirmed-channels-20261031`. The older diagnostic branch is evidence only and is not merged wholesale.

## Configured channels

| Channel | Requested model | Existing credential | Local attempts/day | Minimum interval |
| --- | --- | --- | ---: | ---: |
| OrcaRouter | `deepseek/deepseek-v4.1-flash-free` | `ORCAROUTER_API_KEY` | 50 | 7 s |
| Token Harbor | `deepseek-v4.1-flash:free` | `TOKENHARBOR_API_KEY` | 200 | 2 s |
| Experiential | `deepseek-v4.1-flash:free` | `EXPERIENTAL_API_KEY` | 100 | 7 s |
| Kilo | `nvidia/nemotron-3.5-super-vl:free` | `KILO_API_KEY` | 200 | 20 s |
| OpenRouter | `nvidia/nemotron-3.5-super-vl:free` | `OPENROUTER_API_KEY` | 50 | 4 s |
| Vercel | `nvidia/nemotron-3.5-super-vl` | `AI_GATEWAY_API_KEY` | 200 | 2 s |
| Google native | `gemini-3.8-flash` | `GEMINI_API_KEY` | 20 | 7 s |

These are application workload ceilings, **not newly granted provider quotas**. Experiential also stops locally after 1M confirmed tokens/day; its `:free` endpoint enforces the provider allowance. Token Harbor's cost-denominated weekly allowance can run out before the local 200/day cap. Kilo's shared infrastructure/IP limits may reduce actual throughput. No quota evasion or IP rotation.

Daily cron stays `5 0 * * *` (03:05 Moscow); GitHub may start later. The default run captures at most 300 public targets and attempts at most 500 calls within its time budget. This is not a promise of 300 successful documents, 500 successful requests, or a daily full-catalogue refresh. Per-channel time slices allow later channels a chance to run rather than letting the first slow route consume all runtime.

## Durable state and input behavior

The existing `loyalty/llm-state` writer lock and state version remain intact. The Orca ledger is not reset. Each added channel has its own attempts, confirmed tokens, and pause timestamp. A provider access/quota refusal does not prevent the remaining independent channels from proceeding. Unknown transport outcomes and completed-but-invalid model answers are not repeated through a second account in the same run.

Accepted evidence/contract fingerprints remain compatible with the old cache. Adding a provider does not invalidate all accepted JSON. Exact requested/returned models and serving provider remain attached to results. The prompt, schema, full text, and every source PNG remain unchanged; the Google adapter only translates the wire format and omits thought parts from the final answer. No external model tools/search are supplied.

Token Harbor's explicit weekly reset in the error message now takes precedence over a shorter `Retry-After` header. This avoids treating an hourly retry hint as renewed weekly allowance.

## Vercel free-credit admission

Vercel uses the previously verified promotional grant, not a zero-priced route. It has a durable $4.50/calendar-month local budget, $0.25 reserved before each network call, and a $0.50 balance floor. Current account balance and exact model pricing/context are read before a call. The full-context-plus-maximum-output upper cost must fit the reservation. Unverifiable/insufficient balance or pricing defers Vercel only; no account or billing API is mutated.

There is one generation attempt per reservation. A completed response settles it to reported cost; a timeout or missing cost retains the whole reservation. No credit purchase, auto-recharge change, or paid model fallback is implemented.

## Decisions, assumptions and review limits

- Ruling: preserve cache compatibility across the approved models, with exact provenance. This avoids unnecessary regeneration; quality equivalence on every page is not guaranteed, so results remain review-only.
- Ruling: enable Vercel against the existing verified free grant using the bounded policy above. Its balance API does not identify the funding source of every dollar. Other applications/account changes are outside this queue's concurrency boundary; this is not a provider-side billing lock.
- Ruling: Google uses the existing project's published free-tier setup, with a small local ceiling. API-key inference alone does not independently attest Cloud billing configuration; this change does not activate a paid tier.
- Ruling: the explicit request to enable these channels authorizes integrating the scoped changes into main after successful checks; a second request to choose whether to leave a PR unmerged would not accomplish that request.
- Runtime limitation: local container/Python returned ClientError. Tests and source transformation ran in isolated GitHub Actions without exporting model credentials. The one-time builder and patch script were removed after verified source commits; their history and artifacts retain the evidence.
- Review is an author self-review against the requirements, not an independent human/subagent review. No claim of a broad blind model-quality benchmark.

## Verification ledger

1. Initial RED: tests `7388fd7`, workflow `19d8ce1`, run `41194836341`. The 15 new contracts failed against the old two-provider implementation (missing routes and short weekly-reset delay). Logs were read; the initial test workflow also lacked the required poppler declaration.
2. First implementation run `41195226923`: all 15 new contracts and 7 KEY tests passed. Full Python suite had exactly one remaining failure, the test-workflow PDF dependency declaration. The source commit was correctly withheld.
3. Corrected build `41195590428`, source base `3883c232546bac090766ee51252a4c56dbb0f859`: 15/15 new contracts, **1556/1556 full Python tests**, **7/7 KEY tests**, no skips. Tested source files committed as `bf81ca3`; the runner fetched the feature ref again and verified its SHA. Logs independently read through the GitHub connector.
4. Build artifact `13041335124`, ZIP SHA256 `ecfd548ff930dc4d4db945030c4ee3e2e84fa14cce2c1c4c98e59cdf688884ee`, includes executed source, production patch, test logs and internal hashes.
5. Final boundary coverage adds three tests for malformed native responses, independent per-channel manual caps, and prices exceeding the credit reservation. These exercise the real extractor/queue; only HTTP is replaced.
6. Merge and a small production verification run are still to be recorded in the PR after final checks. The intended verification uses the same daily workflow, five approved new channels, at most one attempt per channel, and independent durable-state readback. No full-catalogue or duplicate model benchmark is required.
