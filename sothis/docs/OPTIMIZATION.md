# Optimized release 0.7.1

0.7.0 is retained as the feature baseline. 0.7.1 (Android versionCode 9) keeps the same package and signing certificate. Both signed APKs are in releases/.

| Measurement | 0.7.0 | 0.7.1 | Change |
| --- | ---: | ---: | ---: |
| APK bytes | 2,502,906 | 2,330,874 | 6.9% smaller |
| Local PDF.js + worker bytes | 3,040,896 | 1,532,374 | 49.6% smaller |
| Two concurrent cold provider calls, controlled 40 ms readers | 81.37 ms | 41.02 ms | Median of 10 pairs per version |
| Four simultaneous identical provider calls | One fetch under a global lock | One shared fetch, independent keys can run concurrently | Verified by concurrency regression |
| Offline library listing | Loads every stored Blob | Reads metadata only | Original bytes loaded only when opening/exporting |

The timing is a controlled scheduling test, not a claim about real internet speed or physical-device frame rates. Raw values are in optimization-metrics.json; scripts/benchmark_daily.py reproduces the comparison using the retained feature commit.

The second pass adds a bounded LRU and shared in-flight requests through ProviderCache, an explicit DailyService provider registry, reusable native DailyServices with provider interfaces and bounded caches, client request deduplication, and atomic IndexedDB metadata/file operations. Existing downloads migrate from schema 1 to 2 without losing originals. Unrelated native feed/job requests use striped locks; cache bookkeeping does not hold a network-wide lock.

The offline PDF assets are pinned to PDF.js 5.4.296, minified with Terser 5.44.0 and loaded only for PDF reading/import. scripts/vendor_pdf.py verifies upstream hashes and rebuilds the adapted classic scripts. The full Apache license is retained. No CV is sent to a parsing service.

Share rendering reuses its backdrop canvas, avoids repeated image encoding during slider movement, preserves photo aspect ratios with bounded resizing, wraps long source strings, rejects oversized photos, and reduces empty space in story-format cards. PNG dimensions and provenance remain intact.

Validation: **73 Python tests**, **seven shared browser suites**, the authenticated website suite, production Java compilation, native startup regression, v2/v3 signature checks and byte-for-byte packaged-asset checks passed. Additional daily checks cover cache deduplication at startup, local-storage migration and native PNG bridge delivery. All provider network calls are disabled in browser verification.

Physical camera/location, installation and receiving social applications still need device checks. The user's production server and Cloudflare account were not accessed. External providers retain the supported-source and handoff boundaries documented in DAILY_VALIDATION.md.
