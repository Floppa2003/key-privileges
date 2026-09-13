# Literal promo code normalization — 2.3.2

Schema version 2 and the Google Sheets column layout are unchanged. This revision repairs coupon extraction; it does not add catalogue access, sign in, retrieve personalized codes, or certify offers as currently usable.

## Defect and boundary

The previous generic regex could turn `из SMS`, `до 15.09.2026.`, `составляет 2000`, currency limits, and numbered instructions into literal promo codes. It also merged table headings into values and missed lowercase Latin codes and codes stored in an explicit table column.

`promo_codes` now contains conservatively recognized literal values. Original case and internal spaces are retained; surrounding quoted whitespace is removed. Unknown code values remain absent rather than being guessed from redemption instructions. Expiry dates, amounts, numbered redemption steps, section labels, and counts of branded personalized coupons are not literal codes.

## Machine-readable fields

The existing `details` object additionally contains:

- `promo_code_status`: `explicit_codes_extracted`, `mentioned_not_extracted`, or `not_mentioned`. This describes extraction only, not validity or account eligibility.
- `promo_code_evidence`: each code with an exact source-text span or an explicit table cell's full row, headers and zero-based table/column indexes plus row index (header = 0). A table is accepted only when it has exactly one explicit `Промокод`/`Промокоды` column and a rectangular string-valued row. Original tables remain intact.
- `promo_code_delivery`: clauses mentioning a promo code together with SMS, a personal account or an application. Items have `kind=delivery_reference` and `method=sms|account|app`; these are references in text, not a promise that an anonymous reader can obtain or activate a code.

An unresolved mention adds `promo_code_mentioned_not_extracted`. In Google Sheets codes remain in column K; evidence and delivery references are serialized in the existing details column U. No extra tabs or credentials are needed.

The publication validator recomputes code extraction and its evidence from the supplied original text/tables, rejecting mismatches even if a record's overall hash was recomputed. This protects structural consistency, not against every possible semantic ambiguity in natural language.

## Replay audit

Input: all 728 public records from run `34727580271:1`, observed `2026-09-13T00:17:54.545684+00:00`. ZIP SHA256: `ced06752bea478cae707d631ed81d086c55034de2f6c58cba15b1fcb3248d447`.

On the exact same observations, 43 code lists change: 33 false-only lists become empty, six previously missed code-bearing records are recovered, and four existing lists are corrected. Code-bearing records become 97 rather than 124. All source text, IDs, URLs, numeric rates, original metadata and observation/validity dates remain identical. This offline comparison was not uploaded as a new live observation.

Examples: i'way loses the spurious `1`; Ramada uses the published `Крылья` instead of `Скидка 10`; Park Wood obtains `BLUE WINGS`, `SILVER WINGS`, `GOLD WINGS` from the code column rather than including the `Скидка` heading; Olimp and Gorskiy retain each code's tier/discount row. Lowercase `moskvichmag` and `mskvmag` are preserved. Publication and expiry are separate: recovering a code does not renew its source offer.

## Verification and limits

28 additional tests cover negative instructions/dates/amounts, numeric and Cyrillic positive cases, quoted and plural lists, table provenance, and tampered publication records. New failing behaviors were exercised before fixes, alongside passing nonregression controls. Full local suite: 195 Python tests and seven KEY tests. A fresh branch collection and authorized main publication/readback are separate release gates, recorded in the pull request.

The grammar intentionally favors precision over recall. It is not a general natural-language parser: unusual formats, unsupported code labels and ambiguous lowercase Cyrillic words can remain unresolved. A nonempty code list does not imply that every code in the source was extracted, that the discount is active, or that codes can be combined. Full source conditions remain authoritative.

No changes to site access policy, TLS validation, network routes, Google authorization, scheduling, stable IDs or managed-tab boundaries are included.
