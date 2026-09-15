# Public-source continuation: renderer and HTTP controls, 2026-09-15

## Scope

This record extends `SEVEN_ACCESS_FINDINGS.md`. These diagnostic changes are not production adapters. Utair was separately integrated through PR22; none of this diagnostic branch was merged into main. No Google credentials, private data, user browser profile, proxy, property spoofing, CAPTCHA solving or disabled TLS verification was used.

## Results

| Experiment | Result | Supported conclusion |
|---|---|---|
| EKP renderer replica1 | Initial and new blank tabs evaluated correctly. Source returned200, including observed same-host regions/categories/partners responses. Listing readiness nevertheless remainedfalse; no DOM capture was retained in this run. Both post-navigation renderer controls succeeded. | A blanket network-inaccessibility claim is false. Successful API status does not establish a parsed catalog or explain the missing cards. |
| EKP renderer replica2 | Both pre-navigation controls succeeded. Source request was observed without a main HTTP response. Source-tab evaluation later timed out; a fresh blank tab still worked. | Failure follows source navigation, not initial global Chrome startup. The exact network-versus-source-renderer cause is unresolved. |
| Nordwind renderer replicas1 and2 | Pre-navigation controls succeeded on both. The source request produced no recorded main response. Source-tab control timed out afterward while fresh blank tabs worked. | The original timeout is reproduced without a globally dead browser. No readable partner page was recovered. |
| EKP DOM instrumentation replicas1 and2 | Both failed before obtaining a source DOM. No card-probes/HTML were saved, and neither pagination nor detail clicks were reached. | These runs cannot distinguish an empty catalog from a selector/ownership rejection; no parser fix is claimed. |
| EKP direct anonymous HTTPS replicas1 and2 | All three configured URLs returned Requests `ConnectTimeout` before any HTTP status: robots.txt, the public catalog page, and the exact partners endpoint already observed in browser traffic. | In these six requests failure precedes HTML/JSON parsing and is not specific to Playwright. This does not prove a permanent restriction, geographic cause, firewall rule, or an exact lower-level network fault. |

The directly tested API URL was `https://ekp.spb.ru/api/portal/loyalty/partners`, without guessed parameters or replayed authorization. Only that previously observed public endpoint was tested, not private account APIs or arbitrary ID enumeration. Direct diagnostics would have retained limited public structure/examples; all requests failed before response bodies in this round.

The renderer diagnostics use unchanged strict card ownership checks. Sanitization can remove query strings, so a raw-versus-sanitized parser discrepancy was considered; the instrumentation never reached a DOM and **did not establish this hypothesis**. No whitelist, selector broadening or hardcoded partner answer was introduced.

## Runs and independently checked artifacts

### Renderer controls

Run34960355659, commit `cbb210ee4f96242ab07840167f9a122cfcaad818`:

| Artifact ID | Source/replica | SHA256 |
|---:|---|---|
|10392798428|EKP1|5867764357f2ecffcf4a26e94b53d5766738e93d6ad64c3b3116bb9776075f9b|
|10392544400|EKP2|061ee00506bd4f14aa1af3e0d0dae727b6bf99fa21fc947d286c9ce074e224ee|
|10393530011|Nordwind1|0666eba2932e121793a105acdbc05dfba775697895ae30bc643331eb0f2e0f17|
|10392638858|Nordwind2|462b0dfaee6fc5dd4ed47b81d0b477c1eac71dd7a30d1d42a4e313362c6ff98a|

### DOM instrumentation

Run34961164449, commit `2d1979e57267ac9256ebf27b01bb94b3f337e6cf`:

| Artifact ID | Replica | SHA256 |
|---:|---|---|
|10392994288|1|b98d661a61ef9ca9f55fc7ab71757897c6afdc5e3eb9f31cec3ce12f87240bb0|
|10393019047|2|67aa57501891a60af53510a7d031b81f58a4a5cb37d2f92df1c8835cf8157616|

### Direct public HTTP controls

Run34963068943, commit `5984e4cf329446306ea5b78eef4ce75ac492b1bd`:

| Artifact ID | Replica | SHA256 |
|---:|---|---|
|10394018419|1|e8e1b0f33ee40c0a6485153961ed268f727bbc77a914f8cfda33d60df9c8cca0|
|10393104914|2|3899974a4c42ce40480f29116ac44888d50bc3157864e6d5bb8aed66329b1ab3|

All eight listed ZIPs were downloaded, SHA256/CRC checked, and their included execution scripts checked against manifest digests. A successful diagnostic workflow means evidence was preserved, not that its source was accessible. These runs add no verified EKP pagination, partner-detail extraction or full-catalog coverage. Coral club, Coral promo, RZD and Aeroflot were not re-probed by these experiments; their prior failures remain unresolved rather than being counted as fresh observations.

Artifacts have seven-day retention, expiring2026-09-22. This document preserves the conclusions and identifiers beyond that expiry.
