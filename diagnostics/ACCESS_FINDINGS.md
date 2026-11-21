# Public-source access investigation — 2026-09-14

## Scope and state

This is a bounded access investigation requested by the user, NOT a release of a new production adapter. Main baseline is `0191423147c5fa577bd0254ae1509e3f8d1e8c2b` (scraper 2.7.0). All code changes are isolated to this diagnostic branch. No Google credentials, spreadsheet reads/writes, private memberships, purchases, proxies, paid services, personal sessions, CAPTCHA solvers or disabled TLS verification were used. No production source/workflow/schedule was changed.

The pass tests Linux x86 and ARM, Windows, ordinary Chromium/Firefox/WebKit contexts, default versus TLS1.2/HTTP1.1, canonical public hosts, publicly served HTTP content and official missing CA trust. Target requests are separated from crawler robots prechecks for this finite diagnosis. HTTP200 alone is not accepted as useful content. Browser/transport metadata and source identities are retained.

## Findings

| Source | New evidence | Conclusion |
|---|---|---|
| Loyals | HTTP homepage succeeds on both initial Linux runners and all three confirmation runners; the advertised WordPress REST API returns real unprotected published post objects. A final two-page traversal returned all89 posts reported by X-WP-Total and X-WP-TotalPages, including every80 homepage native ID. | A working public structured access route exists from ordinary GitHub runners. HTTPS remains invalid. HTTP lacks encryption and authenticated source integrity; do not label this HTTPS-verified data. |
| CoralBonus club, promo and MEDSI card | First Windows runner returned HTTP200 and real catalogue/promo HTML plus the exact MEDSI conditions. Its curl TLS1.2 club read also returned real content. Two new Windows runners and the Linux confirmation runner returned403 for the same root/card, another card, a category and a promo detail. | Direct GitHub access is possible but intermittent in this sample. Windows alone is NOT a stable fix. Network allocation, server policy and time are not isolated enough to name the root cause. |
| VTB exact Aeroflot debit-card page | On the first trust-test runner, default Requests certificate verification failed; the same exact request with official national-CA trust returned200 and the correct product page. A second runner timed out both with and without the added CA. | Missing trust can be fixed without disabling verification; separate network instability remains. One successful page is not a proven permanently stable catalogue. |
| NSPK exact EKP article | Default Requests failed issuer verification; adding official CA trust returned200 and the correct article in both independent trust runs. | Reproducible correction of missing trust for this exact page. |
| Uralsib exact RZD promotion page | Default trust failed. Official CA trust established valid TLS but first response was302 to the same exact URL. Preserving one ordinary anonymous Requests session and following that bounded same-host redirect returned200 with the real promotion, reproduced on two runners. | Correct CA plus ordinary session-preserving redirect handling solves this exact page. Its own offer period is September2023–March2024, not a current2026 promotion. No account login was performed; ephemeral session cookies were not exported. |
| EKP and Nordwind | DNS resolves but TCP443 connection times out on all three initial environments. Linux default/TLS1.2, HTTP80, headed Chromium, Firefox and WebKit did not yield catalogue data or EKP API objects. | No new working direct route established in this pass. Earlier external Moscow HTTP-header observations are not a full browser proof. No platform-wide impossibility claim follows. |
| RZD primary site | Verified connection/TLS but target403, including alternate canonical hostname and Linux browser engines. | No successful direct workaround established. |
| Aeroflot primary catalogue | HTTP200 with explicit owner-restriction text rather than the catalogue, across tested transports/browser engines. | Not a source-data success. No successful direct workaround established. |
| Old Utair support page | Target401, including tested canonical form; ordinary browser engines do not produce the article. | Old page remains inaccessible. Existing official media/PDF alternatives are separate source evidence. |

VTB, NSPK and Uralsib are additional previously failed public-reference pages, not three of the eight primary catalogue routes. Do not inflate the count of repaired primary catalogues.

## Loyals: completeness and semantic limits

The homepage advertises `https://loyals.ru/wp-json/`; the same public API is served over HTTP. No private API method, login or password parameter was used. The exact collection request is `http://loyals.ru/wp-json/wp/v2/posts?per_page=50&page=1&orderby=id&order=asc&_fields=id,date_gmt,modified_gmt,link,title,content,excerpt,status,type,slug,categories,tags`, followed by page2. Totals were stable:89 posts, two pages (50+39). IDs were unique; all records had `status=publish`, `type=post`, `content.protected=false`.

All80 IDs linked from the homepage occur in the API; nine additional published posts are not linked there. Two posts (4671 and5076) have no body text. They are preserved as source observations with an explicit warning, NOT promoted into offers. There are87 nonempty bodies and86 posts containing recognized discount-rate evidence. This is NOT89 verified current discounts.

Source modification timestamps range from2021-03-24 to2025-08-12. Source publication/modification dates are distinct from this observation's2026 timestamp and are not offer expiry or current eligibility. Prototype records preserve raw public fields, exact API URLs, canonical publisher URLs, text, numeric evidence and HTTP-trust warnings. They are diagnostic projections, not registered production schema-v2 records and not a new Google Sheets publication.

The two tested numeric-post browser links redirect from HTTP to invalid HTTPS. Reading the advertised public API avoids that particular redirect, not certificate validation. Prefer restoring valid HTTPS for authoritative ongoing ingestion. Any optional HTTP ingestion must be explicitly opt-in, anonymous and marked transport-unverified, with independent revalidation before using a discount.

## Official CA experiment

Official primary guidance: https://www.vtb.ru/crt/ . Certificates downloaded over already-verified HTTPS from official distribution endpoints:

- https://gu-st.ru/content/lending/russian_trusted_root_ca_pem.crt — file SHA256 `936a43fea6e8e525bcc0f81acd9c3d21b4fc4b9b68acea7906d698005afc6504`.
- https://gu-st.ru/content/lending/russian_trusted_sub_ca_pem.crt — file SHA256 `f0ae589f36774f29ef3648f7984b08d42fcce6f1ffeeb6236d773daeb2744ea6`.

They were appended to a temporary certifi bundle for exact allowlisted Requests reads, NOT installed into OS-wide trust. Hostname, signature/chain and validity-date verification stayed enabled. This is an explicit additional trust decision, not a reason to use verify=False. Loyals still fails as expired with this bundle; its failure is not a missing national root. The narrower Uralsib redirect experiment pinned the downloaded root file digest and refused any change of scheme, host, path or query.

Public API documentation used to check discovery and pagination: https://developer.wordpress.org/rest-api/reference/posts/ and https://developer.wordpress.org/rest-api/using-the-rest-api/pagination/ . No external article is treated as proof of a successful GitHub read.

## Runs, failures and independent evidence

1. Access matrix run `34844378610`, baseline experiment commit `b99df61b6de4eee924e8aba6e92ff312af576a45`: Linux x86 and ARM jobs succeeded. Windows job failed AFTER successful Coral HTML reads because subprocess text decoding used the platform codepage and hit a UnicodeDecodeError, then a metadata TypeError. Its completed HTML files and cURL HTTP statuses remain evidence; no complete Windows transport report is claimed. This is a diagnostic harness bug, not a site failure.
2. Initial CA run `34844706595`: completed, VTB and NSPK content obtained; Uralsib302 and Loyals expiry explicitly preserved.
3. Independent confirmations run `34845322769`, commit `e9683962c019dd517879d91832cf631d52b51482`: both Windows jobs and Linux job completed. Explicit UTF8/error handling fixed the metadata failure. System cURL, Git cURL, Requests and Chromium were compared on the same Windows machines: all returned403 on Coral there. Both Windows cURL variants use Schannel; a TLS-fingerprint explanation has NOT been isolated. Linux repeated the CA test: NSPK succeeded, VTB timed out, Uralsib302.
4. First structured run `34845951626`: Uralsib returned302 then real200. Loyals collection encountered a published empty-body post and the prototype aborted its own projection. This result is not complete Loyals collection, despite successful workflow exit.
5. Corrected structured run `34846378668`, commit `a8813f177becc47eb4198f41bf29a7e89e7e862e`: all89 public API posts retained with the two empty-body warnings; all80 homepage IDs accounted for. Uralsib again302 then200. Empty/nonempty/protected fixtures and count/evidence/trust-boundary assertions passed.

Independent local readback checked nine downloaded artifact ZIPs against GitHub's SHA256, all ZIP member CRCs, eight execution-code digests against recovered scripts, all89 unique published IDs and raw protection flags, every80 homepage ID, the two empty observations, every numeric evidence substring and HTTP warnings. Seven recovered script files compiled. These are diagnostic checks; the production409-test suite was not rerun or represented as newly passing in this pass.

| Artifact ID | Run | SHA256 |
|---|---|---|
|10347930389|34844378610|86ecdd067b0596f2f307578d94f041e3ce87eb26779f59e9142eeb7dcc2b24d9|
|10347347319|34844378610|bebfcbb0826cdcca12667a4329e22b158b340ec6466fa925f3554ccf8c63f963|
|10348210692|34844378610|906b9d5a640aa0a266afcce5bd58b7716c5b83fafd98d33da67dce62ca3e9cc2|
|10348195382|34844706595|7b844b1be4363c16ed2a355fbe4dbea1a740237b7df9f803bf9aba0dc1d3063d|
|10348260864|34845322769|afa183fc0e252905d799edd203740c02fa4da698803ae3ef94d568b8d9acf036|
|10347808461|34845322769|c21ee5bc5a4a0b627f04ca0c74d5a34ff08abe63fc69bb555825de4a7f1be9eb|
|10348231913|34845322769|a39881f5efa230a9a084cd4569914ced5aacd7a283826bfa4961c98d4350ea40|
|10347238513|34845951626|e5f4516f700192e6600c29bf009f7421f58cbf3cff4088a320cb133dd4f029e9|
|10347734836|34846378668|2567d80a8e274c95a7396bdc6ed9e9dfd3a1eac77bb2257a5c92f2a280b77288|

## Engineering disposition

- Implement narrow explicit trust-bundle support for eligible VTB/NSPK/Uralsib reads, preserving exact host bounds, verified TLS and source status.
- Loyals has a confirmed structured read path. Do not silently change production to HTTP or claim its historical posts are current; make the integrity tradeoff explicit in any subsequent integration.
- Do not switch all production jobs to Windows based on one Coral success. A bounded optional source-specific runner fallback may recover some observations, but reliable coverage still needs controlled egress/permission or another demonstrated public route.
- Further tests for EKP/Nordwind/RZD/Aeroflot need a new controlled network or an actually discovered public endpoint; this matrix gives no evidence that another User-Agent, TLS version or robots toggle will fix them.

The diagnostic workflows run only for explicit changes on this branch and have no schedule. This report is evidence for decisions, not a claim that the production parser or spreadsheet has been upgraded. No new private source is part of the scope.
