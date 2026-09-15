# Free-only retrieval path — 2026-09-15

## Scope and owner setup

The user requires zero rental/subscription spending and no maintained server or always-on laptop. Free API accounts are permitted. The existing daily collector/publisher stays unchanged. This additional workflow checks all six unresolved original routes, not only CoralBonus.

Chosen candidate: ScrapingAnt's **recurring Free plan**, advertised as 10,000 credits each month without a payment card. Its API documents Russian country selection (`RU`) with standard datacenter proxies. These are vendor capability claims, **not a successful live test of our sources**.

One-time setup:

1. Register at https://app.scrapingant.com/ and stay on the Free plan. Do not enter payment details, purchase standalone proxies or activate paid upgrades. The API key is on the account dashboard.
2. In this repository, open Settings → Secrets and variables → Actions → New repository secret. Save the key as **`SCRAPINGANT_API_KEY`**. Do not paste it in chat, a commit, an issue, a workflow input or the spreadsheet.
3. The `Free original-source access check` workflow picks it up on its next daily 06:03 UTC run. It can also be run with `Run workflow`. The original 05:23 UTC data collection remains separate and unchanged.

Repository connection used in ChatGPT cannot create repository secrets; its documented API excludes secret administration. The owner setup above is not a server-management requirement. No additional service account, Google permission or laptop connection is required for this public probe.

## What the implementation does

- Resolve the six IDs `ekp`, `nordwind`, `coral`, `coral_promo`, `rzd`, `aeroflot` from the existing reviewed registry. No new target sources or literal offer answers.
- Without the new secret: write `not_configured` and make zero provider/site requests.
- First read `/v2/usage`. Require a recognized Free plan, at most 10,000 total credits and at least 65 remaining. A paid/unknown plan or insufficient balance stops before all target reads. The exact free plan name still requires live confirmation; unknown names do not silently enable collection.
- Make sequential HTTPS `/v2/extended` requests with `proxy_country=RU`, `proxy_type=datacenter`; no residential mode, paid purchase call or automatic upgrade exists.
- Maximum eleven target reads and 65 **estimated/reserved** credits: five plain robots documents at one credit and six JS-rendered roots at ten credits. Validate `Ant-credits-cost` after every response. Stop on a missing/higher cost, quota/auth/rate failure, or timeout. There are no automatic retries or country/IP-rotation loops.
- Reuse the production `robots_document`, robots parser and source-refusal checks. Read a root only after policy permits it. Origin status comes from `status_code`, not the provider's HTTP envelope. Provider failures are not missing robots documents.
- A fixed read-only JavaScript snippet records the browser's final location. Reject missing/unexpected destinations; retain only the already observed EKP SPA transition as an equivalent path. This does not independently audit the provider's complete redirect/TLS chain.
- Discard cookies, XHRs, headers, iframe bodies, forms, scripts, hidden fields, event attributes and URL query/fragment data from artifacts. No account session is sent. Source output is untrusted data; it never changes code, configuration or output targets.
- Return sanitized root documents as **unverified candidates**, with counts, checksums and fresh observation times. No partner details or pagination are claimed. `published_records=0` is deliberate. A candidate page is not automatically a valid discount or eligible benefit.

The key is passed only over verified HTTPS to the provider using its documented query parameter. Requests, raw exceptions and raw provider errors are never logged. Keys must not be prefixed with `ant-` (which would forward a header to the target). The wrapper rejects a credential echo rather than saving it. Secret masking is not the privacy control. No Google token, spreadsheet ID, source account cookie or private spreadsheet row enters this workflow.

At one run per day the documented upper estimate is 65 × 31 = **2,015 credits/month**, before any other use of the same account. This is an estimate for **root access checks**, not for full catalogue extraction. A changed provider billing policy or later paid account upgrade is not made free by a code cap; do not add payment details and retain Free status. The API's usage/charge checks additionally stop unexpected configurations. No signup occurred and no real API key was obtained in preparing the code.

## Why this candidate and not another generic cloud

Prior GitHub, Jina and Microlink experiments failed before useful catalogue content. Prior independent measurements made a controlled Russian exit a relevant hypothesis. ScrapingAnt offers this selection inside a recurring free allowance, unlike an unverified arbitrary free browser in another foreign region. This is still a hypothesis until a real key is connected.

Browserless (1,000 units/month) and Cloudflare Browser Run (10 minutes/day on Workers Free) have recurring free offers, but their basic free plans do not by themselves prove suitable network access to these six sites. Do not request several unnecessary accounts before testing this one.

## Continuation / acceptance

This is the ready-to-connect **access probe**, not restoration of six production sources. Before routing provider responses into the normal publisher: inspect actual current cards, source ownership and conditions, traverse relevant catalogue pages, preserve incomplete/authenticated boundaries, verify repeat reads, then separately verify Sheets publication/readback. Reuse existing source adapters where their contracts fit. EKP draft PR23 is not implicitly merged or certified by this workflow.

CoralBonus registration was already completed by the user. Do not ask them to register again. Their authorized session is not part of this public provider probe; an authenticated path needs private handling, and code issuance remains a separate operation from reading offers.

## Official documentation checked

- Recurring Free allowance and no-card requirement: https://scrapingant.com/
- Country and proxy type: https://docs.scrapingant.com/proxy-settings
- Charge table and credit response header: https://docs.scrapingant.com/credits-cost
- Usage response: https://docs.scrapingant.com/api-credits-usage
- Extended response and origin status: https://docs.scrapingant.com/json-response
- Parameters: https://docs.scrapingant.com/request-response-format
- GitHub key setup: https://docs.scrapingant.com/github-action
- Browserless comparison: https://cloud.browserless.io/pricing
- Cloudflare comparison: https://developers.cloudflare.com/browser-run/limits/
