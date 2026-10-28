# Experiential: exact credential name and live access check — 2026-10-28

## Result

The user supplied the exact GitHub setting name `EXPERIENTAL_API_KEY` (not `EXPERIENTIAL_API_KEY`). The evaluation workflow now maps `secrets.EXPERIENTAL_API_KEY || vars.EXPERIENTAL_API_KEY` to the existing worker's `EXPLABS_API_KEY`. Readback confirmed the mapping at commit `7cd6acfa28a7d1f605bd2d37e878af6d8a9e2fd5`.

A targeted rerun received the credential (`credential_present: true`, `experiential_variable_present: false`). A separate catalog job using only `secrets.EXPERIENTAL_API_KEY` also authenticated successfully. No rename, new key, or disclosure of its value is needed.

## Actual inference result

Run: https://github.com/Floppa2003/key-privileges/actions/runs/40765619821
Probe job: https://github.com/Floppa2003/key-privileges/actions/runs/40765619821/job/123089063843
Execution SHA: `7cd6acfa28a7d1f605bd2d37e878af6d8a9e2fd5`.

One POST at approximately 20:42:52 UTC to `https://api.experientiallabs.ai/v1/chat/completions`, model `deepseek-v4.1-flash:free`, returned HTTP 403 in 2.554 seconds:

```json
{
  "error": {
    "message": "deepseek-v4.1-flash:free is not available: free access to deepseek-v4.1-flash has ended or is not offered to your organization right now. Use the model id deepseek-v4.1-flash instead, billed to your credits. Buy credits at https://platform.experientiallabs.ai/credits.",
    "type": "permission_error",
    "param": "model",
    "code": "model_not_granted"
  }
}
```

The first request was the existing synthetic image check. No completed model response, no document extraction, no retries, no call to the plain/paid model ID. The four frozen documents were prepared but never sent after this denial. Other providers were not called: the matrix contained only `experiential` and only its credential was passed.

This is a provider-side denial of free access, not a local catalog/robots/schema preflight blocker. It is not an observed 429 quota exhaustion or a 402 card-verification response. The exact account-side cause (promotion eligibility, activation, or a service inconsistency) is not established; do not promise that paying $1 or purchasing credits will fix free access.

## Independent catalog and artifact readback

Read-only run: https://github.com/Floppa2003/key-privileges/actions/runs/40766417963
Job: https://github.com/Floppa2003/key-privileges/actions/runs/40766417963/job/123091659746
Execution SHA: `7b3eb2a5ffbf2ca469f455ac7529733f25890781`.

Authenticated `GET /v1/models` returned HTTP 200 and 314 model entries. Both `deepseek-v4.1-flash` and `deepseek-v4.1-flash-1017` are listed. Their pricing objects report 300000000 nano-USD per million input tokens and 1200000000 per million output tokens ($0.30 and $1.20 list prices). Catalog visibility is not confirmation of free eligibility. The snapshot's inference/free route was NOT tested; no positive free-access verdict can be assigned to it from the list alone.

The read-only job downloaded the preceding probe artifact, verified its ZIP SHA256 and all 8 internal file hashes, and read back the original error. This job made no generation request.

Inference artifact: 12850705787, ZIP SHA256 `453110fc340f07c9ac7b59ae76f222a20ba11182b0a42a6572271ea77b04089e`.
Catalog artifact: 12851025405, ZIP SHA256 `fb2441cf60a24704b5cd2123fc7e362d21b023f5f88b0f4717940802337f0c42`.

## Checks, scope, limitations

The optional before/after accounting calls to `/api/gateway/usage/daily` returned 422 because `query.org_id` was missing. They did not block the inference request. Account spend was not independently reconciled; do not turn missing accounting data into a measured zero-spend assertion. No paid inference, purchase, subscription, card change, or recharge was requested.

The targeted Actions run completed prepare, probe, and review jobs. Green workflow status means the diagnostic ran and preserved results, not that the model worked. The production main, merchant queue, schedule, and Sheets were not modified by these branch-only diagnostics. Experiential has NOT been added to the daily provider pool. The inference payload, full-evidence contract, parser, prompt, and JSON schema were unchanged.

Current public catalog still advertises DeepSeek V4.1 Flash as Free: https://platform.experientiallabs.ai/models . Documentation says `:free` stops rather than charging credits: https://platform.experientiallabs.ai/docs/errors . These public statements do not override the actual account-level 403.
