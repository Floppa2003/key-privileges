# Seven public routes: verified continuation, 2026-09-15

## Status and scope

This is an access investigation, not a production release or a complete catalog export. The resumed request was to keep trying the seven remaining public addresses through GitHub. Work continues on `diagnostics/seven-routes-transport-20260915` from `2fd148c8e53e5a5155ebdaea0972bc8e0bfc9c2c`.

**Disposition: one reproducibly readable source (Utair), one intermittently readable initial catalog (EKP), five routes without a successful read in the new test.** No new production adapter, normalized offer publication, Google credential, schedule change, proxy, account login or private browser profile was introduced.

The two new Actions runs have completed: `34958485244` (nine isolated source jobs) and `34959172180` (two additional EKP jobs). Workflow success means the diagnostic finished and retained evidence; it does not mean a website was accessible. The latter run completed normally while both source reads failed before loading cards.

## Exact source results

| Source | Requested URL | New observations | Disposition |
|---|---|---|---|
| Utair | https://www.utair.ru/support/2/kakiye_partnery_est_u_utair_status | Two independent fresh runners: main document 401, then 200; genuine article with seven in-article links and 2,130 full-DOM text characters | Reproducible article access; not the entire loyalty program |
| EKP | https://ekp.spb.ru/capabilities/loyalty/ | One runner: 200 shell, then 30 distinct numeric partner-card links. Other initial runner: no recorded main response and DOM-read timeouts. Two follow-up runners also timed out before catalog loading | Real but intermittent initial catalog access; pagination and details unverified |
| Nordwind | https://nordwindairlines.ru/ru/club/partnerlist | No recorded main document response; all four DOM checkpoints timed out | No usable page; network versus browser/control cause unresolved |
| Coral club | https://coralbonus.ru/klub-privilegii/ | Actual HTTP 403 | Unresolved refusal |
| Coral promo | https://coralbonus.ru/promo/ | Actual HTTP 403 | Unresolved refusal |
| RZD | https://www.rzd-bonus.ru/?accessible=true | Actual HTTP 403 | Unresolved refusal |
| Aeroflot | https://www.aeroflot.ru/ru-ru/afl_bonus/partners | HTTP 200 whose title explicitly says the owner temporarily restricted access | Restriction document, not partner content |

### Utair: recovered evidence and fresh confirmation

The interrupted predecessor run `34955859571` had two downloadable artifacts. Both independently contained the real Utair article, although the overall run was cancelled and the second artifact did not contain all seven source attempts. These are recovered observations, not new requests.

New run `34958485244` reproduced the article on two more independent runners. In both, the early DOM snapshot was unavailable during page transition; the later checkpoint, scheduled at eight seconds after initial navigation, contained the article. Thus four successful Utair observations are verified across the recovered and new rounds. The article lists five mileage partners and two additional program links; seven links are not seven newly verified discounts.

The successful diagnostic starts the installed Chrome in a disposable headful profile under Xvfb and attaches Playwright through loopback CDP. It performs ordinary navigation and bounded waiting without modifying browser-exposed automation properties, solving a CAPTCHA, replaying protected API calls or importing saved cookies. The browser executes the site's normal scripts. TLS verification remains enabled. This identifies a working configuration in these observations, not the unique cause of earlier client failures or a guarantee of future access.

### EKP: distinguish shell, listing and detail

The recovered predecessor snapshot had navigation, filters and footer text but zero partner-card URLs. Its broad `content_candidate` heuristic was insufficient. The new readiness check requires same-host links matching `/capabilities/loyalty/tiles/[0-9]+`.

On replica 2 of run `34958485244`, the two-second checkpoint was only a shell; the eight-second checkpoint contained 30 distinct partner cards. The saved UI displayed `Все регионы`. Independently parsing the saved main content found 30 card containers, including 21 without a login notice and nine with `Требуется авторизация`. Public listing text is visible; this does not grant access to login-gated redemption.

The ordinary browser also observed successful same-host public requests for loyalty regions, categories and partners. Only bounded URL/status metadata was retained, with query strings removed; their responses were not replayed as a guessed API.

Follow-up run `34959172180` was designed to activate one visible `Показать еще` control and one dynamically discovered card without a login notice. Both runners timed out at the initial catalog stage, so **neither pagination nor partner details were reached or verified**. Across the four new EKP runner observations, one loaded cards and three did not. These are bounded observations under related but not identical diagnostic scripts, not an estimate of long-run reliability. No claim that all EKP data was parsed is supported.

## Changes and checks

Only these new diagnostic files were added during the continuation:

- `diagnostics/source_readiness.py` and `.github/workflows/source-readiness.yml`: per-source process isolation, bounded startup/navigation/DOM/cleanup, incremental evidence, explicit shell/refusal classifications.
- `diagnostics/ekp_followup.py` and `.github/workflows/ekp-followup.yml`: bounded public UI continuation using discovered identities; no literal partner ID or stored benefit answer.
- This findings document.

Readiness uses 14 local self-check assertions; follow-up uses eight more. They cover changed numeric card IDs, same-host ownership, shell rejection, actual HTTP refusals, an HTTP-200 restriction, source-structure requirements, login notices and sanitization. Both groups passed locally and are required before their relevant Actions reads. They are diagnostic regression checks, not the full production parser test suite.

The nine new readiness ZIPs and two follow-up ZIPs were downloaded and checked against GitHub's SHA256 metadata and ZIP CRCs. Their executed script copies match the reviewed local files. All stored public DOM copies were hash-checked; successful readiness classifications and the 30 EKP URLs were independently reproduced from those copies. The two recovered predecessor ZIPs were also checked. Original raw DOM is not retained in the new artifacts: its reported hash is an observation, not independently recomputed evidence. The sanitized DOM is explicitly labeled as such.

Main was read before and after these experiments at `d45e7ae35e8a1f3a497a6e1f83ff757e4389ec4c`. The four implementation commits differ from the resumed diagnostic head only in the four files listed above. No Google Sheets read or write was performed in this continuation; no independent claim about unrelated concurrent Sheet edits is made. Existing production source configuration, permissions and scheduled workflows are untouched.

## Run and artifact inventory

Readiness run: https://github.com/Floppa2003/key-privileges/actions/runs/34958485244

Execution commit: `b2a32636dec7fb2e845d6f4ee07de98b26f89bcb`.

| Artifact | ID | SHA256 |
|---|---:|---|
| readiness-utair-1 | 10392635403 | f211988039c5c2686096ea29e860637a71622f1914225ddad4574629677197a9 |
| readiness-utair-2 | 10392595672 | ebac51427bf5fbd80aeaba343ae2406f1113610be928ea2d25b8c4ec8679cbe3 |
| readiness-ekp-1 | 10392267412 | f63d66c90941efd4cd87155dcd86166aefb89c4153d81773b2e47968d70804a4 |
| readiness-ekp-2 | 10392371981 | 392bae2154f3eb92cca63d6899fa01cafb5702928a6465f9588ed1b2a15e75ad |
| readiness-nordwind-1 | 10392297967 | 4cf5347461e2914c5c8c11fc6cd37fa12899cc037bd57ef52b66c2ae9f3588b1 |
| readiness-coral-1 | 10391869828 | d190d6c8c942de521323cdc0eed1eb42122bca8434640a77fedb71687513b8c2 |
| readiness-coral_promo-1 | 10391912765 | fe822e790ecd7eab5099ae07d61e60c78166abcb2e6015f7b80ebbb26138ac8a |
| readiness-rzd-1 | 10392710103 | 07195964d6f695e0d31377adc30b01b798113b6acd35a8063a146d36e951363b |
| readiness-aeroflot-1 | 10391917830 | 1f6754d93d984e21e8d38def67e0c5a50b25333c5fdd6c844fae697c74e5bb23 |

EKP follow-up run: https://github.com/Floppa2003/key-privileges/actions/runs/34959172180

Execution commit: `0e6ad0f21ff9885ed4e8be7e09d1ba83290cc79a`.

| Artifact | ID | SHA256 |
|---|---:|---|
| ekp-followup-1 | 10392701629 | eefcbcba557ac2d6419b1303bcfdd51df35c0cc611a13ecdb224212ebdfd0c64 |
| ekp-followup-2 | 10392821299 | 65107ab80a48db42ac64d9a42d8dfbd17fa80e3307c70e724fde188718bc8be9 |

Recovered run: https://github.com/Floppa2003/key-privileges/actions/runs/34955859571

| Artifact | ID | SHA256 |
|---|---:|---|
| seven-browser-1 | 10391108550 | b65bcac0250faa34408291cd3e53b8ae0143aca420026700da127b491d5c2416 |
| seven-browser-2 | 10392170695 | 6476bf656cb8bc56cf1c96d14b6c0f7ea2d4b11c649dc489a38d97d08174f589 |

New artifacts expire on 2026-09-22 under their seven-day retention setting. The code and this record remain in the diagnostic branch. No account/session values or Google data are included in the new artifacts.

## Next engineering acceptance criteria, not completed work

1. Utair: integrate the reproducible public article read into the existing source dispatcher only after source identity/evidence validation, changed-input tests and normal publication readback. Do not substitute today's seven links as fixed answers.
2. EKP: instrument a failing browser read to separate missing network response, page execution and CDP/control failures. Then independently reproduce listing readiness, actual new identities after a visible pagination action and one public detail. Full catalog scope and coverage need a separate test; login notices remain boundaries.
3. Other five: retain the exact failure evidence. New tests should distinguish a concrete hypothesis rather than repeat the same browser/OS matrix or call restrictions successful. No impossibility claim follows from these failed requests.
