# On-demand publication

Update `loyalty/request.json` with a unique request ID on `main` to request a diagnostic collection and Google Sheets intake publication. The request file is only a trigger and audit marker; none of its contents are executed or used as command arguments. This uses the same trigger-file pattern as the separate KEY collector.

`loyalty-request.yml` has only repository content-read and Actions-write permissions. It checks the repository, branch, enable flag and configuration presence, then uses the runner's ephemeral GitHub token to dispatch the existing `loyalty.yml` on `main` with `limit=12` and `publish=true`. It does not authenticate to Google or obtain a Google token. The real publisher remains a separate job, with the existing two-tab write boundary and readback checks.

Neither a successful dispatcher nor a successful collector proves publication. Check the dispatched run's `publish` job and the actual `parser_inbox` and `parser_runs` values. A missing variable or secret fails the request without printing its value. A manual request does not enable the periodic schedule. Keep `LOYALTY_SCHEDULE_ENABLED=false` until separately authorized.

The currently configured Google project and Workload Identity provider are shared infrastructure, not resources to recreate. A dedicated service account is used for this spreadsheet. The IAM subject binding selects this repository's `main` branch; it does not distinguish individual workflows within that branch. No new Google Cloud configuration, IAM permission widening or long-lived key is required by this dispatcher.

The collector is still a diagnostic sample. Publishing page text is not automatic certification of a current benefit and does not modify the curated loyalty sheet. See `README.md` for parser limitations and Google API permission boundaries.
