# Scoped table discounts and partial-result retention — 2.3.3

This repair keeps schema version 2, stable record IDs, source URLs and the existing Sheets layout. It does not enable inaccessible sources, retrieve personalized codes, activate offers or change Google authorization/scheduling.

## Structured table benefits

`details.table_benefits` contains `components` and `issues`. A component carries an exact source scope (`card_type`, `room_type`, or `promo_code`), a numeric percent discount, any literal code in the same source row, and full header/row evidence with zero-based table and row indexes (header row = 0).

```json
{
  "scope": {"kind": "card_type", "value": "Серебряный"},
  "rate": {"kind": "discount", "value": "7", "unit": "percent", "qualifier": "exact"},
  "promo_codes": ["КРЫЛЬЯ10"],
  "evidence": {
    "table_index": 0,
    "row_index": 2,
    "header": ["Тип карты", "Скидка", "Промокод"],
    "row": ["Серебряный", "7%", "КРЫЛЬЯ10"]
  }
}
```

The example is the published Gorskiy row in the reviewed source snapshot: the code's digits do not determine its discount. Room categories remain room categories; color names inside coupon strings do not create membership tiers. Different source tables are not joined by row position even when values appear similar: booking channels and surrounding conditions can differ.

The parser accepts only explicitly recognized discount/scope headers, rectangular text rows and a whole-cell percentage (exact, `до`, `от`, or a bounded range). Missing cells are not shifted/forward-filled. Unknown headers, extra unrecognized columns, compound percentage clauses, invalid ranges and missing scope labels create an issue rather than a guessed component. An unrelated hotel-amenities table is not a discount table. Instructions such as `Получить в приложении` are not literal promo codes.

Global source conditions and eligibility still apply. These scoped rates are deliberately not copied into the unscoped top-level `rates` list. Source text and raw tables remain authoritative. Component count is not a count of unique or current discounts. The publication validator recomputes components/evidence from the original tables and rejects mismatches even after a record is rehashed.

Google Sheets: existing column U (`Детали JSON`) carries `table_benefits` alongside raw `tables`, coupon evidence and other details. No column is inserted or shifted. The JSON/JSONL record has the same object under `details.table_benefits`.

## Read-budget repair

S7 and RGO detail reads now consume the remaining source deadline while reserving five seconds for returning completed records, validation and browser cleanup. A stalled later HTML/PDF read is cancelled at that boundary; earlier collected records are returned as a partial result with a diagnostic, rather than being discarded by the outer source timeout. A leaf read timeout is not mislabelled as the whole-source deadline. Expired budgets do not start another read.

Both detail loops stop starting further card requests after HTTP 429. The failing/current and remaining selected cards are counted in the stop diagnostic. No retries of access challenges, authentication failures, certificate errors or rate-limit responses were added.

This is a bounded fix at the S7/RGO detail-read seam, not persistent checkpointing for every adapter or immunity to process termination, arbitrary parser stalls, pagination failure or browser-cleanup failure. Mir retains its separately tested 2.3.1/2.3.2 response identity, freshness and transient-5xx handling.

## Verification

On the exact same 727 observations from main run `34752196066:1`, table normalization yields **96 scoped components across 29 records**: 90 card-type, 3 room-type and 3 promo-code components. One unrelated Atrium amenities table stays unparsed with an explicit header issue. Raw source text, tables, IDs, URLs, coupon lists, top-level rates and observation/validity times remain identical. Only adapter version, the added structured detail and consequent content hashes change. This replay is not uploaded or relabelled as freshly collected data. Maximum prepared cell length in the replay is 7,481 characters.

Twenty-two added regression/nonregression tests cover source-row associations, qualifiers, missing/shifted columns, invalid percentages, rehashed tampering, code-delivery instructions, in-flight cancellation, preservation of prior S7/RGO records and terminal rate limits. New broken behaviors were observed before the fixes. All **221 Python tests and 7 unchanged KEY tests** pass locally.

Fresh branch run `34753714434` passed tests, collection and payload preparation: 727 records, 45 source reports (37 ok, 8 failed), 96 scoped components in 29 records, 97 code-bearing records. Artifact `10316509338`, SHA256 `41178b2c9762984b9c7acd614de537f021f54264063b3075a6037fcf83edea58`, was independently downloaded. All eight changed implementation/test file hashes and every runtime module hash match the locally tested bytes; every record passed JSON Schema, application integrity and publisher validation. This confirms live nonregression; controlled stalled-read/rate-limit tests, not this ordinary successful collection, prove the recovery branches.

The recovered 2.3.2 production publication was independently read back before this repair: 727 fresh rows and 45 reports matched all 18,805 managed cells; 729 retained IDs and 247 historical coverage rows. The private export is the before-snapshot for 2.3.3 verification, not a public repository artifact.

## Remaining source-access limits

Two additional fresh GitHub VM inspections (`34753133943`) timed out at EKP robots navigation before returning any catalogue/API objects. No speculative EKP adapter was registered. Its earlier one-off successful catalogue observation remains evidence of possible access, not a complete or stable contract. Nordwind/Coral/RZD/Aeroflot/Loyals and the old Utair URL retain their diagnosed limitations. The user-controlled desktop was still offline during this pass; no new Russian server or network exit was provisioned.

Existing source coverage warnings, six unrelated sheets, manual Z/O columns, production workflow/auth, KEY code and disabled periodic schedule are preserved. Temporary patch-transfer and branch-test workflows are removed before merge. Verify a fresh authorized main run and independent Sheets readback before claiming publication of 2.3.3.
