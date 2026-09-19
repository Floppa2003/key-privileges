# PR72 publication — completed and independently verified

This supersedes the pre-publication boundary in **ALFA_PUBLIC_FRONTIER_ACCEPTANCE.md**. The implementation, source semantics, failed temporary-helper diagnosis and still-unread app/PDF-discovery boundaries in that file remain applicable.

## Exact execution and destination

PR **72** merged on **19 September 2026 at 12:22:38 UTC**, merge commit `a2c74317d2be23390d47839597d1cae50ff17040`, reviewed head `af700c581227a719b1341f35f2f06e6766b77779`. Its merge message used the documented `[skip ci]` convention only to avoid the unrelated Aeroflot push-triggered collector; no schedule, permission or workflow was disabled. The complete tests had passed twice on unchanged production bytes and ran again in the actual main publication.

The existing request mechanism was updated at `a40d90fdb9592fce24ae8b503c28bf31fd52f129` to select exactly **alfa_only_tsum, alfa_only_announcements**. Request run **35442705854** dispatched main **35442711304:1**, executing that same commit. Collection job **105896213574** and publication job **105896452590** both completed successfully, including the full Python/KEY regression, schema dry-run, source upsert/readback and common-view publication/readback steps.

Actual production observation: **2026-09-19T12:24:37.237375+00:00**. Both sources were `ok`, with **2 TSUM + 18 announcement records and zero source errors**. This is a fresh source observation, not the earlier verification artifact relabelled with a new timestamp.

Destination: **скидки**, spreadsheet **1uFR7croj7p6RRNPcoTRYlVl06hKsurkIgyu1IdMMB-4**. Independent native-cell reads showed the correct TSUM Orange/Black loyalty currency, tier scopes, linked full conditions and activation. An intermediate read observed the expected manifest `publishing` state; it was not called complete. A fresh export obtained after the successful publisher completed independently confirmed `verified/current` and the final values below. Its reported modification time was **2026-09-19T12:28:30.713Z**; that is the file modification time, not a claimed exact final-readback timestamp.

## Independently checked results

| Check | Result |
|---|---|
| Parser records | **2621 -> 2641**, exactly 20 new IDs; no pre-existing ID collision. |
| Current common records | **3269 -> 3289**. |
| New parser rows | **2650–2669**. |
| New source reports | **1632–1633**. |
| New source/report managed fields | **528**, all matched the actual main-run payload exactly. |
| New common-view managed semantic fields | **1436**, all matched independent recomputation from actual source rows; generation checked separately. |
| Current common components | **3817 benefits; 9950 conditions/costs; 714 code/delivery rows**. |
| Previously stored source/history/manual content | All nonempty pre-existing cell values/formulas at their original positions preserved across the compared exports. |
| Existing common-view semantics | All previous managed semantic fields unchanged apart from expected generation values. |
| Formulas and archive | **Eight formulas** preserved; hidden archive remains hidden and its stored cells unchanged. |
| Normalization generation | Every current row in all four common views matches the verified manifest. |

The twenty new records contribute **20 common benefit components, 31 condition/cost components and one code/delivery component**. Counts are not unique merchants, independently usable discounts or literal coupon strings. In particular, the eighteen public announcements retain current-validity/eligibility uncertainty and may overlap the guide, bank PDFs, earlier announcements or other merchant evidence.

The preceding PR71 checkpoint's 2620/3268 was not reused as the pre-state: the independently obtained before export already contained a later Mir MEOLLO observation and **2621/3269**. That record and all other old records remained intact.

The read-only audit compared a genuine before export with a fresh after export. It did not write the workbook, infer a private bank balance, audit ACLs or perform a whole-workbook rendered-layout inspection. Blank styles and export file size are not record counts. Private workbook exports and their complete contents remain local, not in the public repository or deliverables.

## Payload and code evidence

Production artifact **10583679473**, `loyalty-public-35442711304-1`:
- ZIP SHA256: `cbe10e31c80516730d2578141fe8057f5b2fdd7cd2b0290cdd17d062f3f928c2`.
- Original `normalized.json` SHA256: `f7e306980fdbf5e2adea5da5bd60f3d668d51b019daeddc37b12fd0521d2fc5c`.
- ZIP digest and CRC independently verified before reading the payload.
- All five changed/new production Python hashes match the successful verification. The two JSON config files are outside the collector's Python-only hash manifest and were independently read from the exact execution commit: `partner_pages.json` blob `4e4e45320aab35d4bd119782f7e5965123af2879`; `sources_normalized.json` blob `ae7c3c56523e2a3b9f630c545a1da90c254a2168`. Both match the reviewed bytes.
- Local read-only audit result SHA256: `5b91de45de631d8d875427f6c6ff737a9d0c701d370d65b399669473b78e1e37`.

Verified source snapshot fingerprint: **589adf3a346b3835ddea29df28bffa130a07713a8e512a5a5b9604f205b73507**.

Verified current normalization generation: **3df875fa34a6f4f8cad24b5a01781c6d086a431caa82eec20541123362c2482b**.

## Remaining limits

This release is public-source expansion, not completion of Alfa banking/app access. The exact bank partner-offers catalogue and Only Assist discount feed remain unread; the generic Konsierge directory was not silently relabelled as Alfa Only. The channel's bank-publisher attribution was not independently established by the extra bounded search; its rows remain unverified announcements. Automatic discovery/migration of new Alfa PDF revisions is still pending. No source-specific authenticated session, paid provider or new schedule was introduced.
