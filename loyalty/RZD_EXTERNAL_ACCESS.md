# RZD external partner paths — direct GitHub evidence, 2026-09-17

## Scope and outcome

The previously accepted RZD catalogue archive35135328617 contains26 external-link occurrences representing two distinct destinations: RZD Tour and UniCredit CASH&BACK. This continuation tested the destination sites directly from GitHub, without a source account, API key, Google identity or paid service. **Both public destination pages loaded; neither is a demonstrated GitHub-network blocker.** No new external-condition record was published by this diagnostic.

Run **35207613565**, commit **0c2eae837a7a05e1cbfefedf9fb383dfdb498390**, branch `diagnostics/rzd-external-conditions-20260917`, completed successfully. Its workflow has no schedule and is not merged into production. Runtime collection remains unchanged. Source selection came from the prior accepted public catalogue; that catalogue was not freshly re-fetched in this diagnostic.

## Actual requests

All five requests used ordinary TLS verification, no redirects and no retries. Robots for each host were read and checked before target reads; a minimum five-second interval was observed. Response limits were2MB and bounded connection/read timeouts. Credential-bearing forms/scripts were removed from retained HTML.

| Target | HTTP | Observation interval UTC |
|---|---:|---|
| https://rzdtour.com/robots.txt |200|09:54:07.013062–09:54:07.950638|
| https://rzdtour.com/ |200|09:54:12.952114–09:54:17.398041|
| One tour actually linked by that fresh home page |200|09:54:22.524066–09:54:24.036999|
| https://www.unicreditbank.ru/robots.txt |200|09:54:24.038398–09:54:25.439008|
| https://www.unicreditbank.ru/ru/personal/cards/pi-packages/debit-cash-and-back.html |200|09:54:30.440866–09:54:31.459157|

The exact originally recorded RZD Tour card href was `http://rzdtour.com/?erid=2Vtzqxi4WZC`; this probe explicitly selected its public HTTPS root without the advertising parameter. It did not claim to follow or verify that original redirect/query chain. The UniCredit target is the exact catalogue-linked HTTPS path.

## Findings, not new generalized offers

RZD Tour's current home page exposed29 unique URLs under its cruise-train prefix: one category URL plus28 tour pages. The first eligible linked detail was `https://rzdtour.com/kruiznyie-turyi/kruiznyie-poezda/velichie-severa-2.velichie-severa-s-poseshheniem-muzeya-rozhdestvenskoj-igrushki`. Its own `.modal-main.content-price .text-content-route` block contains an explicit RZD Bonus clause:5% for participants, with purchase through the RZD Tour sales office or a website application identifying the card number. That statement was read in **one tour's pricing block**, not certified as an identical benefit for every tour. The same block contains route-specific inclusions, exclusions and prices. They must stay attached to that tour if this path is integrated; generic marketing prices or another tour's wording must not be substituted.

The current UniCredit destination is a valid CASH&BACK product page, not a transport error or login gate. Its preserved public text does **not** establish the RZD Bonus1:1 exchange advertised in the older RZD catalogue. Absence on this page is not proof the exchange was cancelled, the user is ineligible or a source account would reveal nothing. The page links separate reward rules; those binary rules have not been fetched by this GitHub diagnostic. Do not promote unrelated Mir promotions or generic card cashback to an RZD exchange benefit.

An additional web-reader lookup of the linked bank PDF returned cached text, but screenshots failed and no current binary was obtained in this continuation. That result is not production extraction and was not written into the spreadsheet. A local container's immediate connection failure was an environment limitation; the later real GitHub200 responses are the relevant transport evidence.

## Evidence

Public artifact **10490535781**, SHA256 `6ccba43b34f71af447a4b24430e3876087cc9a31db7932686e1e1e31820147c1`, was downloaded, hash-checked and ZIP-CRC-checked. It contains the exact executed workflow, request metadata, both robots documents and sanitized target HTML. No secrets, account data, private spreadsheet cells or unredacted forms were used.

This is a bounded five-request transport/content probe, not a production adapter test suite or recurring publication. The next useful work is source-bound extraction/publication from these reachable pages and the bank's actual linked rules, not more anonymous proxy experimentation. RZD's eight own-host full-detail gaps remain66/74: six prior login responses and two unresolved import errors. None is labelled technically impossible.

Run: https://github.com/Floppa2003/key-privileges/actions/runs/35207613565
