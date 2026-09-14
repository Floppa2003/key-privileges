# Public crawl frontier — 2.9.2

## Scope

This continues the request to investigate the seven failed public routes or expand the current crawl, with no manually supplied source answers. Source acquisition remains anonymous. No proxy, paid runner, account, CAPTCHA solver, Google permission, global CA change, disabled TLS check or production schedule change is introduced.

## Access experiment

Run `34901327462`, diagnostic commit `7b7c086088f2833ff76d70cdcf1afb3470747942`, used the same Requests version and arguments against the seven exact configured targets on standard Ubuntu24.04, macOS15 ARM and macOS15 Intel. All three produced the same result: EKP/Nordwind connect timeouts, old Utair401, Coral club/promotions403, RZD403, and Aeroflot200 containing explicit owner-restriction text instead of source data. A workflow exit success means the test completed, not that the sites were read successfully.

MacOS Intel had already appeared in older network artifacts; ARM was the new environment. The added comparison did not identify a working route. It is not proof of platform-wide impossibility.

Run `34901775529`, diagnostic commit `54d79f54dfffd415c797e4debc21cedd56983ea9`, tested publisher-advertised www aliases: both Coral paths still403; the EKP catalogue and its previously observed public API path still timed out. No guessed private API endpoint or new direct-origin IP was used. Web search/index readability is not considered successful access from Actions.

Downloaded artifact digests, independently checked with ZIP member CRCs:
- 10371051508: `c5cfc4fdef4b204d1e6f4fc7242f936f1f19b58380d860e75f88b861cbf7593d`
- 10371021691: `61dd9bca0e4ff23844f70ea922e149c96b9656152e1ca30fa060f04d295ec617`
- 10370388028: `35ea7700dea0f79ffb0dd8dede8525d486edb5ec739cfff54097b44548ff427c`
- 10371381618: `6c40c6beede8f9bf66fe02077d40ecdaa50a19ca44cd78b68bb2f94764fae5f3`

## Confirmed crawl gap and correction

The current Utair landing page advertises two document-link classes. The previous collector discovered ut0.ru shortlinks but ignored direct PDF links on the already approved eu-s3.beelinecloud.ru origin. The expansion experiment downloaded four distinct direct PDFs; none of their byte hashes occurred among the19 PDFs collected by2.9.1. They concern baggage privileges, onboard privileges, restricted-route mile use, and companion seat selection. These are additional rules, not four independently additive discounts.

The updated collector re-reads the live landing page and discovers both link classes at every run. Direct links must use verified HTTPS and the publisher's `/utair-log/` bucket with a PDF path. There is no checked-in inventory of document names/paths, expected values, page counts or source hashes.

A direct resource ID is derived from origin+path, not a rotating signed query, document title or content. Signed query values stay only in the transient acquisition URL and are never published or used as row identities. The published source URL is the fetched landing page, with a query-free resource locator, parent response hash and actual PDF hash. `link_kind=page_block`, `benefit_url=null`: the stripped URL is not falsely presented as a tested public deep link. Native/OCR provenance and original text are preserved by the existing document pipeline.

Existing shortlink IDs are preferred when both classes alias the same PDF. Byte-identical aliases merge, whereas changed content stays current evidence; failed downloads do not replay prior text. Old stored observations retain their timestamps under the existing publisher.

Ten new mutation tests cover new paths, signature rotation, source text changes, deduplication, old shortlink identity retention, target refusals, bounded hosts/buckets, redacted errors and forged publication metadata. The original gap was reproduced before the implementation. The actual-dispatcher review and subsequent main publication receipts belong in the release PR; this document does not substitute for their checks.

## Other checked expansion

The same bounded diagnostic followed currently advertised Promo Miles campaign/detail links to depth2, excluding winner/result pages. Seven pages were read; the inspected campaigns are completed. This proves those specific public pages are readable, not that a full general campaign/linked-rule adapter has been implemented. The existing root summary collector is unchanged. No archived campaign is promoted to a current discount.

## Limits

The seven failed primary routes remain failed. The new Utair path improves coverage within an already working source, not access to the old401 support page. Future new storage origins, non-PDF link classes or arbitrary nested document links remain outside this deliberately bounded extension. Downloading PDF text does not certify full semantic understanding of tables or entitlement. General loyalty scheduling remains disabled; per-run freshness and recurring execution are distinct.
