# Alfa public partner clauses — accepted 19 September 2026

## Demonstrated defects

Independent readback after PR68 confirmed that publication run 35402892122 had completed; it was not repeated merely because chat output was interrupted. Five partner-PDF rows already existed at `parser_offers!A2606:Y2610`.

Two source-extraction defects remained: FRESA clause 2.2 stopped at the first comma after Moscow, omitting Saint Petersburg and Vladivostok; all five records had empty redemption fields despite explicit clauses 2.3 (joining through the first qualifying card payment) and 3.1 (card/AlfaTravel purchase requirement).

PR69 extracts those short clauses through their next numbered boundaries, with unique opening and size checks. `practical_clauses` binds conditions/redemption to their source text. It preserves the complete participant/account distinctions in R14 and Mama Tuta / Probka. Existing IDs, rates, caps, source dates, monthly transaction scope and TSP appendices remain unchanged.

## Important correction discovered during final verification

PR69 really did publish its source repair, but the first acceptance searched the whole common-record JSON. That was too weak: the common normalizer retained all source clauses in raw data without emitting the territory and full payment instruction as visible `normalized_conditions` components.

The actual destination check failed this stronger requirement. PR70 adds only two aliases to the existing adapter: `details.activation` is the exact redemption string; `details.limitations` is the exact territory clause. The adapter validates both against `practical_clauses`. No global normalizer, interpretation, new fact, transport, dependency or schedule was added. The new regression explicitly inspects `common['conditions']`, not raw JSON, and fails before this change.

## Tests and fresh-source evidence

PR69 acceptance: run **35407842224:1**, job **105801178779**, execution **5738cc52fa9751258e75ac76ec0a7d6eca020c61** passed **1031 Python / 7 KEY tests** and fetched all five official PDFs. Observation **2026-09-19T00:01:41.429880+00:00**. Artifact **10573382241**, SHA256 **35f9f6aaead6b56a051a3040bf3d4696db3d8a06a19cfd0fb8083270f49b772c**, independently verified by digest, ZIP CRC, code and output comparison. Five new regressions were red before the source fix and green after it.

PR70 acceptance: run **35408913497:1**, job **105804354776**, execution **0551edb209904a86a66094e969be56b462c2613f** passed **1032 Python / 7 KEY tests** and freshly fetched all five PDFs. Observation **2026-09-19T00:19:32.863440+00:00**. All five produced exact visible activation and limitations components; eligibility_verified remained null. Artifact **10573039176**, SHA256 **9088b62d9a98841debd2cfd5574f90835bf5a995b6381fd32efafce39f20486a**, independently verified by digest/CRC and byte comparison with reviewed code. Six focused local tests passed; the new projection test failed before aliases. A previous local broader-suite import lacked protego and is not claimed as passing; full-suite acceptance is the pinned GitHub environment.

Final executable SHA256 `alfa_partner_rules.py`: **033b3b4b513f771ae78746970fae1b7f2665a19c9b12b8cbce9a8aa23bfca4c7**, Git blob **953b3a91ce118f24433ed7e5c73fcb72dcaa78f5**. The independently read main blob matches. The temporary diagnostic workflows were removed before their respective merges.

## Actual releases and destination

- PR69 merged as **4faf19eaf981b8849869cf685dfad6d755b7eccf**. Targeted main run **35408096055:1**, execution **b6ad818713149ece4317e8661344d480cc5f675a**, completed collection and publication successfully. Source observation **2026-09-19T00:06:07.417585+00:00**.
- PR70 merged as **2f1a151acb9f95ffc10c27acd72e5ac2d44999f5**. Final targeted main run **35409104683:1**, execution **3b52bd75ae0037524cd7cdb9a1a8017fa12a4074**, completed both jobs successfully; collector **105804918517**, publisher **105805153525**. Source observation **2026-09-19T00:23:09.767901+00:00**.
- Final publication artifact **10572719870**, SHA256 **d8042f7fbc1fa6f14ed3096e809f91b930ad4065023d8205a1134e62ed737519**, was downloaded and checked independently. Five records, one source, no source errors; executed parser hash matches the tested code. All records and common condition components independently validated.

Destination remains spreadsheet **1uFR7croj7p6RRNPcoTRYlVl06hKsurkIgyu1IdMMB-4**, `скидки`. Fresh native reads and a read-only post-publication export confirm **2582 parser / 3230 unified records, verified/current, practical-offers-v1**. Source fingerprint **f565b704532209b6f0154b0160b088dd5bf92098217d93d55076f1238781b8f1**; generation **f76cf76e928b01a6ac54322adc1c6d67aa173222aa6219fd06382f72b59afa8d**.

Comparison against the separately saved pre-PR69 workbook confirmed:

- all **125 managed cells** of the five source rows exactly match the final payload;
- all five IDs and positions **2606–2610** are preserved;
- all **2577 unrelated parser records**, source manual column and every derived-view manual column remain unchanged;
- original input/history tabs, parser_runs and the hidden archive remain unchanged;
- all **14 sheets / 8 formulas** are preserved;
- all previous coverage values are unchanged; exactly two reports were appended at **1520 / 1521**;
- actual CURRENT `normalized_conditions` rows **10562–10571** contain exact activation and territory for all five parents; this is no longer just a raw-data preservation check;
- manifest terms: **3765 benefits, 9736 conditions, 97 costs, 713 code/delivery components**. These are components, not unique discounts.

Only source cell I2609 and columns J/U/W/X/Y of the five rows changed across the two repairs. Native formatting readback shows the new common conditions WRAP/TOP as before. No whole-workbook Google-rendered layout or permissions audit is claimed. Private workbook exports were not committed or attached.

## Current public Alfa scope, without double counting

The Sheet contains **15 Alfa Only public records**: nine core privileges, one public cashback-limits record and five reviewed partner-promotion documents. This continuation repaired five existing rows; it added no new offer rows.

| Partner document | Published reward and monthly scope | Published end |
|---|---|---|
| Betulla | 10%, all qualifying monthly transactions, cap 1500 points/miles | 2026-12-31 |
| Р14 | 10%, first qualifying transaction each month, cap 1500 | 2026-10-31 |
| ООО «СОМ» — FRESA and other listed TSP | 10%, first qualifying transaction each month, cap 1500; source appendix has eight TSP in three cities | 2026-11-30 |
| Mama Tuta / Probka | 10%, first qualifying transaction each month, cap 1500 | 2026-10-31 |
| Такахули | 10%, all qualifying monthly transactions, cap 1500; already expired | 2026-08-31 |

Four documents are within their stated periods, not proven personally available offers. The exact source wording governs joining, card type, listed TSP, non-stacking and payout timing. Do not interpret first transaction each month as first-ever purchase or assume generic category cashback is identical to these partner promotions.

## Discovery attempts and remaining limits

Baseline audit **35407186521** fetched five partner and two core/cashback PDFs directly and passed **1026 Python / 7 KEY tests**. Hashes matched published documents. Source-CDN `/actions/rules/` and `/sitemap.xml` returned 403.

A public-only Google import test tried exact PDF-link extraction from bank `/actions/rules/`, `/retail/tariffs/` and `/everyday/debit-cards/alfacard-premium/`. All returned `Could not fetch url`. Temporary tab `alfa_index_probe_20260919` was deleted; independent metadata confirmed the original four staging tabs. No production cell carried these formulas.

Indexed official rules pages mention additional candidate promotions, but exact current PDF links/content were not obtained by these tests. Search snippets are not a source inventory. Public partner-PDF discovery is non-exhaustive; automatic detection of newer core/cashback revisions is still missing. Exact core47/cashback101 URLs are reviewed versions, not proof they remain newest indefinitely. The authenticated `web.alfabank.ru/partner-offers/` catalogue remains separate and unread. These results do not justify claiming every anonymous GitHub route has been exhausted.

No bank account, OTP, cookies, personal financial records, activation, new provider account, paid service, new schedule or ScrapingAnt credit spending was used in this continuation. Existing daily collection remains; missing observations do not delete historical offers.
