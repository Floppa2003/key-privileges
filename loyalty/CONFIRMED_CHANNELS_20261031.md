# Confirmed-channel integration — 31 October 2026

## Binding scope

The user approved enabling the five routes verified on 30 October in the existing daily GitHub queue. Preserve OrcaRouter and Token Harbor, existing durable state, full text and all original PNGs, the extraction prompt/schema, and review-only JSON. Do not enable Sheets publication, model web search, purchases, paid fallback, account changes, source-specific parsing rules, or unrelated scraping gates.

Approved additions: Experiential `deepseek-v4.1-flash:free` using the existing exact spelling `EXPERIENTAL_API_KEY`; Kilo and OpenRouter `nvidia/nemotron-3.5-super-vl:free`; Vercel `nvidia/nemotron-3.5-super-vl` within the already verified free credit grant; native Google `gemini-3.8-flash` using `GEMINI_API_KEY`.

Base main: `9f9ec635f98e3940f82fad1d70a68fc7eeeebf39`. Isolated implementation branch: `loyalty/confirmed-channels-20261031`. Existing diagnostics branch is evidence only, not merged wholesale.

## Plan

1. Add failing tests for route registration, complete evidence, native Google transport, returned-family checking, credit safety, independent quotas, restart/cache behavior, and the actual Token Harbor reset time.
2. Extend the existing extractor/provider registry and queue; keep old fingerprints and Orca usage ledger intact. Persist reservations before network IO. Keep per-provider local workload ceilings distinct from provider-granted quotas.
3. Wire all approved secrets and providers into daily workflow. Keep one queue writer and existing schedule; provide a small manual verification mode which uses the same production code, does not change the defaults, and cannot publish to Sheets.
4. Run complete regression, review the branch, merge only the scoped integration, run a small live batch and read the resulting durable state back.

## Decisions and limits

- Ruling: reuse the existing evidence/contract fingerprint across approved models — avoids regenerating already accepted documents. Exact provider/model remain attached to the accepted output. Cost if wrong: quality equivalence is not guaranteed; output remains review-only.
- Ruling: Vercel is credit-funded, not zero-priced. Use a conservative durable monthly budget, reserve before calls, require live sufficient balance and a published maximum request cost below the reservation. Never buy credits or alter auto-recharge. Other account consumers are outside this queue's concurrency boundary.
- Ruling: Google uses the existing project's free-tier setup; API-key inference alone cannot independently attest Cloud billing configuration. No paid tier is activated by this change. Use a small local daily ceiling and preserve that billing-verification limitation.
- Runtime limitation: local container/Python calls failed with ClientError. Tests and controlled verification therefore run in GitHub Actions, without exporting API keys. This does not limit repository writes.

## Progress ledger

- Task 1: tests committed `7388fd7`; test workflow `19d8ce1`; run `41194836341`. New contracts failed against the old two-provider implementation, as expected; full logs still to be read.
- Tasks 2–4: pending.

## Verification focus

Billing stops must affect only the relevant route except a genuine secret/cost anomaly. A cached result must not become a new network call. No native thought text may be accepted as final JSON. Unknown network outcomes retain their reservations and must not be silently repeated through another account. No successful HTTP response may be presented as a full semantic quality guarantee.
