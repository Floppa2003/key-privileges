# Coral linked rules — completed source-to-destination acceptance

## Released result recovered and independently checked

This record completes acceptance of PR46, merged as `1ca2d9feac63e41894633fa371f302cd72595bf9`. Interrupted chat responses did not mean the implementation was absent: existing main code, the actual run, artifacts, destination cells and private read-only export were inspected before further work. No parser implementation was rebuilt during this acceptance.

Trusted-main run **35151106847:1** completed regression, collection and publisher **104984030525**; every job and publisher step was independently read as completed/success. Source observation interval: **2026-09-16T21:14:49.441113+00:00 to 21:27:40.195702+00:00**.

| Scope | Candidates | Accepted records | Verified ordinary products excluded | Final errors |
|---|---:|---:|---:|---:|
| Club sitemap URLs under 20 current categories |101|65|36|0|
| Current promotion-index URLs |23|23|0|0|
| Rules linked from those fresh records |6|6|0|0|

**94 records were published: 88 existing offer/campaign/information identities updated, six new supplementary rule identities added.** This is not 94 new discounts, nor proof of complete current interactive-catalogue membership. Six linked rules are conditions, not incremental monetary benefits.

## Six rule documents

| Source document | parser_offers row |
|---|---:|
| Порядок оказания услуг в аэропорте Внуково |2469|
| Порядок оказания услуг в аэропорту Шереметьево |2470|
| Правила и условия использования подарочного сертификата |2471|
| Правила оформления заявки в бизнес-зал |2472|
| Правила оформления заявки в бизнес-залы Golden Key |2473|
| Правила от 22.06.2026 г. |2474|

The documents are discovered through current parent condition-block links, not a checked-in list of today's URLs. Each retains parent record IDs, source URLs, content hashes and link labels. Heading-owned text and tables are preserved; navigation, unrelated forms and footer content are not substituted. The common model projects one source-linked condition for each document and zero benefits, costs or codes, avoiding false discounts from refund/penalty percentages or example codes. Effective dates are not invented as offer validity dates.

## Retry behavior was exercised in the actual source run

The separate accepted retry run35144714199 had succeeded entirely on first attempts. Unlike that run, **35151106847:1 contains one genuine retry**:

- Target: `https://coralbonus.ru/promo/urovni-bonusnykh-kart-2026/`.
- Initial result: `cg_import_timeout_or_error` at21:26:35.951683UTC.
- Retry began at21:27:05.951815UTC after the configured30-second delay.
- A new successful observation completed at21:27:09.989220UTC and was included in the verified publication.

There were135 import attempts and134 successful observations, zero final source errors, verified scratch cleanup, zero source-account use and zero ScrapingAnt credits. This confirms one real transient failure was recovered; it is not a statistical long-run reliability guarantee. Retry remains limited to recognized public-detail import failures, one retry per failing read and12 per run, within the existing164-import/2700-second bounds. Quota/permission errors, changed formulas, coercion and failed cleanup are not silently retried.

## Source and destination verification

Downloaded archives were checked against GitHub-provided SHA256 values and ZIP CRCs:

| Artifact | ID | SHA256 |
|---|---:|---|
| Public production |10469224109|699213e1d15026a85535fcf870ae1a8b859b5330801f0dc02a7792a2cfd6b551|
| Main executed code and tests |10469655299|26541653aaf1d2719c14965f0ae793e72b250b83cc0a887515af89ff3e369d7a|

The main test log records **779 Python tests and7 KEY tests passed**, without skips. The entire public record set was independently reconstructed using the archived executed code: current category/sitemap candidates,36 merchandise exclusions,88 parent records, six discovered rule links and all six rule records. Every record passed JSON Schema, application validation and production publication preparation. Actual GitHub collector/publisher jobs passed their full policy/bundle validation; no local substitute policy module was injected.

Destination remains `1uFR7croj7p6RRNPcoTRYlVl06hKsurkIgyu1IdMMB-4`, title `скидки`. After the last publisher completed, a read-only export was compared with the prepared payload: **all2392 managed fields matched** (94 records ×25 fields + three reports ×14 fields). The comparison preserved2379 non-incoming parser rows, all manual-comment values and values in the six other original input/audit tabs. No private workbook export was committed or included in the public evidence package.

Additional native readback verified:
- `parser_offers!A2469:F2474` and `W2469:Y2474`: all six rule IDs, titles, record kinds, hashes, dates and run markers.
- `parser_coverage!A1285:I1287`:65 club/23 promos/6 rules, each `ok` in its declared scope, with zero final errors.
- `normalized_records!S3117:V3122`: each rule has0 benefits,1 condition,0 costs,0 codes.
- `normalization_audit!D7:J7`:**verified/current**, **2473 retained parser records /3121 unified records**.

Checkpoint source fingerprint: `1c313abaeec99be470d5c25ddad914c8480f2baccfbb36d7198ab99f7cca3169`.
Checkpoint generation: `c3ca4950b324976037e326cd320941ebf260492c689615efea987f64c737cdc3`.

This verifies faithful extraction/transfer within the supported layouts, not the legal validity of every clause or user eligibility. No full-workbook rendered/style audit is claimed. Later valid publications may change the aggregate checkpoint.

## Further public-document investigation, not a release

The freshly read gift-certificate and programme rules link to two same-host PDFs. A new isolated GitHub diagnostic, run **35155071145**, executed commit `f783c14931567c5ad086758588e53a16c96b684a` on `diagnostics/coral-linked-pdf-20260917`. It made one ordinary TLS-verified, non-redirecting GET to each exact discovered PDF, without a provider key, Google identity or source account. **Both returned actual HTTP403 and HTML, not PDF bytes.** No PDF text was accepted or published. Diagnostic success means the program finished, not file availability.

Public diagnostic artifact10469849291, SHA256 `3851c4d736ae4e2aa1f345ce5872f59d178c311b4b235092423e2a012d6c5c4b`, was downloaded and CRC/hash checked. Its executed workflow and exact request/finish times are retained. No credential/header/cookie payload or failed HTML body was archived. The workflow is branch-only, has no cron, and was not merged into the production collector.

The direct route is unconfirmed for these PDFs; this is not a proof of technical impossibility or equivalence between the PDF and the accepted HTML text. An external search reader returned historical text for one PDF but failed to provide its screenshot/current binary; that cached result was not used for publication. No OCR was run.

A read-only inventory of the previously accepted RZD catalogue artifact also separated26 external-link occurrences into **two distinct external card URLs**, RZD Tour and UniCredit. Their catalogue text is a concrete remaining coverage candidate, not26 separate missing offers. No new RZD source crawl, external detail read or publication was performed in this acceptance.

## Operations and remaining boundaries

Coral Google import remains Wednesday/Saturday09:17UTC (12:17Moscow). Same destination, Google WIF, publishers,164 total imports,2700 seconds and12 linked-document limit. Other collectors, provider quotas and schedules were not changed. This acceptance and PDF diagnostic spent zero ScrapingAnt credits; no new free-balance claim is made.

Seven previously stored Coral pages absent from the sitemap remain outside this path, with the interactive/provider collector retained. Linked PDFs, further external conditions, RZD's eight full-detail gaps and EKP's110 gated observations are not marked complete. Personal eligibility is never inferred from a source's presence.

Destination sharing was independently re-read during acceptance and still shows `anyone:writer`. It was not changed. No account session, SMS, token, issued personal coupon or authenticated-only material may enter this link-accessible Sheet or public artifact path without resolving sharing. `private_complete` is a normalizer mode, not an ACL.
