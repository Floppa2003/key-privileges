# Experiential DeepSeek free-access diagnosis — 29 October 2026

## Finding

At 14:19–14:22 UTC the live Experiential API had **no active public free promotion for either `deepseek-v4.1-flash` or `deepseek-v4.1-flash-1017`**. The user's key is valid and its account reports `is_free_tier=true`. Both exact `:free` requests are rejected with HTTP 403 `model_not_granted`, including a minimal text-only request. This is not a local parser rejection, missing GitHub secret, observed quota exhaustion, image issue or reasoning-parameter issue.

The live model-detail responses report `promotional_listed=false`, `promotions=[]`, `ads_on_all_requests=false`, both without authorization and with the user's key. Anonymous and authenticated response SHA256 values match for each model. In the plan-discount metadata, lanes with a discount mapping specify `free:0.0`, `pro:100.0`, `max:100.0`, `ultra:100.0`; two additional Flash lanes have no mapping. These are plan discounts, not a claim that all accounts receive free requests. No paid plan was purchased or tested.

The compatible `/api/v1/models` catalogue returns both DeepSeek variants at nonzero list prices ($0.30/million input and $1.20/million output), with no DeepSeek `:free` entry. The free-only suffix prevents spending the account's existing credits; removing it would be a paid-model test, not a repair of free access, and was not done.

This establishes the current configuration-level cause. It does not establish when the free promotion ended, whether a former advertised offer was ever valid for this account, or whether the website's indexed Free badge is stale versus misleading. The earlier recommendation based on that badge was not sufficient evidence of usable free DeepSeek capacity.

## Reproduction

Executed script: `python diagnostics/experiential_access_debug.py`.
Secret: existing `secrets.EXPERIENTAL_API_KEY`; never exported into results.

The following body went directly to `POST https://api.experientiallabs.ai/v1/chat/completions`:

```json
{"model":"deepseek-v4.1-flash:free","messages":[{"role":"user","content":"Reply OK."}],"max_tokens":64}
```

No PNG, system prompt, JSON schema, tool, search, reasoning parameter, temperature or streaming option was supplied.

| Request | HTTP | Result | Seconds |
| --- | ---: | --- | ---: |
| `deepseek-v4.1-flash:free` | 403 | `model_not_granted`; free access ended or not offered to the organization; use plain ID for credit-billed calls | 0.772 |
| `deepseek-v4.1-flash-1017:free` | 403 | Same refusal for the exact snapshot | 0.166 |
| `clef-flash:free` control | 400 | `unsupported_capability`: native decisions model, not Chat Completions; server directs callers to `/v1/systemone` | 0.185 |

Three new POST attempts; zero completed model answers. Clef's different error is not proof of a successful inference or account-wide free eligibility. It is not a drop-in replacement for our full-text-plus-PNG extraction. The native decisions endpoint was not called. No retry, paid fallback or other-provider call was made.

## Account and accounting evidence

Authenticated reads on the same key:

- `GET /api/whoami`: HTTP 200, own organization resolved internally; `is_provisioning=false`.
- `GET /api/orgs/{own_org}/provider-policy`: HTTP 200, `policy=null`, `zdr_entitled=false`. No custom restrictive policy was present. No settings were changed.
- `GET /api/v1/key`: HTTP 200, `is_free_tier=true`, `usage=usage_daily=usage_weekly=usage_monthly=0.0`, `limit=null`, `limit_remaining=null`.
- `GET /api/v1/credits`: HTTP 200, `total_credits=1.0`, `total_usage=0.0`.
- `GET /api/gateway/usage/daily?org_id={own_org}&scope=org`: HTTP 200, zero usage rows.

The $1 credit exists and the service records zero charged usage at read time. Its origin and the settlement status of any card-verification payment are not established by this read. Do not tell the user to pay another $1 or replace the key as a supposed solution to an inactive model promotion.

An earlier diagnostic statistics query omitted `org_id`; the first query in this turn supplied the ID but omitted `scope=org`. The API then explained that API keys must read organization scope. The corrected query above succeeds. Those diagnostic query errors never prevented the model POST and did not cause its 403.

## Live catalogue comparison

For both DeepSeek variants, public and authenticated detail endpoints agree:

```json
{"promotional_listed":false,"promotions":[],"ads_on_all_requests":false}
```

Public/authenticated hashes:

- Flash: `09d8a019beacc1b82b3a5e7507eaada142f4b0a6d14b108b1b5752b098845810`
- Flash 1017: `99c9d11d80c920539c68487a7e7aebbaa29939b1d8bfe8a8454139220197c983`

Clef Flash, in contrast, has `promotional_listed=true` and a nonempty promotion labelled `Clef Flash free on Experiential Cloud` (`listed=true`, `display_only=false`).

The compatible catalogue returned 317 entries. Its only IDs ending in `:free` were `cloudflare/clef-flash:free` and `openai/gpt-6-luna-decisions:free`. These are catalogue observations, not verified replacements or an OpenAI endorsement. The latter route was not invoked.

The publicly indexed model-list page still advertised Free for DeepSeek in this investigation. Actual authenticated inference and current catalogue JSON take precedence over that badge. Official errors/coding-agent documentation describes `:free` as free-only, with no credit-billed continuation; a conditional Free core token ceiling does not itself grant access to an inactive promotion.

Official references:
- https://platform.experientiallabs.ai/docs/errors
- https://platform.experientiallabs.ai/docs/coding-agents
- https://platform.experientiallabs.ai/docs/cost-api
- https://platform.experientiallabs.ai/models

## Execution and independent readback

### Actual requests

- Run: https://github.com/Floppa2003/key-privileges/actions/runs/40890300378
- Job: 123504961250; execution SHA `cd5544ac886b7b1df9c8dd1b454f1cd42824eaa8`.
- Artifact: 12904691800, `experiential-access-debug-40890300378`, 9849 bytes.
- ZIP SHA256: `343149a92b12a121105d144b9aa266ea75093587081c4f2338133eb623af1fe9`.
- Boundary assertions passed: exact free-only model IDs, minimal payload shape, unapproved model rejection, denial/success classification, identity filtering. This was not a full production regression suite.

### Read-only verification

- Run: https://github.com/Floppa2003/key-privileges/actions/runs/40890704714
- Job: 123506403501; execution SHA `bc79550ca0d0ed2e332fd8049bec5e950b499d5b`.
- Downloaded preceding artifact, verified ZIP digest and all four internal file hashes, and reread the actual POST outcomes. Made zero generation requests.
- Re-read promotion metadata and the account's budget through the API; corrected statistics scope.
- Artifact: 12903273883, `experiential-entitlement-40890704714`, 2803 bytes.
- ZIP SHA256: `c9374f7d5effbb02db67d67febdea73e02a053101a5bcf596238ef596571682c`.

Both jobs completed and their logs were read back. Green diagnostic workflows mean evidence collection completed, not that free DeepSeek started working.

## Scope and remaining action

Only diagnostic code/workflows/report on `loyalty/deepseek-capacity-recheck-20261028` were written. No main change, queue write, Sheets publication, provider-account mutation, purchase or paid inference was performed by this investigation. The production ref separately read at the end was `00aea58644664bb1164f2d80cae14ab7c6f04d71`; do not assert it equals yesterday's ref.

Free DeepSeek through Experiential remains unavailable. There is no justified request/prompt change that would restore this missing free offer. For free-only capacity, do not count this route until a new successful free-only response or a restored entitlement is established. A provider support clarification could reconcile the advertised badge with the live promotion metadata, but this investigation did not send a support message. Vercel and production integration of other candidates were outside this focused diagnosis.
