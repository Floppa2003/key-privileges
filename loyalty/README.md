# Normalized public loyalty collection

The current pipeline is v2: `collect_normalized.py` -> `normalized.json` / `offers.jsonl` -> `sheets_normalized.py`.

- [Data contract and source-specific routes](NORMALIZED.md)
- [Machine-readable offer schema](offer.schema.json)
- [Registered source routes](sources_normalized.json)
- [Daily schedule, manual runs and coverage objective](OPERATIONS.md)

Each record keeps a stable ID, program/partner, benefit, conditions, redemption text, lexical rates and promo codes, source dates/status, actual detail URL or shared-page locator, source-specific tables/fields, observation time and integrity hash. Normalization is **not** automatic confirmation of eligibility, current availability or a combinable final price. Unknown dates remain unknown; inspect conditions text too.

## Running

```sh
python -m pip install -r loyalty/requirements.txt
python -m unittest discover -s loyalty/tests -v
node --test key/refresh.test.mjs
python -m playwright install --with-deps chromium
xvfb-run -a python loyalty/collect_normalized.py --limit 500
python loyalty/sheets_normalized.py --input loyalty-output/normalized.json
```

The last command is a dry run. On trusted `main`, changing the unique request ID in `loyalty/request.json` dispatches the configured workflow with publication enabled. The workflow preserves the existing WIF/service-account setup and destination secret; no additional user authorization or long-lived key is required.

## Destination and operation

The public publisher updates `parser_offers` (A:Y managed; Z manual comments) and `parser_coverage` (A:N managed; O manual). The subsequent private normalization stage updates the common normalized views in the same spreadsheet. Curated benefits, source audit, Yandex/VG and the old `parser_inbox` / `parser_runs` remain untouched. The old `collect.py` / `sheets_sync.py` v1 entrypoints are retained for compatibility, not used by the current scheduled workflow.

Writes are literal, ID-upserted and read back. Failed/missing source observations never delete or expire old offers; consumers must check latest coverage and row observation times. Green workflow status means the pipeline ran, not that every registered site was fully collected.

Mir uses the anonymous JSON POST filter API: the page number is in the request body. The public SBP/Mir switch is observed, both accessible catalog profiles are traversed and overlapping offer IDs deduplicated. Counts are regional and profile-specific, not an all-Russia/personal-account total. Later-page failures retain earlier-page evidence.

The independent KEY collector remains unchanged. The public repository/artifacts must never contain spreadsheet exports, destination IDs, Google tokens or personal browser sessions. Artifacts expire after seven days. Following explicit authorization on 2026-09-15, collection runs daily at 05:23 UTC in this repository. The old `LOYALTY_SCHEDULE_ENABLED` opt-in condition is no longer used; the separate existing `LOYALTY_SHEETS_SYNC` publication guard remains. Disable the workflow in Actions to pause it. See `OPERATIONS.md`.

Source access is variable; some registry entries remain probes rather than implemented parsers. Do not infer catalogue completeness from the number of registered routes or from a successful CI badge.
