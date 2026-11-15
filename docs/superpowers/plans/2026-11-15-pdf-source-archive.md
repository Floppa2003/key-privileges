# PDF originals and lookup through the existing Google Sheet

## Approved design

Keep public original PDFs in `source-documents/<sha256>.pdf` on `main`.
The existing Google Sheet is the sole document catalogue: programme, partner,
source URL, observation date and a `Копия документа` link. Do not create a
separate archive branch or JSON index. A changed file gets a new hash; equal
bytes share one immutable copy. Unparsed documents remain discoverable and
are clearly marked as requiring visual review, without invented benefits.

The lookup skill in `Floppa2003/skills` resolves the Sheet first and opens the
exact archived PDF when a future question needs source verification. Existing
LLM jobs and eligibility rules are outside this change.

## Implementation and verification

1. **Capture:** add `loyalty/pdf_archive.py`; capture bytes before extraction in
   every existing public PDF path. Guard hashes, filenames, size, corruption and
   immutable deduplication. Preserve document observations on parse failures.
2. **Identity:** retain the partner and programme supplied by the live discovery
   card, including the real RGO Beeline document.
3. **Projection:** add the copy link to the generated Sheet view, with guarded,
   idempotent native UI migration. Keep unparsed and bulk documents searchable
   without treating them as parsed discounts. Links require verified local bytes.
4. **Persistence:** archive collection output to `main` before Sheet publication.
   Every live publisher then reads a fresh, verified snapshot of only the PDF
   data from `main`, while its executable checkout remains at the tested run
   revision. This also protects queued publishers from erasing newer copy links.
   Keep the write job separate from Google credentials. Verify remote committed
   bytes and retry only explicit concurrent-head conflicts. Preserve all versions.
5. **Backfill and skill:** retrieve known public document sources from current
   Sheet metadata and existing collectors; match historical hashes exactly,
   report unavailable versions, and publish the validated reusable lookup skill.
6. **Gates:** meaningful tests using real source evidence, focused regression
   tests, the complete Python and Node suites, independent review, CI, then merge.
   Read back the live Sheet and archived PDF bytes after the final material write.

## End-to-end acceptance

Search Билайн in the Sheet, distinguish its programmes, follow the RGO archived
copy, verify SHA-256 against the saved original, and inspect its page visually.
Check that an OCR-unverified document is still discoverable, a missing archive
does not produce a fake copy URL, and repeat publication is idempotent.

## Boundary

Public PDFs only. Private Sheet exports and personal codes stay out of GitHub.
The source date is an observation date, not an inferred offer expiry. Original
PDF availability does not prove that a privilege is current or that the user is
eligible. No massive LLM backfill is introduced.
