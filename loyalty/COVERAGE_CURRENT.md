# Current original-source coverage checkpoint — 2026-09-16, after RZD publication

This is the current handoff. The previous complete EKP/Coral checkpoint is retained in Git history at `5b810559cde3c397a11c806707c8b6a53287db67`; historical numbers describe their own observation times. Do not rebuild completed adapters from older diagnostics.

## Objective and constraints

The owner wants current data from the originally requested sources in the SAME Google discount spreadsheet, updated regularly through GitHub, with no paid service, server rental/administration or always-on laptop. The latest scope specifically targets original catalogues that had never produced records, rather than more work on already recovered sources.

Free API keys are allowed; the existing ScrapingAnt key and Google WIF authorization are configured. No second ScrapingAnt account is needed or used. Source-account access is authorized in principle, and Coral registration has already been completed by the owner, but no authenticated source session is connected. Do not ask for that registration or the existing API key again.

## Operational result for the two formerly zero catalogues

| Original source | Current operational status | Evidence boundary |
|---|---|---|
| RZD Bonus | **Implemented and published; partial catalogue content** | 66 current imported detail records from 74 discovered same-host detail pages; actual GitHub collection and both destination publication stages completed |
| Aeroflot Bonus main catalogue | **Blocked by published source crawl policy** | Default robots group explicitly disallows the requested `afl_bonus/partners` path; no main catalogue records published; no claim of universal technical impossibility on GitHub |

Aeroflot's exact decision, complete policy-projection provenance, applicable group, alternative discovery attempts and reopening conditions are in [AEROFLOT_ACCESS_STATUS.md](AEROFLOT_ACCESS_STATUS.md). A source-policy blocker is not the same as a network timeout or proof that arbitrary code cannot download a page. Existing partner-owned rules and Promo Miles do not count as recovery of that original catalogue. Permission from the source, an approved feed, or changed applicable rules would reopen the decision.

## RZD release and actual production result

PR40 is merged at `2ba43842cc579fda447880a5cf4708bb81f066ac`. Production run **35085594949:1** used that commit. Regression, collection and final publisher job **104769971215** all completed successfully.

- Collection started `2026-09-16T10:34:52.536949+00:00` and finished `2026-09-16T11:09:35.458282+00:00`.
- The source's canonical homepage links to `https://rzd-bonus.ru/partners/`; the coverage report retains the originally configured `https://www.rzd-bonus.ru/?accessible=true` as its root identity.
- 23 source-owned catalogue pagination states were read. The discovered single-PAGEN page queue was exhausted. The code avoided 264 repeated combinations of independent category pagination states; these are not 264 missed catalogue pages.
- 74 distinct same-host detail URLs were discovered and attempted. 66 yielded accepted public text records, including Auchan, Chefmarket, Sportmaster, Afisha, Yandex Afisha, MIF and other partners/campaigns. These are records, not necessarily unique merchants, active cash discounts or personal entitlements.
- Eight detail pages did not yield conditions. Two returned Google import errors. Six returned only `Скидки и суперакции` and `Вход в РЖД Бонус`; the validator correctly rejected this 36-character generic content. This alone does not establish whether the target is expired, redirected or authentication-gated.
- External card-link occurrences were counted (26 across the observed pages), not fetched or claimed as distinct covered partners. Linked files, image-only rules and personal redemption were not read.
- Source status is honestly **partial**, not `ok`: catalogue discovery completed within its defined scope, but eight conditions pages remain unavailable.
- 99 import requests were attempted; 97 successful cell observations were retained: one robots, one home, 23 catalogue and 72 detail observations. Six of the 72 detail observations failed semantic validation, leaving 66 published records.

### Transport and cost

GitHub controls Google IMPORTDATA/IMPORTXML in a separate public-only scratch workbook. It then reads typed results through the existing Sheets-scoped authorization, validates them and sends literal records to the ORIGINAL discount workbook through the established publisher. No source account, provider key, source-session cookie, paid reader or rented machine is required. **ScrapingAnt consumption for this new RZD path is zero.**

The reader respects the observed 20-second source crawl delay, finite runtime/page/import bounds, fixed host/URL/formula recipes, workspace identity and generation markers, two stable reads and verified cleanup. The reader never reads the discount database during collection. Current fields are dynamically extracted, not replaced by a recorded answer.

Google imports return parsed cells rather than original HTML or an origin HTTP response. **Origin cache age and exact network fetch time are not exposed.** The stored observation time identifies the requested calculation, not a certified uncached origin read. Nine accepted records contain date serials explicitly retained as Google display/typed evidence; no expiry date is inferred from a publication date. Other numeric coercions are rejected rather than silently changing coupon values.

The technical setup is already complete. No additional owner action, key or registration is needed for the released public collection.

### Artifact and code verification

Public artifact **10442639040**, `rzd-import-public-35085594949-1`, ZIP SHA256:
`03d22b365e9f207686bc7533538e804f208916e04936a291570638fa645ad240`.

The archive was downloaded, CRC/hash checked, and all **66** records independently reconstructed exactly from their own typed source observations. All were JSON-schema validated, application validated and prepared by the production publisher. The discovered graph, distinct identities, observation ordering, 74/66/8 counts and partial/completeness flags were checked without a second source crawl. The actual workflow also ran the full real robots-aware validator before obtaining publication credentials.

Main test artifact **10442221882**, SHA256:
`82042f0fb0a8cfb8acf9df0ed75cbf63f873d482fb1abd6d5281bd962a120de2`.
It contains the executed tree and logs showing **681 Python tests and 7 KEY tests passing**. Three critical executed files were independently compared with their Git blob identities at the runtime commit: `rzd_import_collect.py` = `659611ceb93b54c0c19d3bf09621ffdff52ca574`, `rzd_import_catalog.py` = `7aa4a31f1960e402c1626d50cea8a9283cf4456d`, `rzd-import.yml` = `7bee181f52a056edbfd0dddea59c53db4dbaf7bc`. Eighteen targeted RZD tests also passed locally. The missing local Protego dependency prevents claiming a repeated full local suite; pinned Actions is the complete-suite evidence.

### Native destination acceptance after the final write

Destination remains `1uFR7croj7p6RRNPcoTRYlVl06hKsurkIgyu1IdMMB-4`, title `скидки`.

- **66 new RZD rows occupy `parser_offers!A2159:Y2224`.** All 66 native content hashes in X were compared programmatically with the source artifact; all matched. All 66 Y values contain run `35085594949:1`.
- Native IDs, names/titles and record kinds at rows2159,2160,2161,2224 match the source. First/last timestamps match. The full Auchan conditions sample was read natively; it includes earning and exclusions, not just a title. Last-row manual column remains blank.
- `parser_coverage!A1275:N1275` is the exact current report: 74 discovered,66 normalized,8 errors, `partial`, with the eight failed URLs and scope limits preserved.
- `normalization_audit!A7:J7` is **verified/current**: **2871** input/output records, including **2223** retained parser records. These totals are retained data, not all freshly read in this RZD pass.
- Final source fingerprint: `c061ffce4edd615da4312da5470c7d5c381b2e5c06c77875a32fa766e9a1e9dc`; final normalization generation: `dc061c43c846efef615365bca3c16dd832afb842e5667a1098d86611f9e73999`.
- Normalized row2807 contains the corresponding new Auchan record and native top/wrap/10pt styling. No exhaustive rendered-workbook or independent private-cell comparison is claimed. The established publisher performs complete output readback; these independent connector checks cover all new hashes/run markers and declared actual-value/report/manifest samples.
- EKP sentinel2153 still has its prior successful run `35070130567:2`, hash and timestamp. RZD publication did not relabel it as a new RZD observation.
- The public staging workbook was read across its entire `public_fetch!A1:D2048` after collection: only the header and `idle:35085594949:1` remained. The temporary Aeroflot policy tab was deleted and metadata read back; the RZD workspace is intact.

Before this release, the latest direct scheduled work had brought retained parser count to2157, five more than the earlier EKP checkpoint2152. RZD adds66, giving2223. Do not attribute that earlier five-record increase to this RZD adapter.

## Regular operation

| Collector | UTC schedule | Moscow schedule | Provider reservation limit |
|---|---|---|---:|
| Original direct sources | Daily05:23 | Daily08:23 | No ScrapingAnt in this path |
| Coral/Nordwind and remaining provider probes | Mon/Tue/Thu/Fri06:03 | Mon/Tue/Thu/Fri09:03 | 269/run |
| EKP anonymous catalogue | Monday07:13 | Monday10:13 | 175/run |
| RZD Google import | Wednesday08:37 | Wednesday11:37 | 0 ScrapingAnt |

PR40 prevents provider source collection on ordinary code pushes while preserving its schedule/manual trigger; regression still runs. This avoids charging the Free quota for unrelated implementation commits. The existing conservative provider ceiling5986/31days excludes manual tests, other account usage and tariff/cron anomalies. No new balance was measured in this RZD/Aeroflot continuation, so do not repeat an old balance as current.

The released RZD bound is32 catalogue pages,100 details and135 imports with3300-second runtime. If a future catalogue has more than100 same-host details, the worker rotates the chosen detail subset weekly and explicitly reports partial coverage; it does not certify an unbounded full programme. Current74 details were all attempted, so this bound did not limit the present result. A successful release-triggered pass is not proof of future scheduled reliability.

## Sharing and account-data boundary

**Do not call the original destination private.** A fresh Drive permission read confirmed `anyone:writer` (link sharing, not indexed discovery), in addition to its owner and a writer. This was already set; no sharing permission was changed here or by the RZD release. The existing normalization mode string `private_complete` describes which source tabs it processes, NOT the spreadsheet's sharing ACL.

Only public source descriptions enter the new path. Do not add cookies, tokens, SMS values, authenticated-only conditions or personal issued codes to this destination/public artifacts under the current sharing state. The owner's permission to use accounts is not permission to expose credentials or private results. Existing original data and permissions were not automatically rewritten.

## Remaining work and stopping criteria

1. **RZD is no longer a zero-output source:** source-to-destination acceptance is complete with66 records and eight explicitly unresolved condition pages. Improving that partial content is a separate task from proving the GitHub-controlled path exists.
2. **Aeroflot remains unimplemented due to an evidenced source-policy blocker.** Record the scoped status, not `impossible_on_GitHub` and not a fabricated success. Reopen only with an appropriate permitted source channel or changed policy; consult AEROFLOT_ACCESS_STATUS.md rather than repeating the same failed proxy matrix.
3. EKP retains the previously published1045-entry anonymous region98 catalogue, with935 public terms and110 gated observations. Its other-region/private/linked/image eligibility limits remain. Existing Coral and Nordwind data retain their own observation times and latest partial/failed reports; they were not recrawled in this continuation.
4. Future failed imports must preserve historical record times, publish clear coverage failures where validated, and leave the common manifest unverified if final publication/readback fails. Current-page extraction, completed publication and native readback remain the acceptance gate.

Public artifacts expire after7days (this release around2026-09-23). Repository code, source-policy decision and this checkpoint persist. No pending release run is represented as completed in this checkpoint.
