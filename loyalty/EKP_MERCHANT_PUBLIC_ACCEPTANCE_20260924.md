# Merchant-owned public EKP clauses — 24 September 2026

## Accepted implementation; publication tracked separately

Three public merchant sources now use the existing HTML adapter registry and normal publisher contract. This is independent public evidence, not recovery of the authenticated EKP catalogue and not a claim of region-98/region-78 entitlement equivalence. Four records were actually collected by the standard selected-source entrypoint. Production publication is not established by this feature acceptance; verify its later main run and the destination before claiming completion.

| Source ID | Records | Publicly supported benefit and use |
|---|---:|---|
| ekp_artparking_public | 2 | Concerts: 15%; children's Gorod Muz programmes: 5%. The merchant publishes the literal code edkarta for both. Online use still requires showing EKP before the event. Reservation/availability and the Zelenogorsk church exclusion are preserved. Advance payment of children's programmes is not copied to the concert record. |
| ekp_domknigi_public | 1 | 10% on the assortment in shops and online. Say/enter a code, but the literal code is NOT published on this page. No combined promotions, bonus earning or bonus spending. Offer starts 24 February 2026 until a marketing-department instruction; the article's 13 March publication date is not the offer start. |
| ekp_itc_public | 1 | 15% on education programmes when paying with EKP. Showing a card alone is not the published payment condition. No code or expiration is invented. |

Exact source URLs:
- https://www.artparking.org/ekp/
- https://dk-spb.ru/news/news-company/dom-knigi-i-edinaya-karta-peterburzhtsa-zaklyuchili-partnerstvo/
- https://itctraining.ru/about/partnery/

Artparking is an older publication that was read again; an HTTP200 does not independently guarantee transaction eligibility or an unchanged contractual offer. No source supplies a fixed expiration date for these records. Dom Knigi explicitly links its EKP region-78 card; that is retained as provenance, not a licence to overwrite a different regional gated record.

## Actual acquisition and tests

Feature execution: 08ed6b09a02998595ae14080a3e44d18affa7b1c.
Run 35976076098:1, job107556763694, completed/success. Its individual regression, collector and payload-validation steps were read back after completion.

The complete regression suite passed **1348 Python tests and 7 KEY tests**, no skips. Eleven new tests cover source dispatch, individual product rates/codes, changing source values rather than canned rates, missing clauses, conflicting rates, article versus offer dates, actual EKP payment, browser-repaired nested paragraphs, neighbouring partner contamination, duplicate sections and registry wiring.

Standard command: `python loyalty/collect_normalized.py --limit 500 --sources ekp_artparking_public,ekp_domknigi_public,ekp_itc_public` under the existing browser environment. Source observation is **2026-09-24T08:36:20.618537+00:00**. Results are 2+1+1 records, three reports ok, zero failed items, all workers finished. Source policies returned200. Both normal publication dry-run and selected-source health checks passed. The four records' rates, public code, conditions and redemption text were independently inspected in the downloaded payload.

Artifact10798371454, name ekp-merchant-acceptance-35976076098, SHA256201f95d7cb40245d0fa92ac2ea7b45bd6db511dc097c1b2cfa16170fcb7688f1. ZIP SHA256 and CRCs were verified; its exact repository-code archive and regression logs were read. This artifact includes public source-derived records and public code, not the private destination export.

Earlier public capture35969050271 at07:20 obtained the three original merchant pages by ordinary anonymous HTTPS. Artifact10795133466 SHA256fd1feb15eb34085865ae1e2127c1610a2b73fe2af3225202de12f1d7efe2c96c was independently verified. Those source-owned content blocks informed selector review; the later08:36 standard browser collection is a separate fresh observation, not relabelled fixture replay. Server cache Age was not supplied; no uncached-origin claim is made.

## Boundaries and operation

No bank/source login, app credential replay, OTP, coupon issuance, activation, booking or spending was performed. The code adds only an existing-pattern parser, registry entries, public fixtures and tests. The two temporary feature-only wiring/acceptance workflows are removed before integration. Existing production workflow, permissions, schedules, budgets and publisher remain unchanged. Main targeted publication must refresh only these three new sources and preserve every pre-existing source identity, row and manual value.

The broader research recovered a public-channel inventory of106 EKP-name searches and8 RZD-name searches. That finite archive search is not an exhaustive audit of106 independent merchant websites, nor proof of current validity for older announcements. Only Assist's public JS graph likewise remains research, not an accepted anonymous source. None of those incomplete findings is counted among these four records.
