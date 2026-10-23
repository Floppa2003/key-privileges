# Converter-only reasoning follow-up, 30 September 2026

This follow-up was specified after reading the completed museum and bookshop artifacts from run 36741893989; the other two cases had not yet been inspected. Museum descriptions were correct in both modes but both converter outputs copied target.as_of to valid_until. The think-on bookshop description retained the book categories but its converter output dropped them. These are observations, not a conclusion that all conversion failures have one cause.

Hypothesis: turning thinking on in the converter can improve field assignment and completeness without modifying the description, prompt or schema. The user's request explicitly allowed think=true. No source-specific rules or target answers are introduced.

Use ALL FOUR documents' unedited think-on descriptions from execution 49339414cc352907c7c3542e9dc979ad4e96a401, not a selection of favourable answers. Load their actual stored converter requests, validate the first-stage completion, source artifact execution, checksums and exact description identity. If a first-stage answer failed, do not invent a converter input.

For each document, execute the stored converter request twice on one runner: think=false and think=true. The only request difference is /think. Keep the same target (including as_of), description, system instruction, existing practical schema, pinned Qwen3.5:4b and Ollama0.34.4, temperature=0, seed=1, num_predict=4096, num_ctx=16384, num_thread=4, num_gpu=0 and 900-second timeout. The baseline is repeated for a same-machine controlled pair, not to replace an unfavourable historical answer. Fresh process per request; alternate order using the already frozen case order. Maximum eight calls; no repeated attempts for preferred output. Original sixteen-call results are preserved separately.

Evaluate fidelity to the actual description and correctness against original source separately. Priorities: do not manufacture expiration/accrual dates from metadata or publication/statistics years; preserve category/limit/eligibility and action information; do not invent codes or conditions; keep target-programme ownership. Empty evidence is expected when the description has no source quotations. A wrong first-stage statement faithfully preserved is still a source error; a new converter error is recorded separately. Do not promote either stage merely for schema-valid JSON.

Preserve raw replies including reasoning, actual requests, measurement and runtime logs, descriptions, hashes and both execution IDs. Verify thinking is actually observed in the returned field. No speed comparison across old and new runners. Report single-pass paired timings only; this is a diagnostic on familiar cases, not a general accuracy result or a proof that two passes are necessary.

No main/default/production/parser/Sheets/schedule changes. publication_allowed=false; PR stays draft. No report or answer is manually repaired and passed off as a model result.
