# Aeroflot airline coverage — accepted production, 2026-09-16

## Outcome

PR42 is merged at `2cd058a6029620a441e6bfeb16fc29e59a795e1d`. Actual trusted-main run **35108510915:1** used that commit. Regression, collection and final publisher job **104837542824** completed successfully. Six new airline-rule records were published to the SAME discount spreadsheet and independently read back after the final write. The earlier229 company records were not recrawled or given new observation times.

| Observed source airline | IATA | Own fare groups | Own status-coefficient entries |
|---|---|---:|---:|
| Аэрофлот | SU | 27 | 8 |
| China Eastern Airlines | MU | 7 | 4 |
| Vietnam Airlines | VN | 7 | 4 |
| Xiamen Airlines | MF | 4 | 4 |
| Россия | FV | 0 | 0 |
| Shanghai Airlines | FM | 7 | 4 |

The list returned four roots; two more were discovered from those roots' actual child references. All six details were read. The zero table count for Rossiya is the source's own returned structure: its description and separately identified parent conditions are retained, not a fabricated child table. **52 fare groups and24 status coefficients (including zero entries) are rules, not76 cash discounts.**

## Current-source method and scope

The accepted original-root link led to `https://www.aeroflot.ru/partners/airlines?_preferredLanguage=ru`. Its current frontend module identified:

- List: `https://www.aeroflot.ru/partners/ws/v.0.0.2/json/skyteam?lang=ru&full=0`.
- Detail: `https://www.aeroflot.ru/partners/ws/v.0.0.2/json/airline/get?lang=ru&id=<discovered-id>&returnFullParentInfo=1`.

The reader uses the existing public Google-import workspace, short-lived WIF identity, validators, literal upsert and unified publisher. It imports the current list and each discovered detail on every run; no fixed list of airline answers or previous capture is a runtime fallback. Source-approved access is recorded on the owner's reported Aeroflot permission, not an independently located email, source login, special-crawler identity or global robots override.

The mapping preserves cabin, tariff, booking code, code ID, percentage and each referenced numbered note. Repeated letters are not deduplicated across different scopes. For example, this source returned MU booking H at100% for international travel and30% for domestic travel. Native normalized rows3573 and3575 retain those separate notes and coefficients. Full eligibility and exceptions still need their own conditions; these examples are not unconditional travel advice.

A child's own fare table is not overwritten by a returned parent's table. Parent conditions remain a separately identified section/object. Source metadata and minimum-mileage scope codes are preserved without inventing current airline affiliations, geography or a universal earnings calculator.

`airline:<source-id>` rule identities are disjoint from the existing `partner:<source-id>` company identities. The common projection emits `earn_miles` with unit `percent_of_distance`, a distance-mile basis, fare/note scope and distinct status-coefficient roles. Generic lexical discount extraction is not applied to these records: the exclusion for tickets discounted by50% must not become a50% discount offer. Literal exclusions remain in the source conditions.

## Completed run and artifacts

Run: https://github.com/Floppa2003/key-privileges/actions/runs/35108510915

- Source calculation interval: `2026-09-16T14:29:45.411371+00:00` to `2026-09-16T14:30:32.785206+00:00`.
- Nine import observations: robots, original-root discovery, airline list, six separate details. Zero source/mapping errors; scope=`airlines`, four roots/six total, all discovered airlines read.
- Public artifact10451661662 SHA256: `d10cd322677bf79539674b987d194155942200266c3739c77e94ed621029af4c`.
- Main test artifact10451123538 SHA256: `677e2a53b9ea0afb253f56f332f58cfccd7ec1e545259e2f732c51713ab25c68`.
- Branch test artifact10450713547 SHA256: `7130e3001fdf5558301a3b3bf1ccdce751dfad8932fbacfb6d2a6c2eaa279abc`.

All three archives were downloaded and SHA256/ZIP CRC checked. Every new record was independently reconstructed from its typed source observations, schema/application validated and prepared by the production publisher. The complete bundle validator passed as an offline replay at its original finish time, not a new source fetch or permission to republish old data. All seven changed executed files matched the reviewed local bytes in both branch and main test archives.

**719 Python tests and7 KEY tests passed in both branch and main Actions, no skips.** Locally38 Aeroflot tests and7 KEY tests passed; the complete local suite lacks dependencies and is not claimed successful. New tests cover changed identities/values, repeated booking codes, note references, source privacy/identity, child traversal, partial retention, bundle reconstruction and real common normalization.

## Independent native destination checks

Destination: `1uFR7croj7p6RRNPcoTRYlVl06hKsurkIgyu1IdMMB-4` (скидки).

- `parser_offers!A2454:Y2459`: six new `program_rules` records, all six native IDs, hashes, dates and run markers matched the source output. Manual column Z samples remain blank.
- `parser_coverage!A1277:N1277`:6 discovered/6 normalized/0 errors/`ok` within the explicit airline scope. Zero newly read company records does not invalidate the previous accepted229-company run.
- `normalized_records!A3102:AB3107`: six corresponding current rules, all current-generation markers read back.
- `normalized_benefits!E3534:H3609`: native search scanned76 rows and matched76 `percent_of_distance` entries, with four displayed samples. Native value/scope reads of rows3573 and3575 verify MU's distinct H notes. Actual program_rules kind and the separate Rossiya parent-conditions section were also read natively.
- `normalization_audit!D7:J7`: **verified/current**,2458 retained parser records,3106 unified input/output records. Overall term totals3603 benefits/10119 conditions/117 costs/651 codes. These retained totals are not all newly read in this pass.
- Final source fingerprint: `60442f77d62e55617f673a5655f4daf281dd9172b92e618021f8b8f9687f856d`.
- Final generation: `72bbfbdc24fb6cd4506bf4f34102e6b52e3ac466bcced479dc59df307b582649`.
- Old EKP2153, RZD2224 and company2453 sentinels retained their previous hashes, times and runs. Native normalized samples retain top/wrap/10pt styling. These are all-new-identity/hash checks plus declared field/scope/manifest samples, not an independent rendered audit of every private workbook cell. The existing publisher performs its full output readback.
- Temporary `af_airline_probe` was removed and metadata read back. Both production scratch rectangles were read completely: only headers and their own idle markers remained. RZD scratch was not modified.

## Free operation

The new released airline reader consumes **zero ScrapingAnt credits**, just like the existing company and RZD Google-import paths. One-time module discovery used a datacenter attempt costing1credit and a successful residential read costing25credits, both within the existing Free account. No new paid service, server, key or account was introduced. No current provider balance is claimed.

The existing Thursday08:47UTC /11:47Moscow schedule now requests `all` (companies and airlines). Manual default is also `all`; reviewed code pushes request `airlines` only, avoiding an unnecessary229-company refresh during this release. The accepted live run was airline-only; combined-scope traversal passed tests, but a combined scheduled live pass has not yet been observed. Other collector schedules and provider budgets are unchanged.

Bounds remain explicit:260 companies,60 airlines,324 combined imports,3000seconds, five-second minimum import interval, stop an affected loop after three consecutive failures. Future larger or slower sources may be partial rather than silently truncated or declared complete.

## RZD investigation in the same continuation

No new RZD conditions were recovered or published. Two previously failed URLs again returned Google import `Resource at url not found` errors: the Renaissance Smart Plus4000-point page and Grand Karat Sochi2026 page. A broader extraction for the Admiralteyskaya18% page returned a generic promotion index/navigation with other offers, not the requested hotel's terms. Unrelated suggestions were not substituted. These observations do not prove origin HTTP404, expiration, deletion or mandatory login. The other five prior failed pages were not retried here; existing66/74 acceptance remains.

## Limits and next checkpoint

Google imports expose parsed calculation results, not origin HTTP status, redirect chain or origin-cache age. Timestamps identify the import request/calculation, not independently certified uncached downloads. Current catalogue scope is what this source response disclosed, not proof of every historical partner, all codeshare routes or every personal entitlement. External rules, PDFs/images, redemption and individual combinability were not tested. No account data, personal coupon, bonus spending or purchase was used.

The source authorization basis and existing destination sharing are unchanged. Do not publish account-only material into the link-accessible destination or public artifacts. If permission is revoked or narrower than reported, stop/review that scope. A successful release pass is not proof that every future scheduled pass will succeed.
