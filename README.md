# KEY privileges mirror

Public, machine-readable snapshot of the privilege catalog exposed by the KEY concierge Telegram Mini App.

The repository exists so ChatGPT can answer privilege questions from any device without depending on a logged-in Telegram Web session or a desktop browser connection.

## Files

- `key/catalog.json` — normalized privilege catalog.
- `key/status.json` — freshness, source mode, warnings, counts, and content hash.
- `key/trigger.json` — on-demand refresh trigger.
- `key/refresh.mjs` — dependency-free scraper/parser.
- `.github/workflows/refresh-key.yml` — GitHub Actions refresh workflow.

## Data sources

The scraper reads only public application resources:

- KEY Netlify application JavaScript for the base partner catalog;
- KEY public content contract for stable partner content IDs;
- KEY public Supabase configuration to recover the public anon key when needed;
- the production `miniapp-content` Supabase Edge Function for current Russian content overrides.

No Telegram token, browser cookie, Telegram `initData`, or user session is required or stored.

## Refresh behavior

The catalog refreshes every six hours. It can also be refreshed manually in GitHub Actions or on demand by changing `key/trigger.json`.

For an on-demand refresh, write a unique value such as:

```json
{
  "request_id": "2026-09-11T03:45:12+03:00",
  "reason": "on_demand_refresh"
}
```

A consumer must not assume the refresh completed merely because the trigger file changed. Verify `key/status.json` afterward and require:

- `ok: true`;
- `request_id` equal to the requested ID;
- `partner_count >= 20`;
- a non-empty `content_sha256`.

`remote_ok: true` means the Supabase production content layer was successfully mapped onto the Netlify base catalog. `remote_ok: false` means the snapshot is still usable but currently reflects only the published Netlify base data; inspect `warnings` before treating it as a live content verification.

## Failure policy

If the required Netlify base cannot be fetched, parsed, or validated, the refresh fails and the previously committed snapshot remains untouched. A Supabase override failure is non-fatal but is recorded explicitly in `status.json`.

Remote JavaScript is treated as untrusted input. The scraper does not execute the whole application; it extracts only the required data literals, rejects executable constructs, evaluates them in a restricted short-lived VM context, and validates the normalized result before writing output.
