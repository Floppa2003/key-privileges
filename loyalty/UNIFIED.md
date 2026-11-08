# Common normalization of all stored data — 1.0.3

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
as new formulas. Record IDs from the public input are unchanged. Populated
`parser_offers` and `parser_inbox` rows must have a nonblank string ID; missing,
numeric or boolean IDs fail before publication and never acquire a row-based ID.
Legacy IDs are
explicit **sheet-plus-row locators**, not vendor IDs or permanent business
identities; sorting those source rows changes their association. Do not use such
IDs for an external permanent offer registry without a separate identity design.

Populated public start/end date columns and recognized explicit legacy intervals
must contain valid dates. Malformed endpoints fail instead of becoming missing
bounds. Free-form legacy validity text can still remain unknown and is preserved.
Timestamp conversion validates the complete value and retains its source calendar
date without a timezone conversion. An explicit normalization `as_of` must be a
calendar-valid `YYYY-MM-DD` string; only an omitted value defaults to today's UTC
date. An explicitly empty or otherwise invalid value fails before publication.

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
- literal denials, spending, account balances and certificate face values vs
  neighbouring earned points/miles; recognized prefix/postfix actions own their
  quantities, including an intervening purchase stage and shared amount lists;
- amount vs purchase minimum, reward cap and rate denominator;
- lower/upper range bounds, exact vs up-to rates;
- literal code vs SMS/app/account delivery; parenthesized code labels remain scope;
- an audience-scoped code is not duplicated as an unrestricted code;
- actual published interval vs source observation vs normalization date;
- reward lifetime, qualifying period and status duration are not offer expiry;
- a gift-card exclusion is not a complimentary gift.

Literal reward quantities preserve word/dash ranges and lower/upper bounds.
Recognized positive bonus/earning wording and `+` amounts do not discard their
units. A stated exchange/purchase/period denominator is kept literally (for
example, 20 miles per 500 points); a malformed/nonpositive explicit denominator
does not become a bare award. Bare monthly/day maxima and parenthesized reward
limits are conditions, not an additional guaranteed award. No exchange value is
calculated. Reference quantities do not create earned rewards.

Bounded postfix labels such as `10% (постоянной скидки)` own their percentage,
without also labelling a neighbouring payment/tax percentage. Discounts,
cashback and gifts retain local denials; product exclusions and restrictions on
paying a gift's cash equivalent do not erase the positive component. A plural
predicate can deny a mixed list, while a singular predicate remains local.
`комплементарная` alone remains ambiguous and is not a typed free gift.

First/repeat purchase scopes belong to their literal benefit component, including
mixed discounts, gifts and reward quantities. A clearly shared prefix can scope
the bundle; a sibling's tail cannot. Denominators and parenthesized caps remain
children of their owning component. An explicitly excluded purchase stage is a
rule, not an affirmative scope. The original clause stays intact as evidence.

`condition_ids` binds only the same exact evidence or explicit equal nonempty
scope, excludes explicitly incompatible first/repeat stages, and restricts local
reward caps to their owned benefit even when sibling stages are identical.
Other parent rules still apply and are not expanded into invented logical
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

The reader catalogue excludes explicitly chance-to-win campaigns, including
`шанс выиграть` and `шанс стать одним из ... обладателей`. Their campaign record
and source evidence remain auditable; they are not guaranteed ordinary offers.
The bounded check covers the owned benefit, conditions and activation fields,
without scanning unrelated nested source text.
Promotional use of `шанс` alone does not hide a stated discount for every participant.

## Changing numerical terms in supported source formats

Source adapters read current literal numbers instead of pinning previously seen
values. GPB notification fees retain the stated starting month and decimal amount;
the old after-first-month alias exists only when the source says month two.
Student eligibility keeps its stated calendar-valid day/month and relative next
academic year, without inventing an absolute offer expiry.

Alfa partner PDFs retain the exact operative percentage, literal reward cap and
payout days. A headline saying **up to** is an upper bound, not the operative rate;
the body may state a lower rate but cannot exceed that headline. Generated titles
use the operative rate. Invalid numeric tokens, ranges presented as an exact rate,
and contradictory clauses still stop that source adapter.

For reviewed retail-mileage rules, common projection rederives discount/delivery
treatment from the retained literal redemption evidence. Both benefit scope and
linked condition use that interpretation; cached old metadata cannot override it.
A complete basis requires explicit, unambiguous treatment of both discounts and
delivery. The raw source record stays unchanged.

The reader preserves flight qualification clauses when their count changes,
including worded counts. Campaign completion has no fixed year list: an owned
completion statement or complete unambiguous end date is required; a start-only
date does not prove expiry. The stated end day remains included. Unrecognized or
conflicting free-form dates remain unknown, including a conflict with the
published structured interval. An explicit early-closure statement overrides a
scheduled future end date.

Payment/prepayment percentages remain conditions at any amount. A nominal price
does not establish a benefit by being exactly one ruble: the supported reader
forms require an owned positive code activation or an explicit first/trial
subscription period. A purchase minimum alone is insufficient, and a sibling
discount's code does not establish another price benefit. No savings amount is
calculated from that promotional price. These are bounded source/phrase rules,
not a claim to understand every possible wording.

Version 1.0.3 changes the derived generation even for identical stored inputs and
the same assessment date, so corrected interpretations can be republished without
pretending that source observations are new.

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
