# Current original-source coverage — 2026-09-16, after Aeroflot publication

This is the current handoff. The previous complete RZD/EKP/Coral checkpoint is retained in Git history at `1aa98dd2eb39155f1e83923f755d596b103c4565`. Historical observations must not be relabelled as current runs. Do not rebuild released adapters from older diagnostics.

## Objective and constraints

Deliver useful current data from the originally requested sources to the SAME Google discount spreadsheet through regular GitHub-controlled operation. No paid service, rented/administered server or always-on personal computer. Existing Free ScrapingAnt and Google WIF authorization are configured; no extra key or second provider account is needed. Coral registration is already completed by the owner, but no source-account session is connected. Do not request those steps again.

The owner now reports Aeroflot approved the previously discussed public parsing method by email and explicitly requests continuation. The approval was not located by searches of three connected Gmail accounts, so the implementation records **owner-reported permission**, not an independently verified email. The exception covers the specified public Aeroflot catalogue/API only, not arbitrary robots overrides, private pages, account actions or publication of private data.

## The formerly zero-output catalogues now have working paths

| Original source | Operational result | Exact accepted scope |
|---|---|---|
| Aeroflot Bonus | **Implemented and published** | 229/229 current company-partner details in 15 categories; separate airline catalogue and external rules not read |
| RZD Bonus | **Implemented and published, partial content** | 66 accepted details from 74 discovered same-host pages; eight pages did not yield conditions |

The previous Aeroflot `blocked_by_source_crawl_policy` decision is superseded by the owner-reported approval and completed release. This does not mean the robots file changed. See [AEROFLOT_ACCESS_STATUS.md](AEROFLOT_ACCESS_STATUS.md) for exact permission scope, source evidence and acceptance. Existing partner-owned pages are separate evidence, not counted as recovery of these official catalogues. Neither source result certifies all personal entitlements or all parts of its loyalty programme.

## New Aeroflot acceptance

PR41 is merged at `dd9ffb8c5b73eea4af30367ec7ec5c8e27ece821`. Actual production **35094999686:1** used `1aa98dd2eb39155f1e83923f755d596b103c4565`. The first release attempt was cancelled in the shared pending-run queue before source execution; the accepted run completed regression, collection and final publisher job **104799253783**.

- Started `2026-09-16T12:18:51.756594+00:00`; collection finished `2026-09-16T12:46:05.400491+00:00`.
- 232 retained import observations: robots, original-root discovery, current category response and one separate detail calculation for each of 229 company IDs. All categories' partner IDs received matching details; no duplicate IDs or source/mapping errors.
- Source endpoint: `https://www.aeroflot.ru/partners/ws/v.0.0.2/json/partner/categories?lang=ru`. Its language parameter is not an eligibility-region assertion. Detail endpoint and IDs are source-derived; no fixed partner answers or earlier diagnostic captures serve as runtime fallback.
- Public artifact10446862972, ZIP SHA256 `8115d22022397e2b64a671d7e6521b9dcbe7206c0b2db42806072be5d9c6499e`. Downloaded, CRC/hash checked; all229 records independently reconstructed exactly from their own typed observations, JSON-schema/application validated and prepared by the actual publisher. Full bundle validation also passed as an offline replay at the original completion time, not as a new source fetch or stale republication.
- Main test artifact10444859633, SHA256 `a8a3a533ab7949a2ad3f1fc02605d7392633862ad4ffcbd80092d63c928383cc`: **704 Python and7 KEY tests passed**, no skips. The23 Aeroflot tests and7 KEY tests were repeated locally. No repeated complete local suite is claimed.
- Executed collector, mapper and workflow bytes match their Git blob identities at the runtime commit; exact identities are in AEROFLOT_ACCESS_STATUS.md.

Run: https://github.com/Floppa2003/key-privileges/actions/runs/35094999686

### Native destination verification after the final write

Destination: `1uFR7croj7p6RRNPcoTRYlVl06hKsurkIgyu1IdMMB-4`, title `скидки`.

| Metric | Before Aeroflot | After Aeroflot |
|---|---:|---:|
| Official Aeroflot company records | 0 | 229 |
| Retained parser records, all sources | 2223 | 2452 |
| Unified input/output records | 2871 | 3100 |

- **229 new rows:** `parser_offers!A2225:Y2453`. All229 native hashes in X were compared programmatically with the source output and matched. Hash-projection SHA256 `eeb93000109f73417628dc610c1c1e65e459d986b7cf81cd430852142f900cbe`.
- Native search of `Y2225:Y2453` scanned229 rows and matched229 markers `35094999686:1`; the two displayed samples are not a two-row scan.
- Native literal samples2225–2227,2339,2390,2452–2453 match names, IDs, kinds, dates or declared condition samples. Chefmarket earning/spending sections and Askona online-store exclusions are present. Manual-column samples remain blank.
- `parser_coverage!A1276:N1276`: **ok**,229 found/229 normalized/0 errors, all current company-category partners read. Airline, linked-rules and full-eligibility flags remain false.
- `normalization_audit!A7:J7`: **verified/current**,3100 inputs/outputs and2452 retained parser rows. Final source fingerprint `6658ee94c83bf9c639f39aba4564a62d7f88c950800002734998b5da28c12e89`; generation `e5b0443314e2d698fe28b15462c44d65ceeb0e82bfd883bc44505007f8ad2cde`.
- Existing EKP2153 and RZD2224 retain their earlier hashes, observation dates and runs. Native normalized examples retain top/wrap/10pt formatting. Independent verification covers all new hashes/run markers and declared literal/report/manifest samples, not an exhaustive independent private-workbook or rendered-format audit. The established publisher performs its complete output readback.
- Both full staging rectangles were read after cleanup: `af_public_fetch!A1:D4096` and `public_fetch!A1:D2048`. Only headers and respective idle markers remained; no formula or stale result was left running.

The229 new records are not229 necessarily active cash discounts. Source earning, spending, award and special-offer fields remain separate; no personal eligibility or combinability is inferred.

## Prior accepted sources retained

RZD PR40/run35085594949:1 remains accepted:23 catalogue states,74 same-host detail URLs,66 public records in rows2159–2224, eight explicit failed pages, and zero ScrapingAnt use. Its original artifact10442639040 SHA256 `03d22b365e9f207686bc7533538e804f208916e04936a291570638fa645ad240` and complete acceptance are recorded in the previous checkpoint. These66 were not recrawled in this Aeroflot acceptance.

EKP retains1045 anonymous region98 records from35070130567:2:935 public-term offers and110 login-gated observations. Other-region, private, linked and image-only conditions remain outside that acceptance. Utair, Nordwind, Coral and other released sources retain their own run histories and latest explicit partial/failure reports; no fresh crawl of them is claimed here. The provider's most recent failure must not overwrite evidence that a separate accepted reader has successfully published the same source.

## Recurring operation and free-budget boundaries

| Collector | UTC | Moscow | ScrapingAnt reservation bound/run |
|---|---|---|---:|
| Original direct sources | Daily05:23 | Daily08:23 | 0 |
| Coral/Nordwind and provider probes | Mon/Tue/Thu/Fri06:03 | Mon/Tue/Thu/Fri09:03 | 269 |
| EKP anonymous catalogue | Monday07:13 | Monday10:13 | 175 |
| RZD Google import | Wednesday08:37 | Wednesday11:37 | 0 |
| Aeroflot Google import | Thursday08:47 | Thursday11:47 | 0 |

Aeroflot and RZD use separate public-source tabs and the existing short-lived Google WIF identity, then the established publisher for the original destination. No Google scope, source account or additional paid infrastructure was introduced. Provider schedules/manual operation are preserved; ordinary provider code pushes are regression-only. RZD code pushes now also run regression only, avoiding an unrelated source crawl when Aeroflot registers in the shared normalizer. Aeroflot retains trusted-main release/manual execution.

The existing conservative provider ceiling is5986 credits/31days, excluding manual diagnostics/reruns, other use, tariff changes and cron anomalies. This Aeroflot acceptance consumed no provider credits; no new provider balance was measured. Do not repeat an earlier balance as current. A successful release-triggered run is not proof of future cron reliability.

Aeroflot bounds:260 details/263 imports/3000seconds, at least5seconds between imports, stop after3 consecutive failures. Current229 details were all attempted. A larger future list rotates its selected subset with explicit partial coverage. RZD bounds remain32 catalogue pages/100 details/135 imports/3300seconds and its20-second source delay.

## Provenance, permission and data safety

Google imports return typed calculation results, not original HTML or exposed origin HTTP responses. **Origin cache age, redirect chain and exact server fetch time are not verified.** Observation timestamps identify import requests/calculations, not certified uncached downloads. Each run clears prior cells, uses new generation markers, checks its exact formula and two stable typed reads, and verifies cleanup. Source layout/coercion/refusal errors remain errors, not repaired canned values.

Do not call the destination private: the last permission checks before this continuation reported `anyone:writer`. No sharing permission was changed here. Normalization mode `private_complete` names the input-processing mode, not its sharing ACL. Only public source material was added; source sessions, SMS, tokens, issued personal codes and authenticated-only descriptions must not be placed in this publicly link-accessible destination or artifacts. If the reported Aeroflot permission proves revoked or narrower, stop/review that source scope.

## Remaining coverage work

1. The previously zero Aeroflot source now has completed GitHub-to-Sheet acceptance for **companies**, so do not restore the obsolete blanket blocked status. The separate airline-partner catalogue, linked special-offer pages, PDF/image rules, human-facing detail URL verification and personal eligibility are not covered.
2. RZD remains partial on eight discovered conditions pages and excludes external-card destinations. Keep their concrete failure list and observations; do not infer expiration, login or deletion from a generic response alone.
3. Coral rotating-half/category/detail gaps and intermittent Nordwind reads remain separate coverage/reliability work. Inspect actual latest reports before deciding which page to retry; do not confuse old successful output with a current refresh.
4. Improving completeness requires current permitted source evidence, sustainable free operation, completed publication and native readback. Tests, fixtures, category counts or partner-side substitutes alone are not the end-to-end acceptance gate.
5. Failed imports must preserve old offer observation dates and publish validated failure coverage. A failed final publication/readback must not be described as verified. All release stages described above have completed; future scheduled executions have not yet been observed.

Public artifacts expire after7days (this release around2026-09-23). Code, the exact source-scope acceptance and historical checkpoints persist in Git. No pending job is being reported as finished.
