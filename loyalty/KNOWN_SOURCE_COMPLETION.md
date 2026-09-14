# Known public pages and linked rule documents — 2.6.0

This release adds the residual public-page/rule-document pass to the existing collector. It does not claim all websites, regions, personal catalogues, outbound links or historical source references have been exhausted. The explicit reviewed set here is 46 residual pages plus three unmatched old S7 URLs, and 19 public Utair shortlinks. The wider curated-source URL inventory is a separate reconciliation task; matching another programme card is not proof that every alternative document was fetched.

## Implemented routes

Exact approved page URLs, selectors, required identity/condition text and record roles are in `known_rules.json`: 26 public rule routes. One additional route, `utair_rule_documents`, reads the 19 exact public aliases in `utair_documents.json`. The complete source registry has 75 routes; its bounded publication limit was raised from 50 to 128, not removed. Existing schema-v2 columns are unchanged; the additive `program_rules` record kind distinguishes supplementary conditions from a new discount.

| Group | Implemented source IDs |
|---|---|
| Aeroflot partner earning/redemption | af_bootwood_rules, af_wolford_rules, af_iway_rules, af_skyshop_rules, af_x5_rules, af_tripster_rules, af_comfort_rules, af_vipzal_rules |
| Bank/deposit programme conditions | af_gpb_rules, af_primbank_rules, rzd_finuslugi_rules |
| Membership/participation and activation | rzd_student_rules, t2_registration_rules, t2_magnit_rules, t2_sim_rules, t2_mixx_rules |
| Hotel programme details | azimut_privilege_rules, azimut_earning_rules |
| Utair linked programme details | utair_family_rules, utair_generations_rules, utair_rule_documents |
| Reviewed local/transport partner rules | ekp_sfera_rules, rgo_headquarters_rules, smartavia_rules, mir_101_rules, mir_aeroexpress_rules |
| Explicit historical terms | promomiles_otello_rules |

Smartavia emits four differently priced annual plans and one separately scoped EKP discount on the subscription, not a fabricated discount on every air ticket. Other page routes each emit a supplementary rule bundle. One bundle is not one incremental saving or one new unique partner.

### Reviewed native PDF extraction

Finuslugi and Primbank PDF rules use a native text layer, expected page counts, identity checks and explicit source fragments. Finuslugi retains deposit/bonus bands and timing conditions; Primbank retains spending/mile bands, fees and caps without inventing ambiguous boundary inclusivity. The documents were visually inspected alongside extracted text. No OCR, guessed missing text or silent truncation is used.

The 19 Utair aliases are fetched only while still linked from a freshly read official Status page. A public alias redirects to the observed HTTPS document host, `eu-s3.beelinecloud.ru`. The server-issued signed download URL is used transiently: it is never stored in records, logs or artifacts. Personal login and private-code activation are not involved. Redirect host, status, size, PDF format, page count and source title are checked. Network exception text is redacted; an actual refusal is not retried or treated as a valid document.

Full native text is retained page by page, with hashes and the stable public shortlink. Layout tables are NOT turned into guessed tier-to-service entitlements. The four-page transfer document has a visually verified sparse last-page table row, `Глубина (см) 22 24 26`; only that exact text is accepted as a sparse exception. A changed sparse tail fails review instead of being silently dropped. Reward lifetime, ticket validity or status duration is not offer expiry.

The concierge aliases `TlYigt` and `bFwqtV` returned byte-identical documents and merge by document digest plus equal text. Similar titles alone never merge documents: the two airport-privilege PDFs are different and remain separate. A successful current run normally contains 18 unique documents from 19 aliases. Partial failures preserve previously accepted documents and diagnostics. Cross-run partial-alias canonicalization is not an unrestricted global deduplication guarantee.

### Public product path and User-Agent correction

The public GPB product URL `/personal/cards/7515685/` was wrongly caught by a generic private-account-path rule. Only this exact host/path without query is now admitted; other personal, login, activation, credential or redirect paths remain refused. The ordinary anonymous Requests/Mozilla read succeeds where the default browser-context HTTP read returned 403. The adapter uses the tested read method, continues to apply the source policy, rejects redirects/refusals, and bounds bytes/time. Transfer commissions remain conditions, not rewards. Paid/unpaid mileage options, spending minimum, monthly mileage limits and separate fees have explicit fields.

## Finite disposition of the 49 residual page URLs

The 26 implemented exact URLs are enumerated in `known_rules.json`. All had at least one successful real dispatcher read in the development runs below; that does not erase a failure on a later run.

Three read pages are not added as extra discount records:
- `https://media.utair.ru/ugoodness`: donating miles to charity, not a shopper benefit.
- `https://media.utair.ru/promo`: a navigation page with time-scoped promotions, ordinary fare search, gift-certificate and charity links. Its observed August/early-September contests/sale windows were not promoted to current loyalty offers.
- `https://www.uralairlines.ru/baggage_detail/sverkhnormativnyy-bagazh/`: the Gold baggage allowance is already represented by the reviewed Gold tier section. The separate route/time-dependent excess-baggage fee engine is not claimed parsed or equivalent to a loyalty discount.

Twenty exact residual URLs did not yield accepted source content in this pass:

| Public URL | Observed limitation |
|---|---|
| https://www.rendez-vous.ru/aeroflotbonus/ | target HTTP 424 |
| https://sp.yandex.ru/s7 | access challenge; existing S7 programme-card evidence is a different source |
| https://vkusomania.ru/partners/aeroflot/ | target HTTP 450 |
| https://sovcomins.ru/bonuses/mili-programmy-aeroflot-bonus/ | target HTTP 401 |
| https://afl.premier.one/ | timeout |
| https://www.vtb.ru/privilegia/karty/debetovye/privilegiya-aeroflot/ | TLS verification failed in independent Requests diagnostic |
| https://uralsib.ru/aktsii/privetstvennye-bally-rzhd-za-oformlenie-karty | TLS verification failed |
| https://www.nspk.ru/press-center/details/00d06ff9-ac6f-41fd-9aad-39965b9762cd | TLS verification failed |
| https://rgo.ru/membership/loyalty-program/book24-ru/ | old exact path HTTP 404; not a claim about every Book24 offer |
| https://www.gov.spb.ru/gov/otrasl/c_econom/news/312063/ | timeout |
| https://www.gov.spb.ru/gov/otrasl/c_econom/news/312678/ | timeout |
| https://www.coral.ru/poleznaya-informatsiya/offers/aktsiya-sherwood-resorts-hotels/ | target HTTP 403 |
| https://www.utair.ru/support/6/dopolnitelnye_uslugi/ob_usluge_povyshenie_klassa_obsluzhivaniya | old support target HTTP 401 |
| https://www.utair.ru/support/6/dopolnitelnye_uslugi/povyshenie_klassa_obsluzhivaniya_za_mili_uteir_status | old support target HTTP 401 |
| https://www.utair.ru/support/9/kak_poluchit_promocod | old support target HTTP 401 |
| https://www.utair.ru/support/6/dopolnitelnye_uslugi/usluga_fast_track | old support target HTTP 401 |
| https://www.utair.ru/support/11/biznes_zaly | old support target HTTP 401 |
| https://marketplace.s7.ru/city/offer/tsum | exact legacy card HTTP 404 |
| https://marketplace.s7.ru/city/offer/CozyHome | exact legacy card HTTP 404 |
| https://marketplace.s7.ru/partners/offer/airo | exact legacy card HTTP 404 |

Official Utair PDF rules provide alternative source evidence, not proof that the old support URLs work. These 20 failures are separate from the eight primary catalogue failures already present in the production registry. Many failed candidates are deliberately not registered as repeat probes. No global claim that a host/country/GitHub can never fetch a URL follows from these observations.

## Development evidence and limits

- Discovery 34783973608: the 46 explicit residual page URLs and the public Utair aliases.
- 34788978963: recovered prior work, 29 rule/plan records across 25 newly implemented routes, all successful.
- 34788696611: specific Requests/TLS checks; GPB product returned real public HTML.
- 34790084864: all 19 public Utair shortlinks resolved to native PDFs with the verified ordinary User-Agent. An earlier default-Requests-UA attempt failed and is not the final result.
- 34790556879: four raw public PDFs saved for table/sparse-page visual inspection.
- 34790978787: 47 records /27 routes; 19 aliases ->18 documents succeeded, but GPB's original read method still returned403.
- 34791411313: corrected actual production dispatcher, 47 records /27 routes. GPB succeeded,18 Utair documents succeeded; the separate Generations HTML page returned403 on that runner, despite previous successful reads and the successful corresponding PDF.
- 34791683129: all three unmatched old S7 URLs above returned404; no old amounts were copied in as newly verified offers.

Latest branch archive SHA256: `04aa6210a53912008ceb394147f4fd54782ea88d523e4fe1371f1e1cd5d640a6`. Payloads passed independent JSON Schema, application validation and publisher preparation. All checked code/config/test bytes match the tested local revision. 335 Python and seven KEY tests pass locally, and the corresponding Actions test job passed. Tests cover known source registration, the >50-source publication boundary, late SPA article content, earning versus redemption, bank subscription and commission separation, PDF identity/size/sparse pages, ephemeral redirects, partial preservation and false rule-to-offer promotion.

Main publication is a separate gate: use its actual payload/counts, terminal publisher status and independent Sheet readback before claiming a completed sync. A successful workflow does not mean every source succeeded. Existing curated/legacy sheets, manual comment columns, Google permissions, scheduled-run flags and KEY code are unchanged. No paid service, new proxy, personal session, CAPTCHA solver or TLS override was introduced. Temporary diagnostic/registration files are removed before merge.
