# Sothis 0.1.0 validation

Validated on 9 October 2026.

## Completed

- 14 Python tests passed: province queries, national inclusion, category/date filtering, FTS escaping, spelling suggestions, content versioning/deduplication, evidence pins and export, HTML parsing, social-link attribution and share-link exclusion, private/allowlist URL guards, token enforcement, API round trips, remote binding requirements, login-gated source handling, crawl path scopes, and the OCR-required signal for image-only PDFs.
- Browser checks passed at desktop width and a 390 × 844 mobile viewport: real engine search, date filters, evidence details, case creation, pinning, Markdown download, CIPC access state, all province groups, native-bridge snapshot behavior, device case persistence across reload, report saving, and no horizontal overflow or JavaScript page errors.
- A fresh engine database bootstrapped from the bundled asset and returned the four expected Geordin Hill-Lewis passages for Western Cape.
- Ten public-source connectors exercised against real pages using bounded collection. The snapshot contains 36 searchable passages from 23 URLs. A scanned DPSA-linked PDF returned an explicit OCR-required error. Indexing status retains request-failure counts.
- Native Java client compiled against Android SDK 35. Resources linked, classes converted to DEX, APK zip-aligned, and APK v2/v3 signatures verified. Manifest inspection confirms Android 8.0+ / target 35 and internet as the only requested permission.
- Bundled snapshot text hashes were checked against the captured extracted text before packaging. Region tagging was corrected for generic national pages reached from a Cape Town directory seed. A known provincial-directory jurisdiction mismatch is disabled for manual review.

## Limits of this verification

No Android emulator or physical phone was used. Browser tests exercise the bundled UI and native bridge contract with a stub for Android-only functions; they do not prove the Android file picker, share sheet, WebView behavior, or networking on a particular phone. Install/startup on the user's device remains to be confirmed. The Gradle/Android Studio configuration is supplied; the APK was built with the documented SDK/ECJ pipeline.

The registry is an initial directory inventory, not a certified list of every government website. Most source entries have not been crawled. No completeness claim, person-account ownership claim, actual-salary claim, or automatic CIPC directorship claim is made. Commercial/general news search, OCR, entity verification, graphing, continuous scheduling, and AI narrative generation remain future work.
