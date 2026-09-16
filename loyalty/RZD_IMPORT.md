# RZD public catalogue through a Google import workspace

## Scope and acceptance

This candidate implements the existing `rzd` source, not replacement offers from
unrelated websites. The old configured root is retained in coverage. The current
source's Host directive and homepage link establish the bare HTTPS catalogue at
`https://rzd-bonus.ru/partners/`; no unobserved HTTP redirect is claimed.

The September16 exploratory read obtained the current robots rules, source
sitemap, real catalogue/pagination links, and two source-owned detail pages using
Google IMPORT functions. Those exploratory results are NOT runtime answer data.
A release is accepted only after a new GitHub source run, completed existing
publisher/unified normalization, and independent destination readback.

## Data flow

GitHub starts a scoped, short-lived Google WIF session using the existing service
account. The reader accesses only the separate public-data staging spreadsheet
configured in `rzd_import_collect.py`, never the discount database. The public
workspace has been shared with that same account; no OAuth scope or original
workbook sharing setting is widened. No source account, SMS, cookie, paid service
or ScrapingAnt credit is used.

Each read clears the controlled workspace and its old number formats, verifies
empty cells, writes a constant allowlisted URL/XPath formula with a new generation
marker, then requires two stable native cell reads. Formulas are cleared and that
cleanup is verified after each request, including failures. An expired Google
token or ambiguous state fails rather than relabelling an old import. Only the
original existing writer accesses the discount database after validating the
public artifact.

The reader requests robots first and obeys the ordinary crawler group, including
RZD's20-second delay. The homepage must again expose the catalogue link. All
source-owned `partners__frame` links are discovered from that response. Separate
Bitrix category pagers use observed single `PAGEN_n` URLs; combinations retaining
another category's page are counted, not traversed as a Cartesian product. No
unobserved page number, partner ID, discount or coupon value is inserted.

The bounds are32 catalogue pages,100 detail pages and135 import requests, with a
3300-second overall budget. Above100 details, the selected window rotates by week
and coverage explicitly remains partial. The source-owned `/partners/<id>/` and
`/promo/<slug>/` pages are parsed below their own H1; external cards, image-only
clauses, linked PDFs and private areas are not fetched. Forms/coupons/purchases
are never operated. Unexpected types, layout/identity, formula changes, wide
spills, caps and source refusals are explicit failures; earlier valid records are
retained.

## Representation and freshness limits

IMPORT results are **Google-parsed cells, not original HTML or an exposed origin
HTTP status**. The formula is removed/reinserted on each run, but origin cache age
and redirect chain are not reported by Google. Store that limitation, the exact
import recipe hash, calculation timestamps, typed cell projection and its hash.
Do not call this an independently measured live HTTP response.

A source date may arrive as a Google date serial. Preserve its displayed date and
numeric/format metadata with an explicit coercion warning; do not infer an offer
expiry or publication date from it. Other numeric/boolean coercions are rejected,
especially to avoid silently changing literal numeric coupons. No manually
corrected source values or saved snapshots serve as fallbacks.

A source instruction aimed at the agent is rejected as text, never executed.
The public artifact contains only source projections/reports, not Google headers,
account identities, staging formula access credentials or original Sheet exports.
The existing publisher verifies every reconstructed record and coverage counts.

## Operation

The proposed job runs Wednesday08:37 UTC, with manual dispatch and reviewed-main
release execution. It shares the existing collector concurrency lock. The
collection token lasts at most3600seconds for the bounded slow read; the publisher
obtains its own existing600-second token and uses the unchanged Sheets scope.

The ScrapingAnt workflow keeps its Mon/Tue/Thu/Fri schedule and manual dispatch.
Code pushes still run its regression suite but no longer automatically spend
provider credits, so registering this zero-credit RZD adapter does not consume a
second provider crawl. No original direct-source or EKP schedule changes.

Google references checked in this investigation:
- https://support.google.com/docs/answer/12188454?hl=en
- https://developers.google.com/workspace/sheets/api/reference/rest/v4/spreadsheets#SpreadsheetProperties

External-import permission is enabled only on the separate empty staging
workbook. This is not permission to put formulas or account-only material into the
original discount workbook. Its actual sharing must be checked independently;
older prose calling the destination private is not proof of current permissions.
