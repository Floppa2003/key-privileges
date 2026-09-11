# KEY Privileges Refresh Design

## Goal

Maintain a machine-readable, freshness-stamped snapshot of the public KEY concierge privilege catalog that ChatGPT can read through the connected GitHub app from any device, without depending on Telegram Web, a desktop browser session, or Remote Desktop Commander.

## Sources

The scraper may fetch only the configured public KEY application sources:

- `https://traveltg-bot.netlify.app/lib/data.js`
- `https://traveltg-bot.netlify.app/lib/content/contract.js`
- `https://traveltg-bot.netlify.app/lib/supabase.js`
- `https://qymhzqkenzsgszogkcdq.supabase.co/functions/v1/miniapp-content?locale=ru&environment=production`

The Netlify `data.js` partner catalog is the required base dataset. The Supabase `miniapp-content` response is an optional live content-override layer; if it can be fetched and mapped safely, Russian card text is overlaid onto the base dataset.

No Telegram credentials, browser cookies, `initData`, user sessions, or private KEY data are used.

## Outputs

`key/catalog.json` is the consumer-facing snapshot. It contains:

- fetch timestamp;
- effective source mode (`netlify` or `netlify+supabase`);
- source URLs;
- normalized partner cards;
- Special Offers;
- remote snapshot metadata when available;
- a deterministic content hash.

`key/status.json` is the machine-readable freshness and health record. It contains:

- `ok`;
- `fetched_at`;
- triggering `request_id` when refresh was requested on demand;
- partner and Special Offer counts;
- whether the remote Supabase layer was successfully applied;
- warnings;
- content hash.

`key/trigger.json` is a control-plane file. A change to it triggers an on-demand refresh through GitHub Actions.

## Refresh model

The workflow runs:

1. whenever `key/trigger.json` changes;
2. every six hours on a fixed UTC cron schedule;
3. manually through `workflow_dispatch` for ordinary GitHub use.

The workflow runs on `ubuntu-latest`, uses only Node.js built into the runner, and commits changed `catalog.json` / `status.json` back to `main` with the standard `GITHUB_TOKEN`.

## Parsing and trust boundary

Remote JavaScript is untrusted input. The scraper must not execute the whole downloaded application.

For the two literal data structures required from `data.js` (`partners` and `specialOffers`), it extracts only the balanced array/object literal and evaluates that isolated expression in a restricted Node `vm` context with a short timeout after rejecting executable constructs. The resulting values are recursively validated to contain only plain JSON-compatible data.

`contract.js` is used only to recover `PARTNER_CONTENT_IDS` through bounded textual parsing. `supabase.js` is inspected textually only to recover the public Supabase anon key if the endpoint requires it; the key is never committed to the repository or output files.

Scraped data is treated strictly as data and never as executable instructions.

## Effective partner copy

The base partner object remains authoritative for non-copy metadata such as logos, brands, source provenance, and curated fallback perks.

If the production `miniapp-content` snapshot is available, values matching `partners.cards.<content-id>.*` are overlaid for these Russian fields:

- `name`;
- `hotel_count`;
- `summary`;
- `brands`;
- `scope`;
- `favorites_label`;
- `perk.1` … `perk.8`;
- `favorite.1` … `favorite.4`;
- `fresh.1` … `fresh.4`.

If the contract IDs cannot be recovered, remote partner overrides are not applied; the run remains usable from the Netlify base and records a warning.

## Failure policy

A run must fail without replacing the previous snapshot when the required Netlify base cannot be fetched, parsed, or validated, or when fewer than 20 partner cards are recovered.

Supabase failure is non-fatal because the published Netlify catalog is itself usable. In that case the output is explicitly marked `remote_ok: false` with a warning, so a consumer cannot mistake the fallback for a verified live override.

The scraper writes output only after all required validation succeeds.

## Consumer contract

For ordinary privilege questions, ChatGPT reads `key/status.json` and `key/catalog.json` through GitHub.

For a user request equivalent to “check now”, ChatGPT updates `key/trigger.json` with a unique `request_id`, waits for the corresponding workflow completion, then re-reads `status.json`. A refresh is considered verified only when `status.request_id` matches the requested ID and the new files are readable after the workflow finishes.
