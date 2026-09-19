# Alfa public partner clauses — 19 September 2026

## Demonstrated defects and smallest repair

An independent read of the actual published `parser_offers!A2606:Y2610` after PR68 confirmed five partner-PDF rows. Publication run 35402892122 had succeeded; it was not repeated merely because chat output was interrupted.

Two defects remained in the stored content:

1. FRESA's clause 2.2 was truncated at the first comma to Moscow. The freshly fetched source clause also names Saint Petersburg and Vladivostok; the existing TSP appendix already contained all eight addresses.
2. All five rows had empty `redemption_text`, despite explicit clauses 2.3 (joining through the first qualifying card payment) and 3.1 (card/AlfaTravel purchase requirement).

The parser now extracts each of these short practical clauses through its next numbered boundary, with an exact opening, unique start and size bound. It retains the full source wording, including beneficiary/account distinctions in R14 and Mama Tuta / Probka. It does not infer a separate activation step, waive Alfa Only eligibility, or generalize beyond the listed TSP.

A `practical_clauses` evidence object binds published conditions and redemption to the extracted text. Rehashed payloads with changed geography or redemption fail validation. Source dates, IDs, partner identity, rate, cap, monthly transaction scope and TSP appendices are unchanged.

## Verification before release

- Five new regression tests failed against the preceding parser, then passed after the fix.
- Existing partner fixtures gained the actual numbered joining/payment clause structure; their original assertions were retained.
- Exact local replay of all five fresh PDFs changed only redemption/evidence/hash in four records and additionally the territory text in FRESA. IDs, source dates, rates, caps, scopes and appendices matched the preceding output at equal observation time.
- GitHub run **35407842224:1**, job **105801178779**, tested commit **5738cc52fa9751258e75ac76ec0a7d6eca020c61**: **1031 Python tests / 7 KEY tests passed**.
- The same run fetched all five official PDFs without credentials, parsed all five records and verified the payment/geography clauses through `sheets_normalized.prepare` and the common normalizer.
- Observation time: **2026-09-19T00:01:41.429880+00:00**.
- Artifact **10573382241**, SHA256 **35f9f6aaead6b56a051a3040bf3d4696db3d8a06a19cfd0fb8083270f49b772c**, was downloaded independently, digest/ZIP CRC verified and compared to the locally tested code and outputs.
- Executable SHA256 `alfa_partner_rules.py`: **e3ebd2047989d9a2824b4680498bb436317ef0744f0b30346e7818c3fee6b432**.
- A local attempt to import the broader partner suite lacked `protego`; that attempt is not claimed as a full pass. The complete pinned GitHub environment above is the full-suite acceptance.

## Source discovery checks, not new offers

An earlier baseline audit in this continuation, run **35407186521**, fetched the five partner PDFs and the two public core/cashback PDFs directly and passed **1026 Python / 7 KEY tests**. Their hashes matched the already published documents. The source-CDN alternatives `/actions/rules/` and `/sitemap.xml` returned 403.

A separate public-only Google import test tried PDF-link extraction from the bank's `/actions/rules/`, `/retail/tariffs/` and `/everyday/debit-cards/alfacard-premium/`. All three imports returned `Could not fetch url`; the temporary tab `alfa_index_probe_20260919` was deleted. No discount-sheet cell was used for those formulas.

Search-indexed official rules pages suggest additional public partner documents, but their exact current links and contents were not obtained by these tests. Search counts and snippets are not a current catalogue, and these failures do not prove that all useful public routes are exhausted. Automatic discovery of newer core/cashback revisions and a complete partner-PDF inventory remain open.

## Release boundary

This file initially records pre-release acceptance. A subsequent release/readback section must identify the actual merge, targeted publication and destination checks before claiming that the repair is live. The temporary audit workflow must be absent from the merged tree. No new schedule, provider account, bank authentication, OTP, cookies, offer activation or ScrapingAnt spending is part of this repair.
