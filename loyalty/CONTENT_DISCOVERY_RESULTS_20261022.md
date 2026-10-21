# Content-driven discovery repair — 22 October 2026

## Scope and status

Repair branch: `fix/content-driven-discovery-20261022`. This is independent of
experimental LLM PR #90. No model calls, billing changes, credential changes,
schedule changes or Sheets publication were made by these repair workflows.
Runtime changes are recorded in `aa11e15bb71d0b27b2d239d81d620bb483a78ce0` and
`10782096de722dbc99830cabbb06c62d850d98be`; the final cleanup changes only CI/docs.
This report does not assert deployment to main.

The current extraction contract is in `CONTENT_DISCOVERY.md`. Confirmed live
content allowlists were removed from FlyStation, Mantera FAQ/hotel/partner tiers,
Tsvetnoy HTML/PDF tiers, Utair/Wings tiers, TSUM/Alfa, MiXX, Utair partners,
Sacvoyage, Artparking, Dom Knigi, GPB options, Utair Generations, Ladoga EKP,
HSE unanchored partner sections and Smartavia plan labels. Routing by trusted
source identity, structural ambiguity checks and security policies remain.

## Verified execution

| Check | Result |
| --- | --- |
| Recovered initial patch: run 39694777931 | 1402 Python tests + 7 KEY tests passed |
| Follow-up patch: run 39696515363 | 1418 Python tests + 7 KEY tests passed |
| Follow-up Python runtime | 58.167 seconds |
| Historical normalized rows from run 39583519809 | 1390 validated, 0 errors |
| Exact follow-up source transport | All 9 before/after hashes verified; committed source matches tested files |

The interrupted initial delivery failed on a payload hash before any parser
changes were applied. Two exact transport insertions were removed; the original
compressed/patch/source hashes were retained and verified. This was not a test
failure suppressed to obtain a green build. Staging files and write-enabled
bootstrap workflows are removed from the final tree. The retained regression
workflow is read-only, uses no repository secrets and has no publishing step.

Follow-up mutation tests were observed failing on the old code: new Ladoga rates,
gift items, note/card counts and links; new/renamed HSE unanchored headings;
arbitrary Smartavia tariff names. Separate failing controls showed a 100%/50%
prepayment being interpreted as an additional discount. Both raw normalized
rates and literal reward terms now use the same scoped reward phrases in the
affected adapters. Source conditions retain the prepayment requirement.

## Captured-source replay

Inputs: artifact 12385379666 from run 39685263932, observed
2026-10-21T22:16:49.553074+00:00. Page and PDF hashes were verified before replay.
This is deterministic replay of captured pages, not a new crawl at replay time.

| Source | Inventory | Retained records | Explicit exclusions | Evidence-only records |
| --- | ---: | ---: | ---: | ---: |
| FlyStation | 7 | 7 | 0 | 2 |
| Tsvetnoy | 123 | 86 | 37 | 0 |
| Mantera FAQ | 5 tiers | 5 | — | — |

FlyStation includes the newly published flight-school promotion without adding
its title to a parser list. The two unclassified/price-only panels remain source
observations, not invented discounts. Tsvetnoy accounts for every discovered item;
its 37 exclusions are reported, not silently dropped. Mantera replay covers only
FAQ: independent hotel and partner pages were not part of this capture.

## Evidence artifacts

- Initial verified patch: artifact 12390158325, run 39694777931;
  ZIP SHA256 `a64007471e3b3b64adc8125ec905e2155e770bf93dc091dca83f73cfc38892a7`.
- Follow-up verification: artifact 12391451255, run 39696515363;
  ZIP SHA256 `ee469a9c64319dab8492cf10fa142dda667297b662a4422aa90bf5a1594cea0f`.
- Capture: artifact 12385379666;
  ZIP SHA256 `38115357819d3594485145eb72f4def48ff456fdcdebd37a29420f4d68b7a1ec`.

The archives contain execution source snapshots, raw test logs and replay
results. Artifact retention is finite; the checked-in mutation tests remain
runnable without these artifacts or live websites.

## Limits and compatibility

Legacy names can remain in frozen historical projection code or ID aliases.
They are not live admission lists and never substitute old rates/conditions for
current evidence. New collectors explicitly version evidence where required.
Unknown free text is retained for review, not promoted to a confirmed benefit.

Dynamic inventory discovery is not universal semantic extraction. DOM roles,
programme boundaries and parsing grammars still matter; a wholly new layout or
ambiguous text can require adapter work. Tests cover reviewed surfaces and
mutations, not live availability of all 125 sources. No claim is made that all
unrelated source failures have been repaired.
