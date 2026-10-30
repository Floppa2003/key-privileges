# Daily merchant channels — 30 October 2026

Owner authorization: add successfully audited channels to the existing daily queue. No purchases, subscription changes, paid fallback or automatic Sheets publication.

## Runtime and scope

The existing `merchant_queue.py` / `merchant_extract.py` remain the entrypoints. `merchant_channels.py` defines exact routes/adapters/allowance guards; `merchant_credit_prices.py` bounds donated-credit cost. There is no second scheduler or queue. The original prompt, schema, all text/images and evidence/contract fingerprint are unchanged.

Daily cron remains `5 0 * * *` UTC (03:05 Moscow). Actual scheduled starts can be delayed. Scheduled/manual defaults are at most 300 captured pages and 500 HTTP attempts overall, with existing 20-minute capture and 75-minute pool admission windows. These are ceilings, not promised throughput. Main runtime/workflow pushes run a bounded deployment check of 4 pages / 4 attempts, not a second full batch.

Provider order is defined once in `merchant_channels.DEFAULT_PROVIDERS`:

| Order | Provider | Exact model | Local attempts/day | Minimum spacing | Additional guard |
| --- | --- | --- | ---: | ---: | --- |
| 1 | OrcaRouter | `deepseek/deepseek-v4.1-flash-free` | 50 | 7 seconds | Existing persisted quota/reset handling |
| 2 | Experiential | `deepseek-v4.1-flash:free` | 100 | 7 seconds | Stop after 1M reported input+output tokens; retain free-only suffix |
| 3 | Kilo | `nvidia/nemotron-3.5-super-vl:free` | 180 | 20 seconds | Shared IP allowance remains server-enforced; no rotation |
| 4 | Vercel | `nvidia/nemotron-3.5-super-vl` | 100 | 2 seconds | Audited donated $5 only; $1/day donated-credit ceiling with worst-case reservation |
| 5 | Google native | `gemini-3.8-flash` | 20 | 15 seconds | **Blocked until this key/project's Free Tier billing is independently verified** |
| 6 | Token Harbor | `deepseek-v4.1-flash:free` | 200 | 2 seconds | Existing weekly shared allowance remains server-enforced |

**OpenRouter is excluded from the automatic list.** Its Super VL integration canary on 30 October (run 41110786925) returned valid JSON and five matching evidence quotes but imported the neighbouring Mendeleev card's screenshot/identity-document requirement into EKP. This supersedes the earlier one-case pass. The exact registered route and quota adapter remain available for explicit diagnostics; no automatic quality re-enable or retry-until-pass was added.

All numeric attempt ceilings are project safeguards, not independent provider grants or additive guaranteed capacity. Quota/access refusals pass pending documents to another approved channel. Successful answers are cached across providers. An invalid answer or unknown network execution is not regenerated through another account in the same run. New channels use one POST per item; old routes retain their bounded HTTP retries. No model answer repair or web tools were added.

## Billing boundaries

Experiential, Kilo and the explicit OpenRouter diagnostic route require finite zero reported cost and reject explicit BYOK. Missing/invalid cost, a nonzero free-route charge, or credential echo stops the pool. Schema validity alone does not establish semantic accuracy.

Vercel is a priced model funded by donated credit, not a zero-price route. Before every call, credit balance and exact-model pricing are read. The runner requires the audited `balance + total_used = $5`. Where `varies_by_provider` is set, it also fetches the exact model's `/endpoints` response, examines **all published providers and regional price books**, and reserves the largest context at maximum input and output rates plus margin. It does not treat the default catalogue price as a bound. Cache-write costs are conservatively added; unknown price fields, unbounded nonzero auxiliary fees or missing endpoint data stop admission before POST.

That reserve is saved before generation. Known actual cost refunds only the unused portion. Ambiguous execution/spend remains locked across runs and UTC days. An unverified new grant, inadequate balance, or a cost above the preflight bound blocks further spending. **Future/unrecognized monthly grants are not automatically certified as free by this initial integration.** No purchase, auto-top-up or billing-setting API is invoked. This is a client-side guard, not an account-wide lock against concurrent independent account changes.

Gemini's successful inference and published Free Tier are not evidence of this project's billing status. The adapter is wired but sends no requests until a real account read justifies `GEMINI_FREE_TIER_KEY_SHA256` (this key's SHA256) and `GEMINI_FREE_TIER_VERIFIED_UNTIL` (UTC timestamp no more than seven days ahead). Missing, expired or wrong-key attestation blocks the channel. No attestation was fabricated or set during this integration.

Existing secret names are retained: `ORCAROUTER_API_KEY`, `EXPERIENTAL_API_KEY` (intentional spelling), `KILO_API_KEY`, `OPENROUTER_API_KEY`, `AI_GATEWAY_API_KEY`, `GEMINI_API_KEY`, `TOKENHARBOR_API_KEY`. Provider credentials are supplied only to inference, not public capture or state publication.

## Durable state and publication

State remains `loyalty/llm-state:state.json`, version 1. The original Orca ledger stays at the root; added providers have separate ledgers under `providers`. Accepted JSON and its provider/model provenance survive refresh failures. UTC day changes reset daily counters, not completed results or unresolved spend locks.

The original concurrency group `merchant-daily-orcarouter` prevents races between old and new daily executions. Each state push is followed by a remote fetch and verification of commit and JSON hash. Raw responses, complete source evidence, ordered images, request fingerprints and summaries remain artifacts. `publication_allowed=false`; no Sheets writer was added.

## Verification record

- Bootstrap run 41109565418: 22 new tests failed before wiring as expected; after integration, all 1563 Python tests and 7 Node tests passed. Generated source commit 37988572666d3955f2297698af1c7f98fceb5720 was verified by remote fetch.
- Revision 46dce0fd8f49791e0138289b9ef40b5514c1d805, run 41110786925: 1563 Python + 7 Node passed again. Real canary used the saved theatre case, all 4 PNGs and 4608 text characters, through the production queue with scratch state. Experiential and Kilo preserved the essential conditions at zero reported cost. OpenRouter failed semantic attribution and was quarantined. Vercel was blocked by the initial conservative pricing guard before POST; no credit was spent. The failed run remains failed and its outputs are retained.
- Read-only run 41111966298: exact Vercel `/endpoints` and model API both returned 200, exposing Baseten, DeepInfra, GMI Cloud and Together AI price books. A separate documentation-page fetch returned 403, so the workflow is not called wholly successful. API evidence artifact 13004620706 remains available.
- The corrected guard has additional regression tests. The final verification reruns regression and **only** the previously blocked Vercel canary, then combines immutable prior Experiential/Kilo artifacts without replaying their requests. It never replaces OpenRouter's bad answer with a subsequent lucky sample.

These are integration tests on one familiar document, not a broad or blind quality benchmark. Production deployment and durable-state acceptance must be verified separately after merging. No branch canary changes production state.

## Rollback

Disable `merchant-llm-daily.yml` to pause processing. To revert added serving channels while preserving progress, explicitly set `orcarouter,tokenharbor` for both prepare and pool. Retain the state branch and all accounting locks; do not reset counters or delete accepted results.
