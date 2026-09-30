# Short visual description and thinking: diagnostic protocol, 30 September 2026

The user approved testing a short plain-language extraction before JSON and also testing think=true. This experiment answers that question without merchant-specific rules or publication.

## Hypotheses and interpretation

1. The compound extraction/schema task contributes to errors: a short description may be correct where a previous direct JSON answer mixed programmes. This is a historical diagnostic comparison, not a concurrent prompt-only A/B against the old long prompt.
2. Reasoning mode contributes: holding the entire short request fixed and changing only think from false to true may improve programme ownership or completeness. Same model weights and same runner within each pair.
3. Structuring contributes: a correct description may become an incorrect JSON object; compare the unedited description with the converter output separately from source correctness. A faithful conversion of a wrong description is not correct extraction.
4. Errors may persist already in the plain description in both modes. That locates the error before JSON, but does not prove the model's capability limit or rule out a better prompt.

## Frozen inputs and controlled variables

Four familiar cases from field-routing run 36705324742: museum, bookshop, theatre, hotel points. All nine PNGs (max edge 1024) and full texts are preserved byte-for-byte. plan.json records the exact source request/text/image hashes. No website reads or source filtering/cropping. Programme and partner come from each frozen request, not hardcoded extraction rules.

Stage 1: a 368-character general system prompt asks for a plain Russian description of benefit, scope, redemption and restrictions. No JSON Schema in the API or user message; no requirement to create practical advice. User message contains the original target, complete text and every image in order. Two requests per document differ only in think=false versus think=true. Qwen3.5:4b Q4_K_M, Ollama 0.34.4 and original model digest remain pinned via existing setup/runtime. Temperature=0, seed=1, num_ctx=16384, num_thread=4, num_gpu=0. Both arms use num_predict=4096 and 900-second request timeout, increased relative to historical 1600/600 to allow reasoning. A capped, empty or timed-out response is not success. Capability and an actual nonempty returned thinking field are checked for think=true.

Stage 2: each completed, unedited final description is passed to the same local model with the existing practical JSON schema and a short conversion instruction. The converter always uses think=false, holding that mode fixed; it receives only target and description, NOT original pages/text, NOT the first-stage thinking, and NOT labels or a repaired answer. Description SHA is recorded. This isolates conversion fidelity, not a new independent source verification. evidence must be empty unless the description explicitly contains original-page quotations; no new advice is requested. A model-generated description is never relabelled as a primary source.

At most 16 model requests: four documents x two first-stage modes x two stages. Skip conversion when the description fails. No retries for preferred answers. Fresh Ollama process per request; alternate mode order across documents. Four runner jobs can execute in parallel, but each document's modes/stages stay on one runner. Preserve original failures, raw outputs, thinking, requests, metrics, memory samples and logs. No model weights included in artifacts.

## Evaluation fixed before inference

Read full source and final description for programme ownership, benefit value/unit/basis, audience, scope, limits, redemption, dates/accrual and unsupported additions. Check JSON against BOTH its actual input description and the original source, distinguishing propagated errors from newly introduced conversion errors. No regex-based semantic acceptance and no secret target answers in prompts.

Museum: retain 10%, cashier-only channel and all exclusions; ordinary card advice is a provenance detail, not automatic failure. Bookshop: keep the offer with unknown value and published categories. Theatre: preserve the target programme's actual instructions/limits without adjacent programme documents or general concession offers. Hotel: preserve points per night, membership-number/booking action and accrual delay without conflating them. These are review criteria, not model input.

Use the user's two-axis utility/fidelity rubric from PRACTICAL_EVAL.md. Empty advice is allowed; sensible low-risk advice does not invalidate correct benefits. Conversely, wrong programme requirements, amounts, deadlines or missing material limits remain substantial. Do not overclaim success merely because optional advice disappeared or a correct quote exists.

Same-assistant review on four known sources is neither blind nor a general accuracy estimate. Historical timings are not a speed benchmark. Compare thinking off/on only within a runner pair and report both stages separately. Hardware accounting anomalies require logs, not silent relabelling. Green CI means functional execution, not semantic acceptance.

## Scope

New diagnostic files only; reuse frozen loader, setup, local runtime and schema. No production parser, defaults, main, schedule, registry or Google Sheets changes. PR remains draft and publication_allowed=false. Do not merge. Record the results and read back the resulting repository/PR state after the experiment.
