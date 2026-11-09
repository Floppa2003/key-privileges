# Remaining numerical changes in supported source templates

## Goal

Remove reproduced dependence on old numerical values and numerical spellings
after the 1.0.3 release. A changed amount, quantity or period within a supported
template must keep its published meaning and complete evidence.

## Acceptance

- Backit accepts complete, currently applicable date intervals longer than 93
  days; the conservative year-inference restriction remains for missing years.
- Ural qualification captures whole flight counts, spending thresholds and
  calendar-year counts. Only a literal one-year window has the legacy
  `calendar_year` alias. Utair supports grouped numeric spending thresholds.
- Known HTML/PDF rules and the Domina/X5 adapters accept complete decimal reward
  rates and money values, grouping separators, and normal inflections caused by
  changed numbers. Counts and duration fields stay positive integers.
- Avolta recognizes literal quantities in `N по цене M` when N > M > 0, in digits
  and supported Russian number words, without inventing a percentage discount.
- Alfa public documents retain changed caps, expenses, quantities, delays,
  participant labels and contact numbers. A new 20-point expense must not become
  the prefix 2. The cashback row retains changing category counts and caps.
- Every changed path validates full numeric tokens; malformed, negative,
  fractional-count, duplicate or contradictory input cannot become a convenient
  valid suffix or borrow a number from another clause.
- Preserve original text, field ownership and existing public records unless a
  reviewed delta follows directly from these repairs.

## Global Constraints

- No LLM processing, new dependencies, schedules or access-control changes.
- Preserve raw records, literal evidence, observation timestamps and private data.
- Do not commit private workbook rows, codes, identifiers or credentials.
- Source URL allowlists, document revision identity, section numbers and product
  names remain explicit; new document discovery is outside this repair.
- Use a feature branch; finish with tests, public-fixture replay, one independent
  whole-branch review, PR CI, merge, publication and independent native readback.

## Limits

This proves the repaired numerical paths in supported templates, not arbitrary
Russian prose or every future source layout. Unknown number words remain
unresolved. Source collection is not repeated merely to change parser code.
