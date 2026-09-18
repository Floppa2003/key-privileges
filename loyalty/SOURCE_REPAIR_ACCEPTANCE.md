# Source repairs accepted — 18 September 2026

## Released result, not universal source completeness

PR64 merged as `2a12fc672ee03966da3097d67da514e39cbdb0f9` at18:30:05UTC. Its six intended production/test files fix HSE partner ownership and introduce an exact-URL, verified-TLS, HEAD-only Alfa availability probe. Existing schedules, source registration, publisher, free-provider arrangement and permissions remain unchanged.

Main one-time publication **35380667200:1**, execution `e976005f3e5b44bf2ca90c3efff164a8592dcd53`, verification job105715800202 and publisher105716148108 completed successfully. Source upserts/readbacks finished18:32:52UTC for184Mir rows and18:33:01UTC for56HSE/T2 rows. Final common-view publication/readback completed **18:35:51UTC**. The same Sheet `скидки`, ID`1uFR7croj7p6RRNPcoTRYlVl06hKsurkIgyu1IdMMB-4`, is destination-verified. The completed one-time publisher is removed in this acceptance commit; it is not a new recurring job.

## HSE: corrected a real cross-partner ownership error

The public catalogue has55listed cards. Its printing studio section has the exact heading **«Морда довольна. Студия печати»**, but no `mordapechat` named anchor. The old parser consumed that section as part of the preceding `kvadrat` partner while keeping the studio preview-only. Its15% clause, HSEALUMNI and contact email consequently appeared under KubKvadrat alongside KubKvadrat's actual10%.

The mapper now stops the preceding section at the reviewed exact heading and independently owns the unique unanchored printing section. Only source identity is configured, never rate/code answers. Duplicate or contradictory anchors/headings fail closed. Future restoration of the real anchor takes precedence. The studio keeps its original stable native ID and a real root-page/block locator, not a fabricated fragment. Its benefit URL is empty rather than a nonexistent direct anchor. Hidden/foreign content and rehashed ownership substitution are tested.

Real-source replay at the original observation time changed **only `anchor:kvadrat` and `anchor:mordapechat`; all53others matched**. Fresh collection confirms **52detailed records /3previews**, not51/4. Remaining previews: `skyeng`, `skillcup`, `academiya`; absence/empty source sections are not fabricated details. The separate `mordadovolna` gift-store offer is not the printing studio.

At acceptance source rows2587–2588 retain their positions and stable IDs:
- KubKvadrat: `ab95b5a67182c9fb57797412f0430314a7d870b48fce35760f4f11223ff5975c`,10%, ownHSEALUMNI/hsealumni spellings only.
- Printing studio: `352ee259336a0714f685018cef8fc389d798ab24607367f0eb35284158539e0d`,15%/HSEALUMNI, source-stated order by email `hello@modoband.ru`. The underlying print-product restrictions remain owned by that studio.

The common view projects the printing discount, not a free corporate-gift claim inferred from product vocabulary. Source publication is not checkout acceptance or personal eligibility. PR63's expiry and SilaVetra month-only distinctions remain; no unrelated HSE offer was rewritten from memory.

## Mir: successful fresh recovery without speculative code change

Mir job **105707481333** in **35378087590:1** completed successfully. That workflow's independent HSE replay-helper job failed; therefore acceptance checks the successful Mir job and exact payload, not a falsely claimed all-green parent run. Original Mir observation: **2026-09-18T18:05:30.373606+00:00**. Main publication preserves this timestamp.

**184unique offers /184discovered,0errors**, with independently read public details and four complete count/page scopes:

| Region | Payment | Source count / observed | Pages |
|---|---|---:|---:|
| Moscow/Moscow region | SBP |97/97|9|
| Moscow/Moscow region | Mir |166/166|14|
| Saint Petersburg/Leningrad region | SBP |90/90|8|
| Saint Petersburg/Leningrad region | Mir |154/154|13|

Regional unions178and166 overlap by160 source-equivalent observations, giving184unique records, not the sum of all four catalogue counts. These184stable IDs already existed in the Sheet; the publication refreshes them rather than adding duplicate merchants. The unchanged reader uses anonymous visible UI and observes its public responses, without replaying private APIs.

Separate bounded diagnostic **35378776256:1**, execution`71be1f1865229bdfad63df5a9a1ffafc1e8bba53`, checked only first/last Moscow pages. Both production readiness predicates passed: SBP lastpage9contained1card, Mir lastpage14contained10. This does not establish a structural pagination bug from prior timeouts; no Mir code change was made. It also does not certify all future runs.

Mir source artifact10560833033 SHA256`a21150a6529b1a25d692bac1eaad2f179083d94337baea72b0efe92ac1e3b84c`; exact normalized payloadSHA256`a60994e5b6079db10afb4c1f4eb4487035c2df14fcbfd3492a11becaa42bd424`. Last-page artifact10561451383 SHA256`9cfd7128d71e6dac69d9db47623b34a33f35c42ff08269bb551ba21587f29ea0`. ZIP digests/CRCs independently checked.

## Alfa: TLS diagnosis resolved; private cashback catalogue still unread

Official bank certificate guidance is `https://alfabank.ru/cert/`. The existing reviewed root URL/pin is reused from `recovered_contract.CA_FILES`: `https://gu-st.ru/content/lending/russian_trusted_root_ca_pem.crt`, SHA256`936a43fea6e8e525bcc0f81acd9c3d21b4fc4b9b68acea7906d698005afc6504`.

Ordinary default trust failed. A temporary bank-scoped bundle of defaultCAs+the pinned official root passed certificate/hostname verification. Diagnostic35377249536:1 then found a302onrobots to bank authorization. Exact-offers **HEAD** diagnostic **35377774952:1** at18:02:01UTC independently found302from `https://web.alfabank.ru/partner-offers/` to the known `private.auth.alfabank.ru` authorization path. No response body, redirect follow, cookie, query or source-account session was retained or used. This is stronger than the old undiagnosed certificate failure, but is not a full GET/browser/account investigation or proof no other public catalogue exists.

Final real dispatcher **35380093960:1** again successfully verified TLS and recorded `alfa_bank_authentication_redirect`. That actual source report is now in `parser_coverage` row1513 at acceptance: **failed/0offers**, methodHEAD,302, TLSverified, account/body/follow/activation/catalogue flagsfalse. It deliberately does not turn transport success into collected cashback.

The official CA host itself is intermittent: initial intermediate download failed; later public-CA-only diagnostic35379749147:1 could not download either certificate. The preceding real dispatcher35379313650:1 also recorded a transport failure. Such future failures remain distinct; the code does not replace them with an earlier auth observation. Trust is temporary per request, never installed globally or in the user's browser. No TLS verification is disabled, and no bank login/activation/private-data publication occurs.

Diagnostic artifacts:10560737148/root-plus-intermediate attempt,10560950340/root-only TLS,10560434432/exactHEAD. ExactHEAD ZIP SHA256`d230d7206b1ec226d344f56f0b3c0cdad658de63cb460738ffb81ba5b3b65bc7`. No bank content/cookies/query secrets are in these artifacts.

## Other sources and the source-health denominator

The baseline audit matched105configured routes to available reports, not105independent programmes. Some failed direct probes are alternatives for programmes already delivered by Google/browser collectors; they must not be counted as wholly absent offers. Retired bulk rules are out of practical scope, not parser gaps.

T2Selection's previously failed public programme page now returns1record/ok and is refreshed in the final payload. This is not all personal T2 privileges. Uralsib's public linked rules succeeded in35378598217:1 but failed again in35379313650:1; this remains intermittent, and no new Uralsib report was published by this release. Rostelecom's configured public press page still timed out at policy retrieval; its old stored rows were not erased. The independently indexed regional URL `https://www.company.rt.ru/press/REGIONALNEWS/d476187/` is only a candidate for a subsequent exact-source test, not a released replacement. RZD8full-detail and EKP110protected observations remain separate unresolved scopes.

## Test and code evidence

NineHSE regressions reproduced the old error; sevenAlfa tests cover URL/pin/redirect-redaction/TLS/no-body/no-false-coverage and real-dispatch routing. Successful HSE verification35378598217:1 passed1001Python/7KEY and real source replay/collection. Final **35380093960:1** passed **1008Python /7KEY, no skips**, actual HSE55/T2one/Alfa auth report; source observation **2026-09-18T18:26:45.537010+00:00**. Its six changed file bytes exactly matched independently reviewed local code. The final cleanup changes only temporary files; main regression and code/payload validation subsequently passed in35380667200:1.

Final artifact10561054108 SHA256`bf3da95f11f3ff21e3260365177a6919fab148e99da60be6ec96c91f7e1afece`; normalized payloadSHA256`eae3c7a354f780bfc37b73c0b229d721f7a1da951d848754b80af9611a975564`. ZIPCRC checked. Source payloads were published unchanged, within24hours of their actual observations, using existing main-only serial WIF writers; no source was re-fetched solely for publication.

Preparatory failures:35378087590's HSE replay helper used00:00instead of the record's actual observation; corrected without source-time relabeling.35379313650 passed1008tests but an overstrict external assertion demanded an auth redirect despite an actual CA/network failure. The final validation separates passing error-handling tests from source-access success; final access did in fact return the auth redirect. Local full-policy tests were unavailable withoutprotego; no local full-suite success is claimed.

## Independent destination verification

A fresh read-only export after completed publication and native cell checks confirm **2567parser /3215unified records, verified/current**, unchanged record totals. **240existing source rows** (184Mir+55HSE+1T2) and4newreports matched all **6056managed fields** of the approved payloads. All2327unrelated parser records and positions, all1508previous report rows, every manual field, sevenoriginal/historytabs, all8formulas and hidden64recordarchive remained unchanged.

An independent reconstruction of the five actual input tabs and practical normalizer matched **every current managed field** in all four common views and the manifest:3215records,3755benefits,9753conditions/costs,713code/delivery components. Export numeric types and percent formats were preserved; baseline reconstruction independently matched the old manifest before comparing the new state. Read-only private exports were not uploaded or delivered.

Current source fingerprint: **`315711dfbf5317ff871ccc0324c238630f6c2f8dd50f02ce6582ca0fed8ff78e`**.
Current generation: **`638c212da654b65c00efe24705b0e9519c3c0f4f05ef0ab19ca396fadcc93c2b`**.

These are stored-state identities, not universal freshness, usable-discount totals or personal eligibility. Native checks confirmed current source/report fields; full Google-rendered layout and ACL were not audited. No new paid service, provider credit consumption, account, schedule, server, permission, private banking data or bulk document expansion was introduced.
