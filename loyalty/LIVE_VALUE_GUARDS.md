# Live-value guard audit — 2.9.1

This follows live document/caption extraction 2.9.0 and the user's requirement for reusable, fresh public ingestion rather than hand-curated answer substitution.

## Defect and correction

Some existing identity checks required a previously observed price, percentage, code, account cap, example number or fixed set of four plans. These were not returned canned answers, but would reject ordinary source updates. Identity and scope checks now retain programme/page/template markers without those numeric snapshot requirements.

Affected configurations: Sfera/EKP, RGO headquarters, MiXX rules, Utair Family, Mir/101Hotels, Mir/Aeroexpress, Otello Promo Miles, Wings/Cars&GO, AZIMUT earning. Otello's display title no longer embeds a past promo code/year. Original exact source URLs and original stable IDs are retained; archival pages do not become current promotions.

Smartavia reads the current bounded nonempty set of tariff cards, supports a multi-digit additional-traveller count in the existing 1+N grammar, and rejects duplicate/malformed labels. It does not demand the old four-card set. Askona identifies an undated accrual sentence by numeric earning grammar and scope, not the old 1-mile/100-ruble values; conflicting or only dated candidates fail rather than becoming a base rate. VTB excludes its footer using the observed footer component structure, not a particular telephone number or the word 'free'.

## Evidence

Ten mutation tests cover altered prices, rates, cashback caps, years, codes, family account/period limits, plan-set cardinality and multi-digit labels, separate dated/base earning and footer phone changes. The original defects were reproduced before changes. Full local tests: 480 Python and seven KEY tests pass. The local environment has pypdf5.9.0; exact pinned-production dependencies are tested by Actions.

Actions review run34880107144 called actual production entrypoints for all12 affected source routes, yielding27 records and12 ok reports. The same full480+7 tests passed there. Artifact10363095416 SHA256 db8846de12116bc387eb828b0b593a7da51e3d02397f9bc0a9ff8e590c084a64 was independently downloaded, CRC checked and all98 archived code/config/test digests verified. Every27 public record passed schema, evidence/identity validation and publisher preparation. A temporary checksum-bound development patch and review workflow are removed from the integration tree.

## Boundaries

This is not a promise of universal future semantic or layout correctness. Exact programme identity, site-specific selectors, safe public routes, resource budgets and supported clause grammar remain intentional contracts. Unknown service concepts, new storage hosts, changed markup or ambiguous semantics require explicit review/failure, not a canned replacement. Test fixtures are not loaded into production output.

Neither source collection nor Google publication uses saved review artifacts as fresh data. Old retained observations keep old timestamps; current execution downloads actual sources. General scheduling and Google permissions are unchanged. Main publication and the final independently verified counts belong in the release PR after its run.
