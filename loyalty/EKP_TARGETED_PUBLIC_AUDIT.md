# EKP targeted public-reference audit — 18 September 2026

This extends EKP_GATED_AUDIT.md. It is a public-reference investigation, not authorized recovery of the 110 protected catalogue records.

## Observed scope and independent checks

Main catalogue parent: run 35070130567:2, artifact 10435868136, source observation 16 September. Its 110 gated native identities give 106 distinct displayed names. The names were derived from the source's public projection; protected description fields were not retained.

Targeted run **35345909729:1**, execution **6d3cac139039245ed84055b888d2b65ddafdcab8**, queried one public search page per exact displayed name in the official `ekpcard` channel. Source interval **2026-09-18T12:40:58.948513+00:00 to 12:47:24.200402+00:00**. No source account, Google destination credential or ScrapingAnt credit was used.

- All **106 query names attempted**; **79 saved public pages**, **27 responses with no source-owned public posts**.
- **40 distinct posts** contain exact source-owned `/capabilities/loyalty/tiles/<id>` references matching **42 of the 110 gated IDs**.
- **Three pages advertised more results and were not paginated**. All-names-attempted is not exhaustive search results, an exhaustive channel archive or full offer coverage.
- Five posts have two or three recorded link variants: 4163, 5440, 4390, 4961, 4723. Their extracted body text is identical between these observations, but link arrays differ. The variants are retained; no values are silently combined.
- Artifact **10546842538**, SHA256 **bb29ed71214af2a28a25e7e360914b412335ca768edf032222964dc9a4090ac8**, matched GitHub metadata and passed ZIP CRC. Every one of the 79 saved HTML files passed its saved SHA256, exact public-search location, HTTP200 and ordered-time checks. Existing source-owned message/linked-card extraction independently reproduced all 40 post objects and their variants. Saved UTF-8 was explicitly decoded; no inferred character repair or alternate source text was used.

The following table preserves exact references beyond the artifact's seven-day retention. Native IDs are identifiers present in the current gated set, not certified unchanged merchant identities or identical regional terms.

| Official post | Original publication | Referenced gated native IDs |
|---|---|---|
| https://t.me/ekpcard/2243 | 2024-03-20 | 1846 |
| https://t.me/ekpcard/2258 | 2024-03-22 | 797 |
| https://t.me/ekpcard/2405 | 2024-04-19 | 797 |
| https://t.me/ekpcard/2507 | 2024-05-10 | 797 |
| https://t.me/ekpcard/2679 | 2024-06-14 | 1144 |
| https://t.me/ekpcard/3128 | 2024-10-01 | 265 |
| https://t.me/ekpcard/3183 | 2024-10-14 | 2236, 2237 |
| https://t.me/ekpcard/3205 | 2024-10-20 | 27 |
| https://t.me/ekpcard/3799 | 2025-03-27 | 1144, 2336 |
| https://t.me/ekpcard/3887 | 2025-04-18 | 2596 |
| https://t.me/ekpcard/4137 | 2025-07-04 | 2673 |
| https://t.me/ekpcard/4163 | 2025-07-11 | 2700, 2703 |
| https://t.me/ekpcard/4390 | 2025-09-04 | 251, 1593, 2151 |
| https://t.me/ekpcard/4486 | 2025-10-01 | 2237 |
| https://t.me/ekpcard/4548 | 2025-10-16 | 2869 |
| https://t.me/ekpcard/4581 | 2025-10-26 | 1944, 2528 |
| https://t.me/ekpcard/4635 | 2025-11-09 | 2900, 2902 |
| https://t.me/ekpcard/4687 | 2025-11-25 | 2933 |
| https://t.me/ekpcard/4723 | 2025-12-06 | 2922, 2933, 2935 |
| https://t.me/ekpcard/4755 | 2025-12-18 | 2952 |
| https://t.me/ekpcard/4789 | 2025-12-26 | 1593 |
| https://t.me/ekpcard/4819 | 2026-01-13 | 2950, 2951 |
| https://t.me/ekpcard/4823 | 2026-01-15 | 2127 |
| https://t.me/ekpcard/4845 | 2026-01-23 | 1704 |
| https://t.me/ekpcard/4875 | 2026-02-04 | 2673 |
| https://t.me/ekpcard/4953 | 2026-02-27 | 3266 |
| https://t.me/ekpcard/4961 | 2026-03-02 | 338, 715, 1991, 2334 |
| https://t.me/ekpcard/4985 | 2026-03-10 | 2700 |
| https://t.me/ekpcard/5050 | 2026-04-01 | 1593 |
| https://t.me/ekpcard/5075 | 2026-04-10 | 251 |
| https://t.me/ekpcard/5107 | 2026-04-22 | 2951 |
| https://t.me/ekpcard/5130 | 2026-05-01 | 3338 |
| https://t.me/ekpcard/5163 | 2026-05-14 | 3369 |
| https://t.me/ekpcard/5187 | 2026-05-22 | 2509 |
| https://t.me/ekpcard/5196 | 2026-05-24 | 2900 |
| https://t.me/ekpcard/5209 | 2026-05-28 | 1991 |
| https://t.me/ekpcard/5260 | 2026-06-10 | 3009 |
| https://t.me/ekpcard/5279 | 2026-06-17 | 3382 |
| https://t.me/ekpcard/5337 | 2026-07-08 | 3525 |
| https://t.me/ekpcard/5440 | 2026-08-08 | 3377, 3558, 3561 |

## Practical interpretation, not a false closure count

Most matched posts announce a partner, an event, or a special offer whose actual terms/code require EKP login. No protected terms were recovered by this search. The 68 IDs without a match have no exact link in this bounded result set, not proof that no public reference exists elsewhere.

Two quantified historical posts deserve explicit treatment:

- **Rostelecom, post4755, 18 December2025:**20% for new home-internet customers, connection for RUB1, and10% for eligible existing customers. The baseline Sheet already has separate public new/existing-customer records at parser_offers566–567 from another official public source. No duplicate row or fresh validity claim was added.
- **Zenit, post3128, 1 October2024:**10–20% by match category, official club-site purchase and an EKP code. This old post does not certify a2026 match, current code, eligible seats or unchanged campaign. It remains a dated reference rather than a newly verified current offer.

Post3183 concerns the **Silver Age** programme. Keep it separate from ordinary EKP eligibility. Post4635 links native2902 under the name **Alpinetti**, whereas the current gated catalogue displays **Джельмино** for that ID. An old native-link match alone cannot settle renaming, identity continuity or terms equivalence. Other multi-partner posts and event listings likewise cannot assign a single percentage to every linked partner.

Some retained links contain source encoding variants such as `amp%3B`; no corrected URL was invented and fetched to turn a weak reference into a successful read. Region parameters and original publication dates remain material.

## Separate useful public sources

The same continuation independently found and released two partner-owned routes in **PR60**, `ekp_artflora` and `ekp_litres`. Their source-specific terms were published separately through main run **35347752248:1**; they do not replace or authenticate original EKP native1617/2660. See **PUBLIC_GAP_COMPLETION_ACCEPTANCE.md** for actual source-to-destination evidence and limits.

No exhaustive crawl of all106 partners' independent websites was performed. Protected catalogue text, literal gated codes, exact regional equivalence and personal eligibility remain unresolved. Do not repeat all106 searches or rename42 references as42 recovered discounts merely to claim completion.
