# Aeroflot combined refresh and bounded retries — accepted 2026-09-18

PR52 merged as `faf23824956235de04f7d41e476d8032a81b3403`. Main run **35274931392:1** completed regression, collection and publisher **105392440686**; all final jobs and publisher steps were independently read as success.

Source interval: **2026-09-17T21:09:09.883799+00:00–21:38:14.079267+00:00**. The current discovered catalogue was read completely in one pass: **229 companies and six airlines, 235/235, zero final errors, 239 Google imports, zero provider credits**. This refreshed existing identities, not 235 new offers. The previously failed company endpoint id523090 was read successfully.

The new reader permits one cleared retry per discovered company/airline detail URL, at most 12 per run, after 30 seconds. Only import error cells and calculation timeouts qualify. Identity, authorization, semantic, quota and cleanup failures do not. The original 324-import/3000-second bounds remain. **No retry was needed in this live run (`detail_retries=[]`); retry behavior is test-verified, not demonstrated by a live retry recovery here.**

The exact main code passed **874 Python and seven KEY tests**. Main test artifact10520206893 SHA256 `c0e5795e2793aa07519639970668bb9c5886c7e97df69222befb2aa2eeb33682`; source artifact10520864024 SHA256 `1978eb63b8587c3319b36d58df544d849ddad7fd4d67f713c01fb7231090525c`. Digests and ZIP CRCs were checked. All 235 records were reconstructed using the actual executed code with an explicitly historical completion clock; replay is not a fresh source observation.

## Destination acceptance

Same spreadsheet `1uFR7croj7p6RRNPcoTRYlVl06hKsurkIgyu1IdMMB-4`, title `скидки`. A read-only export after completed publication matched **5889 managed source/report fields** (235×25 +14). Updated source rows2225–2459 and report1397. Common-record titles, partners, source rows, observation times, benefit/condition counts and current generation matched the per-record projections.

Compared with the pre-Aeroflot export, all **2288 other parser records**, all2523 manual comments and six original input/audit tabs' values/formulas were unchanged. Final native manifest was independently read as **verified/current;2523 retained parser records /3171 common records**. Generation `b54d543a015dfece9acd8cde8c2bf7762ef2abb54450a9c825faee7c4899ff9c`; source fingerprint `57e9b463b1c83e756df47b46e6ae0ac24dc768c7a04f7ce6bc9e562da8a8b871`. Export SHA256 `bfa62023646443bd491b462ca4ee2d409059ccec7076d10807e874a8374ba20f`. Private exports were not committed or published.

No whole-workbook rendered layout audit is claimed. Native sampled styles remain wrapped/top-aligned/10pt. The Thursday08:47UTC schedule, shared publication exclusion, existing Google WIF and zero-credit route are unchanged. No source account, new key, paid service or sharing change.

This closes a demonstrated transient completeness gap in the current root catalogue, not external rule traversal, personal eligibility or all future refresh reliability. Google import cache age remains unknown. See EKP_LINKED_ACCEPTANCE.md for the separate five condition records accepted before this refresh; they are retained unchanged. Further source-linked external rules remain a separate unfinished scope.
