# Regular collection and publication

## Current checkpoint — 2026-09-15, after PR30

**Read `COVERAGE_CURRENT.md` first for current source status, verified publication and exact next acceptance gates.** It supersedes the pre-Coral counts and diagnostic-only conclusions in the historical Nordwind checkpoint below. PR29/30 are merged: final run35025789983 published61 fresh records (7 Nordwind,31 Coral club,23 Coral promo), adding54 Coral records this continuation. Native final readback verified1066 retained public parser records and1714 total inputs. The other Coral category half and one promo remain incomplete.

EKP's separate latest catalogue-only experiment35028374541 saved240 real cards after actual UI growth, but no detailed conditions or Sheet publication. RZD remains unreadable; the alternate Aeroflot policy disallows the requested root. The two regular schedules remain05:23 and06:03 UTC. The combined daily Free reservation bound is now290 credits; unscheduled diagnostics are additional Free usage, not paid services. See `FREE_ACCESS.md` and `COVERAGE_CURRENT.md` for costs, evidence and limits.

## User objective, clarified 2026-09-15

Maximize useful, current extraction from the originally requested sources, with a recurring job controlled from GitHub. The execution engine is an implementation choice: Actions, a user-authorized external worker or an external reader can be used when it demonstrably improves coverage. A passing test suite, a diagnostic artifact or additional supplementary URLs is not itself an increase in original-source coverage. Do not substitute fixed answers, old page captures or unrelated sources for fresh extraction.

The user-facing outcome is a current Google Sheets knowledge base: the user asks ChatGPT from a phone about a merchant, and the answer is grounded in the actual destination rows, applicable conditions and source freshness. GitHub orchestrates updates; the user should not have to run a scraper for each question. Absence of a match is not proof of no discount when relevant sources failed or are incomplete.

## Daily operation

The existing `loyalty.yml` now schedules the full registered collection daily at **05:23 UTC** (`23 5 * * *`). Recurring operation was explicitly authorized by the user on 2026-09-15. The old `LOYALTY_SCHEDULE_ENABLED` opt-in condition is no longer used. Scheduled collection is restricted to `Floppa2003/key-privileges`; GitHub schedules use the default branch. Disable the workflow in GitHub Actions to pause it.

The original direct public collection remains credential-free. The additional Free API path described below uses only its protected provider key, not source-account sessions. The separate publisher still requires trusted `main`, successful collection and `LOYALTY_SHEETS_SYNC=true`; it uses the already configured short-lived Google WIF credentials. No Google permissions or long-lived keys are added. It upserts `parser_offers` and `parser_coverage`, then recomputes the common normalized views. Both stages verify destination readback. Private source tabs, corporate codes and manual comments are not exported as public artifacts.

Partial source failures must remain explicit and must not prevent usable records from other sources being retained. Missing records are not silently deleted or given a fresh observation time. Original catalogues, supplementary rules, announcements and partial previews must be distinguished when reporting coverage. Published source text is not a claim that every condition or the user's eligibility has been established.

GitHub's schedule is best-effort: a future cron run is not certified by a manual test. Verify the actual run, source coverage and publication result. The user explicitly prohibits rental/subscription payments, server administration and an always-on laptop. Free API accounts are allowed; no repository/server purchase or paid external service is authorized.

## Authorized account sources — scope extension, not a deployed adapter

On 2026-09-15 the user explicitly permitted using their own accounts, including creating/activating a CoralBonus account, to increase original-source coverage. Anonymous-only access is no longer a project-wide product constraint. Use the ordinary account flow and only the user's authorized access; account IDs are identifiers, not substitutes for a valid session. New paid commitments, purchases, bonus spending and coupon redemption are not implied by authorization to read discounts.

CoralBonus's published registration form requires personal/contact information and SMS confirmation; the success state identifies an activated card. The program rules state participation is free and permit online registration, with SMS activation (sections 1.2, 2.1, 2.3, 2.6); club access requires an authorized participant with an activated card (11.1–11.2). Some partner descriptions are publicly readable while the coupon action requires login. Thus public-description access, authenticated entitlement and coupon issuance are different capabilities.

Evidence inspected 2026-09-15 (website content, not a successful authenticated run):
- https://coralbonus.ru/pravila-programmy/
- https://coralbonus.ru/klub-privilegii/
- https://coralbonus.ru/klub-privilegii/podarki/flowwow/

The user subsequently completed CoralBonus registration. No authenticated session was obtained or account-scoped catalogue published in this continuation. Exact session storage, lifetime, renewal behavior and whether account login affects the earlier network refusals are unverified. Do not ask for registration again or invent cookie names, tokens, API endpoints or account IDs.

Authenticated collection must not be added blindly to the public artifact path. Keep account sessions and private results out of repository files, logs, traces, caches and public artifacts. Supply secrets through an appropriate protected store, scoped to the reviewed trusted job; secret masking is not a replacement for avoiding sensitive output. Verify the destination's actual sharing scope before writing account-only data and preserve private provenance in downstream normalization. Do not widen Google access or expose original private sheets to a crawler.

The account worker must return useful offers and eligibility/redemption requirements to the same user-authorized Sheets destination, with observation time and explicit source status. Do not copy authentication material into the spreadsheet. Separate reading existing codes from requesting issuance: a button can trigger email, expiry, limits or a charge. Do not mass-issue codes or spend bonuses during a catalogue refresh. An expired/revoked session must be reported as requiring reconnection, while other sources continue and historical rows keep their original timestamps. A reusable session may still require a later human SMS confirmation; do not promise perpetual unattended authentication before testing it.

Acceptance for an authenticated source remains end-to-end: valid ordinary sign-in, real fresh catalogue/conditions, a second scheduled-style read without a new interactive sign-in where supported, safe handling of expired authentication, successful destination publication and independent readback. If host/network access fails before authentication, diagnose that separately rather than assuming an account ID fixes it.

## Manual operation

Update `loyalty/request.json` with a unique request ID on `main` to dispatch the same `loyalty.yml` with `limit=500` and `publish=true`. The request file is a trigger and audit marker; its contents are not executed or passed as shell arguments. `loyalty-request.yml` has repository content-read and Actions-write permissions, checks the trusted repository and configuration, then uses its ephemeral GitHub token. Dispatch acceptance is not publication success.

The current Google project and Workload Identity provider are existing shared infrastructure, not resources to recreate. A dedicated service account targets this spreadsheet. The IAM subject binding selects this repository's `main` branch rather than an individual workflow; keep credential-bearing work in the reviewed publisher jobs.

## Coverage interpretation

The released Utair support adapter remains active. Nordwind's seven observed partner-list accordions are mapped and published through the Free API path; this does not claim every page or external partner site in the program. Coral public terms are now partially published through PR29/30. EKP PR23 remains an unmerged candidate, and its newer diagnostics are not a production release. A category/index/preview is not a collected set of detailed benefits. Read `COVERAGE_CURRENT.md` for actual latest scope; test a materially different retrieval path before repeating an unchanged failing probe.

## Historical Nordwind Free API checkpoint — before PR29/30, 2026-09-15

The following paragraphs preserve the earlier Nordwind release evidence. Their retained counts, then-current cost bounds and pre-Coral limits are historical, not the latest state.

The owner added `SCRAPINGANT_API_KEY`; no further owner setup is currently needed for this public route. PR27 adds source-owned Nordwind mapping and the existing two-stage publisher; PR28 repairs a real unreachable-robots case with one separately identified browser read and honors the source HTML base URL. Both are merged.

`loyalty-free-access.yml` runs daily at **06:03 UTC**. It reuses the existing Sheet destination, WIF, validators and bounded writers, sharing the original workflow's concurrency group. It publishes only newly accepted records; failures in other sources remain explicit, and missing source rows keep their original observation time. The original 05:23 UTC collection still runs separately.

Fresh main run **35018777242:1** at commit `c06184abdb92e92e9d51fcec50515d8cf9922db2` completed regression, collection and publication. Its current Nordwind page was read after a real plain-policy failure followed by successful browser-policy loading. All seven on-page cards were independently re-parsed from the saved live DOM. Native destination readback confirmed rows 1007–1013, all six new source reports, the correctly scoped mileage denominators, and the final `verified/current` normalization manifest. There are 1012 retained public parser records, not 1012 newly read records from this run. This was a push-triggered end-to-end test, not observation of a future cron run.

The final full suite passed 561 Python and 7 KEY tests. Public artifact 10416807438 was hash/CRC checked; SHA256 `3c4ff195f39c7624aaad3d67b934c6b0cf85252fe730cbd2c59dcacf3a3302b3`. The sanitized source DOM SHA256 is `cc112ba0024bd93716aa97320efcb7970976189cae7a4325e0591c55d789cfc0`. No previous attempt's capture was republished with a new timestamp.

This final attempt made 10 provider source requests, reserving 55 credits and observing 42 credits in validated successful response headers. Failed-call charges are not included in that sum, so it is not a reconciled account debit. Worst-case code bounds remain 115 reserved credits and 16 requests, with Free-plan/balance checks; see `FREE_ACCESS.md`. No paid plan, billing details, source-account sessions or personal devices were used.

Latest other-source evidence at that historical checkpoint: Coral club 20 category boxes and Coral promo 24 linked headings read successfully but had no accepted detail adapter yet; EKP failed at policy transport (provider 404 then 500), RZD at policy with provider 423, and Aeroflot with unreadable policy content. Those outcomes did not establish impossible access. The next work at that point was fresh discovered Coral category/detail traversal within the Free budget, plus a distinct retrieval test for the three remaining transport failures. A source account remains an optional separate path, not a reason to ask the user to register at Coral again.

The independent readback was targeted to new public rows/reports, normalized mileage terms and the final audit state. The existing publisher runs its own full output/readback and input-fingerprint checks. No additional exhaustive comparison of every private cell or visual format was performed in this continuation. Repeated source phrasings and historical records remain separate evidence, not additive discounts.
