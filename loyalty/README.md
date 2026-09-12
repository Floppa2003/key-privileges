# Loyalty catalog diagnostic and Google Sheets publisher

Independent of the existing `key/` scraper. Public sources only: EKP, S7 Marketplace and CoralBonus.

## Current scope

This is a bounded **diagnostic collector**, not a certified complete catalog parser. It discovers individual offer URLs using a fresh Chromium session, follows up to four category pages and six explicit load-more clicks per page, and saves at most 12 detail pages per source by default (manual limit 1–100). It saves each page title, URL and unabridged visible text (up to 40,000 characters; larger pages are rejected, never silently truncated).

All records have `needs_review`: page content may include navigation or related offers. No automatic numeric discount, expiry date, partner identity or current-availability certification is inferred. Record count is not partner coverage. Missing/blocked pages and robots restrictions remain explicit in `bundle.json`. A failed collection cannot delete or expire prior records.

Output `loyalty-output/` contains only public page text, candidate URLs, network path/status metadata and a validated JSON bundle. It contains no spreadsheet exports, private source material, cookies, login tokens or browser storage. The repository is public; its Actions artifacts must be treated as public too. They expire after seven days; durable evidence storage is not implemented in this diagnostic version.

## Run

```sh
python -m pip install -r loyalty/requirements.txt
python -m unittest discover -s loyalty/tests -v
python -m playwright install --with-deps chromium
python loyalty/collect.py --limit 12
python loyalty/sheets_sync.py --input loyalty-output/bundle.json
```

The last command validates without connecting to Google. Public scraping needs outbound network access. It never activates offers, signs in or bypasses access challenges. Cookies and session state are not saved.

The workflow runs the diagnostic on pushes to its development branch. After merging, manual runs are available. Weekly Monday 05:23 UTC collection is **disabled unless** repository variable `LOYALTY_SCHEDULE_ENABLED` is `true`. The current sample limit does not constitute a full periodic catalog refresh.

## Automatic Google Sheets upload

A separate job uploads after successful collection only when all gates hold: trusted `main`, schedule or explicit manual `publish=true`, and `LOYALTY_SHEETS_SYNC=true`.

It creates/upserts just two tabs in the configured **existing** spreadsheet:

- `parser_inbox`: stable ID, source, page title, direct offer URL, raw page text, review status, observation time, text hash, run ID. Column J is reserved for manual comments and never overwritten by updates.
- `parser_runs`: source-level counts, sample-coverage declaration and collection failures.

The existing curated loyalty sheet, source audit and other tabs are not read or written by the publisher. This is automatic delivery into the spreadsheet, **not automatic promotion into the curated benefit database**. Promotion needs source-specific parsers and matching checks, not guesses based on a whole page.

Writes use `stringValue`, never executable formulas from websites. Stable IDs prevent duplicate retries; vanished records remain. Unexpected schemas, duplicate IDs and readback mismatches fail closed. Read-after-write verifies each publication. Workflow concurrency prevents simultaneous jobs in this workflow; it cannot make Google Sheets transactions atomic against an unrelated editor. Avoid editing the automatically managed A:I columns; use J for manual notes.

## One-time Google authorization (not provisioned by this code)

The ChatGPT Google Drive connection is not exported to GitHub. Use Workload Identity Federation **through a dedicated service account**, not a personal OAuth token or a long-lived JSON key.

1. Choose a Google Cloud project under your control. Enable the Sheets API, IAM API, IAM Service Account Credentials API and Security Token Service API.
2. Create a dedicated service account, with no broad Google Cloud project role. Share only the target spreadsheet with that account as **Editor**. Do not enable public editing for this purpose. Google Sheets OAuth scopes cannot restrict access to individual tabs; the two-tab restriction is enforced by this program. Protected ranges or a separate intake spreadsheet provide additional isolation.
3. Set up a Workload Identity Pool/provider for `https://token.actions.githubusercontent.com`. Map the repository and owner numeric IDs. Restrict admission to your exact repository ID and owner ID, `refs/heads/main`, the exact `loyalty.yml` workflow and events `schedule` or `workflow_dispatch`; do not trust all repositories/forks or pull-request events. Grant `roles/iam.workloadIdentityUser` on this service account only to the matching repository principal set.
4. Set repository variables `GOOGLE_WORKLOAD_IDENTITY_PROVIDER` (full provider resource name) and `GOOGLE_SERVICE_ACCOUNT` (service-account email). Set secret `DISCOUNTS_SPREADSHEET_ID` to the target spreadsheet ID. No credential belongs in a commit, artifact or chat message.
5. Merge/review the code, set `LOYALTY_SHEETS_SYNC=true`, run the workflow manually on `main` with `publish=true`, and verify the publisher job plus the actual two new tabs. A successful scrape or skipped publisher does **not** prove Google authorization or upload.
6. Only after that end-to-end verification, enable the schedule variable when periodic **sample diagnostics** are useful. Full-catalog adapters remain separate work.

References:
- https://github.com/google-github-actions/auth
- https://cloud.google.com/iam/docs/workload-identity-federation-with-deployment-pipelines
- https://developers.google.com/workspace/sheets/api/scopes
- https://developers.google.com/workspace/sheets/api/guides/batchupdate
- https://playwright.dev/python/docs/ci

## Acceptance boundaries

Local unit/in-memory HTTP tests cover stable identity, literal writes, idempotence, manual-note preservation, no primary-sheet writes and readback failure. They are not a live Google authorization test or proof of complete catalog parsing. Inspect the concrete Actions run artifacts for site-specific results before widening limits or enabling publication. The existing KEY workflow and snapshots are unchanged.
