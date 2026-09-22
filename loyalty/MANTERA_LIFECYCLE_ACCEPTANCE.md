# Mantera roster lifecycle — accepted implementation, 22 September 2026

Continuation of PR80. This is pre-publication acceptance; verify the main execution and destination separately before marking deployed publication complete.

## Why this change exists

PR80 added ten roster-derived property cards alongside five FAQ tiers and the independently sourced Congress card. Its publisher did not reconcile a later successful roster against those earlier cards. A counterfactual removal from genuine public DOM reproduced the gap: the formerly named hotel remained usable in the reader until the observation-age limit. The new test failed before the change and passes afterwards. This was a simulated source transition, not an actual hotel departure.

## Scope and implementation

- `mantera_lifecycle.py` validates the existing Mantera health contract, every source record/hash and one identical roster/resort evidence pair across all derived cards. A full coherent, same-time named roster authorizes reconciliation of its own native record IDs.
- Many hotels share the same roster URL. URL-level retirement would conflate distinct properties; native IDs remain the unit of reconciliation.
- Only stored `public_partner` records with the exact roster URL, matching name and stable ID can be withheld when absent. The five programme tiers and the independent Congress page are excluded from this policy. A roster cannot invalidate independent evidence or prove programme-wide departure.
- `source_lifecycle.py` reuses the existing reversible metadata, last-offer timestamp preservation, stale-write protection and row upsert. No source text, original observation time, row positions or manual columns are deleted. Fresh accepted evidence restores the same row and removes the hold.
- Failed, partial, missing, empty, duplicate, mixed-version or mismatched inventories cannot justify withdrawal. Existing withheld cards do not become current merely because a later read failed.
- Source health uses the same validated snapshot as reconciliation. The existing selected-source check and publication of other successful sources remain separate.

No collector URL, source scope, current offer rate, membership requirement, native search formula, programme list, freshness threshold, schedule, TLS setting, provider or account configuration changes.

## Verification

Temporary feature workflow **35773968531**, execution **d0e241a31446a3c1c124d2930026f549a6f1ec8c**, job **106902341517**, completed successfully. It ran the complete repository's **1234 Python tests and 7 KEY tests**, no skips. Thirteen new tests cover removal/restore, notes/positions/timestamps, partial successes, older writes, missing reports/records, corrupt identities, mixed evidence, independent Congress/FAQ scope and a separately simulated change in property-specific redemption rights.

The feature workflow then genuinely collected **16 Mantera records, zero errors**, at **2026-09-22T19:29:37.786841+00:00**, passed source-health, normalized dry-run and all16 source-to-reader replays. Reconciliation of that unchanged real snapshot produces no holds or duplicate IDs. No Google credentials or publication were used in this workflow.

Artifact **10715232751**, `mantera-lifecycle-35773968531`, ZIP SHA256 **2166e112401345c672d5c0ddad2904efb692da6ad782ad09f922a45e5de56a47**. ZIP digest and CRC were checked independently. All three changed Python/test files matched the local reviewed bytes; all **84 production Python hashes** in the source manifest matched. Every actual source record was independently reproduced from its own public evidence and timestamp. Artifact retention is one day; this durable report preserves the run/code identities.

Local checks: the13 focused tests passed. The initially restored previous code archive lacked several unrelated workflow files, so a local whole-suite run produced9 FileNotFoundError errors rather than a complete pass. The full-checkout GitHub run above resolved that environmental limitation without altering, skipping or weakening those tests. Two earlier local attempts hit the command timeout; they were not reported as passed regression.

The temporary verification workflow is removed before merge; production/test bytes remain those accepted above. No new recurring job or ChatGPT task is introduced.

## Publication acceptance still required

After merge, use the existing main request mechanism to collect only `mantera_moments`, then inspect actual collect/source-health/publish results and the source artifact. Independently compare a genuine before export with a post-completion export; check the16 actual source fields, unrelated data/manual positions, all reader rows, eight original formulas and native search/visibility. Do not write counterfactual hotel removals or fabricated dates to the live spreadsheet.

## Remaining boundaries

This release prevents stale roster-derived claims; it does not expand the previously accepted11-property public coverage or confirm account eligibility. Empty or wholly removed rosters require review rather than automatic mass retirement. The existing seven-day age limit remains a freshness policy, not a source expiration date. Only Assist still requires the separately planned authorized device session. Backit marketplace redirects and DragonPass price conflicts are unchanged; no repeated probes of those routes were made.
