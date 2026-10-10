# Everyday and share-card releases

## Feature release 0.7.0

The shared Android and self-hosted website interface adds Home, Regions, Opportunities and Profile, with a separate Search control. Explore retains People & parties, Tools and Investigations. Doto remains the bundled pixel heading font. Android versionCode 8 retains the existing package and signing identity.

| Area | Implemented behavior | Boundary |
| --- | --- | --- |
| Home | Dated headline cards, credited SAnews reader, catch-up, topic alerts, local likes and bookmarks | Custom publishers open the original; no invented trending rankings |
| Feeds | Default SAnews RSS, three custom HTTPS RSS/Atom feeds, deduplication and provider status | Custom feeds contribute headlines/links only; unavailable providers remain visible |
| Regions | Default map, first-use layout guidance, persisted choice in preferences, compact More actions | Existing dated indicator definitions and source coverage remain attached |
| Tools | In-place provider workspaces, bounded display counts, returned-date filters, source progress, alert entry points | Extensible provider classes; arbitrary downloaded code/plugins are not executed |
| Search | Collapsible scope menu, actionable index/source counts | Public profile candidates still need identity review |
| Cards | Click/keyboard opening, icon actions, publisher and date, collapsed technical provenance | Research pinning and integrity details remain available in More/research details |
| Profile | Local reading history and estimates, likes/preferences, province preference and opt-in location suggestion | Two-minute inactivity cutoff; external-browser reading is not measured; coordinates are not saved |
| Saves | Bookmarks, downloaded articles/files, offline reader, export/delete and 100 MiB local limit | Bookmarks alone are online links; browser storage can be cleared by the browser |
| Opportunities | Real Eastern Cape eRecruitment public vacancy parser, dates, salary, employer/location, expiry/dedup, Save/Apply | Structured role collection currently covers this provider; DPSA and other official sources use browser handoffs |
| CV | Local builder, TXT/PDF/DOCX import, original deletion, ATS text export, explainable skill matching | Up to 10 MiB, 30 PDF pages; scanned documents need manual text; no automatic CV upload |
| Applications | Official portal review/handoff, profile import, user-recorded acknowledgement references | No unsupported portal/session automation or automatic submission |
| Municipal reports | Fault type, editable recipient/subject/body/date/location, image/video/audio/file pickers, local drafts, MIME attachment export and email composer | Reviewed Cape Town contacts; other recipients require user review. Handoff is not a sent/accepted report |
| Share cards | Long press, keyboard context menu, visible Share controls, frosted/liquid/solid styles, local photo, opacity/blur, square/portrait/story PNG | Android share sheet, supported Web Share or image-download fallback; receiving social apps control their own uploads |

Photos/CVs/report attachments are processed locally. Selecting Apply or an email composer is an explicit handoff to the chosen provider. Custom RSS retrieval uses normal network requests from the phone or connected server. Sources and reporting dates are retained in public image cards.

## Verification

- 70 Python tests cover existing indexing/monitoring/research/authentication plus vacancy parsing, feed permissions, link/date validation, deduplication, cache refresh, partial provider failure and authenticated daily routes.
- Seven browser suites cover the shared interface, existing OSINT/company/tender/Party/province flows and the new daily workflows. Share checks exercise long press, all three treatments, a local background, opacity/blur and a real 1080 × 1920 PNG download. Local PDF and compressed DOCX CV text is checked without uploading it. MIME report drafts include an attachment; no email is sent by the checks.
- The authenticated website suite exercises login/CSRF, archived originals, cases, alerts, province gateway, reload/logout and all nine screens at four widths. Shared visual checks also cover six widths and 44px dock touch targets.
- Browser verification disables outgoing provider network calls and uses controlled fixtures/unavailable states. Separately downloaded public SAnews RSS and Eastern Cape vacancy HTML each yielded 10 real current items during parser inspection on 10 October 2026. This does not assert continuing provider availability.
- Production Java compiles against SDK 35. Signed APK v2/v3 verification and comparison of every packaged asset with the source tree are checked. The executable startup scheduling regression remains passing.

No physical Android device/emulator, installed social-app share target, location/camera hardware or production Cloudflare/server deployment is available in this environment. These release files and the existing deployment guide are ready for those final environment checks; they are not evidence that the public domain has been updated.

## Optimized release 0.7.1

The second release and measured changes are recorded after the optimization pass in OPTIMIZATION.md. Both APKs are retained for comparison.
