# EKP gated-offer audit — 18 September 2026

## Result

The accepted region-98 catalogue has **1045 entries: 935 public-term records and 110 gated observations, representing 106 distinct displayed partner names**. All 110 were inspected, not only a sample. Their public projection has `description_authorized=true`, descriptive text and identifiers, but no retained protected terms. No numeric discount/code was found in those public short descriptions. This is a genuine practical information gap, not 110 failed network requests and not evidence of no offer.

**No gated detail was newly recovered in this audit.** No source account, SMS, cookie, private code, purchase or permission change was used. The existing public collectors and the same destination remain unchanged.

## Evidence and method

- Catalogue: accepted main run `35070130567:2`, commit `354a32cb8ca5d0c35e5462cef4b672bdd79e920b`, artifact `10435868136`, SHA256 `c751f45318f4164894535596d1cad8af8755263eca347fcbe053c334b2b88c3f`. The source observation is 16 September, not relabelled as newly fetched on the audit date.
- Official announcements: main run `35331811091:1`, source observation `2026-09-18T09:53:54.187474+00:00`, artifact `10541703021`, SHA256 `6ecd9471aad9dbb07f4889188baf779c162bcefd09a32e6468bd7549450140c2`. Its EKP scope contains 46 accepted announcements from the bounded 180-day collection; the Sheet retains one additional older announcement.
- Both downloaded ZIPs passed SHA256 and CRC checks. All 110 gated observations and all 46 official announcement records passed the existing record validator. A fresh private Sheet export corroborated the stored 110-observation set and presence of the cited supplementary offers; that export was not published.
- Match the **explicit native partner ID in each announcement's source-owned `linked_cards`**, not a fuzzy brand substring, prose percentage or neighbouring partner. Retain original publication time, linked URL and region parameter.
- Fourteen gated partner IDs have at least one such official announcement reference; the other 96 have none in this bounded announcement set. The latter is not a claim that no public reference exists elsewhere or before the collection window.

**All matched announcement links use `region=78`, while the audited catalogue query used `region=98` (UI label “Все регионы”).** Same native partner ID provides a reference for lookup, not proof that regional offer terms or eligibility are identical. Do not copy/merge rates into the gated region-98 record.

## Exact references

| Native partner ID | Displayed partner | Official announcement | Publication date | What is supported |
|---|---|---|---|---|
| 3377 | СберАвто | https://t.me/ekpcard/5425 ; https://t.me/ekpcard/5440 | 2026-08-05; 2026-08-08 | Own 5% servicing/tyre-service offer in the first post; code remains gated |
| 3561 | MAlbums | https://t.me/ekpcard/5440 | 2026-08-08 | Partner-list announcement, no assigned numeric rate |
| 3558 | Атлон ФМ Север | https://t.me/ekpcard/5440 | 2026-08-08 | Partner-list announcement, no assigned numeric rate |
| 3525 | ГОРБИЛЕТ | https://t.me/ekpcard/5337 | 2026-07-08 | Special-code mechanism, no numeric rate or literal code |
| 3382 | Семицветик | https://t.me/ekpcard/5279 | 2026-06-17 | Partner-specific announcement; fuller conditions require login |
| 3009 | Шишки на Лампушке | https://t.me/ekpcard/5260 | 2026-06-10 | Partner-list announcement, no assigned numeric rate |
| 1991 | Важная рыба | https://t.me/ekpcard/5209 | 2026-05-28 | Special offer/code mechanism, no literal code |
| 2900 | Абсолют Страхование | https://t.me/ekpcard/5196 | 2026-05-24 | Special-code mechanism, no literal code |
| 2509 | Культпоход | https://t.me/ekpcard/5187 | 2026-05-22 | Audio-excursion offer; fuller terms require login |
| 3369 | Академиа Особняк Шувалова | https://t.me/ekpcard/5163 | 2026-05-14 | Special booking offer, no numeric rate |
| 3338 | Коннект Тур | https://t.me/ekpcard/5130 | 2026-05-01 | Partner-list announcement, no assigned numeric rate |
| 2951 | Kaspersky | https://t.me/ekpcard/5107 | 2026-04-22 | Partner-specific special offer; fuller terms require login |
| 251 | Теплоход СПб | https://t.me/ekpcard/5075 | 2026-04-10 | Seasonal public announcement; fuller terms require login |
| 1593 | Нева Тревел | https://t.me/ekpcard/5050 | 2026-04-01 | Online/quay offer announcement; no numeric rate in this post |

Only **one of these 14 partner IDs has a quantified own benefit in this exact announcement set**: СберАвто. Its 5% is for vehicle maintenance and tyre service, through the EKP application's “Автомобилист” service or the Sber Auto assistant chat; the announcement directs users to authorized EKP access for the programme. The literal code, complete exceptions and expiry were not recovered. The announcement and rate already exist in the Sheet as source record `a6309b9e5e1ab3a2c09dd87b79ee22a43db5ece74553bf77ea7d2f185c0e7ef5`; do not count it as a new offer from this audit.

## Useful independent public source already covered

Neva Travel's own public page, https://neva.travel/ru/promotions/skidka-dlya-derzhateley-edinoy-karty-peterburzhtsa/ , states 5% online using an EKP code and RUB 100 at the quay ticket office upon presenting the card before payment, one adult/concession ticket per card. It specifies Saint Petersburg/Leningrad Oblast, navigation season 2026, non-combination and exclusions for special programmes. The displayed period is 8 April–11 November 2026. The code is not published on this page.

The page is already collected as `ekp_neva`, Sheet record `19beaef59338298ed6a0df3f974fdca7c22ed904060814739cd568b21c1f1679`, with the 18 September source observation above. The audit independently opened the official page through web retrieval, whose cache date was older; this was corroboration, not a new pipeline timestamp. Keep this supplementary offer separate from native IDs 1593 and 2236 and from the “Серебряный возраст” programme. A shared brand is not an equivalence proof.

## Lookup and remaining boundary

Search the public official-announcement body in `details.message_parts[].text`, as well as title, benefits and linked-card IDs. An empty `conditions_text` in an announcement is not evidence that the post has no usable information. Do not assign one multi-partner announcement's percentage to all linked partners. Existing public records for a similarly named merchant can concern a different native ID, card tier, campaign or region.

The checked web searches also returned other programmes' benefits (for example the Novosibirsk resident card and bank ЯРКО), old press mentions and unrelated “Афиша” services. They were not used to fill EKP gated fields. There was no exhaustive web search of every partner's independent website.

Remaining: authorized access and a suitable private destination would be a separate account-dependent task. They are not supplied by changing a selector or retaining fields that the anonymous API labels protected. Until then the **110 gated observations remain gated**, with the precise public references above available as supplementary evidence. Do not repeat a whole EKP crawl merely to rename these gaps as completed.
