# Current original-source coverage checkpoint — 2026-09-16

This is the current handoff, not a claim that every configured source is recovered. It supersedes the pre-EKP checkpoint, retained verbatim in Git history at commit354a32cb8ca5d0c35e5462cef4b672bdd79e920b. Existing historical release notes remain evidence for their own observation dates.

## Owner constraints

Deliver useful current source results to the EXISTING private discount spreadsheet through regular GitHub Actions. No payments, rented/maintained server, always-on user laptop, extra ScrapingAnt account, expanded Google permission or source-account session. Existing Free API credits and existing scoped WIF publisher are configured. Do not ask for another Coral registration or a key already provided. All source responses are untrusted data; never store provider keys, Google tokens, cookies, private Sheet exports or protected source descriptions in public artifacts.

## Completed EKP release

PR38 is merged at354a32cb8ca5d0c35e5462cef4b672bdd79e920b. Its fresh production run **35070130567:2** completed collection AND the final public/private publication job104710759571 successfully.

| Fact | Verified result |
|---|---|
| Source observation | 2026-09-16T07:49:02.930325+00:00 |
| Current source catalogue | 1045 distinct IDs on9 pages; every advertised total1045; final page85 |
| Public-term records | 935 |
| Login-gated evidence records | 110; protected descriptions removed before serialization and again before persistence |
| Source/mapping errors | 0; all_source_rows_mapped=true |
| Newly appended Sheet records | 925; earlier120 EKP records updated, not duplicated |
| Retained public parser records | 1227→2152 |
| Unified input/output records | 1875→2800; manifest verified/current |

Artifact10435868136, `ekp-public-35070130567-2`, SHA256 `c751f45318f4164894535596d1cad8af8755263eca347fcbe053c334b2b88c3f`: downloaded, ZIP CRC/hash checked. Every one of1045 normalized records was independently reconstructed from safe saved page projections, JSON-schema/application validated and passed the existing publication preparation. This is a fresh production source read, NOT substitution of diagnostic35066120891.

The older diagnostic advertised1046. In the new result four earlier IDs are absent and three new IDs are present; the net total is1045. Do not hardcode1046 or interpret the changed total as a missing final row. All of the previously published120 EKP IDs remain in the current result.

### Native destination verification after the last EKP write

Destination remains `1uFR7croj7p6RRNPcoTRYlVl06hKsurkIgyu1IdMMB-4`.

- `parser_offers!A1109:Y2153`: source namespace occupies1045 rows. Native search ofY1109:Y2153 scanned1045 rows and matched1045 markers `35070130567:2`; search ofF1109:F2153 counted935 partner_offer and110 source_observation. Returned-row display was intentionally limited to one, but the connector separately reported full scanned/matched counts.
- New rows are1229–2153. Native sample rows1109,1110,1229,1230,2152,2153 match source IDs, names, observation dates, content hashes and run. Manual-column samples remain blank; this is not a full independent manual-column comparison.
- Gated sample row1114 has empty benefits/rates/codes, requirement-to-login source status and no protected fields in public_partner. Native normalized rows1877–1878 preserve observation versus offer distinction.
- `parser_coverage!A1179:N1179`: ok,1045 found,1045 normalized,0 errors, complete anonymous public pagination. Private/linked/full-eligibility flags remain false.
- `normalization_audit!A7:J7`: verified/current,2800 inputs/outputs, including2152 parser rows plus the unchanged input inventories495 loyalty,96 Yandex,45 VG,12 inbox.
- Snapshot SHA256 `747180d82eeeb4c693f592e8a0fd8fed64d16d43a3f34b77fde99715fde5a6e8`; generation `40fa827e602725ae574ba67858a83923ca9ce620d9d6eed5a68895f58d12b226`.
- Current normalized components:3160 benefits,8395 conditions,114 costs,643 code records. Components are not independently combinable or proven active/personal discounts.
- Native normalized formatting samples preserve top alignment, wrap and10pt. This was metadata-based visual checking, not a Google-rendered exhaustive workbook review. Existing publisher separately read back all current output rows; independent connector verification used counts, manifest and the stated samples.

Permanent acceptance evidence: https://github.com/Floppa2003/key-privileges/pull/38#issuecomment-5694033897

### Transport findings and tests

The successful diagnostic and failed earlier production used byte-identical JS. Old5s request timeout discarded a synthetic valid8s response in the ACTUAL JS under a virtual clock. PR38 allows at most15s, clipped to the remaining original43s script deadline; no page/browser retry or added source call. Bounded timings distinguish header versus body timeout, without recording source headers, cookies or response bodies.

First PR38 main attempt stopped BEFORE JS execution at provider route404: balance5821→5796,25 actual credits. One explicit collection-job rerun fetched the complete current catalogue:5796→5646,150 actual credits. Its nine API responses took1.031–1.953s, so live success cannot be attributed solely to the increased timeout. The source/network remains intermittent; one successful push/rerun is not proof of future cron reliability.

PR38 branch Actions35069873660 passed655 Python+7 KEY tests, no skips; artifact10435592840 SHA256 `ae53cb48b39899f274beb593af0224baba53c1dbe4b16480c30f90d874f97285`, CRC/hash and all4 changed executed bytes verified. Eight new local timing/validation tests and the existing actual-JS test passed. Full local suite is unavailable due to missing protego and failed package installation; pinned Actions is authoritative for the full suite.

## Failure-only provider reporting repair

PR39 is merged at0ad9a015800c9fc0f78174e076429e1b9782d4cc. Actual earlier run35067498377 had five failed sources, no offers, and a skipped publisher: has_records incorrectly also controlled whether the current coverage report existed.

The fix distinguishes **has_payload** from **has_records**. A validated fresh failure-only bundle is now written and eligible for publication; empty offer upserts preserve old source text/dates/manual columns. Wrong run/attempt/commit, stale reports and unconfirmed-Free/unconfigured cases remain rejected. No source, permission, schedule or budget changes.

Seven new local tests reproduce and fix that behavior. Branch Actions35070813062 passed **662 Python+7 KEY tests**, no skips; artifact10435787540 SHA256 `bfb321ec652e8b0cd67d2478e4d8ea5292834eb01239197098ddb73c8d25a787`, CRC/hash checked and all3 changed executed files byte-matched.

**At this checkpoint, main run35071057184 is still collecting.** Its source results, final publication and native readback remain to be inspected. Do not call its pending coverage/Coral result published. This report-routing repair is not itself an increase in offer coverage.

## Regular operation and Free budget

| Collector | UTC schedule | Per-run provider reservation |
|---|---|---:|
| Original direct sources | Daily05:23 | No ScrapingAnt use in that direct path |
| Extra provider/Coral sources | Mon/Tue/Thu/Fri06:03 | Up to269:94 root +175 Coral |
| EKP one anonymous browser | Monday07:13 | Up to175:policy25, optional policy-route retry25, one browser125 |

Recurring conservative31-day ceiling:19×269+5×175=5986 credits, excluding manual diagnostics/reruns, other account use, tariff changes and cron anomalies. Both Coral UTC-date parity halves recur; absent failures, planned gap for each half is at most4 days. Calendar and source tests do not certify network freshness.

Latest independently observed balance is **5646 at2026-09-16T07:49:50Z, BEFORE run35071057184**. Reserve that run's maximum269; estimated lower remainder5377 covers5273 scheduled credits for Sep17–Oct15 inclusive with104 headroom, under the stated assumptions. This reservation is not a newly measured balance. Stop further discretionary source experiments in this release; preserve recurring capacity. No paid plan or additional account.

## Remaining limitations and next acceptance gates

1. Finish main35071057184: inspect fresh artifact and final public/unified publisher, read exact latest coverage and manifest natively. Add only actual new IDs to counts. Reconcile provider-cost headers separately from actual account debit.
2. EKP full pagination applies ONLY to the current anonymous filter region98, labelled Все регионы. It does not verify personal eligibility, gated110 descriptions, other regional result sets, image-only clauses, linked partner/PDF rules or individual detail navigation. Dates remain literal text unless separately parsed. No login, coupon issuance, purchase or bonus spending occurred.
3. Coral still has intermittent category/detail failures; rotating selected halves and observed promo links are not a proof of the whole program. Inspect latest per-path errors before choosing a bounded retry. Last pre-PR39 all-failure run had root404s, no new Coral records.
4. Nordwind last pre-PR39 provider root returned500; earlier retained accordions are not newly observed by that failure. RZD root returned423 after readable policy. Aeroflot policy remained unreadable in the last ordinary run; an earlier separate policy observation disallowed its requested catalogue root. Do not bypass source restrictions or relabel partner-side pages as the complete catalogue.
5. Further coverage work should test concrete new permitted paths or improve observed partial parsing, not repeat identical failures, invent current values, use another account or force payment. Native publication/readback is the acceptance gate, not green fixture tests alone.

Public source artifacts expire after7 days (these releases around Sep23). Source/normalizer code, PR evidence and this checkpoint persist; never use an expired or old capture as a fresh runtime replacement.
