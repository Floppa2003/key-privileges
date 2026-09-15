# Regular collection and publication

## User objective, clarified 2026-09-15

Maximize useful, current extraction from the originally requested sources, with a recurring job controlled from GitHub. The execution engine is an implementation choice: Actions, a user-authorized external worker or an external reader can be used when it demonstrably improves coverage. A passing test suite, a diagnostic artifact or additional supplementary URLs is not itself an increase in original-source coverage. Do not substitute fixed answers, old page captures or unrelated sources for fresh extraction.

## Daily operation

The existing `loyalty.yml` now schedules the full registered collection daily at **05:23 UTC** (`23 5 * * *`). Recurring operation was explicitly authorized by the user on 2026-09-15. The old `LOYALTY_SCHEDULE_ENABLED` opt-in condition is no longer used. Scheduled collection is restricted to `Floppa2003/key-privileges`; GitHub schedules use the default branch. Disable the workflow in GitHub Actions to pause it.

Collection remains credential-free. The separate publisher still requires trusted `main`, successful collection and `LOYALTY_SHEETS_SYNC=true`; it uses the already configured short-lived Google WIF credentials. No Google permissions or long-lived keys are added. It upserts `parser_offers` and `parser_coverage`, then recomputes the common normalized views. Both stages verify destination readback. Private source tabs, corporate codes and manual comments are not exported as public artifacts.

Partial source failures must remain explicit and must not prevent usable records from other sources being retained. Missing records are not silently deleted or given a fresh observation time. Original catalogues, supplementary rules, announcements and partial previews must be distinguished when reporting coverage. Published source text is not a claim that every condition or the user's eligibility has been established.

GitHub's schedule is best-effort: a future cron run is not certified by a manual test. Verify the actual run, source coverage and publication result. No repository/server purchase or paid external service is authorized by this configuration.

## Manual operation

Update `loyalty/request.json` with a unique request ID on `main` to dispatch the same `loyalty.yml` with `limit=500` and `publish=true`. The request file is a trigger and audit marker; its contents are not executed or passed as shell arguments. `loyalty-request.yml` has repository content-read and Actions-write permissions, checks the trusted repository and configuration, then uses its ephemeral GitHub token. Dispatch acceptance is not publication success.

The current Google project and Workload Identity provider are existing shared infrastructure, not resources to recreate. A dedicated service account targets this spreadsheet. The IAM subject binding selects this repository's `main` branch rather than an individual workflow; keep credential-bearing work in the existing reviewed publisher.

## Current coverage limits

The released Utair support adapter remains active. EKP PR23 is an unmerged candidate whose live checks failed before catalogue parsing. EKP, Nordwind, Coral club/promo, RZD and Aeroflot primary catalogues must not be marked restored merely because their test fixtures, alternative announcements or partner rules were read. Test a materially different retrieval path before repeating an unchanged failing probe.
