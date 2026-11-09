# Numerical invariance repair — implementation verification

Base: `4b100d5d2adf1e954cf97ee0f68ce7a731732018`. Normalizer: **1.0.4**.

## Reproduced and repaired paths

- Explicit Backit date intervals longer than 93 days; the bound remains for inferred years.
- Complete money/rate tokens and number-dependent unit forms in GPB, iway, X5,
  T2 SIM, Utair Family/Generations, Smartavia, Primbank, Finuslugi and Domina.
- Ural whole flight counts and explicit calendar-year counts; Utair grouped
  thousand-ruble thresholds. Count fields reject non-integral/invalid values.
- Avolta quantity comparisons in source and reader, including changed digit and
  supported Russian word counts, denial and ordinary-price controls.
- Alfa public PDF caps, expenses, delays, participant labels and contact digits.
  Restaurant expenses keep their complete number and unit. Insurance preserves
  all price-table columns, and cashback preserves historical qualifiers in its
  own row. Repeated expense columns do not become a standalone reader benefit.

## Independent whole-branch review

One fresh review of `4b100d5..49f97dd` identified five important findings and no
critical or minor findings. All five were addressed in one material-fix pass:

- Cancelled Avolta bundles remain excluded across source and reader boundaries,
  including cancellation before the phrase, temporal modifiers and spaces inside
  closing quotes. Product exclusions still preserve a valid offer.
- A spaced sign cannot disappear from quantity offers, Primbank earning rates,
  X5 exchange rates or Alfa cashback limits. Explicit table/price separators
  remain valid structure.
- Required field labels are owned before their numerical values are parsed.
  Repeated contradictory or malformed labels in GPB, SIM, Family, iway, Ural,
  Domina and Alfa cannot be skipped in favour of a later convenient value.
- Alfa person, participant and calendar-month bases accept changing counts in
  digits or supported words, preserving the complete literal basis without
  dividing its limit into an inferred per-person or monthly entitlement.
- Finuslugi point/day forms and Primbank mile/welcome forms follow the changed
  number; deposit money retains decimal boundaries while durations stay integral.

The pass added 21 focused regression methods. Native-document replay also caught
and covered a date inside a payout clause being mistaken for a section boundary.
No review findings were deferred and no additional review cycle was performed.

## Deterministic verification

- Baseline: 2,362 Python tests passed.
- Final implementation: **2,431 Python tests passed**, including regression tests first
  observed failing before their fixes. **7 KEY Node tests passed**.
- The 1.0.4 generation differs from 1.0.3 for the same input and assessment date;
  the source input remains unchanged.

## Immutable public replay

Public snapshot: run `42478152200`, artifact `13616417127`, observed
`2026-11-08T12:01:48.103305+00:00`, **1,387 records**.
Archive SHA-256:
`489a0d85ab265bc6c16cbe840c2e6c70ddb59074df81afd0317322a05fc961e4`.

Reconstructing its stored-cell contract and applying baseline/current common
normalization produces the same semantic records, exclusions and **1,185 reader
rows**. Normalizer version and derived hashes are expected to differ. The raw
snapshot is immutable. This is a historical-input reader replay, not a new
publication of obsolete source-derived rate metadata.

Re-deriving stored public reward evidence on both revisions, and parsing the
same Alfa PDF bytes on both revisions, changes only two semantic records:

| Native record | Reviewed delta |
| --- | --- |
| `core47:airport-restaurants` | The second expense includes its parenthesized wording and `Баллов`, rather than ending after the digit. This is the sole changed visible reader row. |
| `core47:travel-insurance` | The source conditions retain every published price column and the unavailable column. No personal eligibility is inferred and this price table alone is not admitted as a benefit. |

The re-derived comparison retains **1,185 reader rows** and the same exclusions.
The prior X5 derived-rate repair appears equally on both comparison sides and is
not attributed to this release.

## Original document controls

Both anonymously retrieved PDF byte hashes match the original snapshot:

| Document | SHA-256 | Parsed records |
| --- | --- | ---: |
| Core, revision 47 | `8e2584b0c91af97293b911eb5f98079e6ca342387f72abf559ca1734a1eed069` | 9 |
| Cashback, revision 101 | `409275f71c94a7807cc09b04c6f169c0bbdb0bbe9edd91a25c28018ed151583e` | 1 |

Stable IDs are unchanged. Cashback output on its original document is unchanged.
No new document version, URL discovery, authentication path or dependency is added.

## Release and limits

The existing request bridge refreshes the two Alfa PDFs because discarded text
cannot be recovered from previously stored excerpts. It then republishes all
stored inputs using the existing serialization and readback checks. Other source
adapters use the corrected code at their next collection; this report does not
claim a fresh live crawl of every affected source.

Russian quantity words are supported through 99; digit quantities have no
offer-specific ceiling. Parenthesized written-out numbers stay literal and are
not independently reconciled with digits. Unknown layouts and new document
revisions remain outside these tests. Final whole-branch review, CI, merge and
publication receipts are recorded on the associated pull request.
