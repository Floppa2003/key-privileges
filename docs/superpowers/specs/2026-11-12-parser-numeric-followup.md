# Numeric and clause ownership follow-up

## Goal

Repair reproduced value and ownership errors after normalizer 1.0.4, including
the live T2 SIM extraction regression. Changing a literal number or its normal
Russian inflection must not silently change the meaning of a supported offer.

## Acceptance

- T2 courier delivery and replacement fees come from their own service section.
  An independent in-salon price must not cause a duplicate-label failure. Repeated
  or malformed prices inside the courier section still fail. Full article
  conditions and stable IDs remain intact.
- Utair numeric mileage multipliers preserve complete positive decimal values;
  malformed, signed, ranged or conflicting factors cannot yield a valid suffix.
  Existing worded factors and integer representation remain compatible.
- Student and Utair ages and activation delays accept normal number-dependent
  year/day forms. Counts remain positive integers; age intervals are ordered.
- GPB introductory and subsequent monthly subscription prices retain their own
  periods. A paid introduction cannot replace the explicitly stated later price.
  Preserve both prices and duration as literal evidence; do not calculate savings.
- Percentage bounds `не более` and `не менее` stay upper and lower bounds in
  source extraction, common normalization and source-owned literal terms.
- Source-owned literal extraction checks each reward occurrence in its full
  sentence. A denial cannot become a positive offer after phrase slicing.
  A separate live benefit and product-specific exclusion must survive.
- Fixed-ruble discounts and caps in separate sentences keep their own amounts,
  purchase stages and condition links. Decimal marks, dates, URLs and `руб.`
  abbreviations are preserved. A cap alone is never an additional reward.

## Global Constraints

- No LLM processing, new dependencies, schedules or access-control changes.
- Preserve raw evidence, stable IDs, observation timestamps and private data.
- Do not commit private workbook rows, codes, identifiers or credentials.
- Preserve reviewed source URL/document identity gates and fail-closed guards.
- Implement in an isolated feature worktree; use test-first repairs, a public
  snapshot replay, one fresh whole-branch review, PR CI, merge, existing publication
  workflow and independent native readback.
- Normalizer 1.0.5 changes the derived generation for identical input and date.

## Evidence and limits

Baseline f61a0be: 2,431 Python tests and 7 Node tests pass. Nov10 collector artifact
13768954714 contains `t2_sim_rules: sim_delivery_price_missing`; the original T2
article has the independent salon price and the courier section. The remaining
findings are controlled mutations of public fixtures, not claims about current
prices. HSE missing details and FlyStation's empty-page guard are not confirmed
parser defects. Unsupported currency denominators and arbitrary prose/layouts
remain outside this repair.
