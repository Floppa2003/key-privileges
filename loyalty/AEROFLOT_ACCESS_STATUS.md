# Aeroflot original catalogue: scoped access decision — 2026-09-16

## Decision

Requested source: `aeroflot`, https://www.aeroflot.ru/ru-ru/afl_bonus/partners .

**Operational status: `blocked_by_source_crawl_policy`. No programme catalogue records have been collected or published.** The requested ordinary anonymous recurring crawl is disallowed by the site's published default robots group. This is a concrete prerequisite blocker, not a proof that arbitrary code on GitHub is technically incapable of downloading the page. Repeated transport failures, a reader's HTTP status, or this policy decision must never be labelled an exhaustive technical impossibility theorem.

The path can be reconsidered after the source changes its applicable crawl rules, grants appropriate permission, or supplies an approved machine-readable catalogue. No such permission or approved alternative feed was established in the bounded investigation. Existing partner-side rules and Promo Miles remain separate sources, not a substitute for this catalogue or proof of its completeness.

## New source-policy evidence

A temporary tab in the separate public-data import workspace evaluated the exact formula:

`=IMPORTDATA("https://www.aeroflot.ru/robots.txt")`

Native CellData verified the formula and its typed result. The complete imported projection occupied `A2:A549`, with 544 nonempty text rows. An authenticated export of that public staging workbook was CRC checked; only this policy tab was extracted for analysis. The spreadsheet export represents the formula through an Excel DUMMYFUNCTION wrapper; that wrapper was not executed. Native CellData, not the wrapper, establishes the original Google formula.

The imported document contains three groups: `*`, `Yandex`, and `Googlebot`. The ordinary `*` group contains 189 Allow/Disallow rules. For the requested path `/ru-ru/afl_bonus/partners`, its matching rules are:

```
User-agent: *
Disallow: */afl_bonus/*
Disallow: */partners*
```

They were independently read back at native rows 2, 63 and 95. None of that group's Allow patterns matches the target. The Googlebot group differs; no special crawler identity was claimed or used to borrow its exception. No forbidden catalogue page was requested during this policy confirmation.

SHA256 of the reconstructed imported policy text (UTF-8, newline-joined rows, final newline): `371dbc2630a1c87d96842e7440f60feca06f05d40103eb5a9cee0cb647a3a8d9`.

SHA256 of the public staging export used for the independent comparison: `112bdfcc1be7d9bdfa13fc05afd4914d19d51e36e626cd60422ff67c68a0e0ff`.

These hashes identify a **Google-parsed cell projection**, not original origin-response bytes. Google does not expose origin HTTP status, redirect history or origin cache age through this import. The observation is a policy check requested on September 16, not a certified origin fetch timestamp.

## Bounded alternative discovery

The permitted homepage was queried for its title and links containing `afl_bonus`, `partners` or `bonus`. Google returned `N_A: Imported content is empty`; this is an import error, not an observed origin HTTP refusal.

The sitemap explicitly advertised in the policy, https://www.aeroflot.ru/sitemap.xml , did load ten sitemap references: nine language maps under `http://aeroflot.ru/sitemap/xml/` and `http://aeroflot.ru/sitemapold.xml`. The web reader could not open the Russian child map. No alternative programme feed was thereby established. Search results and individual partner pages were not promoted into a complete official catalogue.

The temporary `af_policy_check` tab was removed after its evidence was retained. A new metadata read confirmed that only the original `public_fetch` tab remains. The running RZD worker's tab, dimensions and formula generation were not modified. No source account, ScrapingAnt credit, extra account, purchase, coupon issuance, Google scope or production schedule was involved in this check.

## What the status means for answers

For a user asking about a merchant, absence from this catalogue's records is **unknown coverage**, not proof of no Aeroflot benefit. Continue to distinguish any already collected partner-owned terms from this inaccessible main catalogue. Do not mark this source `ok`, supply cached answers as newly collected, or silently remove it from the original-source inventory.
