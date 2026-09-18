# Alfa Only public-access spike and source-level priority audit — 18 September 2026

## Why this source was selected

The owner changed the priority rule: unlock programmes where almost nothing is parsed before chasing a few residual cards in already well-covered catalogues.

A fresh audit of all **105 configured source IDs** against the complete `parser_coverage` history found:

- **`alfa_only_partner_offers` is the only configured source that has never produced a normalized record**: historical maximum `0 discovered / 0 normalized`.
- No other source with a historical run discovering at least **10** items has a best observed normalization ratio below **80%**.
- Current red routes for RZD, Aeroflot, EKP and NORDWIND are not programme-level zeroes: those programmes have successful alternate or previous collectors.
- NORDWIND is the clearest false positive: the current route is failed, but several 15 September runs collected **7/7** accordions from the visible partner list.

Therefore small residuals such as HSE 3 previews, RZD 8 full-detail gaps and individual EKP protected cards are intentionally lower priority than Alfa.

## Existing Alfa authenticated boundary

The requested URL is `https://web.alfabank.ru/partner-offers/`.

PR64 already established verified bank-scoped TLS and an HTTP **302** to the known `private.auth.alfabank.ru` authentication path. The handler follows no redirect, reads no body, retains no cookie/query/session and publishes zero cashback. This remains the correct full-catalogue boundary.

## Public Alfa Only layer

Official public Alfa pages and current indexed copies expose a useful non-personalized subset of Alfa Only privileges (for example TSUM/DLT, restaurants, Ultima/Yandex, RBC and other premium benefits). This is **not** equivalent to the authenticated partner-offers catalogue.

The spike tested whether that public layer can become a recurring anonymous collector without a bank session.

### 1. Direct GitHub runner with verified Russian root

Default TLS failed. The existing pinned official Russian root was reused only in a temporary bank-request trust bundle; no global/browser trust was changed.

The official CA download host was intermittent, so one diagnostic accepted the public mirror `koenrh/russian-trusted-root-ca` only after its DER SHA256 exactly matched the known root fingerprint:

`d26d2d0231b7c39f92cc738512ba54103519e4405d68b5bd703e9788ca8ecf31`.

After TLS verification:
- `/robots.txt` returned 403 on the direct runner; existing RFC-style missing-robots semantics were applied for the diagnostic.
- the public Alfa Only root itself returned **403**.
- no page content was accepted.

### 2. Existing Free ScrapingAnt, RU datacenter

ScrapingAnt could read source robots as a real **200** rule document and allowed the public root.

Important runs:
- **35385289045**: root origin 200; TSUM route provider 500. Root was initially rejected by a local diagnostic bug; only 11 credits were explicitly accounted as charged.
- **35385458430**: reproduced that the root response reached the sanitizer; local duplicate-key diagnostic bug identified.
- **35385553830**: after fixing the diagnostic, root was origin **200**, exact final URL, but sanitized output had **0 visible characters and 0 links**.
- **35385798165** with browser=false: origin 200, 1840-byte server shell, 0 visible text. It contained only ServicePipe anti-bot scripts and disclosed no usable public API endpoint.
- **35385906162**: datacenter browser waited 8 seconds; origin 200 but final location still failed identity validation. Waiting did not yield the public Alfa page.

No source account or Google destination was involved.

### 3. One bounded residential-browser test

Run **35386070270** performed exactly one residential browser read after a fresh robots check.

- source robots: 200 / rules loaded;
- public root origin: 200;
- provider-reported request cost: **125 free credits**;
- free balance immediately before the residential request: **3995**;
- final location still did not match the requested public page;
- no content was published and no retry was made.

This route is too expensive and did not solve the challenge, so it must not be repeated automatically.

### 4. Google IMPORT transport

The existing public-only Google staging workbook was used, not the discount destination.

A temporary sheet `alfa_public_probe_20260918` tried:
- IMPORTXML on the public Alfa Only root;
- IMPORTXML on the TSUM public page;
- IMPORTDATA on the root.

All returned `#N/A — Could not fetch url`.

The temporary sheet was immediately deleted. The staging workbook returned to its original four sheets. No discount-sheet cell was used for this probe.

### 5. No-key Jina Reader

Jina Reader was tested because its documented basic Reader endpoint is available without an API key and normally renders JavaScript.

Run **35386653625** first rechecked Alfa robots through the existing provider (200 / rules loaded), then asked the no-key Jina Reader for the public root. The response yielded no usable page content (`jina_empty_content`).

No Jina account/key was created.

## Cost / mutation boundary

Across the explicitly measured ScrapingAnt Alfa diagnostics, **173 credits are accounted as charged by provider cost fields**. A failed provider response whose cost was not exposed is not included in that number.

These were one-time diagnostics only. No new schedule, paid service, server, provider account, bank session, cookie, coupon activation, Google permission or production collector was added.

The destination spreadsheet `скидки` was not modified by this spike.

## Accepted conclusion

For the **full requested Alfa partner-offers source**, the remaining obstacle is not a parser selector or ordinary anti-bot transport:

1. the exact requested catalogue routes to bank authentication after verified TLS;
2. the separate public Alfa Only marketing pages exist, but all tested anonymous automation paths are blocked or return an anti-bot shell;
3. the expensive residential route also failed and should not be retried;
4. search-indexed public snippets are useful evidence for research, but are not a stable recurring source and must not be substituted for the authenticated catalogue.

The next high-leverage path for Alfa is a **separately authorized authenticated bank session with private storage**, if the owner wants that. The current public/link-accessible Sheet is not an acceptable destination for authenticated banking data.

Until that authorization/privacy boundary is explicitly changed, Alfa stays a truthful `failed / 0 offers` full-catalogue source rather than fabricated coverage.

## Priority consequence

Do not move immediately from Alfa to RZD 8 / HSE 3 merely because those have unresolved cards. Under the owner's programme-level priority rule they are low-priority tails.

Before pursuing another gap, first verify that it represents a programme with little or no successful historical coverage. The current audit found **no second configured programme-level zero**.
