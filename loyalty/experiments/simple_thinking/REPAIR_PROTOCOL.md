# Visible schema and capped reasoning follow-up — 30 September 2026

Specified after reading all results of runs 36741893989 and 36744802667. Original attempts are preserved. This is a bounded diagnostic, not publication or a change to production defaults.

## Observed defects and predictions

The converter's system message requested JSON "according to the schema", but the messages contained no literal schema; only the API format field held it. The model's returned reasoning explicitly treats the schema as missing. All three thinking-on converter attempts hit 4096 generated tokens with empty final content. Non-thinking conversions manufactured expiration dates from target.as_of, dropped scope or actions, or treated generated prose as source quotations.

Ranked hypotheses: (1) missing schema in the language context causes uncertainty about the output contract; exposing it should improve completion/assignment; (2) the generated-token budget can stop a valid reasoning path before its final answer; increasing that limit alone should let the capped theatre description complete; (3) reasoning/decoding or model limitations may persist with a visible schema and sufficient budget. This experiment does not distinguish all such remaining causes.

Ollama's official structured-output guide recommends supplying the schema as text as well as in format: https://docs.ollama.com/capabilities/structured-outputs . This motivates the fix, not a guarantee of semantic correctness.

## Changes and controls

Converter: add the exact API schema as a schema field to the existing user-message JSON. Preserve the input description byte-for-byte, target including as_of, system instruction, model, schema, decoding settings, 4096-token budget and 900-second timeout. Compare think=false and true on the same runner using all three completed think-on descriptions; fresh process per request and frozen order. Only /think differs inside each new pair. Relative to the earlier converter request, the sole content addition is the literal schema. These are new candidate requests, not replacement baselines; do not compare speeds across runs.

Theatre description: use the exact previously capped think=true request, all three 1024px PNGs and complete text. Change only num_predict 4096 to 8192; wall timeout 900 to 1800 seconds is a transport allowance, not another model-input change. No new instruction, crop, source selection, sampling change, answer prefix or manually supplied facts. If it completes, convert its unchanged final description using the corrected schema-visible converter with thinking off/on (4096/900). If it fails, skip both conversions.

At most nine new calls: six converters on completed descriptions, one budget-expanded description and at most two dependent conversions. No retries to obtain a favourable answer. Original failures, raw outputs including reasoning, requests, timings and checksums remain separate.

## Review and limits

Evaluate description correctness against complete original sources and conversion fidelity against the actual description separately. Check programme boundaries, magnitude, units, scope, eligibility, actions and limits. Do not copy metadata dates into offer validity. Do not mark generated prose as an original quote. Ordinary card-use advice remains a minor provenance issue, not an invalid offer; unrelated programme documents remain material. Schema validity is not semantic correctness. A capped/empty output is failed, not a partially inferred success.

The same assistant reviews four familiar documents, not a blind holdout. No accuracy percentage or claim of general readiness. No model/website-specific rule, production default, main merge, registry, schedule or Sheets change. publication_allowed=false. Persist report and read back repo state.
