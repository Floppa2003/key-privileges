# Konsierge recurring collection — 19 September 2026

## Decision and implementation

The project owner explicitly instructed: «ну так не проверяй robots.txt, в чем проблема». The reviewed public Konsierge catalogue now has a source-local no-preflight route. This supersedes the unresolved robots blocker in PR73/74 notes; it does not claim the website owner's permission or RFC-compliant robots handling.

`konsierge_public` is registered in the existing daily `loyalty.yml` scope with `mode=konsierge`, `robots_policy=skip_konsierge_public_by_user_2026_09_19`, timeout420s. The existing schedule remains **05:23 UTC daily** and the same serial Sheets publisher is reused. There is no second schedule, provider account or paid service.

`konsierge_source.py` opens a fresh public browser, reads root plus source-discovered category pages, and passes the sanitized capture to the accepted PR74 parser. It does not fetch robots.txt; the request allowlist also rejects that path. Only reviewed public page/assets and browser-owned catalogue read endpoints are allowed. Account/auth paths and non-read methods are rejected; no direct API replay, source credentials, cookies or personal data are extracted. Catalogue requests are spaced by at least one second, and non-200 catalogue replies stop collection. Failed, timed-out, partial or internally inconsistent captures return no replacement records. The unchanged publisher preserves prior observations.

The shared `public_transport.py`, TLS policy, other sources and `loyalty.yml` are byte-for-byte unchanged. Only Konsierge skips preflight. Existing manual snapshots still validate with their original manual provenance. New captures carry explicit recurring provenance and the source-local robots decision; source native IDs, conditions and literal codes are not changed by the mode switch.

## Actual verification, not an old snapshot replay

Run **35466313814:1**, execution **1220289f32812e13699379d15416e98d106ebd77**, applied hash-guarded edits to the read-back main baseline. It passed **1102 Python tests and 7 KEY tests, zero skips**. Twelve new tests cover source-local routing, continued robots checks for unrelated sources, disallowed paths/methods, no partial replacement, old/manual compatibility, explicit recurring provenance and field sanitation.

The real production command `collect_normalized.py --sources konsierge_public --limit 500` then freshly observed the site at **2026-09-19T20:06:45.143601+00:00** and accepted **159 records**, zero errors, all six categories: restaurants93, hotels13, beauty/health35, services/shopping15, Sochi4, realestate1; two root-only items retained. The report records zero robots requests. All159 records passed publication dry-run and common-view projection.

Only after those checks passed were the three integration edits committed to feature commit **4e55d0cfdbcc34f8be4a663671140180559771fb**. Temporary workflow and patch helper were removed in that same commit. The net implementation changes are five files; no shared transport or schedule changed.

Artifact **10591735659**, ZIP SHA256 **dd9fc11533260497411d2ba7bb4f6ba2dc8a43cb41994d1354770549db8996d5**, was downloaded and independently checked. All five production/configuration/test file hashes match the reviewed local files exactly. The baseline current-checkpoint blob was independently recovered as **e6a97234013dbe4591e9b667c589499323f5dc9d**.

## Normal main publication — completed and independently verified

PR **75** merged at **2026-09-19T20:09:59Z**, merge **dedd09e552c2ba076deac3a57ccf6d5084a9001f**, reviewed head **051c12d03756a9fdc4eb485e00dc60350b80ee90**. The existing request mechanism was updated by **2bfa03aa4f80f5a7e0f4d7aef3890bf86e352a4b**, request `2026-09-19-konsierge-recurring-75`, selecting only `konsierge_public` with publication enabled.

Request run **35466565687** dispatched normal main **35466573005:1**, executing that same commit. This is the normal `loyalty.yml` workflow, not another one-time publication implementation. Collection job **105959885111** completed its full Python/KEY regressions, live collection and publication dry-run. Publication job **105960180080** completed source upsert and all common-view readback steps successfully. Both successful outcomes were read back through GitHub.

The main source observation is **2026-09-19T20:11:23.957490+00:00**, with **159 records, six fully reconciled categories, two root-only items, zero source errors and zero robots requests**. It is a new live observation, not the earlier feature payload republished with a fresh date. All159 headline texts, full conditions and redemption instructions match the previous PR74 snapshot; provenance and observation time changed.

Destination: **скидки**, spreadsheet **1uFR7croj7p6RRNPcoTRYlVl06hKsurkIgyu1IdMMB-4**. Native-cell reads showed the updated source run/time, recurring mode, explicit robots profile and still-unverified customer eligibility. An intermediate manifest was `publishing` and was not called complete. After the publisher finished, a fresh export was independently compared with the genuine before export:

| Independent read-only check | Accepted result |
|---|---|
| Parser/source rows | **159 existing rows2670–2828 updated**, no new/duplicate IDs and no moved old ID. |
| All parser records | **2800**, unchanged count. |
| Other parser records | **2641 complete rows** unchanged, including manual cells. |
| Other source/history/archive sheets | **9175 nonempty cells** unchanged; visibility and hidden archive preserved. |
| Managed source/report fields | **3989 fields** match the actual main payload exactly:159x25 source fields plus14 coverage fields. |
| Coverage | Row **1638**, run35466573005:1,159/159,zero errors. All earlier coverage values preserved. |
| Current common views | **3448 records,3976 benefits,10266 conditions/costs,733 code/delivery rows**, all on the verified generation. |
| Manual common-view cells | Preserved at their original positions. |
| Formulas | All **eight** formulas preserved. |
| Final manifest | **verified/current**. |

The exporter reported modification time **2026-09-19T20:15:58.440Z**. That is the workbook modification time, not a claimed exact timestamp of the independent readback. This audit checked all managed source/report fields, old source/manual/formula preservation, component counts and every current component's generation. The normal publisher separately verified all its managed common fields; this independent audit does **not** claim a second full common-semantic recomputation or a rendered-layout/ACL audit. Private workbook exports remain local, not attached or committed.

Main artifact **10591132599**, `loyalty-public-35466573005-1`, ZIP SHA256 **fc673467d3665b4f26e5167d0b3dfe04f49e570a7049a3a577613baa1e58cacc**; normalized.json SHA256 **d4791151580e2bd8debca00e7bf1fe4ee299b800b1959e946b492ab571d460b9**. ZIP digest/CRC were checked. The three changed production Python hashes match the reviewed local files; source registry blob **f85d8c163bf2f39aa07063518b919a278351677a** was independently read back and matches local bytes.

Verified source fingerprint: **fb7e8704c1cf1ba1fb5d2e2fb1943f2b9ab5a66f02f562cf606255b0300a74fe**.

Verified current generation: **e8bf15ac29b800010d51ac50786b550216f52d495b352a2eb4a771fbe3b44393**.

## Remaining limits

The daily trigger is configured and the same main workflow has completed a fresh controlled run. A future cron-triggered execution has not yet been observed, and future success is not guaranteed. If the site's schema, page count, source totals or access behavior changes, the collector stops rather than publishing an incomplete replacement. An empty category/root is currently rejected conservatively. Expired/conflicting dates and unknown personal Only Assist eligibility retain PR74 semantics. Public catalogue identity remains separate from Alfa bank/app entitlements. No private bank/app route is enabled.
