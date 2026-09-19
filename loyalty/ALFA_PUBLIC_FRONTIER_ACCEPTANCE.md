# Alfa public frontier — 19 September 2026

## Scope and release boundary

This continues the owner-approved search for Alfa offers outside restaurants and the Only Assist app route after PR71. It adds **two public sources**, not authenticated bank integration. Publication evidence will be appended after the actual main run and independent destination readback; the pre-release checks below do not claim a Sheet update.

- `alfa_only_tsum`: https://www.tsum.ru/lp/alfa-only/ — **2 merchant-loyalty tier records**.
- `alfa_only_announcements`: https://t.me/s/aaa_only — **18 public announcements** in the tested 180-day window. These are not 18 unique, current, personally usable discounts.
- Both use the existing public collector, validation, serial publication and daily schedule. There is no new recurring workflow, provider account, paid service, server, login, activation or coupon issuance. The temporary probe workflow and installation helper were removed before release.

## Live and regression evidence

Installation/regression run **35442088448:1**, job **105894540284**, passed **1069 Python + 7 KEY tests, no skips**. Its branch-only installation commit was `3e8c603df0b5149dca15d30444e63566fb575855`. The eight routed/config/fixture files were committed only after that regression. No Google or scraping-provider credentials were present.

Actual production-source read **35442309775:1**, job **105895132899**, executed `b81bdff685b163504ac94cf19c4b0f57f634c1ee`, observed **2026-09-19T12:15:15.524250+00:00**:

| Source | Discovered / normalized | Errors | Boundary |
|---|---:|---:|---|
| TSUM / DLT | 2 / 2 | 0 | Orange and Black tiers on one public merchant page. |
| Alfa Only public channel | 18 / 18 | 0 | 25 archive pages; 112 posts scanned; lookback boundary reached. |

The channel scan saw publication dates 2026-03-11 through 2026-09-18; only posts in the 180-day observation window were eligible. It uses source-owned captions and album ownership checks, not screenshots/OCR or forwarded-post attribution. Linked destinations were not fetched by the announcement collector. TSUM robots returned 200/rules_loaded; the channel collector observed 404/unavailable_4xx under the existing robots semantics. Earlier direct-channel diagnostics observed robots 200. Do not substitute one transport observation for another.

The source collection and `sheets_normalized.prepare` dry-run passed. A **temporary verification helper**, not a production parser, then failed: it sliced the bundle to one row while retaining full-source counters, correctly triggering `Source counts/time contradict normalized records`. No source data were changed to silence this error.

Corrected verification **35442472548:1**, execution `5a930df1775954c8887ea108de691a9238ad9339`, read the exact previous artifact, verified its digest, validated the complete bundle once and then projected each record. It accepted all 20 rows, checked both TSUM common-view records and repeated **1069 Python + 7 KEY tests, no skips**. All ten production/config/test/fixture hashes match the first successful regression. No duplicate catalogue fetch was needed.

Evidence artifacts:
- First regression artifact **10583469829**, ZIP SHA256 `ba7ada158e2277b4a8724abdc314f2f83413c6c38981a6c0b8bc1bc511850ab0`.
- Live source artifact **10583564094**, ZIP SHA256 `0c8926453e4aab18914419e500cd6060a2dab080c83f0d5a061f1ce622dd0970`; original normalized.json SHA256 `8eb6e25862d0add04fac97e29bbba8f909068ce03d4c6f203892a1cc6231f370`.
- Final verification artifact **10583839045**, ZIP SHA256 `1acd5fe3aa321ae2d2a561c7070fde9ec78cbee8a649daefe5abdeb9eb91808c`.
- ZIP digests, CRCs and extracted code hashes were independently checked locally. Artifacts are temporary; these identities and the checked-in public excerpt fixtures are persistent provenance.

## Practical semantics and negative checks

**TSUM:** the source advertises **8% Orange / 20% Black as credit to the TSUM/DLT loyalty card**, not cash or airline miles. Rates are extracted and cross-checked between the visible card and FAQ, not supplied from a hardcoded offer template. Native IDs are `loyalty-cashback:orange` and `loyalty-cashback:black`; consistent source rate changes preserve IDs.

The twelve retained practical FAQ answers and activation steps preserve payment/eligible-card exclusions, SBP/QR and partner-courier baseline rates, purchase returns, accrual timing, conversion, brand restrictions, and tier qualification. The White-to-Orange upgrade is a condition, not a fabricated Black entitlement. Bank account pricing and full linked regulations are outside this short merchant-offer extraction. No expiry is stated in the reviewed HTML: dates remain unknown, not permanent.

A pre-publication common-view check caught generic over-extraction of the **baseline 5%/10% and the other card tier**. The new source-owned projection now emits exactly one `earn_points` benefit per tier, with reward unit `TSUM_DLT_loyalty_credit` and the exact merchant tier. Each benefit links to the complete practical conditions and activation record. Baseline percentages remain searchable conditions, not additional cash rewards. Existing non-TSUM normalization branches are unchanged.

**Announcements:** each row stays `announcement` / `announced_unverified`, with unknown current availability and personal eligibility. Publication date is not expiry. Multi-partner posts are not assigned to one guessed merchant; one post's rates are not merged with a different programme or bank PDF. Plain deposit yield, lifestyle percentages, polls, prize draws and the random privilege wheel are excluded. The SimplePrive excerpt canary retains actual 25%/15%/up-to-40% offer clauses while not extracting a separate 15.8% investment-return statistic as a discount. Dated expired-looking promotions remain announcements with their literal date text; do not present them as current usable codes.

The channel describes itself as Alfa-Bank's lifestyle channel. A separate bounded read of `https://t.me/s/AlfaBank?q=aaa_only` returned HTTP 200 but found **no source-owned linking post**. This check does not independently establish publisher ownership. Do not upgrade a self-described/public announcement into verified bank conditions; independently verify material redemption terms on the merchant/bank site.

The 18 new tests include DOM ownership, duplicated/missing clauses, tier-rate mismatch, coherent rate changes, wrong URL, script contamination, rehashed scope tampering, common-view baseline exclusion, foreign/forwarded channels, current/expired-date uncertainty, and refusal to promote an announcement into a verified partner offer.

## Only Assist investigation — still not parsed

The bank's public concierge page points to Only Assist and describes Alfa ID authorization: https://alfabank.ru/everyday/package/premium/konserzh-servis/ . This establishes a product relationship, not an anonymous catalogue API.

The prior incomplete probe **35436200431** was recovered instead of repeated. Fresh no-provider probe **35441034826**, artifact **10583986642**, read the RuStore app page and all 26 public JavaScript assets. The page identified package `com.konsierge.assist.only`, version 1.16.0/code34 and RuStore application ID 2063665675. Discovered links led to the store application/deep link, not the app's discount feed. The non-www developer host timed out at robots; the www alias redirected to that host. This is not a demonstrated working recurring catalogue route.

Static APK inspection was attempted without installation or execution. Initial probe **35441257922** stopped too early on a robots 403; follow-up **35441372055** used the repository's actual unavailable-4xx semantics and then observed **403 on the distribution page itself**. No APK bytes were successfully inspected, no service endpoints or app catalogue were recovered, and no package signature was independently established. Do not report an APK parser as working or repeat unchanged anonymous login/distribution requests.

The publicly readable generic `https://konsierge.com/benefits` list is a separate concierge catalogue. No source proved its equivalence to Alfa Only's app or customer plan, so those generic benefits were **not attributed to Alfa Only**.

## Remaining work and operating constraints

1. The exact bank `web.alfabank.ru/partner-offers/` and Only Assist catalogue remain unread. Seek a genuinely distinct public route or separately authorized private integration, not weakened TLS/access checks or private data in public storage.
2. Automatic discovery and reviewed migration to new Alfa PDF revisions is **not implemented by this release**. Existing core47/cashback101 and five partner PDFs retain their prior boundaries.
3. Public announcements provide leads for additional non-restaurant merchant adapters. They do not replace those merchants' full practical conditions, nor resolve all current validity.
4. Programmes with almost no coverage stay higher priority than isolated previews in otherwise well-covered catalogues. Preserve the practical-offers scope and existing source IDs; do not restart full-contract/OCR expansion.

The destination before this release was independently read as **2621 parser / 3269 current unified records**, not the older PR71 checkpoint's 2620/3268. A later Mir MEOLLO record was already present. None of these twenty new IDs existed in that snapshot. The private workbook export stays local and is not attached or committed. Sheet ACL and rendered whole-workbook layout were not audited or changed.
