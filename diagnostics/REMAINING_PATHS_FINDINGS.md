# Remaining original sources: retrieval-path results, 2026-09-15

## Outcome

No additional source was restored or published in this continuation. The public production collector, daily schedule and Google publisher were not modified. Work is branch-only, based on main `f7d0b993b26b16969a575990514dcfd83d5c1d6f`.

The user permits any suitable implementation controlled through GitHub, including their own authorized accounts. Their goal is regularly refreshed source data in the existing Google spreadsheet, queried from ChatGPT on a phone; the runtime need not be a GitHub-hosted virtual machine. The user reports having registered at CoralBonus and leaving its tab open. Registration and a remotely accessible authenticated session are separate: Remote Desktop Commander was actually called and returned no available devices. No browser tab, login state, cookie, SMS or account-only offer was obtained.

## Completed experiments

1. Run `34979592042`, execution commit `7e07bc93295a3a6c0ad271da6c45c230bce2dd87`: all six configured roots were opened directly in fresh installed Chrome profiles before attempting crawl-policy loading. Separate DNS/TCP/TLS/HEAD observations distinguish connection failures from browser behavior. Six initial anonymous Microlink requests tested robots documents from outside the GitHub runner network.
2. Run `34980817407`, execution commit `7c242025049bbb0115aa2aa5cfe63864dba9a1d4`: complete the Microlink tests for Coral club, Coral promos and RZD using two origin-policy reads and three exact target reads. The existing `robots_document` semantics distinguish an unavailable 403 robots document from an actual target refusal. This corrected the initial diagnostic's overly conservative stopping point; it did not weaken production rules or turn a target 403 into success.

All seven jobs in the first run and the one job in the follow-up finished successfully as diagnostic programs. That is not source success. Both runs used anonymous, bounded requests without Google credentials, private browser profiles, paid API keys, proxy purchases, CAPTCHA interaction or disabled TLS validation. The eleven total provider calls returned cache status BYPASS and plan free. No quota refusal was retried.

## Results

| Original source | Direct network and fresh browser | External Microlink result | Disposition |
|---|---|---|---|
| EKP | Public IPv4 resolved; TCP connection timed out before TLS. Fresh root navigation produced no main response and DOM reads timed out. | Provider returned success but no origin status and an empty placeholder robots body, not usable rules. The catalogue was not requested through this provider. | Need a working route before testing the catalogue parser. |
| Nordwind | Public IPv4 resolved; TCP connection timed out before TLS. Fresh root navigation produced no main response and DOM reads timed out. | Same empty placeholder behavior at robots; no catalogue request. | Need a working route before parsing. |
| Coral club | TCP/TLS succeeded; anonymous target returned actual HTTP 403 with restriction text. | Follow-up target returned origin HTTP 403 with restriction text. | Anonymous access not recovered; the user's authenticated session remains untested. |
| Coral promos | TCP/TLS succeeded; anonymous target returned actual HTTP 403 with restriction text. | Follow-up target returned origin HTTP 403 with restriction text. | Anonymous access not recovered. |
| RZD | TCP/TLS succeeded; exact configured target returned HTTP 403 with restriction text. | Follow-up target returned origin HTTP 403 with restriction text. | No catalogue content. |
| Aeroflot | TCP/TLS succeeded; target returned HTTP 200 containing the owner's access-restriction page. | Robots returned origin HTTP 200 containing a restriction document, not rules. No provider catalogue request. | No catalogue content. |

The browser reads completed between 14:09:15 and 14:10:07 UTC. The external-target confirmation completed around 14:19 UTC; exact timestamps are in its JSON. Query strings are removed only from public evidence URLs; the RZD request itself used the configured `?accessible=true` URL.

HTTP 200 from a reader service must not be confused with HTTP 200 from the target, and neither proves catalogue content. Empty provider scaffolds are not loaded pages. The initial Microlink round did not test any catalogue: it is explicitly not six failed catalogue reads.

## Prior evidence recovered, not re-run

PR7 (`loyalty/network-feasibility`, September12–13) already compared Ubuntu24.04 and macOS15 Intel. Another identical OS matrix would repeat existing work.

In that earlier experiment, Globalping's Moscow/Timeweb/AS9123 node reached HTTPS200 with authorized TLS for the EKP root, Nordwind partner page, one Coral MEDSI card and the RZD root, while the comparison Amsterdam node stopped before TCP. Neutral controls succeeded in both networks. Those results establish that a controlled Russian exit is worth testing, not that every Russian host works, that every foreign host fails, or that all four responses contained full catalogues. The response bodies were not preserved, and a measurement probe is not our browser worker. Aeroflot was not covered by that Russian test.

Reference: https://github.com/Floppa2003/key-privileges/pull/7

## Continuation decision

The next useful experiment is a bounded browser read from an accessible, user-controlled network, not another speculative parser rewrite. The existing user computer can supply a one-time comparison and the authorized Coral session after it is connected and the relevant tab is approved. Do not ask the user to register again or paste cookies into chat. No controlled always-on Russian worker is available in this continuation, and no server has been purchased or provisioned.

A production external worker is compatible with GitHub orchestration. Keep the currently working sources on their existing path; only route sources that need another environment. Before deploying that path, verify current cards and real detail content/pagination on it, then the actual destination write/readback. Do not attach the user's general-purpose computer as an unrestricted self-hosted runner to this public repository. Account jobs and their outputs need private isolation; no credentials or account-only responses may enter the public artifact flow. A connected laptop for this investigation is not a requirement that it remain online forever.

Coral authentication may help account-gated content but has not been tested against the anonymous 403 responses. Do not assert either that it will fix them or that it cannot. Reading offers is distinct from issuing coupons, spending bonuses or making purchases. Existing account sessions may expire and need reconnection; that must not stop unrelated sources or refresh stale rows.

EKP draft PR23 remains unmerged. None of these experiments reached its live pagination acceptance gate. No historical DOM was used as a live substitute, and no new offer rows were written to Sheets.

## Evidence verification

All eight downloaded ZIPs were checked against GitHub-provided SHA256 values and ZIP CRCs. The seven initial artifacts contain the same executed diagnostic script, SHA256 `d7fdbbcf10e139462a5ae445e0c16162d057d213bba4a886a1ee672260daa4bd`. The follow-up archives its executed workflow (Git blob `a0d34920b42732a473af8e5b391b5a4765808fd4`). This is diagnostic verification, not a new full production regression run. No original private sheets, corporate codes or sessions are included.

| Artifact | ID | ZIP SHA256 |
|---|---:|---|
| external-path |10401370310|0bdfda0c68e5123c3951a9e687a47f6a5e9ee59d358db56f64ee7c966efc973b|
| bootstrap-ekp |10400443870|81c1fe55073801081bd30725002a0cd0943223ee208d5884b703b5d28cdfae0c|
| bootstrap-nordwind |10400722278|647d2f4ecbf4651f028c895ce6ae08de5c95704e1d9a97114a8cd0a0ddcb19bb|
| bootstrap-coral |10401325397|1ecfac8bee165397aaa92a775ebd160ce7085f3bb19ce69338f727b64918648b|
| bootstrap-coral_promo |10401430262|69c485d3471adbdcd0c06a07417d16d289033844cf0c22310f61b48726ed0be8|
| bootstrap-rzd |10401225569|8873be25ea30dd33b348c5ad9825351964177781dd9581b7401a99dc051a9199|
| bootstrap-aeroflot |10401215992|6a90b6c6b08ebe0b077841c2c7a973c3f3c72c973e2097c856d8d9b71d7435b2|
| external-target-confirmation |10401162284|817944832081765a3ad72a33f212464aab6d3f09edd0fe0c6290aca7d833d121|

Runs:
- https://github.com/Floppa2003/key-privileges/actions/runs/34979592042
- https://github.com/Floppa2003/key-privileges/actions/runs/34980817407

Artifacts expire on September22,2026. Code and this report remain on the diagnostic branch. Limits: one fresh direct browser per source; Microlink is not a user-controlled network; authenticated access, full catalogues and a second unattended authenticated run remain unverified.
