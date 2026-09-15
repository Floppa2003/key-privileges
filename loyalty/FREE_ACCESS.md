# Free-only retrieval and publication — 2026-09-15

## Objective and owner setup

No rental, subscription payment, maintained server or always-on laptop. Free API accounts are allowed. The owner added `SCRAPINGANT_API_KEY` as a repository secret. No further owner setup is needed for the currently connected anonymous route. Keep the account on Free; do not add payment details or upgrade. The key must never appear in repository files, workflow inputs, logs, Sheets or public artifacts.

Actual source responses and final destination readback, not provider marketing, define restored coverage. The user's existing CoralBonus registration does not supply an authenticated session to these jobs; no re-registration, coupon issuance or payment is requested.

## Daily runtime

- Original `loyalty.yml`:05:23 UTC, unchanged.
- `loyalty-free-access.yml`:06:03 UTC, trusted-main collection through `free_catalog_bundle.py --collect`, followed by the existing two-tab writer and common private normalization. Both workflows share the publisher concurrency group; the existing WIF/scopes/destination are reused. No Google authorization enters the public collector.
- Nordwind: all source-owned accordions on the observed partner page, complete on-page conditions and separately scoped earning formulas. Outgoing partner sites and user eligibility are not certified.
- Coral promotions: discover the current root index and attempt every linked detail, with rotating priority. Conditions, tables and surrounding context are retained. Some index entries are information/program rules, not separate discounts.
- Coral club: discover current categories, sort them and alternate even/odd category halves by UTC calendar day. Rotate priority within the half. With20 categories this selects10 per day. A complete two-day cycle is a target, not a guarantee when transport, quota, layout or pagination fails. Each report records the selected/read categories and actual detail counts.
- Referral offer cards are distinguished from store merchandise/digital-product cards. The latter are excluded and counted, so this does not claim the whole club or store. Cross-category links must point into a category present in the fresh root inventory. Repeated detail URLs are requested once within the run.
- Public ticket-offer terms are readable without operating the purchase widget. Such records require login/purchase; they are not free coupons. No form, purchase, bonus spending or coupon issuance occurs.
- Partial results survive later page failures. Prior Sheet records are retained with their original observation time, never relabelled as freshly read. An absent result is not proof of no discount.

Only fresh, same-attempt, current-commit root evidence is accepted. The Coral traversal receives that in-memory run and discovers every request from its current pages. Old diagnostic HTML is test/review evidence only, not a runtime fallback. Collection-stage `published_records=0` is not the status of the later publisher. End-to-end release requires actual accepted output and independent Sheet readback after the last write.

## Free-credit bounds

`/v2/usage` must confirm a recognized Free plan with at most10,000 total credits and adequate remaining balance. Unknown/paid plans are rejected. These safeguards cannot make an externally changed provider tariff free.

The root reader retains its115-credit/16-request maximum: five1-credit policy reads, up to five10-credit browser-policy fallbacks and six10-credit rendered roots. Coral detail traversal has a separate175-credit/100-request maximum, checked against current balance again. Categories need10-credit rendered requests; accepted static details use1-credit HTTP requests. The combined bound is290 reserved credits per daily run, or8,990 for31 runs. This excludes manual reruns, diagnostics, other account usage and any provider-side change in charging. Finite credit exhaustion must stop work, not buy a plan.

Provider-wide quota/auth/rate/transport stops prevent starting another collector in the same chain; earlier accepted records can still publish. Missing/excessive cost headers and deadlines stop further requests. Ordinary source failures remain explicit and do not erase other successes. `known_charged_credits` sums validated successful response cost headers; charges for failed envelopes are not reconciled by that sum. Reservation is a separate upper request budget, not an account statement.

One-shot network comparisons are separate unscheduled diagnostic workflows, never a silent expansion of daily cost. The browser-source comparison uses at most36 credits. The alternate residential-pool comparison uses the same Free account, at most150 per source and450 total, with a fresh Free/balance check per source. It does not purchase a proxy subscription, upgrade the account, or enter production automatically. Any useful result still needs source mapping, recurring-budget review and destination verification.

## Source identity, restrictions and privacy

Provider404 means requested-route unreachable, not target404. Only a plain policy request with that error permits one browser read of the exact policy URL. Policy disallow, explicit refusal, challenge, auth and rate-limit responses are not treated as successful content. The main source identity is checked before parsing. Known EKP SPA redirection is the only configured root equivalence.

For static Coral details, one exact source canonical URL is mandatory. This is recorded as `source_canonical_url`, explicitly not an observed browser final location. Rendered category/root reads keep actual browser-location evidence. The origin status comes from the provider's origin-status header, not the provider envelope. API TLS validation remains enabled; the provider's complete internal connection chain and actual exit geography are not independently observed.

Resolve relative links against the page's same-origin HTML base. Reject foreign/unsafe bases. Remove scripts, forms, hidden fields, events and authentication material. No source account cookie is supplied. The public ticket extractor additionally drops order widgets/account placeholders. Source text and outgoing links remain untrusted data, never executable instructions.

Explicit unambiguous `Срок действия предложения до DD.MM.YYYY` supplies an end date. Other booking/travel/certificate-relative periods remain separate source text, not an invented single interval. Existing expired pages remain marked by their published end. Partner display names are not guessed from campaign headlines; titles and full conditions remain searchable, and unresolved identity is explicit. Image-only wording and unread outgoing/PDF rules are not transcribed or certified.

## Verified checkpoints and remaining scope

Nordwind was independently published/read back in35018777242. PR29's first live run35023971363 published43 new Coral records (22 club,21 promo) plus7 Nordwind updates. All50 source records re-parsed exactly from their live artifact bytes and matched native Sheet hashes. Its final normalization manifest was verified/current. PR30 repairs the actual cross-category and ticket-layout failures; its separate new live run must be evaluated on its own results.

EKP, RZD and Aeroflot are not restored merely because a policy response or provider envelope succeeded. The browser-source comparison35024053713 read usable RZD rules but the root still failed with provider423; EKP policy returned provider500, and Aeroflot policy content was unreadable. No records from those diagnostic paths were published.

Full latest run results and continuation are recorded in PR29/PR30 and OPERATIONS.md. A scheduled future run is never claimed as already observed. All source counts are bounded to the actual index/category/detail scope, not an original-source coverage percentage. Public artifacts expire after seven days; private inputs, manual comments and credentials are not exported.

Official references:
- https://scrapingant.com/
- https://docs.scrapingant.com/api-credits-usage
- https://docs.scrapingant.com/credits-cost
- https://docs.scrapingant.com/errors
- https://docs.scrapingant.com/proxy-settings
- https://docs.scrapingant.com/request-response-format
