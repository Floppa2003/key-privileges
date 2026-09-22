# Named Mantera partners and expected-source health — 22 September 2026

Continuation of PR79, limited to the approved Mantera/Backit coverage frontier and three-source health check. This checkpoint is pre-publication; a later publication report must document actual main execution and independent destination readback.

## Actual public evidence

Bounded anonymous probe **35762327090**, execution `c86c0eda61dd5c5a123132bf85c7d166af629bd9`, read three URLs with HTTP200: https://sochiparkhotel.ru/about/programma-loyalnosti/, https://krasnayapolyanaresort.ru/loyalty, https://backit.me/ru/cashback/products. Artifact10710826175 ZIP SHA256 `b7cd5c6c49e99f982ed714cd33c6f3360cbb40307a8d9dbe9dbd880e66643667` was verified before reading.

The Sochi Park page's named accordion contains **11 accommodation partners**, while a separate counter still says6. The named roster, not that counter, is parsed; the conflict stays visible. This does not prove programme-wide completeness or that Sochi Park itself is a currently participating property. Ten new records exclude Congress, whose existing stable ID and independent hotel page remain. The five FAQ tiers remain separate programme records: total16 records =5 tiers +11 accommodation properties, not16 hotels.

The Polyana-owned page specifically confirms both earning and spending at **Долина 960, Кортьярд, Марриотт**. Exact reviewed mappings to the named roster prevent substring inheritance between Marriott and Courtyard. Only these3 receive spending-cap components. For the other named properties, individual spending is not confirmed; general programme caps are not silently applied. Both pages' five-tier earning/cap/annual-spend tables must agree. Retain pre-booking registration,18+, free participation,12-month status,24-month bonus validity, non-cash withdrawal and promo/bonus-funded exclusions. Preserve exact source names, URLs, hashes and original observation time. Unknown new short aliases, missing clauses, pagination, duplicated names or conflicting rates fail closed.

## Implementation and verification

`mantera_partners.py` matches the existing public reward evidence/projection pipeline; two source-specific PublicSource contexts use verified TLS, existing robots/read-budget handling and no account redirects. Failure of either new page returns no newly derived partner records, preserving the earlier6 independently successful FAQ/Congress records and reporting the failed component. There is no new Mantera disappearance/retirement policy; its existing7-day freshness limit remains. Backit/Avolta reversible inventories are unchanged.

Health no longer trusts a fixed Mantera record count. It validates the actual roster, record identities, same-time source evidence and scope. The existing source-health workflow now passes the collector's exact `sources` selection. A selected programme with no report is unhealthy rather than an empty successful all(); duplicate reports fail. Unselected programmes are not required. Publication of other successful sources remains independent of health failures.

Actual source run **35764681102**, code `2e4897184ee4314832e860c98d9f4ca6d59c9ac4`, observation **2026-09-22T18:05:02.207303+00:00**, collected16 Mantera records, zero errors. Actual source-health and normalized dry-run succeeded. A following diagnostic replay used a fixed fixture clock and failed with `Duplicate or foreign observation`; this was an audit helper error, not a source failure. No data was published. It was corrected by replaying the unchanged actual payload with its own timestamp, not by altering source dates or relaxing the publication guard.

Final verification **35765200821**, execution `9f1dfb7bcd8c0e4dfdf2facda2fc813b4211360c`, passed **1221 Python +7 KEY tests**, zero skips, and all16 real-record reader replays. A real CLI subprocess with a missing selected report exited1 and named `missing_source_report`; the genuine payload exited0. The earlier full regression also passed1221+7. All215 compared Python/workflow files match the independently reviewed local code. Final artifact **10712081409**, ZIP SHA256 `eee035e9dc1a009a0394e0370b3b87b88be7d6750183c5a92f3912246b3c9057`; unchanged actual normalized.json SHA256 `0f8bdd9e4e759c6ec47849ab670b450916af9f552d3ba4cd4c60fa0c79929e4f`. No new source fetch was represented by the final offline replay.

Fixtures are bounded genuine public DOM, retaining the full named roster/table/critical clauses and removing unrelated imagery/scripts. They are not invented facts. Temporary verification workflow and patch are removed before merge; the final code is unchanged after accepted regression.

## Backit boundary

The current products landing still links to https://backit.me/ru/cashback/shops/ozon/products. One new direct anonymous check at **2026-09-22T18:05:12.054931+00:00** returned **302 to /ru/cashback/shops**. It was not followed or treated as an available product catalogue. Old compilation redirects already checked in PR79 were not repeated. No marketplace-product offers were imported from cached search pages.

## Release constraints

Use the existing main selected-source pipeline to publish only Mantera after merge and verify actual source-health plus final Sheet state. Preserve unrelated programmes, source row positions, manual annotations, eight original formulas, native search and two-tab visibility. No account login, registration, coupon activation, purchase, paid provider, extra schedule or Browserbase dependency. Public repo artifacts contain only public evidence/test code; private workbook exports stay local. First future scheduled execution and long-term website availability are not claimed by this pre-publication check.
