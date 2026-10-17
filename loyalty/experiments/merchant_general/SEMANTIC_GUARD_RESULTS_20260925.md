# Semantic guard continuation — 25 September 2026

## Status

Draft PR90 remains experimental. No production registry, Google Sheets, publisher, or schedule changes.
The new guard is a conservative precision firewall, not proof that an offer is true.
Every result keeps `publication_allowed=false`.

## Added

- `merchant_semantic_guard.py`: merchant-independent checks for explicit beneficiary,
  explicit benefit language, event-vs-entitlement confusion, promo-code role evidence,
  and lexical support for booking/stay/offer/publication date roles.
- `merchant_guard_eval.py`: deterministic replay over the frozen ACADEMIA, ELKOM,
  and Teplohod SPb block-extraction observations.
- Tests cover a clean cardholder discount, generic visitors, past-event gifts,
  booking-vs-stay confusion, and unsupported code semantics.

No merchant names or domains are embedded in the guard.

## Verified CI

Commit `f35daa70a145d58b27056cc34ff8ed2069216c30`.
Run `36101988314`, job `107966253630`: completed/success.

- 1470 Python tests: pass.
- 7 KEY tests: pass.
- Artifact `10849103896`, 76677 bytes.
- Artifact SHA256:
  `9d177b94c926229e4963a604c3284548ee01af4261b845dbc2abaa59c7c19796`.
- Downloaded artifact SHA256 independently matched the GitHub digest.

Frozen semantic-guard evaluation: `passed=true`, still
`publication_allowed=false`.

Observed reasons:
- ELKOM: review-only because the stored input is a source excerpt.
- ACADEMIA: missing audience + unsupported offer-date role + excerpt provenance.
- Teplohod SPb: missing audience, no explicit reusable benefit, past-event scope,
  unsupported offer-date role, excerpt provenance.

An earlier workflow failed only because a literal `\\n` was accidentally placed
between shell commands. All 1470 Python tests in that failed run had already passed.
The workflow orchestration was corrected and the subsequent run above is the
accepted execution.

## Fresh holdout observations

These were discovery checks, not production integrations and not additions to the
frozen eval corpus.

### Losevo Park

A site-bounded search discovered the public CT Group page. A fresh page read
classified it as a past event: the page describes a December 2023 recognition
ceremony and participation in the EKP project, but states no reusable cardholder
benefit. This is exactly the class the new event/beneficiary guard is intended to
block. No merchant-specific exception was added.

### Meatcake

A site-bounded search result described Meatcake as an official EKP partner, but a
fresh main-content page read exposed no reusable EKP benefit or audience evidence
and the extractor returned `uncertain`. Therefore search snippets remain discovery
signals only and are not accepted as offer evidence.

### Russian Musical Seasons

The official domain was discovered generically as `rmseasons.com`; a bounded
site search returned no EKP page. Absence of search results is not treated as proof
that no offer exists.

## Remaining gates

1. Measure recall/precision on a larger held-out set of previously unconfigured
   merchant domains.
2. Generate and verify atomic semantic claims automatically rather than relying on
   manually authored NLI hypotheses.
3. Confirm unattended source transport; the earlier keyless Firecrawl REST 403 is
   still unresolved.
4. Only after those gates consider wiring block extraction + guard into the
   normal collector. Do not merge PR90 into production yet.
