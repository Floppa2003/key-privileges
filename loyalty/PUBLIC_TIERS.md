# Public Selection previews and airline tier sections — 2.5.0

Three additional public routes use the existing schema-v2 record/publisher contract. Existing source IDs and the curated database are unchanged. These are missing source sections, not a solution for the eight previously unavailable catalogues.

## Source contracts

### `t2_selection_public`

The anonymous Selection landing pages for Moscow/region and Saint Petersburg/region each show four preview cards. Open each card using the ordinary UI, capture its uniquely matched public popup and close it before opening another. Never activate the offer, request a private code, sign in or submit the authentication form.

The ordinary `/api/loyalty/offers` response loaded alongside the landing page is the already-collected Bolshe catalogue, not a Selection catalogue. It is intentionally not counted again. Discovery also verified that the full-catalogue button leads to an authentication screen. The production adapter reads only the public previews and does not test access by submitting that form on later runs.

Each record remains `tier_benefit`, `page_block`, `public_preview_requires_login`, with `benefit_url=null`. The validator enforces this using source identity. The source URL, exact card label and matched popup are the evidence; no individual URL or vendor API ID is invented. A synthetic partner-label key stays stable across rate/expiry edits. Duplicate labels within one region fail rather than silently collapsing ambiguous cards. Equal cross-region evidence merges; conflicting terms produce an error and do not attach the conflicting region to the primary conditions.

Explicit popup expiry is parsed separately from observation time. A missing date stays unknown. MILE·ON·AIR says access to listed airports' lounges; the source does not establish free/unlimited entry or a visit quota. The published four Yandex discounts retain their actual amounts, minimum orders and service restrictions; private SMS/app codes are not retrieved. Partial-region or late-popup failures preserve earlier accepted evidence. Successful preview coverage is not complete personalized catalogue coverage or proof of member eligibility.

### `utair_tiers`

The public `https://media.utair.ru/status` page is read by clicking Start, Basic, Bronze, Silver, Gold and Platinum tabs at their visible label positions. DOM order is not tier order. Qualification is associated with each tab using its published layout rectangle; the selected panel must be uniquely active and each subsequent click must switch panel ID. No JavaScript class mutation is used.

One record contains each tier's visible benefits, embedded tooltips, qualification and general charter/codeshare exclusions. `details.source_blocks` preserves layout fragments and `details.qualification` carries the spend threshold/window. Layout fragments are not independent benefit counts. The publisher does not expand inherited-tier benefits or fetch every linked full-rule document. Signed/credential-like outgoing links are excluded, with a warning, rather than persisted into public artifacts.

The same source currently publishes introductory thresholds of both 7,000 and 10,000 rubles in different responsive sections. Preserve both complete observations in `details.intro_context`, with `conflict=true` and a warning. Basic's 10,000-ruble threshold comes from the actual tier table; it does not silently resolve the inconsistent introduction. The other published table thresholds are 20,000 / 50,000 / 350,000 / 550,000 rubles for Bronze / Silver / Gold / Platinum, over calendar-year flights. No personal status is verified.

### `ural_tiers`

The three explicit tier sections at `https://www.uralairlines.ru/wings_rules/` are separated by their headings, preserving nested restrictions and relevant common bonus rules. Blue is awarded on registration; Silver requires 15 flights OR 200,000 rubles in the stated calendar-year window; Gold requires previous Silver and 25 flights OR 400,000 rubles. These are extracted qualification fields, not inferred offer expiry.

The per-fare/per-geography flight bonus percentages retain their whole source clauses in `details.flight_bonus_rates`, explicitly denominated in programme bonuses rather than bank cashback. Remaining percentages and restrictions retain their source wording. Upgrade/baggage restrictions are not replaced by a simplified unconditional free-service claim.

## Verified branch evidence

Run `34779150443` executed the production dispatcher against all three new routes: 6 Selection previews (4 + 4 minus 2 exact shared observations), 6 Utair tiers and 3 Wings tiers, with no source errors. Observation time `2026-09-13T19:56:07.906039+00:00`.

Artifact `10324645739` was independently downloaded; ZIP SHA256 `23bda225b8c794a29370bf66f4fd1a4144974ed0d27398853450f098fcbe927d`. All 15 records pass JSON Schema, application identity/evidence checks and publisher preparation. All eight changed implementation/registration/test files match the locally tested bytes. 288 Python tests and 7 KEY tests pass locally; the Actions test job passed too. Tests include observed red/green regressions for incorrect adjacent popup association, full-catalogue promotion, conflicts, signed links, source registration and late-read retention.

Discovery runs: `34777696405` (public pages), `34777987751` (popup/full-list authentication boundary), `34778240073` (all public preview popups and airline pages), `34778465035` (all six real Utair tab-to-panel transitions). An earlier optional asset fetch failed, but that was not reported as proof of inaccessible popups. The linked Greatlist restaurant campaign explicitly ran 29 May–30 June 2026; it was not added as a current campaign or used to inflate the new count.

Main publication is a separate gate: inspect its actual payload, publisher completion and independently read-back managed values. Do not use the branch count as proof of a completed Google write.

## Operational boundaries

Total registered routes become 48 (below the existing 50-report publisher bound). No change to Google permissions, secrets, production workflows, schema columns, KEY code, network egress, TLS validation or schedule flags. Managed tabs remain `parser_offers` A:Y / `parser_coverage` A:N, with Z/O reserved for manual notes. Missing observations never delete or expire previous records. Temporary discovery/review workflows and code-registration helpers are removed before merge. Private spreadsheet exports and credentials never belong in this public repository.
