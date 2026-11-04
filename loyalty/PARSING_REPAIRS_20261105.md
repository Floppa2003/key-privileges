# Deterministic parsing repair — 5 November 2026

Scope: public source acquisition, deterministic extraction, normalization and
the handoff between collectors. No model requests, prompt/schema/provider
changes, queue policy changes or increased source budgets are part of this repair.
Dates in the evidence below are UTC; the work date is 5 November in Moscow.

## Findings and changes

| Boundary | Observed failure | Repair and acceptance |
| --- | --- | --- |
| T2 Magnit article | Runs 41454716914 and 41834875353 failed with `known_rule_scope_missing_or_ambiguous`, heading matches 0. Fresh browser evidence still contains both existing selectors. | Wait for nonempty `.support-article__article-title` and `.article-content` through the existing bounded readiness mechanism. Controlled delayed content reproduces the old failure and produces one complete rule record after the change. A permanent shell or HTTP refusal remains failed. |
| Extensionless PDF | Daily source captures 41589577533 and 41782293858 raised `Page.goto: Download is starting` for the Finuslugi disclosure URL. | A browser download response is read as a candidate PDF using the same public URL. HTTP status, each redirect, six MB limit and the actual PDF signature are checked. All pages remain mandatory. The live Finuslugi response is HTTP 200, `application/pdf`, 149364 bytes and three pages. |
| HTML navigation | The same daily captures failed while reading VIP-ZAL because `Page.content` overlapped document replacement. | Register the next main document load event before reading, wait only after this specific race, and recheck response identity/status and URL. Up to three DOM reads; no extra navigation. HTML, visible text and screenshot cannot be accepted from different documents. |
| Saved public record normalization | EKP and Free publication successfully upserted source rows, then failed in unified normalization with `ModuleNotFoundError`. | Real public Tsvetnoy records reproduced the missing `pypdf` import through `public_reward_projection`. Import `PdfReader` only when reading a PDF. Saved record projection no longer requires collector-only libraries. |
| EKP upstream selection | Linked run 41664048573 rejected an old successful workflow, ignoring fresh run 41487463433 whose collection succeeded and publication failed. | Select an exact successful `collect` job and immutable artifact ID from a completed main run. Reconstruct the artifact before using it, reject partial collection, preserve the original observation time and seven-day discovery limit. Publisher validation still defaults to two hours. |
| Regression gate | Run 41639404895 never collected sources because a 30 ms timing test failed under runner scheduling. | Replace wall-clock sleeps in that test with a controlled queue interval and a real-time watchdog. Production collector scheduling is unchanged. A mutation that starts the source timeout before queue admission is detected. |

## Reconstructed evidence

- [Original collector, 4 November](https://github.com/Floppa2003/key-privileges/actions/runs/41834875353): 1357 records, 125 sources (103 ok, 21 failed, one partial). Collection and publication succeeded; source health failed. ZIP digest was verified before analysis.
- [Original EKP collection, 2 November](https://github.com/Floppa2003/key-privileges/actions/runs/41487463433): artifact 13163046259 contains 1017 distinct records from nine successful pages, complete pagination and no collection errors. There are 904 public-term records and 113 explicitly gated observations. Original time remains `2026-11-02T17:05:19.705816+00:00`.
- [Original-page browser probe](https://github.com/Floppa2003/key-privileges/actions/runs/41931973515), commit `cae086c33099b45259e3b3f684c85e4976bdc664`: T2 initial and settled DOM each parse to one rule; FlyStation remains empty after ten additional seconds. Artifact 13372092724 ZIP SHA256 is `28e51ec1d6877eeeca34078372102db5312aed4c8c75dfe98311d1d1e5232dcd`.
- Full 4 November public input replay without `pypdf` in the normalization process: **1357 inputs → 1357 records**, with every raw condition and observation timestamp preserved. It yields 3319 benefit entries, 3593 condition entries, 75 costs and 243 codes; these are structured entries, not independent additive offers.
- Full 2 November public input replay without `pypdf`, `PIL`, `playwright` or `jsonschema` in the normalization process: **1180 inputs → 1180 records**.
- Fresh Finuslugi PDF SHA256: `a24c1a8bf300087b8e8f93d9975b24acb9fb7bd9f574f1e6f2bd71f543e6a09e`. Raw replay preserves all three rendered pages and validates the evidence manifest. Live browser verification is a separate check in `parsing-repair-check.yml`.

## Limits that remain explicit

- FlyStation returns HTTP 200 with an empty promotions container in direct and
  rendered reads. No explicit complete-empty catalogue marker was found. Its
  production parser is unchanged; a new regression ensures this source stays
  failed with zero accepted records, not a healthy empty catalogue.
- HSE's 56 catalogue cards contain only 53 nonempty owned detail sections. The
  missing/empty Skyeng, Skillcup and Academiya sections remain preview-only.
- Historical failed T2 DOM was not archived. Missing readiness is reproduced by
  controlled delay; that delay is not claimed as the proven cause of every
  historical run.
- The three `ut0.ru` links now return an unavailable-site page in direct checks.
  Their current destinations and PDF contents were not verified and are not
  reported as recovered.
- HTTP refusals, challenges, DNS failures, timeouts and login requirements stay
  visible. This patch does not certify all 125 registered sources as healthy.
- Existing public source content and program rules do not establish personal
  eligibility, a current redeemable offer or complete access to gated terms.

## Release verification

`parsing-repair-check.yml` runs the full Python and KEY suites, real Chromium
tests for delayed source content and document capture, and a bounded anonymous
probe of the original T2, FlyStation, Finuslugi and VIP-ZAL pages. It never calls
a model or writes to Sheets.

The existing main-only request mechanism refreshes only `t2_magnit_rules`,
`af_vipzal_rules` and `rzd_finuslugi_rules` after merge. The existing EKP workflows
exercise the repaired upstream and publisher paths. Their actual source status,
publication and destination readback must be reported from the release runs;
passing regression tests alone does not certify fresh source collection.
