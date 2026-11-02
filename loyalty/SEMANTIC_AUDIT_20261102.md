# Semantic extraction audit — 1 November 2026

Evidence: [daily run 41278067049](https://github.com/Floppa2003/key-privileges/actions/runs/41278067049), artifact `13074097773`, ZIP SHA256 `87d38dd4d141ea30380fda9eb165455b204933ee4c50027692965a088759684d`.

All **90 completed document IDs** were reviewed: 89 positive answers and one correct no-incremental-benefit result. Membership is exact, with no duplicates or omissions. The aggregate verifies 90 output hashes and 456 input-file hashes. Two transport errors and one schema failure are excluded from the semantic denominator.

Program mix: Konsierge 63; T2 «Больше» 21; T2 Selection 4; Alfa Only 1; iLocked standalone rules 1. Provider batches: OrcaRouter 9; Token Harbor 13; Experiential 13; Kilo 8; OpenRouter 18; Vercel 29. These are different records, not a comparable provider benchmark.

## Counts by observed issue type

**Counts overlap and must not be added.** They are document-level findings, not an error rate. Original major/minor grades are not aggregated: reviewers used different severity thresholds for facts preserved only in evidence.

| Observed issue | Documents / 90 |
| --- | ---: |
| Advice repeats known actions/conditions, or source facts are labelled inference | 47 |
| Benefit or important detail retained in evidence/advice but absent from its own semantic fields | 26 |
| Benefit in basis/restrictions, or activation action in basis | 12 |
| At least one independent benefit component absent from the entire JSON | 6 |
| Correct no-benefit result loses a separate targeted restriction | 1 |
| Several rates survive in prose but are flattened into one numeric offer | 2 |
| Headline ceiling replaces specific rates explicitly stated in detailed terms | 3 |
| Numeric value does not distinguish an exact rate from an upper bound | 9 |
| Geography, condition, or exclusion missing, broadened, or attached to the wrong component | 7 |
| Unsupported audience, region, redemption location, or exclusive activation route | 8 |
| Conflicting source expiry dates silently resolved | 1 |
| Purchased gift card classified as a benefit gift | 1 |
| Unexpected non-Russian human-readable wording; enums and brand names excluded | 4 |
| Unrelated generated wording absent from the inputs | 1 |
| Internal field/status exposed in user-facing prose | 2 |
| Evidence quote changed from source text, sometimes without changing meaning | 3 |
| Known exclusion lacks explicit negation or is framed as unresolved | 2 |

## Representative cases

| Case | Document ID | Finding |
| --- | --- | --- |
| Олимп клиник (Ямского Поля) | `533981eee869248ea04c2d5f71861d7a` | Several benefits collapsed into a general 10% clinic discount; free consultations, permanent 5%, and first-visit condition disappear. |
| Атлас (Серпуховский Вал) | `4790b53657300ce00b33f55a071e8469` | Headline up to 20% replaces three explicit 10% rates; specific exclusions disappear; 2025 versus 2026 expiry conflict is not reported. |
| World Class (Москва) | `8609176638f706d051d05a492359c2e8` | Only the up-to-20% membership discount survives. Five other benefits disappear, including 10% SPA during the first two months. |
| Додо Пицца | `1fb2504ab1758f4f653a96619a468134` | A closed list of participating towns is broadened to all Leningrad Oblast locations. |
| Цифровая Машка | `1777925f766ad477d1abaaa5e6ff988a` | The source requires buying a gift card; benefit_kind=gift incorrectly classifies the purchased product as a benefit gift. |
| Eshak (Новый Арбат) | `597978d858c9a8aab98c95d784b68b3f` | Priority seating is absent from every output field, including evidence/advice; the 10% discount survives. |
| Four Seasons (Петербург) | `a858d829fc08e6cb5a5648d57371ab2c` | Room-availability condition marked only for upgrade and early/late check-in is applied to all benefits, including breakfast and compliments. |
| Giorgio Suluguni | `854bb98a899ccc6e79e8d3ed88776aa0` | unknowns contains an unrelated semicolon-formatting instruction absent from the inputs. |

## Interpretation and limits

- Six cases lose at least one benefit from the entire JSON: Eshak (Новый Арбат), both Олимп clinics, World Class (Москва/Сочи), and Раковая (Новые Черемушки). This differs from the 26 cases where relevant text survives in evidence/advice but lacks its own benefit field.
- The iLocked negative is correct about an incremental benefit. The lost information is a separate restriction on discounts with gift certificates; do not convert it into a positive discount or call it a false negative.
- A field for the benefit description is needed, but cannot alone fix wrong percentage scopes, upper-bound qualifiers, missing components, or conflicting expiry dates.
- 22 captures did not find target text. Matching collector records were supplied; these answers are checked against saved source inputs, not an independently fresh UI confirmation.
- Source catalog observation was 31 October. Inference date is not proof that old offers remain available. Public records do not establish personal eligibility.
- This audit does not authorize automatic publication or certify unseen queue items. No model calls, provider changes, or remote writes occurred during the audit aggregation.

## Reproduction metadata

Evidence commit: `ef83c6068740f30bb9aca0dcf8f24020a23ef721`. Source catalog run: `41194911797`, artifact: `13041115453`.

The local reproducible aggregate retains all original issue descriptions and reviewer grades separately; the compact public summary contains no spreadsheet exports, destination IDs, credentials, or private account data.

## Implemented contract repair

PR #104 adds explicit benefit text, exact/up_to/from qualifiers and standalone program restrictions; adjusts target boundaries, per-component scopes, conflicts and user-facing wording; and fixes a transient null-body capture error. Fresh local full regression: 1576 tests, OK. GitHub run 41415126433 independently passed 1576 Python tests, 4 Chromium scenarios and 7 KEY tests. An additional general prompt rule distinguishes client benefits from internal personnel/partner remuneration after reviewing the Atlas source; it contains no partner-name or rate-specific exception. Schema/contract tests alone do not establish model answer completeness. Bounded live replay is the remaining model-quality check.
