# Daily merchant channels — 30 October 2026

Owner authorization: add the successfully audited channels to the existing daily queue. This does not authorize purchases, subscription changes, paid fallback, or automatic Sheets publication.

## Runtime

The existing `merchant_queue.py` / `merchant_extract.py` remain the entrypoints. `merchant_channels.py` contains the exact added routes, API adapters and allowance guards. No new scheduler or second queue is introduced. The original prompt, JSON schema, complete evidence and existing evidence/contract fingerprint are unchanged.

Daily schedule remains `5 0 * * *` UTC (03:05 Moscow). GitHub may start scheduled jobs late. Scheduled/manual defaults: at most 300 captured pages and 500 HTTP attempts overall; existing 20-minute capture and 75-minute pool admission windows remain. These are limits, not promised throughput. Changes to the runtime or daily workflow on main trigger a bounded deployment check of 4 pages / 4 attempts, not a second full daily run.

Provider order is defined once in `merchant_channels.DEFAULT_PROVIDERS`:

| Order | Provider | Exact model | Local attempts/day | Minimum spacing | Additional guard |
| --- | --- | --- | ---: | ---: | --- |
| 1 | OrcaRouter | `deepseek/deepseek-v4.1-flash-free` | 50 | 7 seconds | Existing persisted quota/reset handling |
| 2 | Experiential | `deepseek-v4.1-flash:free` | 100 | 7 seconds | Stop after 1M reported input+output tokens; free-only model suffix retained |
| 3 | Kilo | `nvidia/nemotron-3.5-super-vl:free` | 180 | 20 seconds | Shared IP allowance remains server-enforced; no rotation |
| 4 | OpenRouter | `nvidia/nemotron-3.5-super-vl:free` | 50 | 4 seconds | Read actual `free_model_daily_requests.remaining` before each request |
| 5 | Vercel | `nvidia/nemotron-3.5-super-vl` | 100 | 2 seconds | Audited donated $5 grant only; maximum $1/day of donated credit, with worst-case reservation |
| 6 | Google native | `gemini-3.8-flash` | 20 | 15 seconds | **Blocked until this key/project's free billing status is independently verified** |
| 7 | Token Harbor | `deepseek-v4.1-flash:free` | 200 | 2 seconds | Existing weekly shared allowance remains server-enforced |

All attempt ceilings are project safety limits. They are not separate purchased allowances or an additive capacity guarantee. A pending document proceeds to the next approved channel after an account/quota refusal. A completed answer is cached across providers. An invalid model answer or unknown network execution is not regenerated through another account in the same run. New channels use at most one POST per item; old routes keep their existing bounded HTTP retry policy. No response repair or new web tools are enabled.

## Cost and billing boundaries

Experiential, Kilo and OpenRouter require a finite zero reported cost, and reject an explicit BYOK response. Missing/invalid cost, nonzero free-route cost, or a credential echo stops the pool. Raw errors and invalid answers remain in the artifacts; schema-valid does not imply semantic correctness.

Vercel is a priced route funded by donated credit, not a zero-price model. Before each call, the runner reads the credit balance and exact model pricing. It requires the audited `balance + total_used = $5`, computes a conservative bound using the whole context window and maximum output at the highest reported pricing tiers, and reserves that bound durably before sending the request. Known actual cost refunds only the unused reservation. A timeout or ambiguous spend keeps a review lock across runs and days. New/unrecognized pricing, an unverified new credit grant, or inadequate balance blocks Vercel rather than spending. **Future monthly grants are not automatically certified as free by this initial integration.** No top-up or billing-setting API is called.

Gemini's successful inference and published Free Tier do not prove this project's billing status. Until that is checked, its route is wired but makes no generation requests. A verified deployment may set `GEMINI_FREE_TIER_KEY_SHA256` to the actual key's SHA256 and `GEMINI_FREE_TIER_VERIFIED_UNTIL` to a UTC ISO timestamp no more than seven days ahead. These are attestations following a real account read, not a workaround for missing evidence. Wrong key, missing/expired attestation, or an invalid timestamp blocks the channel.

API keys use their existing GitHub Secret names: `ORCAROUTER_API_KEY`, `EXPERIENTAL_API_KEY` (intentional existing spelling), `KILO_API_KEY`, `OPENROUTER_API_KEY`, `AI_GATEWAY_API_KEY`, `GEMINI_API_KEY`, and `TOKENHARBOR_API_KEY`. They are provided only to the inference step, not capture, dependency installation or state publication.

## Durable state and publication

State stays in `loyalty/llm-state:state.json`, version 1. The original Orca counter remains at the root; other channels get separate ledgers under `providers`. Accepted JSON and its serving provider/model are retained. Failed refreshes do not erase previous successes. UTC-date changes refresh daily counters, not accepted results or unresolved Vercel spend.

The original concurrency group `merchant-daily-orcarouter` is preserved so deployments cannot race old daily jobs. Every state push is followed by a remote fetch and comparison of the commit and JSON hash. Artifacts preserve source text, all ordered PNGs, request metadata, raw responses, per-attempt measurements and summaries. `publication_allowed` remains false; no Sheets writer was added.

## Verification and scope

Bootstrap integration run `41109565418` observed the new tests fail before wiring, then passed 22 channel tests, the full 1563-test Python suite and 7 Node tests after wiring. The generated source commit was `37988572666d3955f2297698af1c7f98fceb5720`, followed by independent remote-head readback. Later workflow changes require their own final regression/canary run before deployment.

The bounded canary uses the saved full theatre evidence from run `40077128489`, artifact `12554050020`, through the actual production queue with scratch state. One familiar document per route verifies integration, not broad extraction reliability. Production acceptance is verified separately from the post-merge daily-run output and durable-state readback.

To pause the entire pipeline, disable `merchant-llm-daily.yml` in GitHub Actions. To roll back only the added routes, set the provider order to `orcarouter,tokenharbor` consistently for capture and inference; keep the persistent state and original counters. Do not discard the state branch or unconditionally reset billing locks.
