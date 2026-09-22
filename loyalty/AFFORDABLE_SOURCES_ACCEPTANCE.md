# Backit, Club Avolta and Mantera — source acceptance, 22 September 2026

## Scope

The owner explicitly approved these three programmes. They extend the existing registry, collector, source validation, source-owned common projection and cleaned reader catalogue. No source account, membership purchase, coupon activation, bonus spending, paid provider or new recurring workflow is introduced.

| Source ID | Public root | Scope |
|---|---|---|
| backit_public | https://backit.me/ru/cashback/shops | Russian shop inventory and current non-promotional cashback tariff tables; not a product-level Ozon/Wildberries catalogue or bank acquisition ads. |
| club_avolta_public | https://www.clubavolta.com/ru | Source-linked categories and detailed cards in the Russian public edition; not personal eligibility or booking availability. |
| mantera_moments | https://lk.manteratravel.ru/faq | All five public tiers and their practical FAQ rules; pilot accommodation only, not all properties/businesses of the group. |

**Publication is a separate acceptance boundary.** This document records implementation and source evidence, not a completed Sheet update. Actual main publication and independent destination checks belong in AFFORDABLE_SOURCES_PUBLICATION.md once performed.

## Actual source observations and diagnosis

The original prepared code was recovered rather than rebuilt after interrupted chat output. Run35723564808 succeeded as a job but contained only five Mantera rows: Backit failed its inventory parser and Avolta returned403. These failures were not declared successful collection.

Run35733941590 at2026-09-22T13:32:11.755529+00:00 read **16/17 Avolta partner cards across six categories** and **all5 Mantera tiers**, with zero source errors for those two programmes. One Avolta card, DragonPass, was excluded for contradictory admission prices in the same source page. Source-local ordinary/headed Chromium resolved the tested Avolta request failure; other programmes retain their existing renderer. All TLS, access-refusal and budget checks remain. This is not a guarantee against future transient refusals.

Backit initially served40 server-rendered cards before the client paginator existed. A bounded readiness predicate now requires the expected page, total, page size, exact card count and named cards. Run35735134810 subsequently reached page13 and identified a genuinely valid dotted shop slug,22.10.ru, rejected by the earlier path validator. Dots in a single slug are now supported; traversal, foreign hosts, nested compilation routes, query strings and fragments remain rejected.

Run35735992565 traversed **916 unique listings /23 pages**. Most were not current useful offers:677 were explicitly labelled temporarily disabled and46 were financial/acquisition ads. Of193 attempted details,9 initially parsed,11 were excluded for dated promotional-rate uncertainty and173 exposed overly strict assumptions. Optional merchant SEO text had incorrectly been required for activation; optional merchant-specific conditions had incorrectly been treated as the only practical rules. The corrected parser uses the actual account/purchase controls and source-owned shop-rules panel, with a warning when extra merchant conditions are absent. No account or purchase control is clicked.

The next complete production-source observation, run**35738457482**, execution`e2cfa59990a45d2c5c27f248357830955a7864d1`, at**2026-09-22T14:11:49.926589+00:00**, produced:
- Backit:173 accepted records;677 disabled,49 financial/acquisition and13 dated-promotion exclusions;4 detail errors, all916 inventory entries accounted for.
- Club Avolta:16 accepted /17 listed,6 categories, DragonPass price conflict excluded,0 errors.
- Mantera:5 accepted tiers,0 errors.

The strict diagnostic workflow correctly reported failure for those four Backit details. Its full regression passed **1170 Python+7 KEY tests**; all194 actual records passed source, common-view and clean-reader checks.

Targeted run**35739903382** then read only those four detail pages, not the whole catalogue again:
- VkusVill contains two percentage tariffs and a third, empty-rate row holding a public coupon clause. Preserve that clause and literal code separately; do not convert the coupon amount/minimum order into cashback rates.
- Just Food uses a Latin `p.` among Cyrillic ruble labels. Normalize that observed spelling for display while retaining the exact source evidence.
- MTS Money is a debit-card acquisition ad, not shopping cashback; exclude it with the existing financial-ad category.
- takprodam-ozon returned catalogue content with no merchant-name/rates/conditions panel. Never fabricate a detail from unrelated catalogue cards. The parser recognizes a returned catalogue only when its actual catalogue-card markers and title are present; other missing detail layouts still fail.

## Value and practical-content contracts

**Backit:** fixed RUB amounts, percentages and ranges are separate typed values, with each customer's/order's tariff scope. A range is not its upper rate for everybody. Zero-rate exclusions remain conditions. Cash is only after merchant confirmation, not an upfront price reduction; payout methods/minimums require account review. Public literal coupon text is retained with its own restrictions. Optional HTML marketing paragraphs are not programme requirements.

**Avolta:** whole source-owned practical sentences retain registration, country, tier, frequency and new-customer restrictions. Ratings, merchant inventory statistics and travel advertising are removed from reader fields, not promoted into benefits. Plaza is25% off a paid pass, not a free pass. Kolet's volume, duration, new-user and subsequent-discount clauses remain. Country-limited points ratios and account linking remain literal source clauses. A generic source rates list can be empty even where the common representation retains a concrete non-percentage privilege.

**Mantera:** earning and redemption caps are different benefit kinds and use Mantera bonus currency, not cash. The pilot banner and pre-booking registration requirement remain. The source simultaneously refers to calendar and business days for accrual; both clauses and a conflict warning are retained rather than silently reconciled. No participating-hotel list behind the account was read.

The common projector re-derives each row from source-owned evidence. Rehashing a modified row cannot remove conditions, change the merchant/programme, invent expiry or promote eligibility. The existing clean catalogue quality layer stays active; no raw-announcement switch or source-observation placeholder is added.

## Regression and evidence

Final production code through`d70c360bbcc2b2ecb6d46b14c012e96ff5399da0` passed **1174 Python+7 KEY tests** in run**35740677256**, job106789319244. Its extra temporary replay helper then failed on an incorrect assertion that every fixed-RUB record must populate the legacy lexical rates list. This is not the canonical fixed-cashback representation: those values are carried by the source-owned common projection. The helper was corrected to inspect those values and preserve the original observations; production data/code were not altered to satisfy that assertion. The same194 actual records and two repaired source DOM excerpts also passed local replay. A corrected CI replay follows without another site crawl.

Persistent source fixtures and regression cases cover hydration, page counts, dotted paths, disabled/financial ads, missing/duplicate clauses, customer scopes, range bounds, zero tariffs, coupon-versus-cashback separation, page identity, marketing contamination, Avolta price conflict, Mantera pilot restrictions, rehashed tampering and reader projection.

Digest-verified evidence artifacts:
-10696578677 /run35733941590:865ca504df45a398ab5d156aa30b723294d11787d3f4a42d73d4dd0cf7b0a6d7.
-10697405885 /run35735134810:266e6772b80e5ca20bee58b02b96743085ef0741a265236ea3286b9a1ef47087.
-10697392832 /run35735992565:152f43e831e7da9082f8c8d10370066b5dcc8b48bcc1c9676a1d5560800f7ca0.
-10699341182 /run35738457482:8daff8d83a32c6f1e3cd3a39466980fbf7006d9d433382ef77f353fe12af335a.
-10699591435 /run35739903382:e441594d812b8534ca51aab52f0640d444d423f890519806e3d7b7d0542b1d15.
-10699735209 /run35740677256:65078fef17fed7ed57552e78c8eb6ad2bee514da161694e69851671ed5e4fa02.
All ZIP digests and CRCs were independently checked before reading. Artifacts are short-lived; Markdown, source fixtures and exact execution identities provide recovery.

## Limits and operation

Use the existing daily05:23UTC job and serial private Google publication. Backit's reviewed local inventory/detail ceiling is1200, within a1000-second source budget; it must not silently present a truncated first500 as complete. Avolta has an80-card boundary and source-discovered category links. Request pacing and stops on429/401/403/challenges remain.

Dated Backit promotional tariffs are deliberately excluded pending proper date-context handling. Missing or failed observations do not erase prior stored records; this release does not add a general disappearance/retirement engine. Future excluded previously stored cards can retain their last-known observation under the existing upsert contract: check observation age before calling an offer current. Unknown expiry and personal entitlement remain unknown.

No source-specific credentials or private workbook exports are present in public artifacts. Browserbase is not required by these collectors. This work does not change billing, delete historical artifacts or alter unrelated schedules.
