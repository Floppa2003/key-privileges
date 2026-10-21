# Live content discovery (2026-10-22)

A promotion, partner, service, tier, rate, coupon, FAQ wording or item count is
source data, not a runtime admission allowlist. Discover the current inventory
before interpreting individual blocks. Never add one new title to a frozen list
as the repair for a new promotion.

## Current fixes

- FlyStation: every owned promotion panel uses one literal block extractor.
  Titles do not select extraction branches. New gift and discount clauses work
  without registration in code. Price-only/unclassified panels remain explicit
  source observations, not invented benefits or silently missing inventory.
- Mantera FAQ, hotel and partner pages: names, ordering and tier counts come from
  the current lists/tables. All current FAQ answers and the current pilot banner
  are retained. Current roster names can identify redemption scope; historical
  aliases are identity hints, not an admission list. An unresolved name is not
  assigned to a previously known hotel.
- Tsvetnoy: discover HTML tiers and read PDF column names and cell rectangles from
  the current document. No fixed page width, column coordinates or three-tier
  count. A continuation without headers must preserve column geometry. Header
  changes, contradictory columns and unreadable cells remain explicit errors.
- Utair/Wings: discover actual tier tabs/headings. New tiers are traversed rather
  than silently omitted. Existing tier-ID aliases only preserve old row IDs.
- TSUM/Alfa: all current tier cards and FAQ entries are captured. An unquantified
  card is evidence, not automatically another cashback rate. Independent source
  rate statements must agree; baseline rates remain conditions, not extra rewards.
- MiXX: current service lists, fixed-benefit clauses and speaker models determine
  inventory. Automatic inclusion follows the source wording, not the brand name.
- Utair partners: newly listed public partner links and tier labels are retained;
  this does not authorize fetching arbitrary third-party sites.
- Sacvoyage: owned headings delimit current programme sections; names/count are
  not fixed. Original clauses stay in their own audience. A missing rate is not
  borrowed from another section.
- Artparking: current service/rate/code clauses determine product inventory.
  Dom Knigi accepts changed repeat count and conditions without restoring old text.
- GPB product options and Utair Generations: current options and multiplier are
  data; old coupon codes/tier names were removed as document-identity requirements.
- Ladoga EKP: discover all programme-owned product cards by source IDs, retain
  current links and page notes, and extract current gift/discount clauses. New
  items do not inherit old gift quantities; unfamiliar terms remain observations.
- HSE alumni: unanchored sections match names in the current catalogue, not a
  single historical business. Exact/delimited matching and ambiguity checks keep
  neighboring partner conditions separate. Legacy heading aliases are readback only.
- Smartavia: tariff names are current labels, not a fixed `1+N` grammar. A traveler
  count is filled only when that syntax explicitly provides it, otherwise unknown.
- FlyStation/Ladoga raw rates use the same scoped reward phrases as their literal
  extraction: prepayment percentages are retained as conditions, not extra discounts.
- Collector diagnostics preserve bounded machine ValueError codes while refusing
  arbitrary exception text that may contain credentials.

## Integrity and compatibility

Current evidence is explicitly versioned where fields are replayed at publication.
Unversioned retained records use frozen legacy projection functions **only for
historical readback**. New collectors always write version 2. The legacy functions
are not live discovery, fallback answers, or a reason to reject a new title.

Unchanged entities retain historical IDs through identity-only aliases. When a
source provides no stable ID and renames an entity, a new label-derived ID may be
necessary; this is not a claim that every rename preserves identity. Existing
full-inventory retirement and manual-note protection remain unchanged. Partial
reads must never retire records. Canonical JSON serialization must reproduce the
same projected fields regardless of dictionary-key ordering.

Source observations remain auditable but are not promoted to reader discounts.
Inventory completeness is distinct from semantic completeness. Network policies,
origin/URL ownership, schema/type checks, ambiguity and duplicate checks, finite
resource bounds, and provenance/readback validation remain in force.

## Regression requirements

Test newly named entries, renaming, insertion/removal, permutation, changed rates
and counts, FAQ rewording and source-specific restrictions. Test a new tier/column
count and reordered PDF columns, including multi-page continuation. Also test
negative rewards, prepayment versus discount percentages, cross-programme scope,
canonical serialization, historical readback and no publication of evidence-only
records. Tests must not require a failure merely because old source wording or a
previously observed item is absent.

## Limits

This change does not integrate the experimental LLM path, enable paid inference,
change Google authorization, publish a new snapshot, or change schedules. It does
not make HTML/PDF interpretation schema-free. DOM roles and syntactic/semantic
patterns remain; entirely new layouts or ambiguous free text can still need
parser work. Do not claim all 125 sources were live-verified from a finite suite.
