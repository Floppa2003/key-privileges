# Anonymous access boundary audit — 23 September 2026

## Result and correction to the previous frontier

This is a completed diagnostic, not a release of new discount records. No production collector, source registry, publisher, Google Sheet, source account or recurring schedule was changed. The temporary push-only diagnostic workflows are removed with this report. Their executed revisions and actual job outputs remain identified below.

**EKP:** the hypothesis that the existing mapper alone hides otherwise supplied restricted conditions is now falsified for the complete current anonymous catalogue query. All **110 restricted entries** in the **1053-entry, nine-page** response set contain literal JSON `null` for both `loyaltyDescription` and `discountScheme` BEFORE any production projection. Removing the mapper filter cannot recover those values. This does not prove that every possible public representation or independent merchant publication is inaccessible.

**Only Assist:** further static inspection confirms that the inspected benefits-client factory installs a logging interceptor and a language-query interceptor, but no personal-token interceptor. However, an actual request without Authorization received **401**. Personal Alfa ID login, application/service authentication and tariff eligibility are different boundaries. No embedded credential was replayed, and no app catalogue record was recovered.

**RZD:** current direct and Exa attempts did not recover the six historical login-page details. The fresh direct refusal was **403**, not a newly observed login form. Two other historical import failures were not retested in this diagnostic. The independent-merchant backlog remains open.

These findings supersede the overly categorical Only Assist wording in earlier status documents. The authorized-device UI path is an available design, not proof that all possible data-access paths require an interactive personal login.

## Actual execution identities

| Diagnostic | Run / attempt | Commit | Jobs read to completion |
|---|---|---|---|
| Anonymous HTTP baseline and freshly downloaded APK client inspection | 35897295974:1 | 9152e73a49e7616cac092c8712196200295f1879 | anonymous 107304292373; static-apk 107304291846 |
| First-page EKP pre-projection sample | 35897750391:1 | 0e78b5b53bc5794f4aa5cbaf8e4c662dc4b00494 | metadata 107305805186 |
| Full EKP field-state inventory | 35898439909:1 | f5f53e6a2f4770c895013ad598c24c592e55a6b6 | metadata 107308145046 |

All three workflows and their jobs were independently read as completed/success. These jobs intentionally return structured diagnostic outcomes, so a green job does NOT mean that its target website was successfully read. The concrete outcomes below, not the job colour, establish the result.

## EKP: complete raw-field presence check

Exact ordinary anonymous UI query:

```json
{"pagination":{"limit":120,"offset":0},"filters":{"categories":[],"name":"","qrDiscount":false,"region":"98"}}
```

Endpoint: `https://ekp.spb.ru/api/portal/loyalty/partners`.
The same query was used at the source-owned page offsets below. Region98 is the literal UI filter labelled "Все регионы", not proof of geographic eligibility.

Direct GitHub HTTP first returned `ConnectTimeout` at 17:41:17 UTC. The already deployed Free-provider anonymous-browser route then succeeded. Its API fetch used `credentials:'omit'`, no Authorization header, no redirects, `cache:'no-store'`, bounded timeouts and source pacing. No account was opened or source permission changed.

The first-page sample at 17:45:42.514–17:45:43.928 UTC found 85 unrestricted/nonempty and 35 restricted/null pairs. The full independent traversal at **17:51:39.340–17:52:04.338 UTC** then checked all nine pages, stable reported total1053, exact page lengths and absence of duplicate native IDs.

| Offset | HTTP | Entries | Restricted: both raw fields null | Unrestricted: both nonempty | Unrestricted: redemption mentions login |
|---:|---:|---:|---:|---:|---:|
| 0 | 200 | 120 | 35 | 85 | 0 |
| 120 | 200 | 120 | 25 | 95 | 0 |
| 240 | 200 | 120 | 20 | 100 | 0 |
| 360 | 200 | 120 | 10 | 110 | 0 |
| 480 | 200 | 120 | 12 | 108 | 0 |
| 600 | 200 | 120 | 2 | 117 | 1 |
| 720 | 200 | 120 | 2 | 118 | 0 |
| 840 | 200 | 120 | 1 | 118 | 1 |
| 960 | 200 | 93 | 3 | 90 | 0 |
| **Total** | | **1053** | **110** | **941** | **2** |

The two login mentions are a lexical diagnostic, not a finding that two additional whole cards are protected or that the login necessarily belongs to EKP. Nonempty fields are not a semantic review of every offer or evidence of personal eligibility. Only metadata/counts were retained; no newly read conditions were published or used to refresh Sheet timestamps.

Full-traversal source-response SHA256 by offset:

```text
0   ab251024ee56110f8297b735132b82e39127dc4013caa565958b29ddbd7be241
120 7bff45c404dc1fac2be4ef6307f7b9f2b0474069c6d6ea857ee022c82007ff17
240 2abf394dc8962abf5db0d06ca3043ee9ede2af6e64a3a73798f63aa51e648c11
360 8fb0fc2889592f25da262de1312193d361084ae907eaebd57f13179572e90fb2
480 bdb087a0fce75665d95e8d55066c0f868213a33f8746764ee5df1cd9d5eb7a3f
600 8b3f6d83488441fb592953d224a49cd0ba3af669c97aff366a9e2d5a38195229
720 40c6b7508aee584fcf3c4f8d9d782166e9bbb77330daf14158521df53c9aa4b8
840 e54055c6f8c89a92bb14005bf9e07d7eea8ece66a8b2f59cacfdad6b87f2e2ef
960 3621d20504362984cff4ad8a2425dd37ebe510f806163152609b039210ad3d3d
```

The first-page digest matches the earlier sample. Identical bytes do not distinguish unchanged origin content from a cache. Cache age was not established; request time is not an independently certified origin-refresh time. Raw bodies are not retained and cannot be reconstructed from these hashes.

1053 is a fresh diagnostic inventory count, not a new Sheet count. Do not automatically interpret the change from historical1045 as eight verified new offers. The exact identity equivalence of the current110 restricted entries and historical110/106names was not certified by this aggregate report.

## Only Assist: full inspected client factory, not credential replay

The current public RuStore package was freshly downloaded and inspected from 17:41:17.850374 to 17:44:43.358952 UTC:
- package `com.konsierge.assist.only`, version1.16.0, versionCode34;
- three split APKs, 73495674bytes total;
- base APK SHA256 `856870ddb0197451612a36cdc86d6a6b46d6880ee25a32c44d0a30f1c2447952`;
- reviewed package-helper Git blob `aa5a655eef17061b6b6199ebbc1d8708be148664` checked before execution;
- JADX1.5.6 official release digest verified; decompiler exit3, so whole-application clean decompilation is NOT claimed;
- the complete emitted `com/konsierge/konsierge/api/benefits/BenefitsClient.java` was inspected, SHA256 `805a8685a622d232a5807e295210ae49b1008e7da9fa6c4e64a309130d011af4`.

The factory uses its own `new OkHttpClient.Builder()`, clears application interceptors and adds only `HttpLoggingInterceptor` plus a query-language interceptor before constructing Retrofit's client. A general `AuthInterceptor` exists elsewhere in the app; its presence alone is not evidence that this benefits factory installs it. The inspected factory does not add a personal user-token header. The ViewModel calls this factory for benefits and rubrics and passes tariff/rubric/pagination parameters. See ONLY_ASSIST_ANDROID_STATUS.md for the separately inspected Basic-header helper and profile-derived tariff chain; their literal values remain omitted.

A distinct actual anonymous `GET https://benefits.konsierge.com/api/client/v1/benefits` at **17:41:26.239307 UTC** returned **401**, with server Date17:41:26GMT and no reported cache Age. The request was not retried with an extracted credential. No tariff guessing, account creation, coupon request, app patch or application execution was performed in this continuation.

Conclusion: a completely unauthenticated read failed. A personal session is not shown in the inspected client factory, but server entitlement enforcement, the correct owner tariff and a supported service-authenticated collection route remain unproven. Do not relabel a service credential as "no authorization" or treat the existing public Konsierge catalogue as the owner's app catalogue.

## RZD: unsuccessful fresh routes and a misleading public alternative

Direct `GET` of the historical Sakvoyazh offer returned403 at17:41:26.836707UTC. The remaining five direct requests were stopped after the host refusal; the code did not obtain six fresh HTML login pages.

Exa was then actually called for the six exact historical detail URLs listed in CORAL_IMPORT_COVERAGE.md. Sakvoyazh, Admiralteyskaya, Hilton Garden Inn Volgograd and Airo returned `CRAWL_LIVECRAWL_TIMEOUT`; Chekhoff and Station returned `CRAWL_UNKNOWN_ERROR`. No conditions or readable login form came from that batch. These are reader failures, not proofs of permanent origin unavailability or authentication requirements.

The official public Station Hotels page https://station-hotels.ru/blog/skidki-v-oteljah-peterburga-uchastnikam-programmy-rzhd-bonus/ was found and read through Exa/web retrieval. It contains15% and a public code, but also explicit booking/stay bounds31.12.2023. It cannot establish the current16% RZD card or its current code. Web retrieval labelled its crawl age last month; this was corroborating public research, not a new uncached production observation. Do not reactivate these historical terms.

Renaissance Smart Plus and Grand Karat Sochi2026 remain separate historical import failures, not newly tested authentication gates. Independent merchant publications have not been exhaustively investigated.

## Cost, privacy and next useful boundary

Both EKP diagnostics independently confirmed the existing provider's Free plan before spending. Actual usage was150+150=**300Free credits**, balance3355→3205→3055. No automatic paid upgrade, extra account or rented service was introduced. Standard public-repository GitHub runners were used; no new workflow artifacts were uploaded. Provider and source authentication are distinct: the provider API key remained inside the existing runner secret and was never exported.

A fresh Desktop Commander device-list read still reports the connected computer offline. No computer/phone command or authenticated UI capture was executed. The owner's already-authorized device remains a possible legitimate validation route when reachable, not proof of API necessity.

Next steps must target a different evidenced public representation, current merchant-owned terms, or separately approved access. Do not repeat the completed nine-page field-state audit, remove the EKP filter hoping to recover nulls, replay APK secrets against401, or count transport failures as completed coverage. Any account-only terms need a suitable private destination; this public repository and link-accessible Sheet are not private storage.
