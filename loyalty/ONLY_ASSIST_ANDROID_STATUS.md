# Only Assist Android integration — 20 September 2026

## Scope and verified boundary

The owner reopened Only Assist after their screenshots showed offers absent from the public Konsierge snapshot, and approved continuing APK/UI investigation, including non-documented routes. This supersedes the earlier instruction to defer app investigation, **not** the existing public Konsierge daily collector.

An interrupted ChatGPT response did not roll back the work. Existing branch `diagnostics/only-assist-android-20260920` and its successful runs were recovered through GitHub before further work. The captured catalogue remains **zero app offers**: startup and login detection are not authenticated catalogue coverage.

## Recovered real application evidence

Run **35474386130**, execution **643c802bed441dba921ec042d447f95ac54530ec**, downloaded the exact `com.konsierge.assist.only` **1.16.0 / versionCode34** package from RuStore. Store metadata and actual APK package/version identities were cross-checked. Three split APKs passed `apksigner verify`; this establishes signed, consistent files, not a separately audited legal publisher identity. The public distribution protocol was found via apkeep's RuStore implementation, not an APKPure account or login bypass.

| Verified package field | Value |
|---|---|
| Store application ID | 2063665675 |
| Actual minimum / target SDK | 32 / 35 |
| Installed APKs | base + arm64-v8a + Russian resource split |
| Total downloaded APK bytes | 73495674 |
| Base SHA256 | `856870ddb0197451612a36cdc86d6a6b46d6880ee25a32c44d0a30f1c2447952` |
| ABI split SHA256 | `bb8e7bfda373cca513e02297b7d95e4fe354d7ef2b7951de7cdc0ca65eb128f5` |
| Russian split SHA256 | `96b28a45348773ab41e63d6a62406a560742225e1e590945d3b38167c91b9f05` |

A fresh **Android API35 emulator** reported ABI list `x86_64,arm64-v8a`. The unmodified app installed and launched. The actual startup UI was observed at **2026-09-19T22:53:04.867320+00:00**. UI Automator returned five source-owned labels including Only Assist, Добро пожаловать and Alfa ID. The screenshot corroborates the Alfa ID button. The outcome was `login_required`; no phone number, OTP or account credentials were entered. Do not infer that every authenticated screen is equally readable.

Artifact **10593956975** (ZIP SHA256 `a33077152065b62e044c23a5fe2f4206da742004104e05257fd3f391c5101d88`) was downloaded afresh and its SHA256/CRC checked on 20 September. APKs and emulator state were not published in that artifact.

## Concrete discount request structure found in the APK

The app contains a separate benefits Retrofit service using **https://benefits.konsierge.com**:

```text
GET /api/client/v1/benefits
  Authorization header; rubric_id, tariff_id, page, per
GET /api/client/v1/rubrics
  Authorization header; tariff_id, datetime_from
```

`BenefitsViewModel` passes a page size of50. `BenefitsFragment` gets `Tariff` through `StorageRepositoryImpl.getTariff()`, which reads the stored Profile and calls `getTariff()`. The tariff ID is passed to the benefits/rubric calls. `BaseAuthHelper.getBenefitsHeaderForAuth()` constructs a separate Basic header from an app literal, rather than showing a direct user-token parameter in those methods. **No literal credential values were exported or replayed.**

This proves that the request path includes a profile-derived tariff filter; it does **not** establish the owner's actual tariff ID, prove how the server enforces entitlement, or prove that tariff filtering is the sole cause of the screenshot/catalogue differences. Do not enumerate tariff IDs, substitute the website catalogue, or advertise a successful Only Assist API read.

Additional static-origin run **35474661949**, execution **c0c93b9fb73afc5ca2e0d6f8253efac6e60cbf01**, observed **2026-09-19T22:56:38.937173+00:00**, preserved structural lines with all non-structural literals removed. Artifact **10593282918**, ZIP SHA256 `66a07ef73e78e641671f9923d955e91ff3690d2cdc6590de0850e11a784710b6`, was independently downloaded and checked. JADX exit code was **3**; only the successfully produced inspected classes support these conclusions, not a claim that the entire APK decompiled cleanly. No source-service request was made by the static probes.

## New device probe

`diagnostics/only_assist_device_probe.py` is a **single-screen readiness/extraction helper**, not a full catalogue scraper. It requires Python3.10+ and Android SDK Platform Tools; it has no Python package dependencies and does not need Appium/Mobile MCP for this limited stage.

Default mode lists ADB device states, selects exactly one authorized device, checks the exact app's installation/version and whether it is foreground. It does not install, launch, reset, click or log into anything. More than one connected device requires explicit `--serial`; serials are never written into reports.

Explicit `--capture --expected-title` captures only an already-open app screen. It checks foreground before and after the dump, requires the requested title near the top (a bottom navigation label is insufficient), rejects other visible packages/password/login screens, and omits editable values and their aggregate containers. Invoke it only for the approved Discounts screen and specific partner cards, not chats, profile or bank screens.

It writes one random temporary XML under `/data/local/tmp` and removes that same file in a finally block. Source-owned labels go only to a private local JSON outside Git working trees, with restrictive POSIX file/directory permissions. It rejects symlink output directories and does not overwrite previous captures. Stdout contains statuses/counts only, never the UI labels. No screenshot, account database, traffic log, tokens, cookies or OTP capture is implemented.

```bash
# From the repository: readiness only, no UI capture.
python3 diagnostics/only_assist_device_probe.py

# Owner opens Only Assist -> Discounts and dismisses keyboard/dialogs first.
python3 diagnostics/only_assist_device_probe.py --capture --expected-title 'Скидки'

# Only after the exact partner card is already open:
python3 diagnostics/only_assist_device_probe.py --capture --expected-title 'USmall'
```

A snapshot is always `catalogue_complete=false`, with `catalogue_records=0`: visible labels do not prove full terms or pagination. Capturing and scrolling the actual authenticated cards, identifying their navigation controls, and testing whole-catalogue completeness remain subsequent work. Do not feed this helper's output directly to the public Sheets publisher.

## New real-device-probe verification

Run **35498452756:1**, execution **3669b940caa1eef7a621a0755bb950345c7afcc3**, job **106045733500**, completed successfully on 20 September. The **21 new synthetic unit tests** passed locally and in GitHub Actions. The workflow then downloaded the same three hash-pinned APKs, installed/launched them in an empty API35 emulator, and ran the new helper through real ADB.

Readiness was verified at **2026-09-20T08:04:47.372610+00:00**. An explicit Discounts-screen attempt at **08:04:50.178891+00:00** correctly returned `login_required` with exit2, no UI labels, no output capture directory, and zero catalogue records. The test independently checked removal of the temporary device XML. This is a successful login-stop test, **not** a successful authenticated discount capture.

Artifact **10601168926**, ZIP SHA256 `d6f0cb57da4bba041858233b620f3427c0b14b8401d81259a14e865f6ad57d96`, was downloaded and its SHA256/CRC verified. Both executed file hashes match the reviewed local bytes:
- probe: `7e5fb9d470015a9b78339c21406b8fb03cb19811d409512c11179e4145e5dcdd`;
- tests: `6069553b67b4a4c6c87d5d78cf2ace5de4b78bb579863ac8ec89c6fd32fa966e`.

The temporary check workflow is removed before merging this diagnostic helper. No shared collector, normalizer, source registry, existing schedule or Google Sheets content is changed. The legacy full-suite count1102 is not claimed as a test run of this standalone addition; this release ran the21 focused tests and the real app/device smoke test.

## Next acceptance boundary

A fresh Remote Desktop Commander `list_devices` call on 20 September found the connected MacBook **offline**. The ChatGPT sandbox separately has no ADB/emulator/KVM. These are distinct runtime checks, not proof that ADB is missing on the owner's MacBook. Nothing was run on the user's computer or phone.

The next required input is an available authorized Android session: bring the MacBook's Desktop Commander online, connect the phone, enable/authorize USB debugging, and leave the existing Only Assist on Discounts. The owner performs any needed Alfa ID login themselves. Then read the root screen and a few specific app-only partner cards. Do not collect private account data merely to find a tariff value. Root, alternate accounts or authentication bypass are not needed by this UI route.

For unattended collection, authenticated emulator operation/session lifetime and private storage must still be tested. Do not put account snapshots or authenticated-only terms into the public repository, public artifacts or the current link-accessible Sheets. Existing Konsierge collection and the shared publisher are unchanged. No Only Assist recurring job or registered production source is introduced by this helper.

Android references: https://developer.android.com/tools/adb and https://developer.android.com/training/testing/other-components/ui-automator .
