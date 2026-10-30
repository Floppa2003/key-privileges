# Provider/model/quota audit — 30 October 2026

## Scope and result

Live checks ran approximately 10:04–10:21 UTC (13:04–13:21 Moscow) using existing GitHub secrets/variables. This is an audit, not a production migration. Only diagnostic files and branch/path-limited, unscheduled workflows on `loyalty/deepseek-capacity-recheck-20261028` were written. No account setting, purchase, subscription, auto-recharge, main code, queue or Sheets was changed. The production ref read at the start and again at the end was `2c486df8553480d427239ed7241fa85740a5ff32`.

**Five additional model/provider pairs actually passed both the image check and a real document extraction with the main offer conditions preserved:** Experiential/DeepSeek V4.1 Flash, Google/Gemini 3.8 Flash, OpenRouter/Nemotron 3.5 Super VL, Kilo/Nemotron 3.5 Super VL, Vercel/Nemotron 3.5 Super VL. This is one familiar document per pair, not a broad or blind quality benchmark. None was added to the production provider pool by this audit.

There were 26 POST generation attempts across three workflows. Thirteen answers were complete and schema-valid: seven synthetic image responses and six document responses. One of those six documents, Kilo Nano Omni, contains substantive source-attribution errors and is NOT a quality pass. Cohere also returned HTTP 200 for its corrected document request, but its output is invalid JSON and contains invented conditions. No failed attempt was overwritten or hidden.

## Method

The image check asks for the four digits in a synthetic PNG (5837). The document check uses the same saved `muzcomedy` page, full text, all PNGs, TARGET, existing extraction prompt and schema for every provider. No model web-search/tool settings, tool execution, intermediate summary or model-based repair. Different API adapters and reasoning settings mean timing comparisons are descriptive, not controlled provider benchmarks.

Inputs come from run 40077128489, artifact 12554050020, `captures/inputs.json`. The source artifact ZIP SHA256 is `39a4d00884c8c421a60a753553dc0b7ae368a769c62df3904b3538ef0fc11948`. Other documents in this four-document/13-PNG bundle were not re-evaluated in this audit. The new comparison sends only the theatre case after a correct image check.

## Fresh working candidates

| Service | Exact requested ID | Image check | Document | Document evidence quotations | Charging observation |
| --- | --- | --- | --- | --- | --- |
| Experiential | `deepseek-v4.1-flash:free` | 200, correct, 1.956 s | 200, schema-valid, 31.451 s | 6/6 found in source | response cost 0; settled account ledger also 0 |
| Google native API | `gemini-3.8-flash` | 200, correct, 66.808 s | 200, schema-valid, 46.772 s | 5/5 | Free Tier published; personal billing ledger not independently reconciled |
| OpenRouter | `nvidia/nemotron-3.5-super-vl:free` | 200, correct, 10.653 s | 200, schema-valid, 55.212 s | 4/4 | cost 0, is_byok false |
| Kilo | `nvidia/nemotron-3.5-super-vl:free` | 200, correct, 1.323 s | 200, schema-valid, 26.258 s | 4/4 | cost 0, is_byok false; reported upstream cost 0 |
| Vercel AI Gateway | `nvidia/nemotron-3.5-super-vl` | 200, correct, 0.546 s | 200, schema-valid, 2.373 s | 5/5 | $0.0014435 total for both calls deducted from the existing $5 free credits |

Content review of these five document answers preserved the central EKP offer: 10%, selected repertoire, maximum two tickets for one performance, at least one day in advance, showing the card at the theatre box office, no stacking. None imported the neighbouring Mendeleev card's identity-document requirement. Field placement is not perfect: Vercel duplicates the card-showing action in restrictions, for example. Matching quotations do not establish every possible semantic property or reliability on other pages.

OpenRouter and Kilo Super VL used the same high-reasoning request bodies. Vercel used the model default and reported zero reasoning tokens. Do not conclude that its 2.373 s response proves intrinsically better speed/quality for the same model configuration.

### Experiential: the previous free-access denial has changed

The ordinary Flash model now reports `promotional_listed=true`, a live `Free core models` promotion, `listed=true`, `display_only=false`. The exact requested free-only ID succeeded twice. By contrast, `deepseek-v4.1-flash-1017:free` still returned 403 `model_not_granted`; its promotion is absent. `glm-5.3-uncensored` also has no active free promotion in the metadata inspected; it was not invoked.

The existing exact secret `EXPERIENTAL_API_KEY` works. No rename, new key, extra $1 or paid subscription is required to reproduce the successful ordinary Flash calls.

Independent settled reads at about 10:20 UTC: `/api/v1/credits` reports `total_credits=1.0`, `total_usage=0.0`. `/api/v1/usage?limit=20` returns the two completed requests with `pricing_known=true`, `cost_usd=0.0`, `real_cost_usd=0.0`. Document usage: 4420 input + 6199 output = 10619 tokens; 5794 reasoning tokens are included in output, not an extra amount to double-count. Image usage: 279 input + 69 output.

Current official published Free core limits: shared 10 requests/minute, 250K tokens/minute and 1M input+output tokens per UTC day. Cached tokens count in full and pending calls reserve input/output. The active free offer has now been verified for this key, but exact personal remaining daily tokens were not retrieved. At 10619 tokens per similar document, 1M tokens corresponds arithmetically to about 94 documents; this is a one-case illustration, not a throughput guarantee.

A fresh Gmail read of the support thread `1a1883011774ebb0` still contained only the outgoing message to the official contact and no answer. Do not attribute restored access to support without evidence. Availability/promotion metadata changed between 29 and 30 October; the internal cause of that change is unknown.

### Vercel: card issue resolved, model eligibility remains selective

The account began this audit with balance $5 and total_used $0. DeepSeek Flash, Flash 1017 and Gemini 3.8 Flash all returned 403 `RestrictedModelsError`/`no_providers_available`: these exact routes are not accessible to this Free Tier account. This is no longer `customer_verification_required`.

Nemotron 3.5 Super VL then worked. Image cost $0.0000766; document cost $0.0013669. The final independent balance read at 10:20 UTC reports `balance=4.9985565`, `total_used=0.0014435`, matching the two costs and the initial $5. The immediately-after-document read lagged the ledger; the later read closes that accounting gap. No credits were bought and no auto-top-up was enabled.

This is a priced model covered by free monthly credits, not a permanently zero-priced route. The public program is $5/month per team, not per model or key. Purchasing credits changes the free-tier arrangement, so no purchase was made. MiMo, GLM Flash, MiniMax and Gemini 2.5 were on a tentative followup list but were NOT called after the first usable model succeeded.

### OpenRouter: exact personal remaining allowance

At 10:12:48 UTC, authenticated `/api/v1/key` reported `free_model_daily_requests={used:2, limit:50, remaining:48}`. These are the request counters. The separate `limit=50` and `limit_remaining=50` fields are spending caps and must not be confused with request counts.

Published general free limits are 20 requests/minute and 50/day for an account without the qualifying purchase. Multiple free models share that allowance. Gemma's upstream 429 is not proof that the account allowance is exhausted; the personal counter still showed 48 remaining. No purchase was made to raise limits.

### Kilo: useful additional route, not a guaranteed 4800-document/day budget

Kilo Gateway publishes a shared 200 free-model requests/hour/IP limit. Successful Super VL calls establish access from the tested GitHub runner, not a guaranteed dedicated throughput allocation or an independent upstream GPU pool. OpenRouter and Kilo may depend on overlapping underlying providers. No IP/key rotation or quota evasion was implemented.

## Limited, failed or unsuitable checks

| Service/model | Fresh result | Limit/status interpretation |
| --- | --- | --- |
| OrcaRouter DeepSeek Flash free | Audit probe 429 `free_rate_limited`; today's production already accepted 50/50 | Public no-purchase ceiling 50/day, 10/minute; response points to 31 October 00:00 UTC / 03:00 Moscow |
| OrcaRouter GLM 5.3 Flash free | Same 429 and reset | Another model in the usual free pool does not create a fresh pool |
| OrcaRouter `tencent/hy4-preview-free` | ReadTimeout after 180.078 s | Published model-specific tier 250/day, 50/minute with no purchase; no completed answer, so usable extra capacity and quality not confirmed |
| Token Harbor DeepSeek `:free` | 429 `free_tier_limit_reached` | Body explicitly names 31 October 08:01 UTC / 11:01 Moscow as reset. MiMo not called after shared allowance denial |
| OpenCode DeepSeek free | Direct API 429 `FreeUsageLimitError`, retry points to 31 October 00:00 UTC | Current docs say free chat models run in OpenCode client; official CLI was not re-run today. No numeric personal allowance confirmed |
| OpenRouter Gemma 4 31B free | 429, `limit_source=upstream_provider_shared_pool`, Google AI Studio | Upstream congestion, not exhausted OpenRouter account quota |
| OpenRouter Qwen3.8 27B and DeepSeek V4.1 free | Exact free IDs absent from fresh catalogue | Not counted as available routes; no new inference requests to absent IDs |
| Kilo Nano Omni 30B reasoning free | Image passed; doc 200/schema-valid but wrong attribution | Imported Mendeleev screenshot+identity-document instructions into EKP; do not deploy on the strength of valid JSON |
| Kilo content-safety free | 404 from Nvidia upstream | A classifier was selected by an over-broad diagnostic catalogue ranking; it is not an extraction recommendation |
| Cohere Command A Vision | Image passed. First doc 400 because requested 16384 output tokens exceeded 8192. Corrected 8192 request returned 200 but invalid/factually wrong output | Invented THEATER10 promo code, 2026-12-31 expiry, one-time/non-transferable restrictions and online redemption; syntax repair alone cannot make this usable |
| Scaleway | Expected credential present; model catalogue HTTP 200 | No generation: actual remaining free budget not verified, ordinary calls may start billing after free tokens. Catalogue visibility is not quota proof |
| NVIDIA NIM | `NVIDIA_API_KEY` unavailable under expected Secrets/Variables name | No live account/model test |
| Nebius | `NEBIUS_API_KEY` unavailable under expected name | No live account/model test; advertised Builder credit is not an activated personal balance |

Cohere corrected document timing was 10.061 s; 6598 input + 247 output tokens; finish_reason stop. The raw content was independently read alongside the original source. Its invalid JSON includes a trailing comma, but its invented facts are the decisive reason for rejection. Official trial limits include 1000 calls/month and 20/minute for the relevant model group; personal remaining allowance/billing was not reconciled.

Token Harbor's current public API limits say 60/minute and 1800/hour/account, 4 MB per free request. Its recurring free allowance is a personal 7x24-hour cost-denominated budget with no confirmed absolute amount; those speed limits are not a document allowance. The production 200/day setting is our safety ceiling, not a provider grant. The error's Retry-After header was only 3600 seconds, inconsistent with its later reset in the body; the queue's stored retry timestamp follows the short header. Waiting until the named weekly reset is more informative than treating every hourly retry as a new weekly pool.

## Other previously discussed offers: research only

These do not constitute newly tested account capacity. Fresh official pages were read, but no signup, paid activation or model generation was performed:

- NVIDIA NIM hosted endpoints: free prototyping/testing; no verified personal numeric quota.
- Nebius Builder Program: published $25 Token Factory credit; activation and remaining amount unverified.
- Alysis Code: 50 credits per 30 days, with shorter rolling windows; credits are not requests, and client/headless integration was not tested. Different fetched/indexed page versions disagree on weekly sublimits, so do not use a numeric weekly claim as a guaranteed quota.
- Freebuff: client usage hours, not a confirmed direct-API allowance for our one-shot extraction.
- Nara: no confirmed free multimodal DeepSeek/MiniMax allowance for this account; no expected key available.
- Infron: the previously advertised DeepSeek free route has a published 29 October end date, now in the past. The actual endpoint was not invoked, so distinguish expired offer notice from independently tested shutdown. No key/funds added.
- Codex/Ollama local/CLI inference was not re-benchmarked here. Expected CODEX_AUTH_JSON and OLLAMA_API_KEY names were absent in this audit; this is not a search of every possible credential name or proof of product unavailability.

## Production pipeline, independently read without provider keys

Daily workflow remains OrcaRouter + Token Harbor only. Configured cron is 00:05 UTC / 03:05 Moscow; the latest run was actually created at 05:29:12 UTC on 30 October, so scheduled clock time must not be reported as actual start time. No cause for that delay was established here.

Latest run 41008693782, execution SHA `8ccdb61e384624849699acdbd5d427fb16825ea4`: 248/248 captures, 51 API attempts, 50 completed extraction JSONs (all OrcaRouter), 1 Token Harbor quota refusal. Batch status is deferred, not fully finished. The 198 pending items in the batch are not the entire remaining catalogue.

Persistent state: 1260 page+partner+program tasks; 320 completed (25.4%), 113 failed_validation, 24 failed, 8 transport_error, 5 deferred, 790 without a status. Thus 940 are not currently completed. State SHA256 `754fd7bdd1aa91ae2c6c1626c6e7c590c2053d9e51fdc4172cab89e13b35e6c1`. Source catalogue has 1449 records; records are not the same unit as tasks or API calls.

No audit outputs were imported into that queue. LLM automatic publication to Sheets remains disabled. Additional useful capacity has now been demonstrated but is not yet used by the daily workflow. No more keys or card setup are needed for the five successful routes above; production integration is the next engineering task, not a completed result of this audit.

## Evidence, execution and verification

1. Main matrix: https://github.com/Floppa2003/key-privileges/actions/runs/41037993591 — SHA `14768cd7151e741a22af559f7cd778c3d815174a`, 21 generation attempts. Readback job 124005850347 downloaded outputs and checked 98 internal hashes. Combined artifact 12970055011, ZIP SHA256 `6b6a72202d622254f21418f46fefc517128747b2f4706c38a14d6d944e488aa1`.
2. Focused Vercel/Cohere + personal OpenRouter quota and document review: https://github.com/Floppa2003/key-privileges/actions/runs/41039061816 — SHA `9d350e0835c9011868f9328b8bf79ea234c59c0b`, 3 attempts. Independent readback job 124007229737 checked 17 internal hashes. Combined artifact 12968843665, ZIP SHA256 `6c1b6f149f7a61e56415a31b4dd5de8d4faeccb4ec1fc20f9fa38cf308900248`.
3. Exact Kilo Super VL + settled accounting: https://github.com/Floppa2003/key-privileges/actions/runs/41039954715 — SHA `dd34bd7dfe9630be726d620e0556ffd26ff8e301`, 2 attempts. Readback job 124010379475 checked 10 internal hashes; accounting job 124010036322 made only GETs. Combined artifact 12968849037, ZIP SHA256 `4104557c3a73b84888bfee74ce17966be26f8a80baaad2bd55c005bb13ed4a80`.

All three workflows completed; original responses, error bodies, measurements and executed source are retained. Diagnostic contract checks passed. This was not a full production regression run. A green audit workflow means evidence collection succeeded, not that every provider/model succeeded. Secrets and auth headers were not deliberately printed/exported; no new credentials were requested from the user.

## Official references checked

- Orca free-package API: https://www.orcarouter.ai/api/free-package/public
- Orca free policy: https://docs.orcarouter.ai/routing/free-models
- Token Harbor API limits: https://tokenharbor.ai/docs/api/rate-limits
- Token Harbor allowance: https://tokenharbor.ai/docs/billing/cashback and https://tokenharbor.ai/faq
- OpenRouter limits: https://openrouter.ai/docs/api_reference/limits
- Kilo Gateway: https://kilo.ai/docs/gateway/usage-and-billing
- Gemini pricing and active-project quotas: https://ai.google.dev/gemini-api/docs/pricing and https://ai.google.dev/gemini-api/docs/rate-limits
- Vercel pricing: https://vercel.com/docs/ai-gateway/pricing ; older indexed versions saying all models are eligible do not override actual account-level RestrictedModelsError responses.
- Experiential current Free core rules: https://platform.experientiallabs.ai/docs/errors and https://www.experientiallabs.ai/setup
- OpenCode: https://opencode.ai/v2/docs/console/models/
- Cohere: https://docs.cohere.com/docs/rate-limits and https://docs.cohere.com/v2/docs/command-a-vision
- Scaleway: https://www.scaleway.com/en/docs/generative-apis/faq/
- NVIDIA: https://docs.api.nvidia.com/nim/docs/product
- Nebius: https://dev.nebius.com/builders
- Alysis: https://alysiscode.com/pricing
- Freebuff: https://freebuff.com/plans
- Nara: https://router.bynara.id/pricing
- Infron: https://infron.ai/models/deepseek/deepseek-v4.1-flash:free/pricing

## Limits on interpretation

Only current successful requests establish access, not catalogue badges. Rate limits, monetary credits and token pools cannot be added as if they were identical daily document quotas. High reasoning and images can greatly change per-document consumption. One familiar document is insufficient to certify quality across the catalogue. Actual model weights and internal provider routing were not independently audited. Balances were independently reconciled for Vercel and Experiential; this is not a universal billing audit for every service.
