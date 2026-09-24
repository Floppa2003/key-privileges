# Block contract and independent NLI experiment — 2026-09-25

## Predeclared scope
Continue PR90, not a production source release. Replace model-written source quotations with immutable Markdown block references. Preserve source offsets, nested redemption instructions and enclosing restrictions; do not certify semantic field roles from a reference match. No changes to existing collectors, Sheets, registry, schedules, or the recorded failed v3 counterexample.

## Structural acceptance
Exact Unicode/CRLF slices; raw UTF-8 hash; source/prediction binding; reject forged IDs and edits; preserve nested sections; flag cross-section claims; retain restrictions not selected by the extractor; keep excerpt provenance; no silent context truncation; all results publication_allowed=false.

## Independent classifier probe, frozen before inference
Model MoritzLaurer/mDeBERTa-v3-base-mnli-xnli, revision 8adb042d524ecd5c26d3e3ba0e3fbcf7e2d0864c. Quantized ONNX SHA256 27c39e884c14b03cf46cfc5485971b6db70ff330220d93dfe729c63fde43af0e. Load data-only tokenizer/config/ONNX, no pickle/custom model code, no account token, no paid inference API. This is a different controlled model/process from the opaque Firecrawl reviewer, not a claim of statistically independent errors.

14 manually labelled proposition pairs: seven entailed, seven not entailed. Eight propositions use four archived v3 source excerpts; two use the newly read ARTSTUDIO M103 excerpt; four are synthetic contrasts about gift alternatives/minimum stay and booking versus stay dates. These are proposition tests, not 14 sites or 14 automatic extractions. The positive school case describes the actual past gifts, not an eligible current cardholder offer. No claim of random sampling or model-training-data exclusion.

Only premise and hypothesis enter inference. IDs, expected labels, provenance and old model verdicts are excluded. Support threshold fixed at 0.90 before the run. No truncation beyond 512 tokens: oversized pairs remain unscored and fail this evaluation. Acceptance for this small probe: no false support, all cases scored, at least 80% of entailed propositions supported. Rejecting everything fails. Even passing does not authorize publication or establish calibrated probabilities, extraction completeness, current availability or end-to-end correctness. Preserve failures without relabelling/tuning the same dataset.

## Evidence and transport
The model runs on a fresh GitHub Actions CPU runner; archive exact cases, source code, package versions, model/tokenizer hashes, raw probabilities and execution commit. Model weights must not be uploaded as workflow artifacts. Existing Firecrawl keyless REST403 remains unresolved. GitHub Models is not used: official GitHub documentation says its inference API retired on July30,2026 (https://docs.github.com/en/github-models). The local classifier requires no inference credential; its download/runtime still must actually pass before it is called working.

Primary model/config: https://huggingface.co/MoritzLaurer/mDeBERTa-v3-base-mnli-xnli . ARTSTUDIO excerpt: https://artstudiom103.ru/ . The NLI corpus stores labelled source excerpts, not full current HTTP archives.
