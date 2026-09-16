# EKP public catalogue API — 2.9.6

## Purpose and release boundary

PR33 replaces the repeatedly failing daily provider-root attempt for EKP with a dedicated anonymous public API collector. The implementation is merged; actual run outcomes and final destination checks belong in `COVERAGE_CURRENT.md` and the PR discussion. Green regression tests or this document alone do not prove successful live publication.

The objective is current, source-owned terms in the existing Google Sheet, without payment, another account, server administration or an always-on laptop. No source-account session is used.

## Source-observed contract

The website's ordinary anonymous UI sends POST to:

`https://ekp.spb.ru/api/portal/loyalty/partners`

Observed query:

```json
{"pagination":{"limit":120,"offset":0},"filters":{"categories":[],"name":"","qrDiscount":false,"region":"98"}}
```

The UI exposes page-size120 and labels the observed filter `Все регионы`. `98` is retained literally; it is not interpreted as a geographic entitlement. Subsequent pages use the same query with offsets120,240,..., subject to fresh policy and bounded source checks.

Bridge run35061202217 compared source API identity, `description_authorized`, `loyaltyDescription` and `discountScheme` against three actually opened public modals and one login-gated modal. All comparisons matched after whitespace normalization. An independent plain HTTP-mode POST with the exact source-observed request returned the same120-row public projection and reported total1046. The total is not an answer constant or future expected count.

The bridge used175 Free credits, with usage6749 before and6574 after. Its archive10432726441 was downloaded and SHA256/CRC checked: `04db1d09bc41e16c604ce6d972e803c473c7851d44386e0bfa55a5409f870fcd`. Extended response cookies, headers, unrelated requests and account-like fields were discarded, not archived. No guessed private endpoint or source credentials were used.

## Public projection and interpretation

`ekp_catalog.py` binds each record to its native partner ID, source name, typed active/access flags, current page digest and observation time. It preserves public business description, loyalty conditions and redemption instructions. Mixed source tags are retained in their native category objects, not assigned as eligibility regions.

When `description_authorized=true`, protected condition fields are discarded **before parsing or persistence**, even if the anonymous API included them. Such records retain only public identity/business description and the observed requirement to sign in. Inactive and missing-term records likewise remain `source_observation`, not current benefit claims. QR/barcode objects, account/subscription fields, contacts and private codes are excluded from the saved projection.

An accepted public-term record is not proof of current offer eligibility. Absolute validity, table relationships, images and linked documents are not guessed. The primary source URL identifies the actual API; `details.public_detail_url` preserves the public website route with region context, while `detail_url_individually_opened=false`. This avoids falsely claiming every detail URL was separately visited.

## Pagination and failure behavior

The collector verifies the source-reported total on every page, exact offset and last-page size, and no duplicate IDs within or between pages. Each accepted row is reconstructed from its safe saved projection before Google authorization. A complete count means the observed public result set was traversed; it does not include private conditions or unread external rules.

The job stops at300 reserved credits,12 source requests or the bounded deadline. One25-credit policy read leaves at most11 pages/1320 source entries. A larger catalogue or later failure produces an explicit partial result; earlier good rows remain publishable. Invalid individual rows are reported without replacing them with old text. A valid failure-only report can update coverage without giving historical offer rows a new date.

Fresh robots rules must permit the root and API. HTTP refusals, challenges, rate/quota/auth errors, unknown prices, unexpected schemas and source changes do not become successful content. Source pacing is honored. There is no automatic paid upgrade or retry loop.

## Operation and Free budget

- Original direct collection: daily05:23 UTC, unchanged.
- Existing provider chain for Nordwind/Coral and remaining roots: daily06:03 UTC, now using `--separate-ekp` to omit the superseded EKP provider-root request.
- Dedicated EKP: Monday07:13 UTC (`13 7 * * 1`) and manual dispatch through `.github/workflows/ekp-api.yml`.
- All credential-bearing collection/publication shares the existing repository/ref concurrency group. Google scopes, service account, WIF, managed tabs and private normalization are unchanged.

Daily provider maximum94 root credits +175 Coral traversal =269. In31 days, at most31 daily and5 weekly300-credit runs reserve9839 credits. This excludes diagnostics, manual reruns, other usage and provider tariff changes. The account's actual remaining balance can be lower during development. Free status and adequate balance are required; insufficient credit stops collection rather than spending money.

ScrapingAnt's published Terms section5 permits only one account (https://scrapingant.com/legal/terms-of-use/). Do not rotate extra free accounts to enlarge the quota. Optimize reads/frequency or evaluate another legitimately free provider instead. No extra account is needed for the designed recurring budget.

## Verification and known limits

Branch execution35062325011 passed611 Python and7 KEY tests, no skips. Test artifact10432638776 SHA256 `c6effb6f3823c78b10837cfaaf857835b6ddaf11b3e9b8da65061cf8b760fc41` was downloaded/CRC checked, and all eight changed file bytes matched the reviewed tree. Tests cover real projection/pagination/partial preservation, protected-field exclusion, mutation/forgery, exact POST routing, quota/price stops and artifact reconstruction. These are not a universal guarantee for future website changes.

Source-response digests are observed before projection; original responses containing discarded fields are not retained. Safe projection digests and reconstructed records are independently checkable. Do not claim to recompute an unretained original body hash from the projection.

Before reporting a source as restored, check the fresh main run, its complete/partial result and errors, the completed publisher, and the actual destination after the final write. A push-triggered release check is not an already-observed future weekly cron execution. PR23's older preview-only draft must not be merged into this implementation.
