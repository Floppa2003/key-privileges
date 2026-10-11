# Field routing v4: protocol fixed before inference

## Question and bounded change

Does explicitly classifying each assertion by programme ownership, source provenance and semantic role improve separation of published actions from optional practical advice?

Only the system prompt changes: the existing `practical_prompt.txt` (practical_v3, 6034 characters) versus `field_routing_prompt.txt` (field_routing_v4, 8201 characters). The candidate adds a source/inference/unknown/unrelated decision rule, distinguishes published actions from limits and accrual timing, clarifies optional recommended advice, and gives a fictional contrast in which adding an explicit source instruction changes its field. No real merchant, URL, selector, percentage, programme name or deadline from the diagnostic cases is introduced in the new prompt text. Existing fictional examples remain. This is deliberate instruction design around observed error categories, not an unseen generalisation test.

No production code, schema, model, model options, image size or source text changes. No response repair, substring-based semantic grader or merchant-specific parsing rule. Reuse `prompt_ab.py` as-is with a new frozen plan. In this experiment raw folders `old` mean practical_v3 and `defined` mean field_routing_v4.

## Inputs and execution

Four documents from run 36500846197, execution b80978fb9ba53d24894dd2b58e00c9f9c852ffee. Plan records exact SHA256 for each original request, complete text and all nine PNG images (long edge at most 1024px). Each source request already includes the practical schema; no candidate schema override is used. The only permitted request difference is `/messages/0/content`, including identical embedded schema and image bytes.

Run one baseline and one candidate per document, sequentially on the same runner for that pair, with fresh Ollama server processes. Alternate order between documents. Local Qwen3.5:4b / Ollama 0.34.4; keep original digest, CPU-only settings, temperature=0, seed=1, context/output budgets and 600-second request timeout. No paid model API or website reads. No repeats to obtain a preferred answer. A timeout or invalid output remains a failed attempt, not an inferred semantic success.

## Review before reading the new answers

Maintain two separate axes from PRACTICAL_EVAL.md: practical utility and source-field fidelity. An ordinary suggestion to show a card does not by itself invalidate a useful offline offer. A tag of inference does not excuse unrelated programme conditions or new restrictive consequences.

Review the entire source and output, not just the existence of a quote or a keyword. A faithful paraphrase is allowed. Empty practical_advice is allowed and is not an omission. Never reward moving every action into advice or suppressing all actions.

- Museum and bookshop: source-backed purchase channel or other explicit action stays in redemption. An inferred way to prove membership, if included, goes only into optional advice. Check that benefits, audience, exceptions and unknown discount size are not lost.
- Theatre: the target source explicitly mentions showing the target card; that instruction remains a published action. Requirements of the adjacent programme and general concessions are still unrelated, even when placed in advice. Report programme mixing separately from the field-routing question.
- Hotel points: preserve the actual registration/booking action, identity of the number, field to fill, points-per-unit basis and crediting time. Do not turn source instructions into advice or infer an unreported impossibility of correcting a mistake later.

A positive diagnostic result requires better separation on the two source-silent card cases, retention of source-explicit actions on the two controls and no new material error in benefit, audience, scope, limits, dates or process. Remaining unrelated-programme mistakes still block unattended publication, even if field separation improves. Minor repetition and phrasing are reported separately; they do not automatically invalidate the underlying offer.

## Evidence and limits

Preserve both prompts, eight unedited responses, actual requests without image bytes, original PNGs and text, schema, metrics, server logs, source hashes and execution SHA. Verify post-run request equivalence and source hashes, JSON completion/schema and sampled memory. Hardware-accounting anomalies require log review and are not silently relabelled. Compare timing only within a runner pair; no prior-run speed claims.

Manual review by the same assistant on familiar documents is not independent, blind or an accuracy estimate. Do not claim a universal solution or promotion from four known cases. Keep publication_allowed=false; no main merge, catalogue/Sheets writes, production parser changes or schedule changes.
