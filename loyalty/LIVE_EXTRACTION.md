# Live extraction, not snapshot substitution — 2.9.0

Every normal collection reads current public responses. Human interpretation of one
post or PDF is not an adapter for future content. Source-like test examples are not
production answer data.

## Removed snapshot handling

The audit found a real exception: reviewed_pdf.py had a SHA256-bound manual
transcription of an RGO/Beeline image PDF, including fixed prices. The text, amounts
and content-hash gate are removed. Generic extraction now reads each fresh PDF.
Historical retained records whose method is digest_bound_visual_review are
preserved as evidence only, without automatic derived benefit components.

The fixed utair_documents.json list of keys, titles, expected page counts and a
literal sparse-page whitelist is removed. Every normal run discovers eligible
ut0.ru links from the fresh Utair landing page, resolves bounded public redirects
and reads current PDFs. New keys, changed titles, page counts and sparse numeric
pages do not require a source-specific patch. Temporary signed download URLs and
cookies are not exported. Unknown storage hosts still fail for safety.

Existing financial-PDF parsers also no longer require fixed page counts or a
manually transcribed sparse page. Their source-specific clause and identity checks
remain: unsupported structures fail explicitly instead of reusing old values.
MiXX selection slots are extracted from the current article, not the constant six.

## Telegram caption ownership

One ordinary caption is handled as before. Multiple captions are accepted only
when each belongs to a distinct media element identified by a same-channel
Telegram ?single permalink. Original captions and member IDs remain paired.
Unowned sibling text, replies, link previews, conflicting/duplicate IDs and foreign
channels are not arbitrarily concatenated. An explicit reward link without a
number remains an unquantified announcement, not an inferred discount.

No production condition or substitute text targets promomir/1635. Synthetic tests
change IDs, rates, titles and captions and require correspondingly changed output.
The actual page is used to reproduce structure, never as an alternative answer.

## Linked public PDFs

VTB, NSPK and Uralsib retain their verified, host-scoped CA profile. Direct same-host
PDF links from the fresh content section become the bounded download set for that
run. File names, versions, document hashes, titles and page counts are not pinned.
Non-PDF and external application/account/navigation links are not followed. Each
result preserves the parent URL/hash, link label, current PDF hash and page text.
Duplicate links download once; failures retain parent and previous good files.
A per-link inventory makes the actual traversal scope explicit. NSPK's campaign
landing-page link is not a PDF and is not falsely reported as a full contract.

These are direct user-authorized file downloads, not recursive site crawling.
File robots rules are recorded as robots_allows_crawling, separately from actual
HTTP refusals. Target status, TLS, rate limits, sizes and host checks stay mandatory.
Catalogue/page robots handling is unchanged. Pinning official CA trust anchors is
a security control, not pinning source answers.

## PDF method and uncertainty

Native text is preferred. Only pages lacking usable native text invoke one bounded
Tesseract rus+eng OCR pass via Poppler. Exact machine output, method, confidence
summary and hashes are retained; OCR numbers are not manually corrected. Missing
text is explicit. No deleted manual transcription serves as fallback.

Large text is split into numbered evidence parts with page/character offsets,
not silently truncated to fit Sheets. Parts are supplementary rules, not additive
discounts. This is not a universal PDF-table or entitlement solver. All semantic
components still require context review. The common projection version is 1.0.1.

## Operation

The normal Actions collector and publisher are reused. No new private source,
Google permission, account authentication, proxy, paid service or schedule change.
The previously retained manual RGO row remains historical evidence only; it is not
refreshed from canned text. Current and historical observation times stay distinct.

## Additional anti-staleness regression checks

The separate T2 powerbank session limit was a fixed three-day field. It now comes
from the current duration clause with exact evidence; absence becomes null, not
three. Numeric session limits changed in tests produce changed output.
Financial PDF tier counts are no longer fixed at three: repeated earning clauses
are parsed completely up to a resource bound, with duplicate/unrecognized tiers
rejected. A changed page break does not confine the reward table to page one.

This does not make every site template schema-free. Source-specific section names,
DOM selectors, eligibility interpretation and network allowlists remain explicit
contracts. Unsupported semantic/layout changes still require a code change and
are reported, not filled with yesterday's values. New websites and unknown storage
hosts are not automatically authorized. A finite test suite is not a proof that
all future layouts will be parsed correctly.

Utair and the generic PDF extractor share a 20 MB document-byte bound; page,
text and OCR-work bounds remain independent. Exceeding a resource bound is a
reported ingestion limit, not an access refusal or permission to reuse old data.
