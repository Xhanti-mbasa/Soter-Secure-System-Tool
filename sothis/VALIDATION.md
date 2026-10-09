# Sothis validation

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
