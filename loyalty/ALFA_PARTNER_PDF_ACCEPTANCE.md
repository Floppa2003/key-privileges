# Alfa Only public partner-PDF acceptance — 19 September 2026

## Scope

This release adds one recurring public Alfa-owned source, `alfa_only_partner_pdf_offers`, for a bounded reviewed set of individual Alfa Only partner-promotion rules hosted on `alfabank.servicecdn.ru`.

It is complementary to:
- `alfa_only_public_rules` (core Alfa Only rules);
- `alfa_only_cashback_rules` (public cashback limits);
- the exact authenticated `alfa_only_partner_offers` source at `web.alfabank.ru/partner-offers/`, which remains authentication-gated and separate.

No bank account, OTP, cookie, personalized catalogue, offer activation or purchase is used.

## Reviewed public documents

### Betulla
- native ID: `betulla_0126`
- URL: `https://alfabank.servicecdn.ru/site-upload/ea/cc/1007/betulla_only_0126.pdf`
- legal partner identity checked from source: ООО «ЛИНДЕН», OGRN 1207800041833
- TSP identity checked from source appendix: Санкт-Петербург, 9-я Советская ул., 1
- published period: **2026-01-01 through 2026-12-31**
- published partner rate: **10%**
- published maximum: **1,500 Alfa-points / bonus miles per calendar month**
- transaction scope: **all expense transactions in the partner TSP during the calendar month**
- source says partner-promotion rewards do not stack; the larger applicable partner-promotion value is used
- source says Bank crediting occurs within 10 days after the calendar month ends

### Р14
- native ID: `r14_0126`
- URL: `https://alfabank.servicecdn.ru/site-upload/22/58/1007/r14_only_0126.pdf`
- legal partner identity checked from source: ООО «ЗЕН», OGRN 1047855044203
- TSP identity checked from source appendix: Санкт-Петербург, ул. Академика Павлова, 5В
- published period: **2026-01-01 through 2026-10-31**
- published partner rate: **10%**
- published maximum: **1,500 Alfa-points / bonus miles per calendar month**
- transaction scope: **first expense transaction in the partner TSP in each calendar month**
- same non-stacking and payout-timing boundaries are preserved

### Такахули
- native ID: `takhauli_0226`
- URL: `https://alfabank.servicecdn.ru/site-upload/e6/79/1007/tkh_only_02.26.pdf`
- legal partner identity checked from source: ООО «ОЛИВЬЕ», OGRN 1227700078726
- TSP identity checked from source appendix: Москва, Малая Бронная, 10с1
- fresh GitHub direct PDF read resolved a conflicting search-index result: the source PDF itself says **2026-02-01 through 2026-08-31**
- published partner rate: **10%**
- published maximum: **1,500 Alfa-points / bonus miles per calendar month**
- transaction scope: all expense transactions in the partner TSP during the calendar month
- this record is therefore stored as **expired_by_published_end**, not as a current September offer

The search/index layer is not treated as source evidence when it conflicts with the fetched Alfa-owned PDF.

## Parser/evidence contract

The collector:
- fetches only the exact reviewed Alfa-owned PDF URLs;
- disables redirects;
- bounds response size and PDF page count;
- extracts PDF text with `pypdf`;
- derives validity dates from the source document;
- validates legal partner identity using OGRN;
- validates the TSP appendix using a reviewed address marker;
- extracts the exact section 3.2 cashback rate and cap;
- distinguishes `all_transactions_in_calendar_month` from `first_transaction_each_calendar_month`;
- preserves non-stacking and payout timing;
- stores PDF SHA-256;
- marks `authenticated_catalogue_equivalence = false`;
- marks the reviewed-PDF inventory as not exhaustive.

A formatting or identity mismatch fails closed for the individual PDF and is reported in source errors instead of manufacturing a row.

The source-specific rate normalizer intentionally derives **exact 10%** from section 3.2. The action title's wording “до 10%” remains source text but does not create a second contradictory normalized rate.

### FRESA and other TSP of ООО «СОМ»
- native ID: `fresa_0226`
- URL: `https://alfabank.servicecdn.ru/site-upload/f6/ac/20418/fresa_only_02.26.pdf`
- legal partner identity checked from source: ООО «СОМ», OGRN 1237800072377
- published period: **2026-02-01 through 2026-11-30**
- published partner rate: **10%**
- published maximum: **1,500 Alfa-points / bonus miles per calendar month**
- transaction scope: **first expense transaction in the partner TSP in each calendar month**
- appendix includes FRESA and other named TSP in Saint Petersburg, Moscow and Vladivostok

### Mama Tuta / Probka
- native ID: `mamatuta_probka_spb_0126`
- URL: `https://alfabank.servicecdn.ru/site-upload/01/03/1007/MamaTuta_Probka_spb_only_0126.pdf`
- legal partner identity checked from source: ООО «Пробка-Север», OGRN 1137847157436
- source PDF text contains malformed legal-name punctuation (`ООО Пробка-Север»`); parser acceptance still requires the reviewed legal-name marker and exact OGRN
- published period: **2026-01-01 through 2026-10-31**
- published partner rate: **10%**
- published maximum: **1,500 Alfa-points / bonus miles per calendar month**
- transaction scope: **first expense transaction in the partner TSP in each calendar month**
- appendix identifies Mama Tuta and Probka at Zoologichesky Lane in Saint Petersburg

## Live acceptance

Temporary pre-merge run **35399740563** on branch `loyalty/alfa-partner-pdfs`:

- **1024/1024 Python tests passed**;
- **7/7 KEY tests passed**;
- all 3 reviewed PDFs were fetched live from Alfa-owned CDN;
- **3/3 records were parsed and accepted**;
- normalized payload preparation accepted all **3** offer rows;
- Betulla: current through 2026-12-31, 10%, all monthly transactions, cap 1,500;
- Р14: current through 2026-10-31, 10%, first transaction each month, cap 1,500;
- Такахули: expired 2026-08-31, 10%, all monthly transactions, cap 1,500.

The temporary workflow used for this acceptance was deleted before PR creation.

Expansion targeted live run **35402505220** on branch `loyalty/finish-catalogs`:

- **10/10 partner-PDF unit tests passed**;
- all **5** reviewed Alfa-owned PDFs were fetched live;
- **5/5** records parsed with **0 source errors**;
- normalized payload preparation accepted **5 parser offers / 1 coverage row**;
- newly recovered current records: `fresa_0226` and `mamatuta_probka_spb_0126`.

The expansion workflow is temporary and is removed before merge.

## Deliberate incompleteness

This is **not** claimed to be an exhaustive inventory of every public Alfa Only partner PDF.

A bounded web discovery pass also surfaced other 2026 Alfa-owned Alfa Only partner/action PDFs whose indexed published periods had already ended before 19 September 2026. They were not added merely to increase row count. The recurring source therefore records only the **five reviewed documents** above and carries `public_partner_pdf_inventory_not_exhaustive`.

Future expansion should add exact Alfa-owned partner documents only after:
1. fresh source fetch;
2. source-derived validity;
3. partner/TSP identity validation;
4. normalized rate/cap/scope validation.

Authenticated partner-only offers remain a separate unresolved boundary.
