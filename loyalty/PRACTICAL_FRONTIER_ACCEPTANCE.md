# Practical frontier checks — 18 September 2026

## Outcome, not merely successful jobs

| Requested gap | Verified result | Remaining boundary |
|---|---|---|
| Eight RZD incomplete cards | Two prior transient failures retried after fresh catalogue membership; both still fail. Zero full details recovered; eight existing previews preserved. | Six historical login pages were not retried as transient failures. Google errors do not expose origin HTTP status or prove removal. |
| 110 gated EKP observations | All 110 inspected; 106 distinct displayed partner names. Fourteen native IDs have exact references in the bounded official-announcement set. | Zero protected detail records recovered. References are not complete conditions; region 78 announcement links are not certified equivalent to region 98 catalogue terms. |
| Coral interactive listings versus sitemap | Across same-day observations of all 20 categories, 69 unique offer URLs; every one already exists in the Sheet. Five observed offer URLs are absent from the sitemap. | Latest browser pass alone is 19/20, with a Gadgets access challenge. Gadgets was supplied by a separately timestamped successful earlier observation, not relabelled as current-run success. ALEF remains sitemap-only. |

No discount-table source records were added or overwritten by these checks. Existing recurring collectors had added four records before this turn's baseline; do not attribute that increase to PR58 or PR59.

## RZD: narrow retry implemented and exercised

PR58 added `frontier_checks.py`, its regression tests, a small public-category URL extension in `coral_import.py`, and the on-demand `practical-frontier.yml`. It merged as `b9a9cf992431ffb3aff010cba03d7a1f8caeacec`; the unique request file triggered main run **35339529804:1**, execution commit **0b20a8e05517951f41a47c5d9a72fa3cca01ed9a**. The merge skipped push jobs to avoid an unrelated complete Coral import; the targeted request ran the final main regression.

The retry selects at most eight transient-error previews from a recent accepted main bundle, reconstructs the original bundle, and checks fresh source policy, home link and affected catalogue membership before reading selected details. It does not retry six login/insufficient-content pages, invent a fixed partner inventory or crawl the full catalogue. Recovered records would be independently replayed before the existing literal same-Sheet writer; no recovery means no offer publication.

Actual RZD job **105582232150**, **11:26:11.155229–11:29:34.378693 UTC**, made **five imports, zero provider credits**. Both targets remained listed and both returned `rzd_import_error_cell`:

- https://rzd-bonus.ru/promo/poluchite-4000-ballov-rzhd-bonus-za-oformlenie-programmy-smart-plyus-ot-renessans-zhizn/
- https://rzd-bonus.ru/promo/500-ballov-rzhd-bonus-za-kazhduyu-noch-prozhivaniya-v-otele-grand-karat-sochi_2026/

The workflow job completed successfully as an audited attempt; the source report is correctly **failed, 2 selected, 0 normalized, 2 errors**. Publication job **105583183481** was skipped. All eight previews remain stored; no source observation was promoted to full details.

Three additional manual reads in an isolated temporary tab of the existing public staging workbook checked Renaissance's title/H1 alone, Renaissance's raw HTML import, and Grand Karat's raw HTML import. Each returned Google `N_A: Resource at url not found.` This is evidence against an overly complex detail XPath as the sole cause, not an origin 404, an expiry statement or proof that another authorized retrieval path cannot work. The temporary tab was deleted; fresh metadata confirmed exactly the four original staging tabs remained. No main discount cells were used for the experiment.

## Coral: static failure diagnosed, rendered inventory reconciled

The same main run read current root, sitemap and all 20 category pages through the existing Google reader: **23 imports**, **11:29:53.647393–11:31:48.294212 UTC**. Root yielded 20 categories and sitemap yielded 101 category-scoped candidate URLs. All 20 category documents were unrendered JavaScript templates and correctly failed with `coral_category_not_rendered`; zero accepted category lists is not an empty catalogue. All 23 successful import observations passed their existing formula/hash checks; the source-category failures were independently reproduced.

PR59 added `coral_browser_inventory.py`, five tests and a separate on-demand workflow. Main merge/execution **4c01ac48de58f4576afff07c485b259de6ca21db**, run **35341044020:1**, collection job **105586985186**, completed at **11:47:13.117987 UTC**, starting at **11:44:36.328036 UTC**.

It reused the checked root/sitemap and the existing Free ScrapingAnt reader. Two sequential shards retained the reader's 111-credit/12-request bounds; the total reservation ceiling was 222. **Actual recorded reserved and charged credits were 202**. Both shards performed the existing Free-plan preflight. No account cookies, new provider, paid upgrade, individual offer details, PDF traversal, coupon issuance or Google destination access were introduced. No schedule was added.

Latest pass: **19 accepted categories, 68 unique offer URLs, 35 ordinary merchandise boxes**, and one explicit **Gadgets `access_challenge`**. No challenge-solving or alternate-route retry followed that category. Every accepted page's HTTP status, exact final URL, saved HTML hash, category identity and ordered timestamp was checked; the original category mapper independently reconstructed the 68-URL union and differences. All 68 URLs were already stored in the Sheet.

### Same-day supplement, with its own time

Existing normal collector **35335174051:1** had successfully read https://coralbonus.ru/klub-privilegii/gadzhety/ at **10:36:28.406319–10:36:34.162655 UTC**. The saved document `d2de14375086e4dc10def6d9d8bd9b4eafa9c0727325730bac24909b38bf2e79.html` matched its SHA256, HTTP 200 and exact final URL. The original mapper extracted LG Electronics Inc and a source-owned cross-category PAURI card; PAURI already belonged to the later union.

Thus **all 20 root categories have a same-day accepted observation across the two runs**, yielding **69 unique offer URLs, zero absent from the Sheet**. This is a union over **10:36:28–11:47:13 UTC**, not one simultaneous snapshot, not a new source observation for old detail conditions, and not 69 guaranteed personal discounts. The latest run remains `complete=false`; its Gadgets challenge is not erased.

### Exact differences that matter

The five observed offer URLs absent from the current sitemap are NAME SKIN CARE, Мариджентал, GELTEK, Feedback and Styx Silk Body, all in the beauty category. They already exist in the Sheet and were updated by the earlier normal collector on 18 September. A sitemap-only collector would miss these; the existing complementary collector did not.

Of the 72 stored club records, three are outside the same-day observed 69-URL union:

- MegaFon and BookingCar already carry published expiry **2025-12-31** and expired status. They are not current missing discounts.
- **ALEF** is still in the sitemap but was not observed in the rendered category list. Its stored 10% offer is dated 17 September and has no known expiry. Preserve it as a discrepancy; do not silently delete it, infer cancellation or present current availability without checking the exact offer.

The sitemap's 101 candidates consist of 64 observed referral-offer URLs plus 37 not in the observed union. The latter reconcile with 36 previously classified ordinary merchandise entries and ALEF; they are not 37 missing discounts. The 35 merchandise boxes in the new rendered pass are a different unit from 36 sitemap merchandise URLs. The current sitemap candidate set also matches the checked 17 September set.

## EKP audit and lookup implications

See **EKP_GATED_AUDIT.md** for all 14 native IDs, official links, publication dates and limitations. All 110 protected observations remain gated. Only SberAuto has a quantified own benefit in the exact matched announcement set (5% servicing/tyres); the code and complete conditions remain behind authorized access. That announcement was already stored. Neva Travel's independently published 5% online / RUB 100 quay-counter offer was also already collected; its online code is not public, whereas the counter alternative requires presenting the card.

The 96 unmatched IDs have no exact link in the checked bounded announcement set, not proof of no public reference elsewhere. No exhaustive crawl of every partner's independent website was performed. Brand similarity, another regional card, a different native ID or a different EKP tier does not authorize copying terms into a gated record. For lookup, inspect source-owned `details.message_parts[].text` and explicit linked-card IDs as well as automatic benefit rows; missing automatic percentages are not proof of no offer.

## Code and evidence verification

PR58 branch preparation **35339136624:1** and main **35339529804:1** passed **922 Python / 7 KEY tests**. The new category-boundary regression failed before the tiny URL extension and passed after. All four execution-file hashes matched the reviewed bytes.

PR59 branch **35340746123:1** and main **35341044020:1** passed **927 Python / 7 KEY tests, zero skips**. Main's downloaded code archive exactly matches the tested branch for the added module, tests and workflow. Main Python log: 927 tests in 40.331s, OK. This is full GitHub-environment acceptance; no complete local transport/policy-suite pass is claimed where the local `protego` dependency was absent. Independent local checks covered saved hashes, exact code, source mappings, times, identities and destination values.

| Artifact | Purpose | SHA256 |
|---|---|---|
| 10544571515 | PR58 main code/tests | e59168eff2706e547ebd10c911e366ae74da8f0504f993c7bf2096d60c81c770 |
| 10543954860 | RZD targeted evidence | 21c24a8c443e1cc8753c95928627b7e14d6ed42234124f189ece5a990702597f |
| 10545140209 | Coral static root/sitemap/categories | 577a2ed10821e7f454ff926477bccb6801b6538f65d59888f3b4f8a1b6dc6819 |
| 10544324259 | Coral latest rendered inventory | 881cc3055644d0b70c8acf904529dd7e28c20e3b81df73e440b344443fbb44ab |
| 10542586687 | Earlier same-day rendered Gadgets | 39e785836d9105547b3ba6a218093a927e3dd1dd45a4c0c199b826940e9d1175 |
| 10544643369 | PR59 main code/tests | cb084313dda07cdfa2a80c6af39d1a5420612b7d65bee301ad78e160cf72b3d7 |

All listed downloaded ZIPs matched GitHub SHA256 metadata and passed CRC. Source archives have the original run identities; they are not rewritten as new observations. Existing private workbook exports were not committed or published.

## Destination preservation and operating limits

Same destination: `1uFR7croj7p6RRNPcoTRYlVl06hKsurkIgyu1IdMMB-4`, title `скидки`. Fresh before/after exports have identical values across **all 14 tabs**, including manual-comment cells; all **eight formula cells** are unchanged. Native manifest still reads **2498 parser records / 3146 unified records, verified/current**, `practical-offers-v1`. The four-row increase from the earlier PR57 checkpoint preceded this work. The 64-record archive remains hidden. Whole worksheet XML bytes differed between exports; no byte-identical formatting or complete visual/ACL audit is claimed.

- Source fingerprint: `75f7e08fba1647cbc9c5abac6e401b9a1e077dcbb5f75cf38b98a84198d49973`.
- Generation: `d02d29c3d62bd678b7595ab37154517ee211a0e4d8d5ffb43fdeea7cda9a3f09`.

Existing schedules and shared serial locking remain. Both added workflows are on-demand, not new recurring consumption. Reusing a source-account session, changing Sheet sharing or publishing protected terms would require a separate authorized/private workflow. Earlier `anyone:writer` sharing was not re-audited or changed. `current` is normalization status, not offer validity or personal eligibility. Do not repeat these whole inventory checks merely to manufacture a higher completion count.
