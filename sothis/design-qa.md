# Sothis visual review

**Source visual truth:** the two NothingOS-inspired images embedded in the user's message: a floating navigation crop and a charcoal Android app screenshot. The referenced uploaded file paths were unavailable; the inline images were visible and reviewed. This is an adaptation of their style to the existing research app, not a recreation of the reference's empty media-player screen. No pixel-perfect comparison score or composite source file is claimed.

**Rendered implementation:** `docs/screenshots/home.png`, `regions.png`, `profile.png`, `tools.png`. Chromium browser-rendered app content, 390 × 844 pixels, CSS viewport 390 × 844, deviceScaleFactor 1. Original reference byte dimensions/density could not be verified because its files were absent. The Android system status bar and home indicator are excluded from app-content captures.

**Comparison evidence:** viewed the inline source references and opened the rendered Search, Regions, representative dossier and Tools screenshots. Full views establish the charcoal surface, monochrome photos, spacious rounded cards, blue active icon and floating gray pill with a separate circular Search control. The rendered dock was also reviewed at its displayed native scale: four equally spaced controls, black active oval, blue line icon and condensed uppercase monospaced labels. The layout retains readable research content and replaces the reference's media labels with Party, Regions, Tools and Cases. Settings is in the header.

## Findings and iteration history

1. P2 — Investigations title overflowed at 320 CSS pixels. The responsive browser check failed on Cases. Reduced that heading's mobile display size and allowed section-heading actions to wrap. The post-fix width check passes for every main screen at 320, 360, 390, 412, 720 and 1200 pixels.
2. P2 — Party's Find control had a blank blue circle after the icon-only search treatment; seen in the first dossier capture. Added the same Phosphor search icon and a descriptive accessible name. Subsequent UI suites and captures pass.
3. P2 — The first dossier capture kept the directory introduction and search form above the portrait, consuming most of the screen. Hide that introduction only while a dossier is open; keep Back to roster visible. The final `profile.png` shows the portrait, name and sourced role details immediately.

4. P2 — Android file-origin pages cannot fetch the new photo metadata. Added a native asset bridge method instead of enabling universal file access. A standalone file-origin browser check with that bridge passes for all ten region photos and the bundled font. The rebuilt APK includes this change.

No actionable P0/P1/P2 visual issues remain in the reviewed states.

## Required visual surfaces

- Typography: bundled Doto at weight 800/850 for brand, display headings and counts; system sans for research prose; monospaced small navigation labels. Doto availability verified in the browser. Readable body copy is intentionally different from the reference's condensed navigation text.
- Spacing/layout: 20-pixel mobile content margins, 26/28-pixel card radii, floating dock with safe-area allowance. All dock targets are at least 44 pixels; no horizontal overflow at the tested widths. Content scrolls beyond the dock with bottom padding.
- Color: charcoal #242424, card surfaces #2d2d2d/#303030, gray dock #565656, black active oval and blue #2e65ff accent. Photos are monochrome through CSS. Focus outlines and failure messages remain visible.
- Imagery: actual credited location photographs in local WebP files, with visible place captions. Official Parliament portraits use the exact directory image URL and fall back to initials. No generated portrait or inferred social-account identity is introduced. Phosphor icons preserve their MIT license.
- Copy: Sothis-specific navigation and evidence labels; existing source, capture-date, remuneration and identity caveats retained. Settings includes source/license links for imagery.

## Verification and remaining gaps

Four browser suites passed, including search, filtering, navigation, Party dossiers, alert/evidence/tender workflows, native-bridge contracts and photo fallback behavior. No uncaught JavaScript errors. Static assets have correct MIME types and unapproved asset paths return 404. Native launch scheduling regression checks and the signed APK build passed. The final APK's assets were compared byte for byte with the tested files.

Physical Android startup, system insets and notification delivery remain device-test gaps. Representative portraits require internet and may be absent; local landscape photos/fonts/icons do not.

**Implementation checklist:** visual refresh implemented; assets and credits packaged; responsive corrections applied; browser evidence captured; existing workflows verified; APK built and signed with the existing key.

final result: passed
