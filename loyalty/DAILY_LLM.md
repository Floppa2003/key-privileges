# Daily GitHub LLM processing (2026-10-24)

`merchant-llm-daily.yml` runs on **main daily at 00:05 UTC / 03:05 Moscow** and supports manual dispatch. GitHub scheduling can be delayed; this is a daily cron, not an exact-start SLA. No ChatGPT reminder is involved.

The job discovers URL + partner + program targets from the latest main `loyalty.yml` normalized artifact, `partner_pages.json`, and `known_rules.json`. It retains previously discovered targets when a catalogue read is incomplete. This is a live queue, not a replay of four acceptance fixtures. Capture checks up to 300 least-recently-checked public pages per run, with a 20-minute admission budget, retaining every PNG page and full text. PDF pages are rendered with Poppler; image-only PDFs still reach the model with all rendered pages, without OCR. Native HTML disclosures are opened; arbitrary JS accordions are not guaranteed complete. Source errors are recorded per item, not global preflight blockers.

`loyalty/llm-state:state.json` stores the durable queue, successful JSON, input/contract fingerprints, last capture/inference dates, provider cooldown, and daily HTTP-attempt count. It is read before processing and pushed with remote readback after processing, including partial runs. No force push. Branch holds public source data only, not keys/cookies. Successful old JSON is retained on a later error, with the latest error status separately recorded.

Only changed full text, ordered PNG bytes, target program/partner, or request contract needs new inference. Capture date alone does not invalidate the cache; cached JSON retains its actual `inferred_as_of`, not a fictitious new inference date. Pixel changes from dynamic banners can conservatively invalidate the cache. Unprocessed captures remain pending; they are not marked completed just because a screenshot exists. A single local capture/size error does not block neighbouring records.

Two explicit free routes serve the same selected DeepSeek V4.1 Flash: OrcaRouter
`deepseek/deepseek-v4.1-flash-free` first, then Token Harbor
`deepseek-v4.1-flash:free`. Existing `ORCAROUTER_API_KEY` and
`TOKENHARBOR_API_KEY` are injected only in inference, never source capture.

The Orca queue limit remains **50 HTTP attempts per UTC day**, at least **7 seconds**
between document calls. Token Harbor has an independent ledger and a local engineering
ceiling of **200 attempts/day**, at least **2 seconds** between document calls.
**200 is not a published or guaranteed free entitlement**: Harbor's actual allowance
is a personal 7-day value-based budget. Server quota refusals/Retry-After take precedence.
The combined run ceiling is 250 attempts, including retries; inference admission is
bounded at 75 minutes and the workflow at 120 minutes. Capture still has a 20-minute
admission budget. None of these ceilings promise that many successes per day.

The existing v1 Orca usage/cooldown/history is preserved. Harbor's accounting and cooldown
are stored independently under `providers.tokenharbor`. An Orca cooldown no longer stops
capture when Harbor is eligible. A server's seven-day hint is not replaced by a midnight
reset. Missing credentials or access refusal on one route do not stop the other.
Before IO up to three attempts are reserved; unused reservations are returned. Other
experiments on the same provider can consume quota outside this queue's counters.

Successful JSON is shared by complete-evidence/target/prompt/schema fingerprint, so the
second provider does not repeat the first provider's completed work and a Harbor answer
is reused on later Orca runs. This deliberately treats the selected model family as the
same extraction contract; the exact provider and returned model snapshot remain in
`inferred_provider`, `returned_model`, and `last_result`. Orca uses the tested high-reasoning
extension; Harbor uses native-default reasoning with a 16384-token output cap (Orca remains 8192). The first live Harbor run completed one document but hit the 8192 output limit on two others; those truncations remain recorded, not accepted as valid JSON. The original Orca
fingerprint remains the canonical contract fingerprint, retaining previous cache entries.

Fallback is for work not processed or rejected by provider capacity/input limits, not
model-answer repair. A validation failure or unknown network execution outcome is not
regenerated on the other provider in the same run. Billing anomalies or credential echoes
halt the entire pool while preserving valid results. Paid route names, arbitrary endpoints,
web search/tools, and account/key rotation to multiply the same workspace quota are absent.


A normal quota deferral is reported explicitly, not treated as a successful extraction or a fatal parser error. Results remain review-only (`publication_allowed=false`); this schedule does not change Google Sheets, deterministic collectors, semantic approval, or historical PR #90. Empty queue / cached results make no model calls. Evidence is kept in run artifacts for 14 days; successful JSON and queue state persist in the state branch. A forced runner loss before state push can lose the newest local checkpoint; artifacts/finally steps are recovery aids, not an exactly-once transaction guarantee.
