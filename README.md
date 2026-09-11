# KEY privileges mirror

Public machine-readable snapshot of the KEY concierge Telegram Mini App privilege catalog, readable by ChatGPT from any device without Telegram Web or a desktop browser session.

## Files

- `key/catalog.json` — normalized catalog.
- `key/status.json` — freshness, source mode, warnings, counts, and content hash.
- `key/trigger.json` — on-demand refresh trigger.
- `key/refresh.mjs` — dependency-free scraper/parser.
- `.github/workflows/refresh-key.yml` — GitHub Actions refresh workflow.

## Sources and safety

The scraper reads only public KEY resources: Netlify `data.js` for the base catalog, the public content contract for stable partner IDs, public Supabase configuration for the anon key when needed, and the production `miniapp-content` Supabase Edge Function for current Russian overrides.

No Telegram token, browser cookie, Telegram `initData`, user session, or private KEY data is required or stored. Remote JavaScript is treated as untrusted input and is not executed wholesale: only required data literals are isolated, executable constructs rejected, evaluated in a restricted short-lived VM, and normalized output validated before writing.

## Refresh

The catalog refreshes every six hours, manually through GitHub Actions, or on demand by changing `key/trigger.json` with a unique value such as:

```json
{
  "request_id": "2026-09-11T03:45:12+03:00",
  "reason": "on_demand_refresh"
}
```

After an on-demand trigger, verify `key/status.json`; require:

- `ok: true`;
- `request_id` equal to the requested ID;
- `partner_count >= 20`;
- a non-empty `content_sha256`.

Changing the trigger alone does not prove refresh completion.

`remote_ok: true` means the Supabase production layer was mapped onto the Netlify base. `remote_ok: false` means the snapshot remains usable but reflects only the published Netlify base; inspect `warnings` before treating it as live content verification.

## Failure policy

If the required Netlify base cannot be fetched, parsed, or validated, refresh fails and the previous committed snapshot remains untouched. Supabase override failure is non-fatal and recorded in `status.json`.
