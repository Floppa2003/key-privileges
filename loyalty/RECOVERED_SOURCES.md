# Recovered public sources — adapter 2.8.0

The user approved integrating the demonstrated public routes from diagnostic PR17. This release adds repo-native adapters, registry wiring, schema checks and tests. It does not merge diagnostic workflows or alter Google permissions, the production job graph, KEY or schedule flags.

## Explicit access profiles

`recovered_contract.py` is the finite reviewed allowlist. `recovered_sources.py` has one anonymous, deadline-bounded Requests session per source. Only exact source and robots URLs are allowed; normal content is never fetched from arbitrary links. There are no account cookies or personal credentials. Requests are paced, body sizes bounded, and 429/Retry-After stops the source. Missing observations do not remove or refresh old records.

### Loyals

The registered `loyals` route replaces the unsuccessful HTTPS probe with **explicitly opted-in public HTTP**. This is not general fallback from failed HTTPS: all other sources still require HTTPS. Only the root, robots and the advertised WordPress post collection with reviewed query parameters are permitted. HTTP is neither encrypted nor source-authenticated. Do not use the fetched data as independently authenticated proof of eligibility, offer validity or a working code.

The collector checks that the homepage still advertises WordPress REST, visits at most ten pages of fifty public posts, checks stable `X-WP-Total` and `X-WP-TotalPages`, unique numeric IDs, `status=publish`, `type=post` and `content.protected=false`, and compares homepage-linked IDs with the API IDs. Collection coverage is not a claim about every website page or currently usable benefits. A late failure retains already validated records and an explicit partial report.

Each record retains the complete public post object, publication/modification timestamps, exact response SHA256 and a JSON pointer. `source_url` is the **actual fetched collection-page URL**, not an invented assertion that the individual API endpoint or canonical HTTPS card was visited. The publisher's own canonical link is separately preserved as not fetched. Stable identity uses the native post ID and does not depend on pagination position.

All Loyals records are fixed to `source_status=public_http_unverified`, `link_kind=api_record`, `benefit_url=null`, unknown offer dates and the explicit `transport_unencrypted_and_unauthenticated` warning. Source identity validation prevents promotion simply by changing status/kind/URL or removing the transport warning. Raw post and normalized title/body must agree. Blank public post bodies are retained as **source_observation**, not offers; the title is evidence-only. Source modification time never becomes a new offer date.

This is an additive schema-v2 change: `source_observation` is a new record kind; only the exact Loyals source can use an HTTP evidence URL. Consumers must retain source status and warning metadata. Other records, their IDs and the Sheets column layout are unchanged.

### VTB, NSPK and Uralsib

Three exact public pages are registered with `russian_nuc_pinned_2026_09`:

- `af_vtb_rules`: VTB Privilegia Aeroflot debit-card rules.
- `nspk_ekp_rules`: NSPK's EKP cashback announcement article, not a complete catalogue or campaign contract.
- `uralsib_rzd_rules`: a historical RZD card-application promotion, not the currently offered card terms.

Official CA root/intermediate files are downloaded through default verified HTTPS and checked against pinned SHA256 values. A temporary certifi-derived trust bundle is used **only for the exact allowlisted source host**. The operating-system trust store remains unchanged; hostnames, signatures and certificate validity dates are still verified. No `verify=False`, browser certificate-ignore option or general TLS downgrade exists.

Only Uralsib permits its observed bounded redirect to the **same exact URL** in one ordinary anonymous session. Redirects to another URL, host, query or scheme are rejected; session cookies are never exported. A CA file change fails rather than silently trusting new bytes.

The adapters scope visible page sections and retain full original text, linked-document addresses (not fetched), source hashes and supplemental-rule provenance. VTB's related Prime card is excluded, card earning ratio is structured, and individual campaign dates do not expire the base card record. Uralsib's explicitly published card-application window is extracted and classified as historical. NSPK remains `public_announcement_not_full_rules`; its article date is not inferred as offer validity.

## Verified development result

Run `34851290322` used the actual production dispatcher and obtained **92 records from all four sources without errors: 89 Loyals posts and one each VTB/NSPK/Uralsib**. Loyals exhausted two pages (50+39), covered all 80 homepage native IDs and retained two empty-body observations. All four robots reads completed with the reviewed access profile; this is not a robots-precheck bypass.

Downloaded artifact `10351072243` SHA256 `c3e803de6cd10dce188ff7fa81e64732941542aa1dce7db71d4cd9733d3ce38b`; ZIP CRCs, executed archive bytes and all seven implementation/config/test files were independently checked. Every record passed JSON Schema, application/evidence checks and publisher preparation. **440 Python tests and seven KEY tests passed locally**, and corresponding Actions test steps passed. A raw-post/normalized-text divergence regression was reproduced red then green.

This document records branch verification, **not main publication**. After merge, the actual main payload and Google Sheets readback must be checked before claiming the production dataset was updated. The existing private unified normalization is downstream of public publication; public artifacts never contain the source spreadsheet or its private records.

## Limits and unchanged sources

The recovered pages are not all newly available current discounts. Loyals posts have historical modification dates; two have empty bodies. Uralsib's published application window is September 2023–March 2024. NSPK is a public announcement and VTB is a conditional premium bank product. All conditions and costs still require contextual review; linked full documents are not automatically read.

CoralBonus had one real diagnostic success but no reproducible network remedy. It is not falsely marked restored by this release. Its two primary routes, EKP, Nordwind, RZD, Aeroflot and old Utair remain separately reported. No new proxy, paid runner, user account or browser session was introduced.
