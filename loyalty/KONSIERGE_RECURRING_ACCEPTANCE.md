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

## Publication boundary

This section records feature verification, not a completed post-merge Sheet update. The latest previously published snapshot is PR74. Append actual main-run and independent destination evidence after the first targeted publication; do not relabel the feature observation with the publication timestamp.

## Remaining limits

A successful fresh control run and configured daily trigger do not prove every future unattended run will succeed. If the site's schema, page count, source totals or access behavior changes, the collector stops rather than publishing an incomplete replacement. An empty category/root is currently rejected conservatively. Expired/conflicting dates and unknown personal Only Assist eligibility retain PR74 semantics. Public catalogue identity remains separate from Alfa bank/app entitlements. No private bank/app route is enabled.
