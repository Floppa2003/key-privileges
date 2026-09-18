# Alfa Only public rules acceptance — 18 September 2026

## Scope

This release adds a recurring **public Alfa-owned evidence layer** for Alfa Only. It does **not** authenticate to Alfa-Bank and does **not** claim equivalence to the personalized catalogue at `https://web.alfabank.ru/partner-offers/`.

The exact authenticated source remains a separate source ID and continues to report the verified bank-authentication redirect with zero catalogue offers.

## Accepted official documents

### Core Alfa loyalty rules

- source ID: `alfa_only_public_rules`
- URL: `https://alfabank.servicecdn.ru/site-upload/4b/2c/2366/prog_loyal_v47.pdf`
- document: public Alfa-Bank loyalty-program rules
- revision: **47**
- effective from: **2026-05-01**
- retrieval: anonymous HTTPS GET, redirects disabled, PDF identity and size bounded
- parser: `pypdf`, fail-closed on revision/effective-date drift

The collector produces **9 practical records**:

1. taxi / transfer / carsharing reimbursement;
2. business-lounge reimbursement;
3. airport restaurant / cafe / bar reimbursement;
4. QR-code lounge access;
5. RBC subscription;
6. concierge service;
7. SimplePrivé Silver;
8. Smart Reading;
9. travel insurance (VZR).

### Reverse cashback rules

- source ID: `alfa_only_cashback_rules`
- URL: `https://alfabank.servicecdn.ru/site-upload/c6/bb/2366/Loyalty_program_rules_revCashBack_25052026.pdf`
- revision: **101**
- effective from: **2026-05-25**
- retrieval and parser boundaries: same public-PDF contract

The collector produces **1 practical record** for the public Alfa Only cashback limits. It records the public minimum category count and aggregate limits. It does **not** invent or infer personalized category rates.

## Live-source acceptance

Temporary targeted run **35392321001** on commit `6e24da30be9666a2c341041df829315776a3afbd`:

- **8/8 Alfa unit tests passed**;
- both official PDFs were fetched live;
- core revision 47 produced **9/9** records;
- cashback revision 101 produced **1/1** record;
- total public Alfa records: **10**;
- `sheets_normalized.py` dry-run accepted **2 coverage rows / 10 offer rows**;
- no bank account, bank session, OTP, cookies, Google destination write or offer activation was used.

The temporary targeted workflow is development-only and must not exist in the merged production tree.

Final one-time release regression **35392595659** additionally passed:

- **1016/1016 Python tests**;
- **7/7 KEY tests**;
- a second live fetch of both official PDFs;
- exact **9 core + 1 cashback = 10** public records;
- normalized dry-run **2 coverage rows / 10 offer rows**.

## Evidence contract

Every record is marked `public_rules_document` / `tier_benefit` and carries:

- exact source PDF URL;
- exact document revision;
- document effective date;
- SHA-256 of the fetched PDF;
- `authenticated_catalogue_equivalence = false`;
- warnings that user eligibility and Alfa Only participant level are not inferred;
- warning that the authenticated partner catalogue was not read;
- warning that a newer revision is not automatically discovered by the current exact-URL collector.

This means a document-format or revision change fails closed rather than silently relabeling new text as old evidence.

## What this does not prove

The public documents are complementary rules evidence, not a complete personalized offer inventory.

Specifically, this release does **not** prove:

- that the user currently qualifies for any particular Alfa Only participant tier;
- that a personalized cashback rate is available;
- that every partner offer shown after bank login is represented in the PDFs;
- that revision 47 / 101 will remain the latest revisions indefinitely;
- that public marketing pages blocked by ServicePipe are equivalent to these documents.

## Freshness audit

During this work:

- core revisions 48–50 were searched for and no newer official indexed document was found;
- cashback revision **101** was found and replaced the initially discovered revision 100;
- cashback revisions 102–103 were searched for and no newer official indexed document was found.

This is a bounded freshness audit, not a proof that no newer unindexed file exists. Exact-URL revision drift is therefore still treated as a monitored gap.

## Priority consequence

Alfa is no longer a complete **public-data zero**: the new public Alfa-owned layer yields 10 practical records.

The exact authenticated `web.alfabank.ru/partner-offers/` source remains **0 offers / authentication-gated** and must remain separate. Bank authentication should be considered only for benefits that remain exclusive to the personalized catalogue after public-source coverage is exhausted.
