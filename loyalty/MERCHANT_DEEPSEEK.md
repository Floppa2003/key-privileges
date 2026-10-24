# Selected model extractor: DeepSeek V4.1 Flash / OrcaRouter

User selection: 2026-10-24. This is the prepared-page model entrypoint, not a replacement of the daily deterministic collector or an automatic publisher.

- Endpoint: `https://api.orcarouter.ai/v1/chat/completions`.
- Exact free route: `deepseek/deepseek-v4.1-flash-free`.
- Credential: `ORCAROUTER_API_KEY` (GitHub Actions secret; never a CLI argument).
- One stage: full text + all ordered PNG bytes + TARGET + unchanged prompt/schema -> one final JSON.
- `temperature=1`, `max_tokens=8192`, `reasoning={enabled:true,effort:high}`.
- No search tools, plugins, URL retrieval, agent loop, server-side response_format requirement, catalog/capability preflight, paid route or automatic fallback. Source collection occurs separately without the model key.

## Use

```sh
python -m pip install -r loyalty/requirements.txt
# Prepare only: no key and no network calls.
python loyalty/merchant_extract.py --manifest evidence/manifest.json --out prepared
# Run against the selected free route. The key must already be in the environment.
python loyalty/merchant_extract.py --manifest evidence/manifest.json --out extracted --execute
```

Every run needs a new output directory. A manifest contains `documents`; each document has an arbitrary unique `id`, `target` (`partner`, `program`, `as_of` in YYYY-MM-DD), relative `text` and ordered `images` paths, and a `sha256` mapping for all input files. There is no merchant, promotion-name or tier allowlist. Optional source URL metadata is preserved, not fetched by the model.

```json
{"documents":[{"id":"new_partner","target":{"partner":"Any partner","program":"Any program","as_of":"2026-10-24"},"text":"new_partner/text.txt","images":["new_partner/page-1.png"],"sha256":{"new_partner/text.txt":"<actual SHA256>","new_partner/page-1.png":"<actual SHA256>"}}]}
```

Batch/input budgets are 30 documents, 40 PNGs/document, 500,000 text characters and 14 MB source bytes/document, 20 MB serialized request. Exceeding a budget is explicit, never truncation. Paths, hashes, PNG integrity, output schema and duplicate keys are checked. The prepared manifest must be valid before execution.

## Outputs and failures

Every document keeps original text/PNGs, a request manifest, exact payload hash, all sanitized HTTP responses, measurements and, when valid, `direct/extracted.json`. `summary.json` records completed and unattempted document IDs. JSON validity is not semantic approval; `semantic_review=pending`, `publication_allowed=false`.

One outer Markdown JSON fence is accepted without rewriting the JSON. Multiple competing objects, duplicate keys, nonfinite numbers, truncated generations and tool calls remain explicit failures. A failed answer does not suppress independent later documents. No second model, answer repair, merchant-specific edits or hidden regeneration is used.

An exhausted 429 limit stops the entire batch and retains the pending document IDs. Retry-After and OrcaRouter JSON retry_after_seconds are lower bounds; the larger valid hint wins. No sleeping for hours in a runner and no switching keys/providers to bypass the limit.

At most three identical attempts are allowed for explicit transient HTTP errors, respecting Retry-After and a bounded retry budget. Network timeouts have an unknown execution outcome and are not silently retried. Explicit nonretryable errors and authorization/payment refusals stop further batch requests. An unexpected nonzero/invalid reported cost also stops further calls but does not discard an otherwise valid answer. Missing cost metadata does not prove zero spending; balances are not audited here.

## Acceptance workflow

`merchant-deepseek.yml` runs full main-based Python/diagnostic/KEY suites, prepares four frozen controls and four new-to-DeepSeek public sources, and calls this same CLI. Only the inference step receives ORCAROUTER_API_KEY. It has no schedule and no write/publication permissions. Its branch-limited push trigger runs regression only. Real API calls require a manual workflow_dispatch with live=true; the default is false. Acceptance artifacts include source code, page captures, inputs and raw results.

The four selected new sources are test data, not parser rules. Capture refusals are reported separately; remaining captured pages can still be extracted. Expired control artifacts require supplying retained evidence or explicitly taking a new comparison snapshot, never pretending new inputs are identical.

This focused change does not merge the historical experimental PR #90. No Google Sheets integration, automatic source coverage claim, or production-wide semantic accuracy is implied.
