# Explicit infrastructure amendment — 2026-10-03

Initial run 37105385881, execution 3a73bf05de29fd9896bb15f47a1680fe7e73ff32: all 1604 regression tests passed. Gemini authenticated model metadata returned 200, but its first theatre inference returned HTTP 503 UNAVAILABLE/high demand; 1 HTTP inference attempt, no answer, 11 unattempted. Kilo's public catalog returned 200, but minimax/minimax-m3:free was absent; paid MiniMax was not called; 0 inference attempts, 12 unattempted. Initial archives and protocol remain immutable.

Before reviewing any successful cloud output, PR conversation comment 5966677112 recorded two explicit bounded amendments, also explained to the user:

1. Exactly one re-run of the failed Gemini job 111152882182 on the identical execution commit. This retries infrastructure after 503, not a semantically wrong answer. The initial HTTP failure stays in all accounting. No automatic retry loop, budget change, prompt change or model fallback. A second service error stops the arm.
2. A separate named Kilo arm qwen/qwen3.8-27b:free, confirmed in the captured live catalog to have zero prices, image input, reasoning and structured_outputs. This is not a MiniMax result. The user previously accepted exploring this model and authorized continuing cloud comparisons. No paid or randomly selected model is allowed.

## Narrow implementation changes

Add explicit --model selection from three approved identifiers, validated against provider. The original defaults and original Gemini request are unchanged. Pass the selected identity through request construction, metadata validation and final-response validation. Both :free and the same canonical model identifier without that pricing suffix are recognized in responses; unrelated models are rejected.

Recognize either response_format or structured_outputs in the catalog capability labels, always additionally requiring reasoning and image input. The actual request still uses the original strict JSON Schema in response_format and the same full schema inside the user message. No dropping or weakening of schema constraints, no output repair.

A dedicated Kilo-only workflow triggers only from its own file on the research branch. It does not re-run Gemini or the unavailable MiniMax. Same maximum 12 calls: three predetermined rounds of theatre, Nevsky, museum and bookshop. Same temperature 1, reasoning high, 8192-token cap, full images/text, TARGET, system prompt and error stop policy. Four additional contracts failed before implementation and all 17 cloud contracts passed afterward; the complete repository suites must pass in Actions before Kilo receives its secret.

No production defaults, registries, schedules, Google Sheets or main changes. No merge or publishing. Publication remains disabled regardless of model quality. Availability checks are not proof that structured-output enforcement or authenticated inference will work; real response results must be recorded separately.

Official Gemini troubleshooting recommends bounded retries for transient 503/429 errors. The single explicit retry here is recorded as a protocol amendment, not retroactively described as part of the original no-retry protocol.
https://ai.google.dev/gemini-api/docs/troubleshooting
