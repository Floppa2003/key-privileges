# Coral bounded retry release — accepted 2026-09-16

## Recovered completed execution

This acceptance concerns the already released retry implementation at `7f6d275a530616d7e095f9e41db446aca0b858ed`, before the separate linked-rules extension in PR46. Interrupted conversation output was not treated as a missing implementation: actual main code, run, artifacts and destination were checked first.

Trusted-main run **35144714199:1** completed regression, collection and publisher **104961783254**. Every publisher step was read back as completed/success. The source observation interval was **2026-09-16T20:09:09.208871+00:00 to20:19:49.145426+00:00**.

| Source | Selected candidates | Accepted records | Inspected ordinary merchandise excluded | Errors |
|---|---:|---:|---:|---:|
| Club sitemap pages under20 current categories |101|65|36|0|
| Current promo index |23|23|0|0|

There were **88 accepted records,128 imports,zero source errors and zero ScrapingAnt credits**. The museum and Gruzovichkof records that had failed in the preceding pass were freshly updated. No new record identity was added. This is now a single complete successful read of this selected public scope, rather than only the union of two partial runs.

**No retry was actually exercised in this live pass (`retries=[]`).** It confirms the released workflow can complete and publish; it does not demonstrate that retry logic repaired a live transient failure or establish a long-run reliability improvement. Retry behavior is covered by deterministic tests.

## Implemented limits

Only a recognized transient public detail import can be retried once, after30seconds, with at most12 retries per run. Existing164-import and2700-second limits are not expanded. Discovery and robots failures, quota/access refusals, unexpected data coercion, changed formulas and failed cleanup are not retried as transient source faults. Retry timing, unique successful observations and result bindings are checked by the publisher. Prior successful source records keep their original date when no new successful observation exists.

## Independent evidence and destination checks

- Production artifact10467656180: SHA256 `5efc64c29cd1586d43462608c385986eb39ec1f530edccdf194c78626c94176e`.
- Main tests artifact10467165303: SHA256 `012dd7f05aca1b3f555e0aef84d22b70c7de062d7743bcd743c20e86caf5c316`.

Both downloaded ZIPs were checked against GitHub SHA256 metadata and ZIP CRCs. Actual test logs report **764 Python tests and7 KEY tests passing**. The source artifacts and executed code were inspected; no historical page was substituted into runtime.

Destination remains `1uFR7croj7p6RRNPcoTRYlVl06hKsurkIgyu1IdMMB-4`, title `скидки`. A post-publication export was read without changing it. All25 managed fields for each of88 source records and all14 fields of the two reports matched the prepared production payload: **2228 managed fields checked**. The private workbook export was not committed or attached as public evidence.

Native readback confirmed `parser_coverage!A1283:N1284`, museum row1034, Gruzovichkof row1098, and `normalization_audit!D7:J7`. Both reports are `ok` in their declared scope. The common manifest was **verified/current**, with **2467 retained parser records and3115 unified records**. These retained totals are not all freshly observed offers.

Checkpoint source fingerprint:`fa1bb36e9c4cadf527c508edf74490041f3f10af30bacfab5ae2254c14f256eb`.
Checkpoint generation:`b8bf0c3e599e229a109ce297ad7929ee78bde3ea822daa5a5cfd89f5e59dde68`.

A later publication may legitimately supersede this checkpoint; the per-record run and observation time distinguish it.

## Remaining scope

The scope is current sitemap-selected club URLs plus the current promo index, not proof of exhaustive current interactive catalogue membership or personal eligibility. Seven previously stored club pages absent from the sitemap remain outside this path; the existing provider path is retained. Ordinary merchandise exclusions are not discounts. Google import dates denote request/calculation observations, not certified uncached origin downloads; HTTP status and cache age are not exposed.

No source account, personal coupon, purchase, paid service, new API key, extra provider account, Google permission change or new schedule was introduced. Supplementary Coral remains Wednesday/Saturday09:17UTC. Linked rule documents are a separate PR46 acceptance and must not be counted as published solely from this retry run.

Run: https://github.com/Floppa2003/key-privileges/actions/runs/35144714199
