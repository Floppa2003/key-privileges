# Numeric changes in published loyalty rules

## Goal

Keep deterministic meaning when a supported source template changes its numbers.
The user explicitly prioritizes rates, amounts, limits, periods and dates over
renamed brands. Source identities, routes and document layouts remain configured.

## Acceptance

- Alfa partner PDFs extract the current exact rate, cap wording and payout days;
  generated titles use that rate. Malformed/range rates and contradictory title
  versus operative clauses must not become an exact percentage.
- GPB notification fees preserve the stated starting month and amount. The old
  after-first-month alias is valid only for a stated second-month start.
- Student relative expiry accepts a calendar-valid stated day/month and keeps the
  relative academic year; it must not invent an absolute offer expiry.
- Retail mileage redemption derives delivery/discount treatment from evidence,
  including when projecting old stored records. Unknown/contradictory treatment
  stays unknown; raw evidence is immutable.
- Reader qualification conditions survive changing flight counts and numeric
  versus worded counts. No whitelist of previously observed counts.
- Reader campaign expiry has no fixed year cutoff; explicit completion and
  published end dates are handled without treating a start year as an end date.
- Payment/prepayment percentages never become a benefit merely because they
  differ from 100. A nominal promotional price must not depend on the price being
  exactly one ruble; an ordinary price alone is insufficient proof of a benefit.
- Permanent tests use multiple independent numeric substitutions through real
  source and common-reader entrypoints, with invalid-number negative controls.

## Boundaries

- No changes to brand/source identities, access controls, collection budgets,
  personal eligibility, LLM processing or schedules.
- Preserve original records, literal evidence, source timestamps and private data.
- Do not commit private workbook rows, codes, identifiers or credentials.
- New parser semantics require a new common-normalizer generation/version.
- Finish with full tests, public snapshot delta review, independent whole-branch
  review, PR CI, merge, publication and independent native readback.

The previously reproduced examples and the user's numeric-substitution criterion
are the authority; no universal natural-language coverage is claimed.
