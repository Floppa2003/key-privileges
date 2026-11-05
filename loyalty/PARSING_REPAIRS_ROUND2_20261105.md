# Deterministic parsing repairs, second round — 2026-11-05

This change repairs source acquisition, browser evidence capture and EKP page
reading. It does not change model calls, prompts, model schemas, providers,
queue policy or publication rules.

## Reproduced defects and changes

1. **Allowed long pages falsely failed scrolling.** The old 40 movements of
   900 pixels could not cover the permitted 40,960-pixel height and did not
   inspect the position after its final movement. The bounded loop now permits
   46 movements and checks the final position. Regressions cover 37,000,
   38,000 and 40,960 pixels, a stuck page, and a page exceeding the limit.
2. **Two static pages unnecessarily depended on browser navigation.** Original
   HTTP responses from GLORIA and Istochnik Kislovodsk contain the complete
   relevant conditions. Only these source configurations select the existing
   raw HTTP path. Source identity, selectors, challenge/refusal/redirect checks
   and record validation are retained. Saved original HTML and provenance are
   included in `tests/fixtures_live`; the real collector is tested against them.
3. **Capture did not reuse the already reviewed CA profile.** The four exact
   Primbank, VTB, NSPK and Uralsib document URLs now use the existing pinned,
   temporary CA bundle to read original response entities. Chromium renders
   those bytes at the original URL. Only that document and bounded public
   same-origin static assets receive this trust. Other requests retain normal
   browser TLS. No system CA installation or TLS verification bypass is used.
   Response hashes and trust provenance are recorded. Cascading resources,
   cancellation, redirects and late capture changes have regression coverage.
   The initial live VTB probe exposed an additional 30-second readiness cap;
   resource completion now uses the existing overall source deadline instead.
   Failure diagnostics also retain response and refusal receipts after cleanup.
4. **Wide screenshots failed despite fitting the total pixel budget.** PNG
   tiles now cover both axes in row-major order, without rescaling or dropping
   pixels. The existing maximum remains 40 images of at most 1024 by 1024
   pixels. DOM geometry is checked before screenshot; actual PNG geometry is
   checked before decoding. Coordinates, source HTML, readable text and failure
   diagnostics are retained. A failed or oversized document is not admitted
   to the successful manifest.
5. **EKP body-read failures lost their exact cause and could not recover.**
   One retry of the same page is permitted after an actual timeout or a body
   `TypeError` following accepted HTTP 200 headers. The existing one-session,
   125-credit, 43-second, 15-second per-attempt, 11-total-attempt and 1.1-second
   pacing bounds remain. HTTP refusals, Retry-After, challenges, redirects,
   schema/total changes and duplicate IDs remain terminal. Header-stage
   TypeError is not retried because `redirect: 'error'` is ambiguous there.

## EKP evidence compatibility

The new timing contract binds every accepted page to its attempt and response
SHA and validates retry order, outcomes and limits. An unfinished terminal
attempt must remain in the session errors; it cannot be certified complete.
The former contract is accepted only for the pinned historical script SHA.

Both actual historical bundles were reconstructed without changing their
records or observation dates:

| Source run | Rows | Original observation | Result |
| --- | ---: | --- | --- |
| 41487463433:1 | 1017 | 2026-11-02T17:05:19.705816+00:00 | Complete, eligible for linked handoff |
| 41934551933:1 | 480 | 2026-11-04T23:34:06.134052+00:00 | Partial, still ineligible for complete handoff |

## Verification and rollout

Behavioral tests first reproduced the original failures. The repaired cases
then passed, including 58 EKP targeted tests, 12 geometry/consistency tests,
8 static-source tests and 13 TLS transport/review tests. The final local full
run passed 1674 Python tests and 7 KEY tests. The complete suite is run again
in the PR against its exact execution tree; real Chromium tests run there.

```bash
python -m unittest discover -s loyalty/tests -v
python diagnostics/test_merchant_evidence_browser.py
python diagnostics/test_source_parsing_browser.py
python diagnostics/test_capture_geometry_browser.py
python diagnostics/test_verified_capture_browser.py
node --test key/refresh.test.mjs
```

The initial round-two branch workflow recorded fresh, read-only observations
for the two static pages and ten affected capture URLs. GLORIA and Istochnik
each produced one valid record. Moskvich and all four merchant URLs captured
successfully. The latter have actual widths 1035, 1137, 1027 and 1092 pixels,
and are now represented without clipping. Primbank kept all four PDF pages;
Uralsib captured successfully. HSE measured 50,087 pixels high and correctly
failed the existing 40-tile limit. VTB exposed the readiness cap described
above; NSPK timed out without producing a source document. These observations
are in run 42049358910 at commit 6639c1eff784a81e7747a8b11971f8b9c84c2ba2.

Only VTB and NSPK are selected for the follow-up probe. Probe completion means
evidence was recorded, not that all sources succeeded. Actual sizes and source
failures remain in the artifacts. The PR records final CI and follow-up results.

After merge, the existing request workflow selects only `ural_gloria_rules`
and `af_istochnik` for normal validated publication and destination readback.
The existing EKP workflow runs under its unchanged budget. The daily model
workflow is not dispatched by this repair.

## Limits

Truly oversized, unavailable or incomplete sources remain unsuccessful. The
capture changes do not guarantee that all formerly failing pages fit 40 tiles.
The EKP retry improves recovery only when the remaining session time is enough;
it does not promise that a fresh remote catalogue will always be complete.
The complete pixels of an acquired screenshot are preserved; future dynamic
content is not declared loaded merely because the screenshot succeeded.
