# Public-source coverage and reliability — verified implementation, 22 September 2026

This release improves the three owner-approved PR78 sources, not every older programme. Preserve the cleaned-reader policy and the existing daily publication queue. Deployment and destination readback are recorded separately after the main publisher completes.

## Source evidence and resolved gaps

Initial baseline: main `7ba7e55ea64831b32d993bbdaa717033bd0a2ea3`; private destination independently read as 3007 parser / 3655 common / 3041 cleaned records. Before-export and native UI reads were captured locally. No private workbook is committed or attached.

Public probe **35746778105** collected thirteen Backit promotion panels, Avolta HTTP/browser pages and marketplace/access boundaries. Artifact10703625501 SHA256 `478a64f1f1a84ff29045cf45c4a4c5fcb3db588705063aec224418b4e598387c`. Public gap probe **35748655315** succeeded; artifact10704182893 SHA256 `5b22076445a2542deef2eb724cf6ad586c6139a3452b5bc139688226c7b7cf9d`. ZIP digests and CRCs were verified independently.

**Backit:** ten of the previously withheld thirteen promotional periods are already over. Three periods cover the observation date: Все Инструменты, Xcom-Shop, Плати по всему миру. Dates are read from the owned promotion panel; DD.MM dates are accepted only with the matching current month/year in the page title. The year is explicitly an inference, labelled `promotion_year_inferred_from_current_page_month` and exposed in the reader. It is not a source-written year or a guarantee that a website never retains stale promotional copy. Cross-year ambiguity, invalid dates, future and expired periods are withheld. Crossed-out base rates are never silently revived. Fixed RUB amounts, scopes, zero-rate exclusions, coupons and customer restrictions remain distinct.

**Backit marketplace boundary:** the public routes `/ru/cashback/shops/compilation/shopsozon`, `/ru/cashback/shops/compilation/shopswb` and `/ru/cashback/shops/mixit-ozon` returned302 to the general catalogue on22September. The Roborock-Ozon page returned200 but explicitly said cashback was temporarily unavailable despite retaining a rate table. No historical search cache is promoted to a current marketplace offer. Product-level marketplace coverage remains unavailable through these tested routes, not silently complete.

**Avolta:** ordinary same-origin HTTP returned the full public root in two independent diagnostics. The collector now uses ordinary HTTP for root, six categories and details instead of a source-local headed browser. It still uses the shared bounded transport: no proxy/credential/header rotation, access-refusal bypass or weakening of TLS. Existing transient-network/502/503/504 retries remain bounded;401/403/challenge responses are not endlessly retried. A successful full HTTP traversal follows below; long-term uptime is not proved by one successful traversal.

The exact DragonPass page consistently states an independent restaurant discount up to25%, while conflicting about lounge entry31USD versus28USD. Only the restaurant component is retained, explicitly partial; neither entry price is published as a benefit. Restaurant redemption is unknown. The app instruction on this page concerns lounge entry, and is not repurposed as restaurant activation. This is a source-component separation, not reconciliation of the contradictory prices.

**Mantera:** the public group landing says six partners but does not expose a named complete inventory; `/app/partners` redirects to sign-in and was not followed. The independent public hotel page `https://manteracongress.ru/loyalty-program` explicitly names Mantera Resort & Congress. One hotel-participation record is added to the five existing FAQ tiers. Hotel earning rates and annual-spend scopes come from its five-row table. General redemption caps remain conditions, not a promise that this particular hotel supports spending: the page says some objects only earn, others also redeem. Pre-registration, no-cash withdrawal, exclusions and the pilot boundary remain. The new6 records are five tiers plus one hotel, not six hotels or full programme participation.

## Operational contracts

`source_lifecycle.py` records an exact URL inventory and named exclusions for Backit/Avolta. Reconciliation is enabled only when a successful same-time snapshot accounts for every unique URL as accepted or explicitly excluded. An empty, malformed, partial or failed read is not disappearance evidence.

A previously stored offer explicitly disabled/excluded, or missing from that complete inventory, receives reversible `_lifecycle` metadata. No original row is deleted, shifted or cleared. Original source text, offer observation time and source payload digest remain unchanged; `checked_at` and the reconciliation run are separate operational evidence. The original `content_sha256` continues to identify the source observation before operational metadata; the common normalizer's input hash covers the actual stored cells including the lifecycle state. Fresh accepted evidence replaces that state and restores the card. Older incoming observations cannot overwrite newer offers or holds. Managed-column compare-before-write and trailing manual-column preservation remain.

A separate **7-calendar-day reader freshness limit** applies only to Backit, Club Avolta and Mantera parser records. It is an internal observation-age policy, not a source expiration date or proof of current applicability. The reader excludes held/over-age observations while retaining technical evidence. The native search formula adds the same source/origin-scoped TODAY predicate; unchanged search/programme/category inputs remain. The only native UI edits are A10's guarded formula and C6's explanatory note. Existing eight original formulas and other programme behavior are outside the edit. Native formula checks are idempotent and reject a concurrent edit. TODAY is evaluated when Sheets recalculates; global recalculation settings and timezone were not changed, and an exact unattended midnight refresh is not claimed.

The existing `loyalty.yml` gains a read-only **source-health** job using the exact collected artifact. It fails when a selected new source is unhealthy, even if other sources have records. The existing publisher still depends on the collector, not the health job: healthy-source publication is not suppressed by another source's failure. The daily05:23UTC schedule and serialized publication are unchanged. No extra recurring workflow, ChatGPT task, paid provider, source account, purchase or activation is added.

## Verification

Feature **35753691428**:
- offline job106834006523 verified every old/new file and patch digest, passed **1206 Python +7 KEY tests**, committed only reviewed Python paths to the feature branch, and read back the normal fast-forward push;
- exact resulting implementation commit **57bb63297a9992529fe3d7fa5b4489bfdd4d458b** was independently fetched through the connected GitHub app;
- read-only collector job106834395791 freshly accepted **201 records =178 Backit +17 Avolta +6 Mantera**, observed **2026-09-22T16:24:09.414863+00:00**, zero source errors;
- Backit reconciled **916 listings /23pages /189 eligible details**:178 accepted and738 exclusions (677 disabled,50 acquisition ads,10 expired promotions,1 returned catalogue); Avolta17/17 public cards in6categories; Mantera5tiers+1hotel;
- every record passed source validation, common normalization and the clean-reader projection;
- public artifact **10705909673**, SHA256 `a1a4c959c609a401b9bf5c6928b35bd52f28006f39a880e0ce078159f0e39742`; normalized.json SHA256 `4dedc420b076194e3888f20861b270f25d211c9ec827424c196a2f650f58644b`.

Final **35755005927**, exact commit **ec63a34a709bd51eb0dd979d86233828d5ced050**, job106838436860, completed successfully after the restaurant-activation correction:
- **1206 Python tests in46.725s +7 KEY tests, no skips**;
- actual-evidence replay preserved200 records byte-for-byte and changed only DragonPass's redemption_text to empty plus its content hash;
- all201 corrected records still passed inventory health, common normalization and reader projection;
- this replay is not a fresh crawl and was not published as one;
- artifact **10706849881**, SHA256 `c29cd691f87132c3a89ced9eb743c0f78c8f9a0f8ae5f9b510f2b854ea2f76b8`; ZIP/CRC and all25 reviewed file bytes independently matched the local implementation.

The tests cover actual row upsert→hold→normalization→reader→restore with a preserved manual note; partial/failed reads; invalid/empty/duplicate inventories; older snapshots; dates and year context; source-scoped freshness; guarded native UI writes; exact hotel identity and rates; a failed hotel fetch retaining five FAQ records; and component-specific DragonPass ambiguity. The local shadow replay against the genuine3007-row workbook found201 upserts, five new IDs and zero current holds. Synthetic lifecycle transitions are tests, not claimed changes to real user offers.

Temporary probes, installation patch/manifest and verification workflow are removed before merge. Only documentation and removal of temporary files follow final accepted production bytes. After merge, run the existing selected-source main publisher, inspect each source-health outcome, and independently read the destination after the last write. Do not call this pre-publication report evidence that the live Sheet has already changed.
