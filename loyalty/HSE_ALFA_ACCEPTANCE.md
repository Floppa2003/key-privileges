# HSE alumni and Alfa Only — accepted state, 18 September 2026

## Result and scope

The owner explicitly requested `https://alumni.hse.ru/loyalty/partners/` and `https://web.alfabank.ru/partner-offers/`. Both are registered in the existing source inventory. HSE offers were actually collected and published into the SAME `скидки` spreadsheet, `1uFR7croj7p6RRNPcoTRYlVl06hKsurkIgyu1IdMMB-4`. Alfa has an explicit failed-access report, **not a collected cashback catalogue**. No login requirement, absence of cashback, personal eligibility or offer activation was established.

PR63 merged as `d51cc66b9c9c53492cf8dbbfb26f12832c1f1cee`. Existing selective request `2026-09-18-hse-alfa-public-sources-63`, commit `d7be819a405d635e60cd6dd3542afa79380af469`, selected only `hse_alumni,alfa_only_partner_offers`. Main run `35371990357:1`: collection job105687885967 and publication105688320796 succeeded. Source observation: **2026-09-18T17:03:41.137073+00:00**. Source rows were published/read back at17:04:15UTC; final unified publication/readback completed **17:06:59UTC**.

Existing daily collection now includes the two registered sources. No new recurring schedule, paid service, provider account, user computer, server, sharing permission or destination was added. The ordinary collector does not use the provider for these sources. The separate Alfa Free-reader experiment was on demand only.

## HSE source result

- **55 inventoried partner entries:51 with owned detailed sections and4 preview-only observations.** Status remains `partial`, not full detail coverage. The whole observed card inventory is represented, but missing source sections are not fabricated.
- Missing named anchors: `skyeng`, `mordapechat`. Empty sections: `skillcup`, `academiya`. These records retain the source summary with no automatic benefit/rate/literal code/full-detail URL. `mordapechat` is not the separately detailed `mordadovolna` offer.
-45 records contain literal codes;29 distinct literal strings,49 code occurrences. These are neither49 merchants nor49 universally applicable coupons.
- Explicitly expired: Ретрит-центр МА-МА ends2026-01-01; ГрузовичкоФ ends2025-12-31. Source publication remains visible, but the date/status are preserved as expired. Other unknown dates remain unknown.
- «Сила ветра»:10% for SV20 training with `HSExSilaSport10`, no stacking, published end2026-12-31. A separate20% clause is **August-only**, without an explicit year on that clause; it must not be presented as a September20% rate. Common benefits retain the calendar constraint and owned rules.
- Flowwow/ФЛАУВАУ:10% with `hse10`; the source says all orders. Gorilla by БАСТА15% with `GORILLATIME` and alumni-card presentation. Альпина15% with `HSEALUMNI`. These are published HSE terms, not tested checkout results.
- «Много Лосося»: separate `VYSHKA10` repeat-order and `VYSHKA20` first-order scopes, app use and thresholds remain in the source body. Do not combine them.
- Донстрой's100% payment prerequisite is not a100% discount. The source-specific rate and common-view paths both enforce this boundary.

The successful live source contains55 cards. An older web-search representation contained fewer cards and different Sila Vetra wording; it is not the current source truth. No external partner checkout, eligibility verification, account creation or coupon issuance was performed.

## Source identity and evidence

Initial ordinary source check `35369084201:1`, execution `d41c13b1a38d04a5210a50540a4a2cd18856b3bb`, read HSE successfully but the generic diagnostic sanitizer stripped fragment/name identity. That diagnostic is not sufficient for exact joins. Its artifact10557474077 SHA256:`adeb4bf5d36db7b0d1575afa8615f083c4df331de22c20ab7c08ef8eb1696afa`.

Corrected HSE source check `35369463758:1`, execution `358dcb539a19f5eac0222383c53fb02d1d3dc117`, preserved the public programme body, raw hrefs and named anchors while excluding scripts/forms. Source interval16:36:53.041473–16:37:01.012400UTC. ActualHTTP200, exact final URL and source rules were checked. Saved public DOM SHA256:`821ea05dbaff1b4afcb22277868e9c8f924845fdaf4f508e0c8b6a97589daf2f`; full received DOM SHA256:`a7754b0075c66696a4584e258487956d8e92526b4b671006da1351378545e2a7`. Artifact10557344872 SHA256:`912bfbb9963df7e95e3948b5f33f6517801f9c19f05948f02e862a0146e4d14a`.

Records join each `.fa-person__item` to its exact named-anchor section, not neighbouring DOM order or a preview rate. A category `.nom h1`, next named anchor including an empty anchor, and source inventory boundaries stop ownership. Legitimate partner H1s and multiple owned sections remain supported. Unlisted old sections are not imported merely because they remain in page markup.

## Alfa: unresolved access, precisely bounded

The ordinary source check and both fresh dispatches stopped during source-policy retrieval with **`ERR_CERT_AUTHORITY_INVALID`**. No authenticated bank session was used and TLS verification was not disabled.

Existing Free-reader experiment `35369543970:1`, execution `23e23be37fdf62771fb99583195bc76bfa54fa39`, interval16:38:12.408241–16:38:14.896545UTC, confirmed the Free plan, reserved/charged **1 credit**, and stopped at **`robots_not_readable`**, before requesting the offers page. Ceiling21credits/3requests was not consumed. Artifact10558225419 SHA256:`7e6104cb60fbbc8b70e2c9a22ee2ca0c61b517deb7a027ac67956dd1ae4a8b1c`.

Accordingly `alfa_only_partner_offers` is mode`probe`,45-second bound, normalized0, status`failed`, coverage`not_collected`. The failure is visible at acceptance in `parser_coverage` row1509. This is not proof of absent cashback, a login requirement, or a fully implemented personal Alfa Only integration. General bank advertising and other premium campaigns were not substituted for the requested catalogue. Correct CA trust or a genuinely public alternative could be a future distinct investigation, but was not implemented or verified here. No personal bank data may be put in public artifacts or a link-accessible spreadsheet.

## Code and tests

Six intended production/config/test files: `hse_alumni.py`, `tests/test_hse_alumni.py`, `normalized.py`, `collect_normalized.py`, `sources_normalized.json`, `unified_normalization.py`. Existing sources and publisher architecture are retained. Temporary patch and both one-time branch workflows were removed before merge; the on-demand main diagnostic remains and preserves earlier runs by commit/run identity.

Preparation `35371529378:1`, execution `aab66548051a158452fcd83042ea3bfd853578ab`, passed **992 Python tests /7 KEY, no skips**, including22 new source-boundary regressions. Wiring tests failed before the integration. Real source replay and fresh normal dispatcher produced55HSE records and the explicit Alfa failure. Every one of the55 replay/live records matched apart from observation time. Common-view replay rejected payment100% as a benefit, retained month restrictions and excluded previews from benefits.

Artifact10558154026 SHA256:`19506ffeab5943310ca3820d8624f875a4634724fd087697702cc507405e9d8e` and ZIP CRC were independently checked. All six code/config/test files byte-matched reviewed local code. Main tests subsequently passed; **all63 executable hashes** in the main source artifact matched reviewed code. Main artifact10557988686 SHA256:`ad035a60571ff3f01fe3008fef8eb58f6c0f1376a677e9dfa812a61e74ac8077`, CRC checked; all55 records again matched reviewed source replay apart from actual observation time.

## Independent destination acceptance

Fresh baseline before PR63:2512 parser/3160 unified records, `verified/current`, practical-offers-v1. Source fingerprint`9df8d22470756f64f930ec09135fec2cf6c279ebe67833037084c5dac77a269e`, generation`481b8dad58b763edd90f5c2a2abc763260c11c52fd1e33ab3ba7aaa0194863cb`. This baseline already includes the three independently published PR62 Sacvoyage records; do not redo them because an earlier chat was interrupted.

After publication, native metadata/cells and a fresh independent export confirmed:

- **2567 parser /3215 unified records**, final manifest`verified/current`, practical-offers-v1.
- New HSE source rows2541–2595 and report rows1508–1509 at acceptance. All **1403 managed new source/report fields** exactly matched the fresh main payload. Later lookups must use stable IDs, not these row positions alone.
- All2512 previous parser records and their positions/manual fields, every previous report cell and seven original/history tabs unchanged: yandex_discounts_complete_all,VG_community_offers,loyalty_partner_benefits,loyalty_sources_audit,parser_inbox,parser_runs,parser_documents_archive.
- All8 workbook formulas unchanged; document archive still hidden. The archive was not re-imported into practical views.
- Independently reconstructed inputs and practical normalization matched **every current managed field** in the four common views:3215records,3755benefit components,9750conditions/costs,712code/delivery components. Manifest audit/fingerprint/generation also matched.
- Native checks confirmed Flowwow code/rate, Sila Vetra seasonal/end-date clauses, both expired records and Alfa's exact failed source report. Sample common-view cells retain10pt/top/wrapped formatting. No whole-workbook rendered, ACL or personal redemption audit is claimed. Read-only local exports were not uploaded to the public repository or another spreadsheet.

Current source fingerprint: **`3a4c08a735bb9504cac776e27dcf64bf6f0ba102b4c5fa384f28216d7875722f`**.
Current generation: **`28bf061d69c3503f2f86ee5365eb81e447db5ddede936d98b3c25554ed0e6981`**.

These are acceptance-state fingerprints, not universal source freshness or usable-discount counts. Existing RZD8 full-detail gaps and EKP110 protected records were not reclassified by this HSE integration. Public catalogue success does not certify future cron runs or personal bank/loyalty eligibility. Keep actual dates, region/programme/partner/code scopes and unknowns; do not revive expired or month-only promotions for a higher completion count.
