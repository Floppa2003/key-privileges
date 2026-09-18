# Accepted Aeroflot linked rules and serial queue recovery

This records the completed 17 September release, independently read back again on 18 September 2026. It is not a new source observation. Later extensions require their own source and destination acceptance.

## Source-to-destination release

PR53 introduced source-linked rules; merge f9a70475e62ac60855a544dfd61e4aaa585a515e. The first main run35284735971 was cancelled while pending, before any jobs. The queue correction05d60953d4f4956d448fec4e80238ecb00a09846 produced accepted main run **35285168294:1**. Regression, collection and final publisher steps completed successfully.

The trusted discovery parent is the235-record Aeroflot catalogue **35274931392:1**, observed2026-09-17T21:09:09.883799+00:00. Its229companies and6airlines are not relabelled as newly fetched. Individual parent IDs, hashes, labels, fields, URLs and observation times remain attached to linked rules.

The linked run interval was **2026-09-17T23:06:14.844429–23:07:50.504006UTC**. It made19physical HTTPS requests and used0provider credits, without a source account.

| Scope | Actual result | Boundary |
|---|---|---|
| Sheremetyevo parking rules | One PDF,37pages,7condition parts |35native-text pages and2OCR pages; extracted text does not certify maps, table relationships, perfect transcription or eligibility |
| Doctor Stoletov exclusions |9listing pages,279distinct products against580advertised |Partial; the default source robots rule blocks page=1-prefixed query values, including10–19; no bot impersonation or query workaround |

The parking PDF SHA256 is5dfc95deb471e6442664f1c0aa085f0cde2bfb6970a5719f3018a0545acfcce6. The report is **partial**, not globally complete. All16records are rules: each projects one condition and zero automatic benefits, costs or codes. Products are exclusion membership, not individual offers or evidence of stock availability.

## Independent recovery readback

Destination is the same spreadsheet `1uFR7croj7p6RRNPcoTRYlVl06hKsurkIgyu1IdMMB-4`, title `скидки`. Native metadata, source IDs/hashes/run markers, coverage and manifest were read. A fresh read-only XLSX export was independently inspected without executing formulas or changing the workbook.

- Source rows2525–2540, coverage row1398, common rows3173–3188.
- **414source/report fields matched**:16×25+1×14.
- All3187common records and their current component IDs, original evidence, hashes and audit were recomputed from the five source tables; **342446common fields matched**.
- Manifest **verified/current**;2539retained source records,3187common records. Components:3644benefits,10203conditions,118costs,653code entries. These are typed components, not counts of personally usable discounts.
- Normalization assessment date remains2026-09-17. Fingerprint255515945849d60f0f5411e1aaae474c9550e6ef3fcdf1e1bf12559768803731; generationce91901df3244548cda2abd52b87458b33eb8a221db019df0a9e80077b444cfc.
- Recovery export SHA256a8435bca9c24ea42b0f2203d8c2fa0cf968f605db2c5d08484497da87c767b7f. The export stays local and is not a public deliverable.

No independently available pre-publication export exists for this16-row release in the recovery environment, so no new full pre/post preservation claim is made. The live readback and deterministic projection are verified; source semantics and source freshness are separate. Native styles were sampled; no whole-workbook rendered layout audit is claimed.

Source artifact10524119397 SHA2565beb12b6ff8dae67c25f8c11f907b66bb607efe1c6e278150268e59147c7005d was downloaded with matching digest and ZIP CRC. Exact production tests/code artifact10523844613 is identified in the preceding release evidence; its executed suite was886Python/7KEY. Historical replay is not a live fetch.

## Shared queue correction

PR54 merge **9ec5f0fbcf04bd21d04d7dabd3c24891ff4bd0d5**, verified root tree15978839c935f18dc7d81d8e64d8a3623d4820d5. All23workflows sharing `loyalty-catalog-${{ github.ref }}` now use `queue: max` and `cancel-in-progress: false`. Group names, schedules, permissions, source budgets and publication serialization were preserved.

Run35285616414 exercised three simultaneously eligible queue jobs; all completed successfully in nonoverlapping intervals23:10:40–23:10:52,23:10:58–23:11:10 and23:11:18–23:11:30UTC. The regression demonstrated22missing queue fields before correction and passed afterward. The full suite was887Python/7KEY. Its final push was refused for missing GITHUB_TOKEN workflows permission; the overall preparation run is correctly recorded as failed, not successful. No permission was expanded. The authorized connector assembled the exact tested blobs after the separate successful object-preparation run35286494064.

Verification artifact10523014369 SHA2566df5a2861d9631550a6d6afc6f70d1afcba7cbf51d49e3bb4c6d1aaecc9a1530 and ZIP CRC were independently checked. Source/main tree identity was read back. No temporary helper workflow is present in the accepted main tree.

Current GitHub documentation permits at most100pending executions with queue:max; this prevents the demonstrated single-pending replacement, not all possible scheduler/source failures: https://docs.github.com/en/actions/how-tos/write-workflows/choose-when-workflows-run/control-workflow-concurrency .

## Operation and remaining scope

Linked rules recur Friday09:57UTC through existing WIF and the same destination, with0provider credits. Bounds remain40pages per root,8roots,100requests,1500seconds and6MB per response. The overall recurring free-provider ceiling is8454credits/31days after the separately accepted EKP linked route, not the older6454; this excludes manual diagnostics/other usage and is not a fresh balance measurement.

Further external rules remain separate work. EKP110gated observations and RZD8unread full-detail conditions remain unresolved. No authenticated terms, personal coupons or source sessions enter this public path. `private_complete` is a normalizer mode, not an ACL; the previously noted link-accessible destination sharing has not been changed here.
