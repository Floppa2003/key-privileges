# Regular collection and publication

## User objective, clarified 2026-09-15

Maximize useful, current extraction from the originally requested sources, with a recurring job controlled from GitHub. The execution engine is an implementation choice: Actions, a user-authorized external worker or an external reader can be used when it demonstrably improves coverage. A passing test suite, a diagnostic artifact or additional supplementary URLs is not itself an increase in original-source coverage. Do not substitute fixed answers, old page captures or unrelated sources for fresh extraction.

The user-facing outcome is a current Google Sheets knowledge base: the user asks ChatGPT from a phone about a merchant, and the answer is grounded in the actual destination rows, applicable conditions and source freshness. GitHub orchestrates updates; the user should not have to run a scraper for each question. Absence of a match is not proof of no discount when relevant sources failed or are incomplete.

## Daily operation

The existing `loyalty.yml` now schedules the full registered collection daily at **05:23 UTC** (`23 5 * * *`). Recurring operation was explicitly authorized by the user on 2026-09-15. The old `LOYALTY_SCHEDULE_ENABLED` opt-in condition is no longer used. Scheduled collection is restricted to `Floppa2003/key-privileges`; GitHub schedules use the default branch. Disable the workflow in GitHub Actions to pause it.

The currently released public collection remains credential-free. The separate publisher still requires trusted `main`, successful collection and `LOYALTY_SHEETS_SYNC=true`; it uses the already configured short-lived Google WIF credentials. No Google permissions or long-lived keys are added. It upserts `parser_offers` and `parser_coverage`, then recomputes the common normalized views. Both stages verify destination readback. Private source tabs, corporate codes and manual comments are not exported as public artifacts.

Partial source failures must remain explicit and must not prevent usable records from other sources being retained. Missing records are not silently deleted or given a fresh observation time. Original catalogues, supplementary rules, announcements and partial previews must be distinguished when reporting coverage. Published source text is not a claim that every condition or the user's eligibility has been established.

GitHub's schedule is best-effort: a future cron run is not certified by a manual test. Verify the actual run, source coverage and publication result. No repository/server purchase or paid external service is authorized by this configuration.

## Authorized account sources — scope extension, not a deployed adapter

On 2026-09-15 the user explicitly permitted using their own accounts, including creating/activating a CoralBonus account, to increase original-source coverage. Anonymous-only access is no longer a project-wide product constraint. Use the ordinary account flow and only the user's authorized access; account IDs are identifiers, not substitutes for a valid session. New paid commitments, purchases, bonus spending and coupon redemption are not implied by authorization to read discounts.

CoralBonus's published registration form requires personal/contact information and SMS confirmation; the success state identifies an activated card. The program rules state participation is free and permit online registration, with SMS activation (sections 1.2, 2.1, 2.3, 2.6); club access requires an authorized participant with an activated card (11.1–11.2). Some partner descriptions are publicly readable while the coupon action requires login. Thus public-description access, authenticated entitlement and coupon issuance are different capabilities.

Evidence inspected 2026-09-15 (website content, not a successful authenticated run):
- https://coralbonus.ru/pravila-programmy/
- https://coralbonus.ru/klub-privilegii/
- https://coralbonus.ru/klub-privilegii/podarki/flowwow/

No account was created, SMS requested, authenticated session obtained or account-scoped catalogue published as part of this documentation update. Exact session storage, lifetime, renewal behavior and whether account login affects the earlier network refusals are unverified. Registration and a reusable session are prerequisites for testing those questions; do not invent cookie names, tokens, API endpoints or account IDs.

Authenticated collection must not be added blindly to the public artifact path. Keep account sessions and private results out of repository files, logs, traces, caches and public artifacts. Supply secrets through an appropriate protected store, scoped to the reviewed trusted job; secret masking is not a replacement for avoiding sensitive output. Verify the destination's actual sharing scope before writing account-only data and preserve private provenance in downstream normalization. Do not widen Google access or expose original private sheets to a crawler.

The account worker must return useful offers and eligibility/redemption requirements to the same user-authorized Sheets destination, with observation time and explicit source status. Do not copy authentication material into the spreadsheet. Separate reading existing codes from requesting issuance: a button can trigger email, expiry, limits or a charge. Do not mass-issue codes or spend bonuses during a catalogue refresh. An expired/revoked session must be reported as requiring reconnection, while other sources continue and historical rows keep their original timestamps. A reusable session may still require a later human SMS confirmation; do not promise perpetual unattended authentication before testing it.

Acceptance for an authenticated source remains end-to-end: valid ordinary sign-in, real fresh catalogue/conditions, a second scheduled-style read without a new interactive sign-in where supported, safe handling of expired authentication, successful destination publication and independent readback. If host/network access fails before authentication, diagnose that separately rather than assuming an account ID fixes it.

## Manual operation

Update `loyalty/request.json` with a unique request ID on `main` to dispatch the same `loyalty.yml` with `limit=500` and `publish=true`. The request file is a trigger and audit marker; its contents are not executed or passed as shell arguments. `loyalty-request.yml` has repository content-read and Actions-write permissions, checks the trusted repository and configuration, then uses its ephemeral GitHub token. Dispatch acceptance is not publication success.

The current Google project and Workload Identity provider are existing shared infrastructure, not resources to recreate. A dedicated service account targets this spreadsheet. The IAM subject binding selects this repository's `main` branch rather than an individual workflow; keep credential-bearing work in the existing reviewed publisher.

## Current coverage limits

The released Utair support adapter remains active. EKP PR23 is an unmerged candidate whose live checks failed before catalogue parsing. EKP, Nordwind, Coral club/promo, RZD and Aeroflot primary catalogues must not be marked restored merely because their test fixtures, alternative announcements or partner rules were read. Test a materially different retrieval path before repeating an unchanged failing probe.
