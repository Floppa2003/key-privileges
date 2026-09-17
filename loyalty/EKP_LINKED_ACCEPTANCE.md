# EKP linked public conditions — accepted 2026-09-17

## Released work recovered after interrupted turns

PR50 (`749900f3713ada8b1fea0b21194bf4af52edfb8b`) added the bounded linked-condition collector. PR51 (`0761cd5333ea15dc7d1ea1c939584e83cf29f2b3`) repaired sanitized-HTML roundtrip stability. Do not reimplement these adapters or rerun OCR merely because the chat ended without a report.

Main run **35265812619:1** completed regression, collection and publisher **105353660799**. All final publisher steps and the job were independently read as completed/success. Source interval **2026-09-17T19:36:54.660241+00:00–19:38:56.928807+00:00**; workflow completed at19:42:57UTC.

| Discovered public document | Actual result | Source rows |
|---|---|---|
| EKP silverage HTML page | One linked-condition record | parser_offers2520 |
| Медпомощь24 discount-card exclusions PDF | One file,2scanned pages,one text part |2521|
| Рестораны Арама Мнацаканова / vamprivet campaign HTML | One linked-condition record |2522|
| Энергия Высоты price PDF | One file,6scanned pages,two text parts |2523–2524|

**Four documents / five records**, not five new discounts. All selected downloads and machine extraction operations completed without final errors. Every record is `program_rules`; the common projection adds one condition and zero automatic benefits,costs or codes per record. This avoids treating unrelated tariff percentages, VAT, examples or excluded services as personal offers.

## Discovery and boundaries

The collector uses the successful main EKP catalogue artifact **35070130567:2**, observed **2026-09-16T07:49:02.930325+00:00**, as a recent discovery parent, not as newly fetched catalogue content. Parent observation times, IDs, hashes and links remain attached. The current catalogue has1045entries, including110gated observations. Those110were not authenticated or recovered by this release.

The current public reference inventory has95URLs; four matched the reviewed linked-document scope. Other references are not automatically proof of a missing discount, nor proof that all external terms have been exhausted. Known source hosts and paths remain bounded. No account login, coupon issuance, purchase or bonus spending was performed.

The source URLs are:

- https://ekp.spb.ru/silverage
- https://mpclinic.ru/upload/1689252399.pdf
- https://vamprivet.ru/supreme-restaurants
- https://xn--b1abfnwkklk1gdn5a.xn--p1ai/img/dogovori/price.pdf

## OCR and visual limitations

Both PDFs are scanned, with no usable native page text. The completed Actions run performed bounded OCR on **all8pages**, preserving exact machine output, page identity, hashes and confidence metadata. No hand-corrected numeric answers were inserted. The PDF content hashes are:

- Медпомощь24: `947ed0bd1937497829c76b5aae6dbd066c7d39565e7eeda9d3e74688215dba27`,909709bytes,2pages.
- Энергия Высоты: `49fa999abc77fe87f1205ec5dea8859a6c9ac8dc1c28071f3c0463c6f4494462`,1549427bytes,6pages.

All8pages were locally rendered from those actual archived bytes and inspected during recovery. The clinic PDF is a list of services excluded from discount cards. The price document contains multiple separate tables, VAT columns, adult/child and weekday/weekend scopes. OCR has visible character and table-order errors; numeric-confidence minima include0on price page5. **Zero extraction errors does not mean perfect transcription or reliable table relationships.** Titles may follow imperfect source labels, e.g. `прейскурантом.`; search by partner and retained condition text as well as title.

The two exact online PDF URLs were also tried with the web reader during recovery; it returned cache-miss/502, so no web-renderer verification is claimed. This is not a GitHub source-access failure: the actual GitHub run obtained the PDFs. No OCR was repeated during this independent recovery check.

## Independent destination validation

Destination remains `1uFR7croj7p6RRNPcoTRYlVl06hKsurkIgyu1IdMMB-4`, title **скидки**. Native metadata, five new IDs/types, all five hashes/times/run markers, source report and manifest were read after completed publication. A fresh read-only XLSX export was then checked without evaluating formulas or editing the workbook.

- **139 source/report fields matched**:5records×25managed fields +1report×14fields.
- New rows2520–2524 and report1396 match the actual normalized bundle exactly.
- All **3171 common records**, their current benefits/conditions/costs/codes and the audit were independently recomputed from the exported source tables; **341742 common-view fields matched**. The selected five rules each have one condition and no automatic benefit/cost/code.
- Manifest: **verified/current;2523 retained parser records /3171 unified records**.
- Fingerprint: `e6f62a394235d602aed821f72e9650541b08374544a9f7fbc925ebfb0c014671`.
- Generation: `a6abc1ce22f38870fb68758bf0fec89aa22c0a13748a978fdb6898750b4f8195`.
- Read-only export SHA256: `d5fc0b50e9e5365731e4380446a7b7beb86071bcfa706774bfa44d5124cb83a2`.

There is no independently available pre-EKP-write export in this recovery. Therefore no new claim of full pre/post preservation across PR50/51 is made. The five records and every current common projection are verified; old catalogue dates are not promoted. The private XLSX export is not a public artifact or deliverable.

`artifact_tool` import was interrupted after60seconds before returning a workbook/preview. Native style samples and exact values were checked; no rendered whole-Sheet layout audit is claimed. No restyling or permissions change was made.

## Executed code and operation

Main test artifact **10516716410** SHA256 `403df84a910f141cb0598a5283f37e20e4d537b0b9705718bb0f36bd3d5d33f2`; public source artifact **10515979088** SHA256 `23d1672b5b33fe2ddab6b2741bdb0fa849fb1dc3a6257689637a408a3a755270`. ZIP CRCs/digests checked; the exact executed code and all normalized records were replayed/schema-validated. Replay supplied the historical completion clock explicitly: this is evidence reconstruction, not a new source observation. Executed suite: **862Python tests and7KEY tests**, no reported skips.

Schedule: **Tuesday07:43UTC /10:43Moscow**, existing GitHub and Google WIF. The verified source run charged **162 existing ScrapingAnt credits**, with173reserved. Bound400credits/run,12files,40requests,720seconds. Adding at most five such runs to the preceding6454/31day ceiling yields **8454credits/31days**, excluding manual debug, other account usage and future tariff changes; it is not a fresh balance measurement. No paid service, extra account, server or Google scope was added.

The destination ACL was last inspected as anyone:writer and has not been changed here. Authenticated-only terms, sessions and personal coupons remain outside this public publication path. RZD's8full-detail gaps, EKP's110gated cards, geographic equivalence and further external-rule traversal remain unresolved; none is declared technically impossible.
