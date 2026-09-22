# PR82 — durable full collection published and independently verified

Actual source/publication events occurred on 22 September 2026 UTC. This report supersedes the pre-publication boundary in DURABLE_COLLECTION_ACCEPTANCE.md. It documents a completed source collection and completed Sheets publication, but not a clean overall workflow conclusion: one GitHub job-status inconsistency remained at the final read described below. No extra crawl is requested by this documentation update.

## Release and actual main execution

PR82 merged at **2026-09-22T20:39:21Z**, merge **cb70bbebbdfc301b64cfb65b72cf1678e9f4510f**, reviewed head **24af5efc6231f0ef332fe9c96e1192a0091ea368**. The connected GitHub app independently read its merged state. Six final files: collection_runtime.py, the existing collector/health integration, two test files and acceptance documentation. The temporary verification workflow was removed before merge; no existing workflow or schedule changed.

Main **35781773598:1**, execution **96275a709b896ed3296ad518bb163cdb4773be53**, selected the entire registered scope through the existing request/main pipeline. Empty source_ids intentionally selects all115 current configurations. Actual batch observation: **2026-09-22T20:41:30.767057+00:00**. This is the collector timestamp, not a source-written publication date or cache-age guarantee.

| Component | Actual result |
|---|---|
| Collection runtime | complete; **115/115** source workers; **702.036 seconds** |
| Reports | **106 ok /1 partial /8 failed** |
| Collected records | **1497**, all already-stored IDs |
| Execution-health replay | healthy; no missing, unexpected, unfinished or duplicate reports; no worker exceptions |
| Backit | **178**, zero errors; strict source-health passed |
| Club Avolta | **17**, zero errors; strict source-health passed |
| Mantera Moments | **16**, zero errors; strict source-health passed |
| Konsierge | **159**, zero errors |
| Applied source holds | **0** |

All85 production Python hashes in the actual source manifest match the accepted full code archive. The complete payload, individual source reports, inventory checks and publication data were inspected independently; none of these outcomes is inferred merely from a green collection job. 1497 refreshed rows are not1497 newly added discounts or proof of personal eligibility.

### Job states and unresolved GitHub metadata

| Job | ID | Independently observed state |
|---|---:|---|
| collect |106928779546| completed/success; completed2026-09-22T20:53:18Z |
| publish |106933441441| completed/success; publication/readback step ended20:57:22Z; job ended20:57:25Z |
| source-health |106933441399| Parent still **in_progress**, conclusion null, although every step including Complete job is completed/success at20:53:28Z |

The source-health discrepancy persisted through both the named jobs tool and a separate raw repository jobs GET. The actual application check is completed/success and its execution/source-health results were independently rerun read-only from the downloaded artifact. The parent job is nevertheless NOT called completed, and no successful overall workflow conclusion is asserted. Cause unknown; no rerun, cancellation or permission change was used to force the state green. The independent publisher is already complete and the final live Sheet is verified below. Re-read this job's metadata on a later continuation instead of repeating the full source crawl.

## What changed operationally

The old main entry wrote normalized.json only after all gather workers and browser cleanup finished. A controlled cancellation after one successful source reproduced complete absence of an output file. The last historical full daily run35714017362 itself succeeded; there is no claim that it lost data.

The deployed runtime atomically checkpoints completed source results after each completed task batch. Partial checkpoints explicitly include failed/interrupted or not_started reports for unfinished sources, with zero invented offers. A disk/serialization/replacement error leaves the previous complete JSON intact. Code hashes are saved before browser work. Existing source observations, stable IDs and output order are preserved; a previous run is never loaded and relabelled fresh.

Four-worker concurrency and each configured source budget remain. Longer allowed budgets are admitted first; waiting in the queue does not consume a source's timeout. Additive queue_seconds/execution_seconds distinguish queuing from reading. This is a scheduling heuristic, not a guaranteed optimum or a controlled speed benchmark. In this actual full run Backit started immediately, while its former position was at the end of the configuration list.

A **1000-second soft collection deadline** is intended to leave headroom inside the existing20-minute collect job. At the soft deadline, accepted completed results remain publishable and unfinished workers remain visibly failed. Cancellation propagates after checkpointing. Cleanup is bounded, but cleanup/disk failures are not reclassified as collection success. No real timeout, cancellation or forced hold was needed in the accepted main refresh.

Execution/report completeness now covers ALL selected source configurations. The three public reward programmes retain their stricter semantic inventory/health checks. Ordinary failures of older source routes remain explicitly reported and do not become claims of successful source reading; their semantics were not globally redesigned. An independent successful publisher remains separate from source-health failure.

Limits: this is not guaranteed recovery from SIGKILL, runner/disk loss, a blocked event loop, or failure to upload an artifact after the CI hard timeout. Records inside an unfinished source are not checkpointed individually. The1000-second limit does not guarantee enough headroom if environment setup itself becomes unusually slow. No rolling remote artifact storage, new provider or second architecture was introduced.

## Real remaining source failures

All eight failed routes also failed in the earlier inspected full daily batch. They are not newly fixed, and some programmes have separately implemented successful collectors.

| Route | Actual latest error |
|---|---|
| nordwind | robots phase TimeoutError |
| coral | http_403 |
| coral_promo | http_403 |
| rzd | http_403 |
| aeroflot | robots_not_readable |
| ekp | robots phase TimeoutError |
| af_primbank_rules | ERR_CERT_AUTHORITY_INVALID |
| alfa_only_partner_offers | alfa_bank_authentication_redirect |

HSE alumni remains partial:55records, with missing/empty detailed sections for skyeng, skillcup and academiya. A failed spare route is not a programme-level zero; inspect alternate source history before prioritising. Do not weaken TLS, infer authentication access, repeat obsolete marketplace redirects, or restore junk to raise coverage counts. Source-specific errors are distinct from the new execution-completeness check.

## Verification before release

Full-checkout feature **35781070515**, execution **60331bcde874566f804d50bef6086705be3f292d**, verify job106926395842 completed successfully: **1252 Python +7 KEY tests**, no skips, real pinned dependencies. Eighteen new tests cover the runtime and actual main/prepare/health CLI: cancellation, deadline, cleanup failure, disk failure, queue clocks, order, identity, sanitation and missing older-source reports. Main repeated the full regression successfully.

The feature also replayed the complete older daily artifact35714017362:1: **112 reports /1286 actual records**, with original timestamp/run identity. Every managed row from sheets_normalized.prepare was exactly equal before/after orchestration. Four checkpoints were written. The1.156-second replay timing is not website performance; zero websites were fetched by that replay. Local Protego/import and synthetic fixture limitations are disclosed in the acceptance document, not hidden by skipping production tests.

## Independent final destination comparison

Destination **скидки**, spreadsheet **1uFR7croj7p6RRNPcoTRYlVl06hKsurkIgyu1IdMMB-4**. A genuine native pre-publication export was saved before the request. After the publisher completed, a new native export was obtained; its last modification metadata is **2026-09-22T20:56:45.115Z**, not the exact time of the later final read. Native CellData separately confirmed formulas, controls and verified manifests. An intermediate publishing state had been observed and was not mistaken for completion.

Read-only auditing used standard-library ZIP/XML parsing and the accepted normalizer. Google-exported empty shared-string cells were treated as native blanks only after native CellData confirmed representative cells were empty. No workbook values or guards were altered to make the audit pass. XLSX DUMMYFUNCTION/cached spill formulas were not treated as native UI formulas.

| Check | Verified result |
|---|---|
| Parser records | **3022 unchanged** |
| Current normalized records | **3670 unchanged** |
| Clean/visible working catalogue | **3056 unchanged** |
| Source publication | **1497 existing IDs refreshed,0new,0holds** |
| History reports | **115 added**;1994 ->2109 report IDs |
| Exact source managed fields | **37425** |
| Exact report managed fields | **1610** |
| Normalized records fields | **102760** |
| Normalized benefit fields | **97306** |
| Normalized condition/cost fields | **171904** |
| Normalized code/delivery fields | **8904** |
| Normalization audit fields | **70** |
| Entire cleaned reader | **3056 rows /51952 fields** |
| Entire visible reader | **3056 rows /42784 fields** |
| Untouched-tab cells | **9175 preserved** |
| Source/common row identity and trailing manual values | Exact match to the independently simulated upsert/retirement plans; old positions preserved |
| Original formulas | **8 preserved**,0formulaerrors |
| Native UI | A10search/A7count, B3:B5empty inputs/B4validation, C6note and G2programme-list formula unchanged |
| Readiness | Both manifests verified/current with identical generation; native A7shows3056/3056 |
| Visibility | Only Скидки and О таблице visible |

The current common view contains4423benefit components,10646conditions,98costs and742code/delivery components. These are not counts of unique coupons, guaranteed active discounts or new offers. Every source-row update was matched against the actual newly collected payload, and every common/reader managed field was independently recomputed from the resulting source snapshot. All unmodified input/history tabs and old source/common manual values remain. No full rendered-layout or ACL audit is claimed. Private workbook copies were not publicly uploaded or committed.

Current generation: **db0a56885e1866d167f231a334d7e907766e8ba5434187872b5cd2164c629e1f**.
Source fingerprint: **2d37ac379ea3139f6e5cdb7d9f157b55491f14c8e8330c6bb53e84072a193c38**.
Reader digest: **60f874a5eb3a60c33f4e3f3188dbeeaa0360328cf7b48b80cea207318b2f62f9**.

## Durable artifact identities and continuation

- Actual main artifact **10718444869**, loyalty-public-35781773598-1: ZIP SHA256 **ec7aacb08d6c811740444b9601e9ff3bc0a5fca2c66ceb6be55a9161b4282c48**.
- Main normalized.json SHA256 **f9a63e43719158c87c7ef9d1d698ed804e808177254bbc7aea9985d9236e5d16**.
- Accepted feature artifact **10716979990**: ZIP SHA256 **37d59103a2fb0186cfed115e47428db0c36aa201124c19d4e691957ea100abb0**.
- Baseline daily artifact **10688223756**: ZIP SHA256 **4e5324c1e0aea0c12add5913699ef756290dacee8ac4d87f4c91c027098597f0**.
- All ZIP hashes/CRCs were checked;85actual main Python hashes match the accepted code archive.
- Shareable aggregate publication audit SHA256 **3caf71de4ef5e4bde2c773542a41666f871f3cf465ffb5d03b1b289960ce702b**.

The pre-PR82 checkpoint remains byte-for-byte at **96275a709b896ed3296ad518bb163cdb4773be53:loyalty/COVERAGE_CURRENT.md**, blob **ce8b260d77e740b8beb2a57ea81ba6f7f4bbb8e6**. Earlier PR79–81 coverage, scope-specific holds and freshness remain. This refresh did not add programmes, resolve product-level Backit marketplace access, resolve DragonPass lounge pricing, or access Only Assist.

Existing daily **05:23 UTC /08:23 Moscow** schedule and serialized publisher remain. This was a controlled workflow_dispatch of the same daily scope, not proof of a first later timer-triggered run. No paid provider, extra account, new schedule, source login, coupon activation, purchase or private-data publication. Continue from the independently verified destination and remaining source errors, not by repeating the completed full crawl merely because chat output was interrupted.
