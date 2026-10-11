# Source-first JSON: protocol and recovered baseline — 2026-10-03

Draft PR #90; no merge, publication, production parser/default/registry or Google Sheets changes. The user's architecture remains one Qwen3.5:4b call, think=true, full frozen images/text + TARGET + visible JSON Schema -> JSON. No second LLM, merchant-specific extraction rule, input cropping or repair of model facts.

## Recovered baseline (not rerun)

Run 36998659984, commit 99606604d1ddf9b05ec4300a4564720ed0c63588, finished 2026-10-02. Two completed, schema-valid responses do not mean two semantically correct extractions.

| Case | Artifact | ZIP SHA256 | Time, seconds | Generated tokens |
|---|---|---|---:|---:|
| nevsky | 11223126797 | 4bfe8f81624fef5d1ed2d5574a75a8274e465eef168e7bb8cc277bd428aced08 | 973.921302871 | 4929 |
| muzcomedy | 11222939725 | 69efbd522446d2ffa93ab0c2a055d85de0580fa2d0bff91c99ea00a7eb922677 | 1164.916085619 | 6740 |

Both ZIP digests/CRC/path safety, all 62 internal hashes, six PNGs and two full-text hashes, raw response -> extracted JSON identity, both schema validations and pure how_to_get -> redemption mapping were checked on 2026-10-03. No model invocation for this audit. Source theatre PNG was also inspected visually.

Nevsky: 500 points/night, website booking + RZD Bonus number in the Comment field, and 45 days after checkout are retained. Published booking instructions are unnecessarily duplicated as an inference; field hygiene remains imperfect.

Theatre: 10%, selected shows, two tickets, one-day cutoff and no stacking are retained. But how_to_get requires an electronic-card screenshot with the holder's name; the same instruction is repeated in practical_advice. This belongs to the neighboring Mendeleev Card block, not EKP. It is a material cross-program error, not harmless generic advice. The relevant source EKP clause instead requires presenting EKP at the theatre cashier. Schema validity and matching evidence quotes do not fix the wrong acquisition instruction.

## Candidate and controlled changes

Execution commit 6e0e3501cbb34216a6a16371c75698f5b47bf336, workflow run 37098547822. One new call per case (nevsky, muzcomedy); not a repeat of a completed experiment. Source inputs are from run 36705324742, artifacts 11092462751 / 11092173951, using the existing checksum manifest.

New source_first.py adds target_blocks as the first schema property and required field, plus a system instruction to quote contiguous target-program blocks before producing offers. All pages and all text are still passed in full, including neighboring programs. The model selects and quotes the blocks; code does not preselect them. The existing baseline system prompt otherwise remains unchanged. Both the prompt addition and schema change are part of this intervention; an outcome cannot isolate property ordering alone.

Fixed baseline code SHA256: f6da311be861ca002ac7802de0224beabb3fa8d2749d53c3514961362f999da2. Model qwen3.5:4b Q4_K_M, digest 2a654d98e6fba55d452b7043684e9b57a947e393bbffa62485a7aac05ee4eefd, Ollama 0.34.4; CPU-only/cloud disabled. Options: temperature=1.0, seed=1, top_p=.95, top_k=20, min_p=0, presence_penalty=1.5, repeat_penalty=1, num_predict=8192, num_ctx=16384, num_thread=4, num_gpu=0. Calling these settings a comparison arm does not establish they are optimal.

Raw JSON is retained. Only after validation does the compatibility copy drop target_blocks and rename how_to_get to redemption. No factual value/list is changed. Contiguous source-span checks normalize whitespace only, preserve ordering, reject invented/changed wording and never repair output. Such checks do NOT determine whether a matched block belongs to TARGET: semantic_review stays pending and publication_allowed=false until manual review (and publication is still not authorized).

## Acceptance criteria recorded before candidate outputs are reviewed

- Nevsky: 500 points for each night; book on the hotel's website; enter the RZD Bonus number in Comment; accrual within 45 days after checkout; no invented promo code/end date. Primary acquisition actions must be in how_to_get, not solely in advice.
- Theatre EKP: 10% on the theatre-selected current shows; present EKP at the cashier; at most two tickets per show; no later than one day before the show; no stacking. No personal-account screenshot/name/identity-document requirement borrowed from Mendeleev Card. No invented calendar deadline; immediate purchase discount has no future accrual timing.
- For both: correct target, essential restrictions and acquisition instructions, no materially unsupported condition; exact/whitespace-normalized target blocks and final structured-output validity are separate dimensions. Duplicated published instructions tagged as inference and incomplete evidence coverage are reported as warnings, not silently repaired.

These are evaluation criteria for two known frozen documents, not merchant-specific production logic. Passing them cannot establish catalog-wide reliability. A single sample per arm, different runners, and changed output/prompt token counts cannot establish robust accuracy or a causal speed improvement.

## Tests and scope

13 local contract tests passed before the workflow was created. The workflow also runs the existing core/prompt/local-visual/resolution/simple-thinking/KEY suites before the two model calls. Generated responses that hit the token limit or fail validation stay failures; a green unit test job is not a claim of model correctness. The source matcher includes a negative-control test showing a verbatim WRONG PROGRAM still needs semantic review.

The inherited baseline prompt's stop-at-next-program instruction and long-document capture limitations are not redesigned here. No catalog expansion, model replacement, schedule, automatic retry, or automatic publication is introduced. Candidate completion/results are to be recorded separately, not presumed in this protocol.
