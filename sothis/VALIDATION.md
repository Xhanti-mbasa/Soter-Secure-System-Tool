# Sothis validation

## Version 0.4.0 — UI refresh

Validated on 10 October 2026.

- Four Playwright suites pass on the seeded engine and recorded native-bridge contracts: indexed/live search, dates, company-number normalization, CIPC access state, local evidence saving, ownership review, cases, export, alerts, tender awards/preparation, Party rosters, biographies, salary provenance, category searches and provider failures.
- The native photoCredits bridge supplies local metadata without file-origin fetch. A standalone Chromium file-origin check with the native bridge confirms all ten region cards and the bundled Doto font load offline. The new visual suite covers six main screens at 320, 360, 390, 412, 720 and 1200 CSS pixels with no horizontal overflow; dock targets remain at least 44 × 44 pixels. It checks local photograph/font/icon delivery and MIME types, unavailable portrait fallback, static file boundaries, Doto availability and uncaught JavaScript errors. Rendered mobile evidence is in `docs/screenshots/`.
- 34 Python tests pass, including the added official-portrait path test. Published portrait URLs are accepted only inside Parliament's MemberImages directory. All 449 captured roster entries have official portrait metadata; an unavailable photo displays initials.
- Nine actual South African landscape photos are bundled with creator/source/license/modification metadata. National and Gauteng share the Pretoria photograph. Doto OFL and Phosphor MIT license files are packaged; Settings displays photography credits and original source/license links.
- The native launch/JobScheduler regression checks pass. SDK 35 resource linking, Java compilation, DEX, alignment and APK v2/v3 verification pass. Package `za.co.zalens`, versionName `0.4.0`, versionCode `5`, minimum SDK 26, target SDK 35. All 31 packaged assets match the tested source byte for byte. Signing certificate matches 0.3.1 for an in-place update.
- APK SHA-256: `9284f3deef658a7c844e12a9a2c60edce4025cf95133bb10ac887ab1863709a9`.
- No physical Android device or emulator was available. Browser rendering and native scheduling boundary checks do not certify device startup, OS insets or notification delivery. Portrait display needs internet; landscape cards, font and icons work offline.

## Version 0.3.1

- Both 0.2.0 and 0.3.0 scheduled a network-constrained persisted job in Activity.onCreate, before creating the WebView, without ACCESS_NETWORK_STATE. The initial 0.1.0 launch path did not schedule this job. This matches Android 14+’s documented SecurityException behavior: https://developer.android.com/about/versions/14/behavior-changes-14#jobscheduler . No device crash trace was supplied, so this is a verified code defect consistent with the reported failure, not a captured phone stack trace.
- Declared ACCESS_NETWORK_STATE in the final APK and retained INTERNET / RECEIVE_BOOT_COMPLETED / JobService permission. Deferred optional monitoring to onPageFinished for the trusted local page. Scheduler permission failures, missing service, rejected schedules and runtime exceptions return a status instead of escaping through startup.
- scripts/check_android_startup.py compiles and executes the actual MonitorScheduler with strict JVM Android doubles: old unguarded permission rejection, successful scheduling with correct permissions, unchanged job ID/network/interval/persistence, missing permission, missing scheduler, declined job, SecurityException and IllegalStateException all checked. This is native boundary regression coverage, not an Android emulator run.
- Existing 33 Python checks and three Playwright suites passed; clean SDK 35 Java/DEX build and APK v2/v3 signature verification passed. Final packaged assets match source, ACCESS_NETWORK_STATE is in the binary manifest, versionCode is 4, and signing certificate matches 0.3.0.
- Device startup still needs the user’s installation check. Saved preferences, WebView storage, cases and evidence are retained by an in-place compatible update.

## Version 0.3.0

- Official Parliament directory capture: 18 parties, 449 unique public representative IDs; explicit party codes, total count and duplicates validated. Individual party pages were observed to have missing/stale entries, so the combined public directory is the roster source.
- June 2026 official public interests PDF parsed and 353 business extracts matched by party and name tokens. Business sections 1–4 retain PDF locators, capture times and SHA-256; residential-property sections are excluded from dossier extracts. Unmatched members retain an original register link.
- Gwede Mantashe’s public Parliament page and government biography were retrieved. Minister/Deputy Minister/Deputy President rates and effective date were visually verified on PDF page 3 of Gazette 53965, Notice 7004 (16 January 2026). The app labels these as dated office rates, not verified personal pay.
- 33 Python regression checks passed, including roster completeness, duplicate/unknown-party rejection, featured-member exclusion, member-page role isolation, failed-refresh preservation, changed-role salary handling, disclosure boundaries and topic/name matching.
- Three Playwright suites passed: existing collection features, standalone discovery/tools and Party. Party exercised ANC search routing, representative filtering, dossier facts and provenance, category queries, export, investigation pinning, alerts, failed-refresh fallback, dossier-referenced originals in the evidence manifest and mobile width, through engine and native-bridge paths.
- Java compiled against Android SDK 35; signed APK verification passed. Package `za.co.zalens`, versionCode 3, versionName 0.3.0, minSdk 26, targetSdk 35. Existing development signing key retained.
- No physical Android device/emulator execution occurred in this environment. Native networking, notification delivery and background jobs still require device verification; the bridge tests exercise the interface contract.

## Version 0.2.0

Validated on 9 October 2026.

- 24 Python tests pass, including previous collection/search/auth/provenance regressions and new discovery deduplication, profile/post classification, registration normalization, explicit provider failures, public fallback parsing, tender status/company filters, monitoring baselines, change triggers, failure preservation, alert deduplication and imported-only CIPC monitoring.
- Both browser suites pass on a seeded real engine and the standalone native bridge contract. Desktop and 390 × 844 mobile checks cover collection/date filters, cases, evidence pins, exports, province groups, live footprint counts, ownership decisions, evidence archive manifests, portfolio ZIP calls, monitoring conditions, compact registration lookup, researcher-supplied company profiles, supplier award filters, bid preparation, persistence and no page errors/horizontal overflow.
- Actual public search responses were fetched and parsed for Sol Phenduka: 19 matching unique hits and 5 profile candidates across Instagram, Facebook, X, TikTok and YouTube. These were index candidates, not ownership assertions. Public Brave requests sometimes returned 429; DuckDuckGo Lite returned usable public results. These observations are bounded checks, not uptime guarantees.
- Official eTenders returned current live opportunities with province, dates, attachments and eSubmission flags. Its supplier-specific company filter returned five awarded notices for a tested published supplier. Public lookup for the user's registration number did not establish a company profile; no CIPC lookup success is claimed.
- CIPC's official notice confirms enterprise lookup moved to BizProfile and requires login. No authenticated registry connector was available. CIPC monitoring was verified against imported test disclosures only.
- Native Java compiles against Android SDK 35. Resource linking, DEX conversion, zip alignment and APK v2/v3 signature verification pass. Version code is 2; package and signing certificate match 0.1.0 for compatible updates. Manifest supports Android 8+ / target 35 and internet, optional notifications, and persisted background jobs.

The prior APK ran on the user's phone, as shown in their screenshots. This update was not exercised on a physical Android device or emulator here. File-picker behavior, native networking, notification permission delivery, OS background scheduling and ZIP contents still need device validation. Browser stubs verify the UI/bridge contract, not Android runtime behavior. The APK uses the documented SDK/ECJ pipeline; Android Studio/Gradle configuration is supplied.

Public web coverage is incomplete and may be blocked. No exhaustive social-account, actual-salary, automatic directorship or registry-monitoring claim is made. Tender preparation does not execute or certify submission. The government directory remains a starting inventory (203 source entries); broad source collection, OCR, relationships and narrative generation remain future work.
