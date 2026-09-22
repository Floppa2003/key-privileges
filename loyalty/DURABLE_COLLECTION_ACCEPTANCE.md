# Durable full collection — implementation acceptance

Continuation of the approved coverage/reliability task after PR81. This is a pre-publication checkpoint: a later report must independently verify the actual main execution and live destination. No source benefits, URLs, access policies, account entitlements or schedules are changed.

## Actual baseline and reproduced failure

The latest inspected full timer run was **35714017362:1**, code48530f341aa053373836618bf97000c5c5783db9, observation2026-09-22T10:06:41.671725+00:00. It completed successfully with112reports and1286records:103ok,1partial,8failed. This successful run did NOT lose its results. Its artifact10688223756 was downloaded through the connected app, SHA256/CRC verified:4e5324c1e0aea0c12add5913699ef756290dacee8ac4d87f4c91c027098597f0. The eight failed routes do not mean eight uncovered programmes: some have separately implemented collectors. The current configured scope is115sources, including the three later public reward integrations.

The actual old collector wrote normalized.json only after every asyncio.gather worker and browser.close finished. A controlled main-entry reproduction returned a valid fast source result while a second worker remained pending: neither before nor after cancellation was any normalized.json present. With the reviewed change the completed source remains in valid JSON before and after cancellation. This is a reproduced orchestration failure mode, not an invented historical website outage.

Three hypotheses were distinguished: whole-run interruption, an unfinished source, and browser-cleanup failure. Tests at the real main entry/prepare boundary cover cancellation, soft deadline and cleanup exception. Source transport itself is mocked in those deterministic cases; actual source evidence is separately replayed unchanged.

## Minimal implementation

collection_runtime.py uses the existing source workers and schema2 bundle. It atomically checkpoints completed results after each completed task batch, with fsync and replace; a failed write leaves the preceding JSON intact. Every selected source has an explicit report. Unfinished sources are failed/interrupted or not_started with zero offers; no old evidence is imported or given a new date. Code hashes are saved before browser work.

Four-worker concurrency and individual source budgets are unchanged. Larger allowed source budgets are admitted first, preserving configured output order and IDs. This is a scheduling heuristic, not a measured universal optimal ordering. Queue waiting does not consume a source's own timeout. Additive execution_seconds and queue_seconds distinguish source latency from queue latency.

A1000second soft collection deadline is intended to leave headroom within the existing20minute CI job for setup/finalization. On that deadline, completed results remain publishable while unfinished source reports remain failures. Cancellation propagates; disk/cleanup errors are not called success. Cleanup is bounded separately. This does not guarantee survival of SIGKILL, a lost runner, disk loss, a blocking event loop, or successful artifact upload after the CI hard timeout. Results from inside an unfinished source are not claimed checkpointed.

The source-health CLI now additionally checks execution/report completeness for ALL selected source IDs. Missing/duplicate/foreign/unfinished reports or unexpected worker exceptions cannot yield green execution health. Ordinary old-source read failures keep their existing reported semantics; this is not a new semantic-completeness contract for every historic programme. Backit/Avolta/Mantera retain their stricter existing source-health, freshness and reversible-hold checks. An independently successful publisher remains independent of source-health failure.

No new recurring workflow, paid service, source login, private-data publication or UI setting. Source readers, transport scopes, rates, credentials, headers, TLS, throttles, old-row identities and user inputs are unchanged.

## Verification

Full-checkout feature run **35781070515**, execution **60331bcde874566f804d50bef6086705be3f292d**, verify job106926395842 completed successfully. It installed the real pinned requirements and passed **1252Python +7KEY tests**, no skips. The18new tests exercise runtime and actual main entry paths, atomic-write failures, cancellation, timeout clocks, ordering, worker identity, sanitation, and the real health CLI. Main soft-deadline output passes actual sheets_normalized.prepare but makes health exit1.

The same feature run replayed the entire actual112source/1286record daily artifact through the new orchestration, preserving its original run and observation. All generated managed publication rows compare exactly equal to prepare(original); execution health passes. Four checkpoint writes,1.156seconds in that replay; **zero live website requests**. That timing is an offline serialization/replay measurement, not website collection speed.

Downloaded feature artifact **10716979990**, durable-collection-35781070515, ZIP SHA256 **37d59103a2fb0186cfed115e47428db0c36aa201124c19d4e691957ea100abb0**. Its test logs and replay-audit.json were independently read. The complete tracked-code archive matches all five changed local files byte-for-byte. The temporary verification workflow is removed before merge; only this report and that removal follow accepted code.

Local environment limits: network/DNS prevented installing missing Protego. Narrow main-entry tests locally used an unused import stub solely because all transport was mocked. The accepted full CI above used the real dependency, no stub and no skipped/altered production tests. An initial synthetic fixture used an invalid source domain; the fixture was corrected to an allowed domain, not by weakening publication validation.

## Release check

After merge use the existing request/main pipeline for one full115source refresh, not another Mantera-only refresh. Inspect runtime, each source report, the separate health job and final publication. Independently compare the final destination with a preserved pre-publication export and actual normalized payload. Do not claim full website success from execution completeness. Keep manual notes, source row positions, the eight original formulas, native search and two-tab visibility. Private workbook exports must stay local. The accepted pre-release checkpoint is main b994d552f5aa0a76b6fb10bbe4376a5f023e396b and COVERAGE_CURRENT.md/PR81.
