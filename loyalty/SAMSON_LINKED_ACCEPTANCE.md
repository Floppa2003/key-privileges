# Samson-linked rules — production accepted 18 September 2026

## Released implementation and actual run

PR55 merged the recovered, already-tested pharmacy extension as `8dc5843b6f4a06b3e5da6525ee66b5f49e928b16`. A one-path trigger correction then produced execution commit `f3f27c1187b40133ce940d3a58bb44ee06b49094` and **main run 35315811926:1**. Regression, collection and publisher **105508256363**, including every final publisher step, were independently read as completed/success before destination verification.

The source interval was **2026-09-18T06:40:40.124917+00:00–2026-09-18T06:44:09.015643+00:00**. The discovery parent remains Aeroflot run **35274931392:1**, observed **2026-09-17T21:09:09.883799+00:00**, containing 229 companies and 6 airlines. Parent dates, source links, record IDs and hashes remain attached; the parent catalogue is not relabelled as newly fetched.

| Scope | Actual main result | Completeness boundary |
|---|---|---|
| Samson Pharma exclusion catalogue | **19 listing pages; 579 distinct products; 579 advertised; complete=true** | Complete observed exclusion-list traversal, not 579 offers or stock/entitlement verification |
| Doctor Stoletov exclusion catalogue | **9 listing pages; 279 distinct products; 579 advertised; complete=false** | Default robots rules prohibit encountered page=1-prefixed pagination URLs; no query workaround or cross-pharmacy substitution |
| Sheremetyevo parking rules | **1 actual PDF; 37 pages; 7 text parts** | Text extraction is not certified transcription, map/table interpretation or eligibility |

Overall: **35 condition records**, **39 physical HTTPS requests**, **0 provider credits**, **no source account**. Overall report is deliberately **partial**, with one partial-list diagnostic and five observed policy-refused links for Stoletov (page=12,19,13,14,10). The 18 September advertised total is 579, whereas the earlier 17 September run advertised 580; the runtime does not pin either answer.

Samson root is `https://samson-pharma.ru/catalog/extra/spiski-tovarov/tovary-bez-skidok/`. The fix selects an already-reviewed rule route even when its source anchor says only “на сайте”. It also supports the source-owned note location. Unknown homepages/account paths are not promoted to rules; product references, pagination and redirects remain within their own pharmacy. Product names, totals and conditions are extracted from each run, not supplied by a fixed answer inventory. Exclusion products are not requested individually.

## Independent destination acceptance

Same destination: **скидки**, spreadsheet `1uFR7croj7p6RRNPcoTRYlVl06hKsurkIgyu1IdMMB-4`. A pre-publication native header/edge/manifest read and private XLSX export were captured. After the final publisher completed, native metadata, all new IDs/types/hashes/run markers, the source report, the common projection counts and manifest were read again, followed by a separate read-only export.

- **19 new source rows: parser_offers 2541–2559.** Existing 16 linked-rule rows 2525–2540 were refreshed in place. One new report is at parser_coverage 1399. Row order follows discovered navigation, not numerical page sorting; page numbers remain explicit in titles and evidence.
- **889 source/report fields matched** the actual main payload: 35×25 managed source fields + 1×14 report fields. All source records passed JSON Schema and independent content-hash checks.
- **3206 current common records and all current component views were independently recomputed** from the five exported source tables: **343282 common-view fields matched**, including all current IDs, source evidence, hashes, generation and audit. No source formulas were executed and no workbook was rewritten.
- Every new Samson record projects **one condition and zero benefits, costs or codes**. The 579 products are searchable exclusion members within those 19 records, not added individually as discounts.
- Manifest: **verified/current**, assessment date **2026-09-18**; **2558 retained parser records / 3206 common records**. Counts are retained database size, not simultaneous source freshness or usable discounts.
- All **2539 pre-existing parser IDs** and their manual comments remain. All **2523 parser rows outside this run** are unchanged. All **1397 pre-existing coverage observations** remain unchanged. Values/formulas in six original input/audit tabs remain unchanged. Existing manual comments in the common views are preserved.
- Common components: 3644 benefits, 10222 conditions, 118 costs and 653 code entries. These are normalization components, not personal entitlements.
- Fingerprint: `029b35564ef7c81e9932c27f9f8c30b555a35f4c1ad540464b0cd2ad3023e0b9`.
- Generation: `e7ba9162603b71b8e939d4cdc5307b0995a5f78d05205272035539e13e7961c2`.
- Private pre-write export SHA256: `cbc4c23dd7399a4d90fd822732951ae8b00a82aeff5f30b2813e7aff3f969d80`.
- Private post-write export SHA256: `1364bd7b1b7741fda788e3e3c86d8f5af806099d328b154460d14f75f5cb454f`.

The XLSX export represents some absent inputs as empty shared strings. Independent native blank-cell samples and the exact native fingerprint established the absence interpretation used by the readback parser. All recomputed views then matched; no destination value or production normalizer was changed to obtain the match. Private Sheet exports are not public artifacts or deliverables.

## Code and test evidence

The branch preflight **35304408913:1** also read all 579 Samson exclusions over 19 pages. The final main run independently passed **897 Python tests and 7 KEY tests**, no skipped tests reported. Ten new tests exercised the real collector against controlled HTTP responses before the implementation, then passed with the patch. Main publisher reconstructed its source bundle before receiving Google write authorization.

Downloaded main artifacts, with matching SHA256 and ZIP CRC:

- Source **10535196861**, SHA256 `a94bb3ee1af6a67f1e5be477f3932e9bd8063160d36b764a32ea3c2204b7efb2`.
- Exact tests/code **10535061419**, SHA256 `488663a9c4d1e8e1a4f03490e19dc3d4eb3b75430f1528dd8d8c6f81b78549da`.

The three changed Python/test files exactly match the reviewed branch execution bytes:

| File | Git blob |
|---|---|
| loyalty/aeroflot_linked_rules.py | fa2599cc7628b5371bd04691803241bb29f99ee9 |
| loyalty/normalized.py | 8beabed596a3ceb75b4e704bdcfcf54923a844ff |
| loyalty/tests/test_samson_linked_rules.py | 55a59f19fa42f0b115dce2ee31e81111902fa109 |

Local source-validator test execution lacked Protego and dependency installation failed, so no local passing source-test/replay claim is made. The independent OOXML/common-model verification did run successfully locally; exact dependency tests and full source reconstruction ran successfully in Actions. The clean release excludes one-time helper workflows and preserves the newer KEY automatic refresh.

## Recurrence and limitations

Existing linked-rule recurrence remains **Friday 09:57 UTC / 12:57 Moscow**, using direct HTTPS, no ScrapingAnt credits and existing same-Sheet WIF. Bounds remain 40 listing pages per root, 8 roots, 100 requests, 1500 seconds and 6 MB per response. No paid service, extra account, rented server, new key, Google scope or destination-sharing change.

All 23 shared loyalty workflows retain the serial `queue: max` correction from PR54; no new concurrency design was introduced. The existing conservative provider budget ceiling remains **8454 credits per 31 days**, excluding manual diagnostics, other account usage and tariff changes; it is not a fresh balance measurement.

Native structure/format samples were checked. A bounded artifact-tool import/render attempt failed with TimeoutError before returning a preview; **no full rendered Sheet layout audit is claimed**, and no restyling was attempted. The existing generic PDF stage handled its scanned pages; no OCR was repeated during independent readback and no OCR-derived numbers were manually repaired.

Known remaining gaps are not declared impossible: RZD eight full-detail conditions, EKP 110 gated observations, Stoletov's unvisited policy-restricted pagination, further unreviewed external rules, Coral interactive/sitemap equivalence and image/table semantics. The destination was last noted as link-accessible; source sessions and personal coupons must not enter this public path. Transfer correctness, source coverage, cache age and personal eligibility remain separate claims.

Earlier evidence: EKP_LINKED_ACCEPTANCE.md, AEROFLOT_LINKED_ACCEPTANCE.md, RZD_EXTERNAL_ACCEPTANCE.md and CORAL_PDF_ACCEPTANCE.md. The current handoff must supersede its older PR49-only counts; do not reimplement any accepted collector because a chat turn was interrupted.
