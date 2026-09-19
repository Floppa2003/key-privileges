# Konsierge public catalogue replaces the Only Assist investigation target

## Owner-approved decision — 19 September 2026

The owner requested: «Давай если konsierge.com/benefits персить легче чем Only Assist то на него перейдем». They previously reported substantial overlap with their Only Assist app.

**Prefer https://konsierge.com/benefits for concierge-privilege collection. Pause further Only Assist APK, login and app-endpoint investigation.** Public collection does not depend on proving equality with a private customer catalogue. Preserve programme/source identity as **Konsierge — публичные привилегии**, not verified personal Alfa Only eligibility. Existing bank, GreatList, TSUM, PDF and announcement sources are separate and unchanged. No app catalogue had been released; there is no app-derived record set or routine app scraper to delete.

This is an accepted target/prioritization switch, **not a claim that a complete recurring Konsierge collector has been enabled**. This investigation changed no production parser, source registry, Google Sheets rows, bank account, plugin permission or recurring schedule. All temporary diagnostics are removed before merging these notes.

## Actual public page and API evidence

| Check | Actual result and boundary |
|---|---|
| Existing PublicSource browser/robots gate, run35461293538, commit78aa55fa37ab486d8771ff462758beb2f060081f | Main-origin robots retrieval timed out, including ordinary browser fallback. No card read occurred in that run. A green diagnostic workflow is not successful collection. |
| One-off exact public page GET, run35461545295, commit552ee1e3eac0b0c37d3d1a5b0e12e30dda39fcdd | **HTTP200**, 23730 bytes, observed2026-09-19T18:33:02.401480+00:00. Raw SHA256 `2c30934a7876e22f4c199950757d5351b7caf1131b37f40410e0d90d4c72a457`. HEAD robots timed out separately. This diagnostic did not override production policy. |
| Independent local extraction of the saved sanitized DOM | **12 distinct named first-screen cards**: 8 discount labels and 4 unspecified «Привилегия» labels. No per-card detailed conditions/redemption were present in that captured markup; pagination was not exhausted. |
| First-party benefits-host policy, run35461803612 | `https://benefits.konsierge.com/robots.txt` returned200 with a comment-only body, no disallow directives. The separate news host returned404. This does not establish main-origin robots availability. |
| Native API discovery, run35462323951 | Observed site chunk2 exposes GET `/api/client/v1/benefits`, `/api/client/v1/rubrics` and a storefront tariff filter. The public client also supplies its own authorization header; its credential values are not retained or replayed. |
| One exact anonymous native-API GET, run35462404308, commit094c5f35d57b73679f1bd04b26c7b6e9344df266 | `https://benefits.konsierge.com/api/client/v1/benefits` returned **401** at the observation2026-09-19T18:49:15.182887+00:00, after a fresh200/empty-policy robots read. No credentials, cookies or retry after authorization failure. No catalogue JSON read. |

The twelve first-screen records, in source order, were: GMS(Смоленская)10%; GMS(Садовническая)10%; GMS Hospital10%; Lotte(Петербург)unspecified; Stella di Mosca(Москва)unspecified; Гранд Отель Европа(Петербург)unspecified; GMS Dental10%; Dropp Market7%; Amnesia up to10%; Muza up to10%; Leto Flowers up to10%; Magritte unspecified. These are observed labels, not independently checked customer entitlements or full merchant terms.

Reusable DOM: `qy-benefits-page`, `.benefitTeasersList`, `qy-benefit-teaser.BenefitTeaser`, `.BenefitTeaser-Title`, `.BenefitTeaser-Rubric`, `.BenefitTeaser-OfferText`. The image paths contain identifiers2615,2616,2617,2047,1835,1838,2618,2442,1842,1843,1844,2601 respectively. Treat these as source-image identities until API/detail correspondence is checked. Empty card hrefs are not valid detail links. The loader/infinite-scroll component and frontend `per=12` prove that a first-screen result is not evidence of catalogue completeness.

Observed public static assets: runtime.a77998f0e7d2a878d619.js; common.92bdba30978f407e2edb.js;1.d19ac291fe76ecbf05cf.js;2.79fd00a7f40471181929.js;4.a36972f331f4cbd99082.js;8.452035ef1e371fa0e22e.js on konsierge.com. The runtime maps chunk0 to **common**, not a numeric filename: initial numeric0 requests were a diagnostic path-resolution mistake, not proof that the actual shared chunk is inaccessible. The corrected native common URL returned200. The domain/path evidence is enough; do not re-download every bundle or inspect the app again.

## Persistent verification references and sanitation

Saved page artifact10589729822 has ZIP SHA256 `6b994d6f3dda8924d63695a5d4c86a455e7fb76b2f91c40efd56bca2b092bc37`; its digest and extracted card identities were independently checked. Anonymous API artifact10590161401 has ZIP SHA256 `783b0d671fa816ffb10181d7ea6996be284fc84691881add5a8a06ba91f8e2ee`, also independently checked. Actual request time does not establish the age of any upstream cache.

One early static-code excerpt artifact inadvertently retained public frontend client-configuration constants. No value was used to authenticate a request. That diagnostic artifact10588829639 and the local downloaded copy/excerpts were removed; cleanup35461803612 verified deletion with a404 readback, and a separate connector artifact-list read confirmed the old run had no artifacts. Subsequent diagnostics retained only vetted paths and redacted method structure. No private customer/account/session material was collected. Do not publish or reuse vendor client constants.

## Remaining acceptance work, now on the website rather than the app

Find a supported ordinary public-page/browser/reader route that preserves names, native pagination and any actual public detail blocks without extracting/replaying client credentials. Main-origin robots failure remains distinct from the API's401. Do not weaken global TLS, authentication or robots handling to silence either observation. The public website being usable is not proof an anonymous direct API is usable.

Before enabling routine collection, compare actual visible inventory against parsed rows, preserve missing terms as unknown, test IDs/duplicates/partial loads and literal qualifiers, then use the existing serialized publication and verify the real destination. Do not report twelve previews as a complete catalogue, inflate «Привилегия» into a numerical discount, or merge bank/app conditions onto public records. Until that acceptance, PR72 remains the last completed data publication.
