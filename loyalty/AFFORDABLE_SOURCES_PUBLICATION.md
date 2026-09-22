# PR78 — three public sources published and independently verified

Completed on **22 September 2026**. This supersedes the pre-publication boundary in **AFFORDABLE_SOURCES_ACCEPTANCE.md**; that document remains the detailed source/diagnosis/test record.

## Release and actual executions

PR **78** merged at **2026-09-22T14:38:01Z**, merge `fd9088e26056bfdb81e0443e23bb4f89040e8de8`, reviewed head `b9cae3cd6fbe6b8be6798e3ab736be52ef2cc04c`. Merge status was independently read back. Final verification **35741126878**, execution `076234622dc459f5bc5ec2e090a9bcca7c856240`, succeeded with **1174 Python + 7 KEY tests, no skips**, exact replay of 194 earlier actual records and two repaired actual DOM excerpts. Since that successful verification, only documentation and removal of the temporary workflow changed before merge; production bytes were unchanged.

The established `[skip ci]` merge convention avoided only the unrelated Aeroflot push crawl. The actual selected-source main runs executed the full regression again; no required check or scheduled job was disabled.

| Actual main run | Execution | Source observation UTC | Result |
|---|---|---|---|
| **35741823411:1** | `f6b7611592a51e1ca40db2bdce0a70118ce86d0b` | **2026-09-22T14:40:54.396113+00:00** | Backit **175**, Mantera **5**, each zero errors. Avolta returned **403 / zero records**. The successful sources were published; the failed Avolta observation remains in coverage history. |
| **35743159469:1** | `d8c5cbe7c41fe9fb18f2e768553796f4e25b7d13` | **2026-09-22T14:53:47.327804+00:00** | Avolta alone: **16 accepted / 17 listed**, zero errors. Published successfully. No repeated Backit/Mantera crawl. |

Collection/publication jobs respectively: **106793265197 / 106796469655**, then **106798575302 / 106799524857**. All four completed successfully and included the actual payload validation and final destination readback. A green collection job was never used to claim all source reports succeeded.

The Avolta recheck was one independent run of the same public browser code, without changing headers, authentication, TLS, proxies, access-refusal checks or provider settings. Its success after the earlier403 shows intermittent access; the renderer change is not a demonstrated permanent cure. Do not repeat speculative anonymous routes or call reliability guaranteed.

The two source times remain distinct. No historical artifact was relabelled as a fresh source observation and no mixed-time synthetic bundle was published.

## Accepted scope

**Backit:** **916 unique public shop listings across23 pages** were accounted for: **175 accepted**, **741 excluded** (677 explicitly temporarily disabled;50 financial/acquisition ads;13 dated promotional rates needing separate confirmation;1 detail replaced by the catalogue). All189 eligible detail attempts were accounted for without errors. Native IDs, customer/order scopes, fixed RUB values, percentage ranges, zero-rate restrictions and public literal coupon clauses are preserved. Cash after merchant confirmation is not an upfront discount. Product-level marketplace listings are outside this collector.

**Club Avolta:** six source-linked Russian categories contain17 cards: airlines4, hotels1, lounges2, lifestyle6, car rental3, food1. **16 are accepted**. DragonPass remains excluded because the same source page contradicts itself about admission price. Country, tier, activation, frequency and new-user restrictions remain in practical text. A discount on a paid lounge pass is not free access. Account eligibility and booking availability were not checked.

**Mantera Moments:** all **five public FAQ tiers**, with separate bonus earning and redemption-cap benefits. The pilot/accommodation-only restriction, registration before booking, qualification window and source conflict between calendar/business accrual days remain. This is not five hotels or all businesses in the group. The participating-hotel list behind the account was not read.

The existing cleaned-reader quality layer stays active. Source-disabled listings, bank ads, unresolved date/price conflicts and empty technical observations are not added as usable reader offers. There is no raw-text return switch.

## Independent destination audit

Destination remains **скидки**, spreadsheet **1uFR7croj7p6RRNPcoTRYlVl06hKsurkIgyu1IdMMB-4**. A genuine private export was captured before publication, a second after the first successful publisher, and a third after the Avolta publisher completed. The final export reported modification time **2026-09-22T14:57:26.124Z**; this is metadata, not an asserted exact readback completion time. Native CellData was also reread after publication.

| Check | Verified result |
|---|---|
| New accepted source/reader records | **196 =175 Backit +16 Avolta +5 Mantera** |
| Parser records | **2811 ->2991 ->3007** |
| Current common records | **3459 ->3639 ->3655** |
| Clean working reader | **2845 ->3025 ->3041**; all196 new IDs accepted, zero reader exclusions |
| Current common components | **4345 benefits,10715 conditions/costs,742 code/delivery components** |
| New common components | **357 benefits,387 conditions,2 code components**; not counts of unique usable discounts or literal codes |
| Source rows | Backit **2840–3014**; Mantera **3015–3019**; Avolta **3020–3035** |
| Source history reports | **1987–1990**; includes the real failed Avolta observation followed by success |
| Exact new source/report managed fields | **4956**, matched both actual main payloads |
| Exact new common managed fields | **19558**, independently recomputed from actual stored source cells |
| Exact new clean-reader fields | **3332**, independently recomputed |
| Final visible reader | All **3041 rows /42574 fields** matched the cleaned catalogue |
| Preservation | All previous source values, manual annotations, source row positions and previous reader semantics preserved; old common fields changed only in the expected generation column |
| Original formulas | **8 preserved**, no formula errors |
| Visibility/UI | Existing sheet visibility preserved; only Скидки and О таблице visible; native search and programme-list formulas/readiness checks remain functional |

The initial preservation pass checked94795 old stored source/history/archive cells and372930 old common semantic/manual fields. The second pass checked preservation again including the180 already-published records. These are field checks, not unique discount counts. Blank styles, workbook byte size and exported cached formulas are not record counts.

The source-input hash audit initially represented blank cells as `{"value":""}` and omitted the blank manual column, unlike actual native CellData. That local audit helper was corrected to reconstruct the exact26-column input shape with empty atoms. Every managed common field, including the original-input hash, then matched. No Sheet value or production code was altered to satisfy the helper.

Google's XLSX export rewrites spilled UI results into DUMMYFUNCTION/cached-value formulas. Those are not the native user-entered search formulas; native CellData was used for the UI formula/check controls instead. A whole-workbook rendered-layout or ACL audit is not claimed. All private exports remained local and are not committed or attached to public artifacts.

The genuine pre-state was2845/3459/2811, not PR77's older2852/3448/2800 checkpoint. Later scheduled observations/date evaluation had already changed the workbook; they were preserved rather than restored to old chat counts.

## Payload and code identities

- Main180-record artifact **10701165081**, `loyalty-public-35741823411-1`: ZIP SHA256 `d964fbe59096b5cf0e0e5857c2c29a82d93ca5159f4f28ceaed1bc4e5b7904c3`; original normalized.json SHA256 `044ba979a0728ec9cdbc699247c7ebfaac079df4af27b792f097cd470cdd5dec`.
- Avolta16-record artifact **10701106399**, `loyalty-public-35743159469-1`: ZIP SHA256 `cb3c8c1f87ef4cbb5eebe366c4ec17d7fdbddc3f7ecad8a177f2d75129ed56aa`; original normalized.json SHA256 `e1f4b62c46164fc79e1cb355d9e8a63f89545094a68e74854195c824a78f81e9`.
- Final accepted regression artifact **10698879206** /run35741126878: ZIP SHA256 `cb311e3c9d9297a87eb9a46e93bb43288e6e1068dde636cd4eeb9b5b36bca7a9`.
- All ZIP digests and CRCs independently verified before reading. **All78 Python file hashes** in each actual main source manifest match the final accepted regression bytes. The JSON source registry was independently read at exact execution commit; blob **aa037312868e30e3b2bec922b439fa3135ec034d** also matches the accepted file.
- Private read-only audit's shareable aggregate report SHA256: **79cfb614226f669a685acae4e4b130261b21d6567a140631a8c2850ce574bed8**.

Final verified generation: **e9277e88481797fda9b832b28d11ff6a9854d95c1ac33973d19a59ab7d6043b2**.
Source fingerprint: **f933de10fde83e3c7cfeb52f9878d582dab047b8fea7868064e0249493237423**.
Reader digest: **3f1ddbc5f7fbb54328aa6549502350306b0d265153d7dde967e6c635a8e707bd**.

## Continuing operation and limits

All three sources are registered in the existing **daily05:23UTC /08:23Moscow** job. The actual controlled runs of that workflow succeeded; the first future timer-triggered run with these new sources has not yet been observed. No extra recurring task, server, paid provider, Browserbase dependency, source-account login, activation or purchase was added. Temporary diagnostic workflows/helpers were removed before merge.

Avolta remains intermittently accessible. Existing upsert semantics preserve the last successful source rows when a new read fails; they do not prove continued current validity. This release does not implement a general disappearance/retirement engine. In particular, a previously stored Backit card excluded in a later read can retain its older observation: compare observation age and source reports before claiming current availability. Dated promotional Backit rates and DragonPass's contradictory price remain unresolved exclusions.
