# Practical utility and source fidelity — revised 2026-09-29

User decision: judge a useful loyalty catalogue, not only verbatim transcription.
A plausible card-presentation suggestion is not equivalent to a wrong discount or
borrowed programme requirements. This is a changed rubric, NOT a retrospective
improvement of the model. Historical outputs, measurements and prior reviews stay intact.

## Output contract

`offers[*].restrictions`, `redemption`, benefit/audience/date fields and `evidence`
remain source-derived. `offers[*].practical_advice` is a separate optional-use array:
`[{"text": "...", "basis": "inference"}]`. Empty is allowed. The consumer must show
it as **Совет (вывод, не опубликованное условие)**, not merge it into mandatory terms,
search filters, eligibility, stacking, price calculations or offer availability.
Published card-presentation instructions belong in redemption. A practical inference
about taking/showing the card belongs in practical_advice; never invent a quotation.
No automatic repair or merchant-specific text rules are introduced.

## Review two axes, do not collapse them

1. **Practical utility:** can the reader correctly identify and use the intended offer?
2. **Source fidelity:** which facts are explicit, inferred, missing or contradicted?

A low-risk practical hint already placed in legacy redemption is a provenance/placement
note, NOT by itself a materially incorrect offer. Do not silently migrate it or claim
the raw answer has the new format. Source silence is not a factual contradiction.

| Severity | Meaning | Examples | Consequence |
|---|---|---|---|
| material | Changes entitlement, value, cost, feasibility or required action | Wrong percentage/unit/code/date; missing cap or excluded tariff; requirements of another programme; unsupported mandatory passport, payment, registration or physical-card-only restriction | Block unattended use until resolved |
| minor | Wording/placement problem without changing the usable offer | Redundant repetition, a low-risk card hint not labelled as inference; generic audience with an unambiguous programme in the displayed TARGET and other conditions | Preserve a note; not a whole-offer failure |
| advice | Clearly labelled low-risk suggestion consistent with the source | Take the named programme card for an explicitly offline cardholder discount | Allowed, optional, no source quotation required |
| none | Checked facts and scope preserved | Correct amount, programme and material restrictions | No identified defect on checked dimensions |

A label `basis=inference` does NOT excuse a false percentage, code, deadline,
programme transfer or invented mandatory restriction. Judge the actual content.
Generic audience is material if it broadens eligibility in the final displayed record.
A correct fact anywhere in structured conditions counts for practical completeness;
a correct quotation alone does not repair contradictory/missing mandatory terms.
Contradictions in unknowns are not automatically harmless: material when they change
how the user interprets/apply the offer; unrelated filler is minor noise to remove.

## Reinterpretation of the frozen grounding v2 set

- Museum: do not reject the offer solely for “предъявить карту”. Keep a placement
  note; the source still does not explicitly prescribe presentation.
- Lavka: same card-hint rule. Hotel/branch unknowns are irrelevant noise, not
  evidence that the published discount is false or absent. Unknown amount is null.
- ACADEMIA/Nevsky: score audience in the full displayed programme context. Do not
  require mechanical repetition of the programme in each string if scope is intact.
- Golden Triangle: amount/tariff/code correctness is separate from contradictory
  unknowns; the latter still need review, not a claim that all offer data is wrong.
- Theatre: borrowing screenshot/FIO/identity-document requirements from another
  programme remains a material failure, not a permitted “common sense” hint.

## Bounded model check, fixed before inference

Four frozen documents: rzd_museum, lavka, muzcomedy, nevsky. One practical_v3 call each,
no repeat-for-better-answer and no fresh website fetch. Same local Qwen/Ollama/digest,
1024px images (all pages), complete source text, as_of and options as before.
Only the output contract plus corresponding prompt change: this is NOT prompt-only A/B.
Old baselines are reused for context, not paired speedup or significance claims.
Review against sources and this rubric, not exact string matching. Report actual
advice placement, core factual defects, completion/time/RAM and uncertain readings.
Theatre separation is not presumed solved. JSON-schema success is not semantic accuracy.
No success count for all partners, production publication or new default without a
separate decision. Previous defaults and historical experiments remain reproducible.
