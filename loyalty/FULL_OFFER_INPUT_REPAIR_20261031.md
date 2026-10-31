# Full offer input repair — 31 October 2026

## Scope

Fix the proven collector-to-LLM data loss, not add another model or conversion stage. Base main: `1860e95378c34af7ed11549c73af16e08715bf57`. Preserve the seven approved channels, cron, provider ledgers, one durable-state writer, all captured PNGs, complete visible text, prompt/schema, and review-only outputs. No purchases, new credentials, model web search, synthetic screenshots, merchant-name/value allowlists, or Sheets publication.

## Root cause and actual source behavior

The queue retained only source URL, partner and programme from a normalized collector record. Consequently it reopened the general Konsierge catalogue without the already-collected `details.public_item`, native offer ID or original description. Four completed JSONs in run 41196701444 reported no offer even though the collector had source records for those partners.

Anonymous inspection run 41216756444 used the original catalogue artifact 13041115453 from run 41194911797 and ordinary browser navigation. Konsierge cards contain title/offer and native identity in their image URLs. Clicking the entire card did not open a detail modal or change the URL. Full descriptions are in the public source objects collected by the existing source collector. No detail URL is invented and no direct private/API access is added.

## Changes

- Preserve complete matching collector records (including nested original objects and unknown fields), native IDs, dates and provenance in the target, durable state, capture manifest and actual single model request. Merge multiple records for the same target without losing rows or mixing programmes.
- Distinguish collector-normalized fields from nested source objects; retain their acquisition timestamps. Acquisition time is not advertised as an offer expiry or independent proof of current applicability.
- Use a published same-origin detail URL when the collector actually supplies one. For Konsierge, wait for native card identity plus title through ordinary lazy loading. For generic pages, wait for the target text rather than photographing the initial loading shell. Missing readiness remains diagnostic and does not block extracting useful supplied source objects.
- Keep original visible text and PNG bytes intact. Append the complete source-record JSON to the model input, not a hand-written/model-generated summary. Hash-check the source-record handoff alongside the existing image/text hashes.
- A schema-valid negative on missing target input becomes `needs_source`. A negative contradicting a supplied collector offer becomes `needs_review`. Preserve the raw answer and schema validation; do not fabricate a positive answer, certify absence, or try another model on the same unresolved input within the same run.
- Old negative entries with newly recovered source records are prioritized once for recapture; prior results and provider ledgers remain intact. Actual source-term changes invalidate the cache. Acquisition-only timestamps/run identifiers do not invalidate it by themselves.

## Verification ledger

1. Run 41216756444: four discovery regressions failed on old production code. The initial shell pipeline failed to propagate unittest's nonzero exit; corrected immediately. Its green job label is not evidence of passing tests. The independent anonymous source inspection succeeded.
2. Run 41217107830: reliable RED, 11 contracts with 10 intended failures and one passing preservation case, no import/setup failure.
3. First browser run 41217720873 exposed an incorrectly declared fixture charset and premature shell exit during the deliberately failing test stage. Both test harness defects were corrected; this run is not a product success.
4. Run 41218022162: the three real Chromium regressions first failed on the old capture (missing hydrated content, missing capture identity, ignored real detail link), then all passed after the production change. Eleven handoff/state contracts passed. Full Python suite: **1570 tests, OK**, including the 11; KEY: **7/7**. Browser tests are three additional tests. No model API calls or provider credentials were used.
5. Tested production files committed by the runner as `0c531f7563f7ab0012daa8574e77a5f7b171bc50`; a remote fetch verified the committed SHA. Build artifact 13049210314 contains executed sources, diff and logs, ZIP SHA256 `5cc516be68bc2df0640deac22f194f3c8a321ced3e8d59c610dcb6b6647a831f`.
6. Final PR checks and a bounded real-source/model verification are to be recorded in the PR. Successful unit tests are not a substitute for that real extraction check.

## Review and limits

Author self-review only; no independent reviewer. Original data transport is generic; Konsierge-specific selectors navigate that site's DOM but do not interpret benefits or hard-code partner names/discounts. The four named historical partners belong only to the diagnostic acceptance comparison.

This repair is not a claim that arbitrary sites' complete content can always be loaded, that old source records remain current forever, or that every model answer is semantically correct. Captured-page metadata reports whether the actual target was found. Existing request/image/time budgets and real access/network failures remain visible. No alternative evidence is silently called a fresh source read. Native thinking settings and model selection are unchanged by this source-handoff repair.
