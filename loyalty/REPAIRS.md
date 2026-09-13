# Read recovery and exact Mir identity — 2.3.1

This release repairs the existing public collector without adding infrastructure, changing Google authorization, enabling periodic scheduling, or reclassifying inaccessible catalogues as complete.

## Fixed behavior

1. Public GET/browser reads retry transient timeouts and the explicitly enumerated connection-reset/network-change/empty-response errors, at most three attempts per transport operation. The same anonymous context, URL and request parameters are retained. Delays respect the source crawl interval. Authentication, certificate errors, access challenges, HTTP 401/403/429 and responses carrying Retry-After are not turned into immediate retry loops. Existing bounded 502/503/504 recovery remains.
2. Mir detail collection retries one missing browser-owned public response once, with a new observation offset. It never satisfies a fresh request from an older stored detail. Non-200 public API responses are now explicit errors instead of silently becoming missing-response timeouts. Malformed payloads and native-ID mismatches do not retry.
3. Observed Mir native IDs survive DOM catalogue validation where a matching public API item exists. The detail's native ID is checked in addition to its exact path. IDs unavailable on subsequent DOM-only pages remain unknown, not guessed.
4. A stalled Mir detail navigation or response wait is cancelled within the remaining source budget. The source deadline now starts before robots processing, rather than granting another full budget after initialization. This gives the collector time to return previously completed detail records. This is a Mir detail fix, not a claim that every other adapter now has a general checkpoint mechanism.
5. The HTTP-200 Russian owner-restriction wording observed during the previous diagnostic is rejected as an access challenge, not accepted as page data.

The normalized schema remains version 2; adapter_version is 2.3.1. The publisher's managed A:Y/A:N columns and manual Z/O boundaries are unchanged. No missing observation deletes or expires a stored offer. No production User-Agent override was added: the earlier S7 diagnostic showed why the working default must not be changed indiscriminately.

## Regression evidence

- Baseline: 154 Python tests. Thirteen new tests exercise transient recovery, finite attempts, terminal certificate/API errors, listener cleanup, retained native IDs, response freshness and in-flight cancellation. Final local suite: 167 Python tests and 7 unchanged KEY tests. Each new behavior had a failing test before implementation; existing refusal tests continue passing.
- First full patched branch run: 34726784275, artifact 10307584693, ZIP SHA256 `2e7423aec5ca5f18522e04a711b2e9688c8ece125c9f2f9a6133d29c06d671e0`. 728 records, 45 reports. Mir collected all 176 discovered unique cards from the two configured Moscow-region public catalogues, MEDSI collected successfully. No missing-response retry was needed in that run; this does not prove the root cause of the earlier intermittent event loss.
- Final 2.3.1 canary run: 34727403405, artifact 10307944412, ZIP SHA256 `ee2a7325bb12c81f228abcd72c1fe86e8b8ff299b0d5c7515d4d1ab0da31567a`. Both exact Deva-Dent card (`db7f56ef-dd05-4b44-a103-21d5b1316d58`) and MEDSI were normalized. Six implementation/test files were downloaded and compared byte-for-byte with the tested local files.
- Two intermediate transfer runs failed before publication: malformed patch framing, then cleanup of the modified temporary patch. Neither changed main or Google Sheets. Checks were retained; framing and cleanup were corrected. Temporary transfer files and the branch-only workflow were removed before merge.

A successful branch collection is not proof of main publication. The release PR must record the actual main run, payload validation and independent Sheets readback before claiming synchronization.

## Remaining gaps

EKP contract inspection still timed out at connection/navigation in this repair pass, including with bounded transient recovery. Its initial matrix diagnostic did observe real catalogue responses, but no complete object contract or pagination was available for building an evidence-backed adapter here. No speculative EKP parser is enabled.

Nordwind, Coral, primary RZD, the main Aeroflot catalogue and Loyals retain the explicit access/TLS failures recorded in the network diagnosis. The old Utair support URL remains a failed probe; the separate official media adapter is not renamed into a complete replacement. These sources need the previously identified access/contract work, not unlimited retries or false success statuses.

This release does not fix the remote Loyals certificate, provision a Russian network exit, bypass login/access challenges, alter personal data, or overwrite the curated manual benefits database. Only normalized parser tabs are eligible for the existing authorized main publication.
