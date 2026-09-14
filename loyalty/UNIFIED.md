# Common normalization of all stored data — 1.0.0

This is a deterministic **source-preserving projection**, not another web scrape,
a new discount catalogue, a personal entitlement check, or a savings calculator.
It consumes all five explicitly supported input datasets in the existing Google
spreadsheet. The other three sheets are control/audit history, not benefit rows.
All eight original sheets are read-only to this stage.

## Inputs and trust

| Input tab | Scope |
|---|---|
| parser_offers | Every retained public adapter record, not just the latest run |
| loyalty_partner_benefits | Every nonempty manual row; old claimed status is not reverified |
| yandex_discounts_complete_all | Corporate offers; private, exact original codes and eligibility wording |
| VG_community_offers | Community offers; private, no membership inferred |
| parser_inbox | Old unparsed pages; evidence-only because neighbouring offers may be present |

The current input schemas are exact and checked. Missing sheets, changed headers,
error cells, duplicate identities and oversized cells fail rather than silently
skipping data. Blank styled trailing rows do not change the input fingerprint.
Numeric legacy discounts are percentages only when their native number format
says so; `0.2` in a plain numeric cell is not silently converted to 20 percent.
Formulas and cached source values are preserved in `raw.original`, never executed
as new formulas. Record IDs from the public input are unchanged. Legacy IDs are
explicit **sheet-plus-row locators**, not vendor IDs or permanent business
identities; sorting those source rows changes their association. Do not use such
IDs for an external permanent offer registry without a separate identity design.

## Common record

`unified.schema.json` describes the JSON record. Every output retains its complete
canonical input in `raw`, including all source-specific details and original cell
values/formulas. `program.key` uses a small exact alias dictionary; other names
get a normalized search label. `partner.search_key` is a Unicode/case/whitespace
search key, not a merged legal/business identity. Original labels and categories
remain present; categories are not invented from a partner name.

Common groups are `benefits`, `conditions`, `costs`, and `codes`. Every component
has a parent record ID, a typed role, scope, a resolvable JSON pointer into its own
raw input, exact evidence text and an extraction method. Numeric quantities are
**decimal strings** to avoid float conversion; units, denominator and range lower
bound are separate. Unknown means `null`, never zero/free/unlimited/false.

Projection priority is explicit source structure, source tables, then conservative
Russian/English clause recognition. Structured amounts keep their audience,
card/tier, option, product or deposit band. Examples of guarded distinctions:

- cash discounts vs cash cashback vs miles/points; no reward-to-ruble valuation;
- earning vs redemption, commissions, subscription prices and minimum cash spend;
- amount vs purchase minimum, reward cap and rate denominator;
- lower/upper range bounds, exact vs up-to rates;
- literal code vs SMS/app/account delivery; parenthesized code labels remain scope;
- an audience-scoped code is not duplicated as an unrestricted code;
- actual published interval vs source observation vs normalization date;
- reward lifetime, qualifying period and status duration are not offer expiry;
- a gift-card exclusion is not a complimentary gift.

`condition_ids` binds only the same exact evidence or explicit equal nonempty
scope. Other parent rules still apply and are not expanded into invented logical
constraints. All terms retain `review_required=true`: this is the context review
needed before application, **not** a claim that every extracted quantity is wrong.
`semantic_completeness=not_certified` is deliberate. The number of unrecognized
clauses is not an estimate of semantic accuracy: descriptions/navigation may also
be counted. Arbitrary text and nested structures remain in raw even when there is
no common typed projection. Native PDF table geometry is not inferred from linear
text. This release does not provide a universal tier/service/limit matrix for PDFs.

Candidate equal-program/label/URL relationships are explicit and unverified. No
conditions, values, timestamps or statuses are copied across records, including
manual/public disagreements. Supplementary rules, announcements and tier bundles
are not counted as independent additive discounts. Source status is retained; date
comparison does not prove current availability or eligibility.

## Five derived Sheet views

| Tab | Row identity / content |
|---|---|
| normalized_records | One record per input row, provenance, dates, counts and quality |
| normalized_benefits | One typed extracted benefit component, amount/units/scope/evidence |
| normalized_conditions | Conditions and costs explicitly distinguished by role |
| normalized_codes | Scoped literals separately from retrieval instructions |
| normalization_audit | Source counts, source fingerprint, publication manifest and limits |

The final two managed columns are normalization state and snapshot fingerprint.
The following column is manual commentary and is never overwritten. Disappearing
**derived** components are retained as `retired_from_normalization` and filtered
out of the current view. This does not delete or expire an original offer. Filter
current rows and the manifest snapshot when consuming views. Counts include
source observations and candidate components, not unique current usable savings.
Raw decimal values are literal strings in Sheets as well; convert deliberately
when doing a calculation and never sum unlike benefit types.

Publication reads all inputs, prevalidates all outputs, rechecks the input snapshot,
writes an unverified `publishing` manifest, upserts derived rows, and reads them
back. It then rechecks the inputs and marks the manifest `verified`; a final read
checks every expected value. Source drift/failure leaves no success claim. Reads
and writes are paced; only explicit HTTP429 quota rejections retry. Network/write
uncertainty does not retry blindly. Sheets has no cross-tab transaction spanning
this entire sequence, and an unrelated editor can still race the final check.

## Privacy and execution

`normalize.yml` runs synthetic tests on the development branch and performs the
private stage only on trusted main with the existing enable flag and Google WIF.
It uses the same workflow concurrency group as the public scraper. A normal
public-scrape publication also runs this stage afterwards. There is no new schedule;
manual/source edits are reflected on the next authorized run, not instantaneously.

**Never upload unified inputs/outputs as public GitHub artifacts or commit them.**
The private job writes no data files, prints only counts/digests and sanitizes error
messages. It does not fetch any URLs found in source cells, retrieve private codes,
activate offers, change Drive permissions or require additional API credentials.
The original public scrape artifacts remain public-only in their separate job.
The optional library public-only projection fails on nonempty manual notes; it is
not exposed as an automatic public-export workflow.

For local private processing:

```sh
python loyalty/unified_publish.py --offline-input input-tables.json \
  --as-of 2026-09-14 --out private-output
```

Input JSON has `sheets`, each a list of typed-cell rows (`value`, optional `formula`
and semantic percent format). For live normalization, use `--publish` with the
existing `GOOGLE_ACCESS_TOKEN` and `DISCOUNTS_SPREADSHEET_ID` environment variables.
Live mode refuses local output arguments. A successful normalization is not a
fresh crawl. Eight unavailable public routes and other missing source pages are
not repaired or filled from memory by this transformation.
