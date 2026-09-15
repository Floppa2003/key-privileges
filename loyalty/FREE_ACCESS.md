# Free-only retrieval and publication — 2026-09-15

## User requirement and owner setup

No rental, subscription payment, maintained server or always-on laptop. Free API accounts are allowed. ScrapingAnt advertises a recurring Free plan with10,000 monthly credits and no payment card; its documented country selection includes RU. Actual site responses, not provider marketing, determine source availability.

The owner has now added `SCRAPINGANT_API_KEY` as a repository secret. No key appears in code, workflow inputs, logs, the spreadsheet or public artifacts. Future reconnection uses Settings → Secrets and variables → Actions; remain on Free, without payment details or paid upgrades. The connected GitHub app cannot administer repository secrets.

## Runtime

- The original `loyalty.yml` still runs at05:23 UTC.
- `loyalty-free-access.yml` runs at06:03 UTC and supports manual dispatch. The trusted main job calls `free_catalog_bundle.py --collect`: fresh public API observations are mapped only by reviewed source adapters.
- Current supported mapping: Nordwind's source-owned partner accordions, including complete on-page conditions and separately scoped earning clauses. No fixed partner inventory or rates. Outgoing hotel websites and user eligibility are not verified.
- Other roots are not automatically promoted to offers. Coral's category landing page is not a collected partner catalogue; promo titles alone are not complete campaign conditions.
- Only freshly accepted same-run/same-attempt/current-commit records produce a publication payload. Old diagnostics, changed HTML digests, missing identity and stale observations are rejected.
- The separate publisher reuses the existing two managed public tabs and common private normalization. It requires trusted main, accepted records and `LOYALTY_SHEETS_SYNC=true`; existing WIF/scopes are reused. Both workflows share a concurrency group so writers do not overlap. No Google credential enters the public collector.
- `free_access_probe.py` itself does not publish; its `published_records=0` field describes that stage, not the later publisher. Final source success requires actual fresh records and independent destination readback after the final write.

## Free budget and source safety

Preflight `/v2/usage` must report a recognized Free plan, at most10,000 total credits and at least115 remaining. Unknown/paid plans stop before source requests. Maximum16 requests and115 estimated/reserved credits per full attempt: five1-credit plain robots reads, up to five10-credit browser robots fallbacks, and six10-credit rendered roots. With no fallbacks, the original65-credit maximum still applies.

One daily attempt has an upper documented estimate of115×31=3,565 credits/month before other account usage. This is not a budget for full multi-page catalogue extraction. Missing or excessive reported charges, quota/auth/rate errors, transport exceptions and the overall deadline stop further work. There is no paid upgrade, residential mode, automatic purchase or unlimited retry loop. Keep the account on Free; code cannot make an externally changed billing policy free.

`known_charged_credits` sums validated cost headers from successful provider envelopes. Charges, if any, for failed provider calls are not included; `reserved_credits` remains a separate conservative request-budget figure. Neither is a independently reconciled account statement.

Provider404 is documented as an unreachable requested URL, **not** an origin404. For a plain robots read only, one browser-mode read of the exact same policy URL is now allowed. It must return a current final-location marker and usable rules before the target may be fetched. Explicit robots disallow, source HTTP refusal, provider423 challenge detection, authentication and rate limits are not bypassed or retried by this fallback.

Origin status is taken from `Ant-page-status-code`, not the provider envelope. The exact target final location is checked; known EKP SPA transition remains the only root equivalence. Browser policy responses must match their exact policy URL. TLS remains enabled for API access; the provider's entire internal TLS/redirect chain is not independently observed.

Relative links are resolved against the actual HTML `<base href>` when it exists, as in CoralBonus. A foreign or unsafe base is rejected. Forms, scripts, hidden fields, event attributes, query/fragment values and extended cookie/XHR payloads are excluded from public output. No source account session is transmitted. Public page text is data, never instructions or executable repository configuration.

## Evidence and current limits

First real key-backed run35008135019 attempt2 read Nordwind's seven actual cards and Coral's20 category boxes. A later new run35016757882 stopped Nordwind at a plain policy request, so it correctly produced no offer payload and skipped publication; it did read Coral's promotion index. This proved intermittent policy transport and exposed incorrect relative link resolution in the old sanitizer. Historical sanitizations must not be used as authoritative new link inventories.

The bounded browser-policy fallback and base-URL repair are tested separately. A successful future live request is not preclaimed here. A new source is considered released only after its fresh output, repeated read behavior and actual publication/readback are recorded in the corresponding PR. The user's existing CoralBonus account remains unused by this anonymous API route; no re-registration or coupon issuance is requested.

Official references:
- https://scrapingant.com/
- https://docs.scrapingant.com/api-credits-usage
- https://docs.scrapingant.com/credits-cost
- https://docs.scrapingant.com/errors
- https://docs.scrapingant.com/custom-headers
- https://docs.scrapingant.com/proxy-settings
- https://docs.scrapingant.com/request-response-format

Previously verified public OpenAPI fetches: run35007046678 and35007883389. Offline/regression tests validate contracts but do not certify live source reachability. Public artifacts expire after seven days; private source exports and credentials are excluded.
