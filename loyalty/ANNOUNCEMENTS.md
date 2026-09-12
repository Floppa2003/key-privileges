# Official announcement sources — adapter 2.3.0

This additive revision keeps schema version 2 and the existing Sheets column layout. It adds `announcement` to record kinds and `source_post` to link kinds. Consumers must not treat either as a checked partner offer. See `NORMALIZED.md` for the underlying v2.2 routes and publication contract.

## Source and scope

- `ekp_announcements`: official public EKP channel `https://t.me/s/ekpcard`.
- `rzd_announcements`: public FPC channel "Вагон скидок", `https://t.me/s/fpcrussia`; only posts directly relevant to РЖД Бонус are retained.

The collector walks at most 60 server-rendered archive pages and the preceding 180 days. It follows only the source's own decreasing `before` cursor within the exact configured channel. It never logs in, activates an offer, requests a private code, fetches arbitrary outgoing links or replays a private API. A bounded read failure keeps already collected records and an explicit diagnostic. Reaching the time boundary is completeness of this filtered announcement window, not of the parent loyalty catalogue.

## Normalized evidence

Each post has a stable native `channel/post_id` identity, the real post permalink, complete published text, its publication timestamp, observation timestamp, source links, linked-card labels and URLs, numeric evidence and warnings. Publication dates never become offer validity dates. Unknown validity remains unknown.

Records are fixed to `record_kind=announcement`, `link_kind=source_post`, `source_status=announced_unverified` and `benefit_url=null`. The validator applies this boundary using the source identity too, so changing only the link kind cannot promote an announcement into a checked partner offer. `partner_name` remains null: a roundup may name several partners with different benefits. Their linked labels are kept in `details.linked_cards`; no common rate is assigned to all of them. Linked URLs are discovered evidence, not independently visited or verified cards.

Forwarded posts, contests, image-only posts, unlinked survey results, unrelated growth percentages and generic train-fare posts whose only programme mention is the standard РЖД Бонус footer are excluded. This is a conservative lexical filter, not guaranteed semantic recall over every post. Image-only and unlinked nonnumeric benefits may be missed; older posts may still describe valid offers outside the selected window. Full text remains authoritative.

## Verified branch result

Run `34720464378` collected 47 EKP and 6 РЖД Бонус announcements without source errors. EKP: 29 archive pages / 521 posts examined. FPC: 7 pages / 126 posts examined. Both reached the configured time boundary. The first prototype retained survey noise; those records were never published and were excluded after inspection and regression tests.

Artifact `10305848269` was downloaded independently. Archive SHA256: `bd8aa73fff54e1153a080d961cf42998851329c1f0b052940c030d2d574be5f0`. All six implementation/config/test files match the locally tested SHA256 values; all 53 records passed JSON Schema, application integrity checks and publisher preparation. 154 Python tests and 7 unchanged KEY tests pass locally; Actions test steps passed. A transport-only attempt failed on test-file blank-line integrity and was corrected without weakening the hash check.

This document does not certify main publication: verify the corresponding main run and independent Sheets readback before claiming synchronization.

## Preserved boundaries

Only existing parser_offers A:Y and parser_coverage A:N are managed, with Z/O reserved for manual notes. The curated sheets, old raw intake, existing KEY code, WIF configuration and schedule flags are unchanged. No missing observation deletes or expires an existing record. Private sheet exports, destination identifiers, personal credentials and browser sessions never belong in public code or artifacts.

The remaining EKP/Nordwind/Coral/RZD/Aeroflot/Loyals catalogue access failures are still unresolved. This alternative evidence source does not conceal those gaps or certify their whole catalogues. Temporary inspection and code-registration helpers were removed before merge.
