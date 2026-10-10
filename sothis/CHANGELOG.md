# Changes

## 0.3.1 — 2026-10-10

- Fixed the native launch failure introduced in 0.2.0: network-constrained JobScheduler work requires ACCESS_NETWORK_STATE on Android 14+, but the permission was missing.
- Added the normal network-state permission; schedule optional monitoring only after the local app page loads. Missing permissions/services, rejected jobs and runtime scheduling exceptions now produce a background-status error without closing the app.
- Show background scheduling errors in Tools; preserve searches, cases, rules and evidence. Clean old compiled classes before APK builds.
- Added executable Java regression coverage of the production scheduling boundary. Android versionCode 4 uses the existing signing key for compatible updates.

## 0.3.0 — 2026-10-09

- Added Party tab, Tools entry and search mode; an exact listed party name/code in live Search opens its roster.
- Captured 18 parties and 449 public representatives from Parliament’s validated embedded member directory, with local capture dates and refresh controls.
- Added public representative dossiers with fresh Parliament roles, sourced education, dated executive remuneration, 353 matched business-interest extracts and separate historical biography roles.
- Added category-specific live discovery for news, government, salary, education, business and social candidates; optional topic queries preserve name-based matching and independent caches.
- Connected party/member mention alerts, dossier pinning, sourced Markdown export and referenced originals in evidence bundles.
- Built Android versionCode 3 using the existing package/signing key; previous APKs retained.

## 0.2.0

Fix snapshot-only person/business searches with native live public discovery, profile-candidate counts, human ownership review and an online footprint. Add registration normalization, CIPC access state and authorised company profiles; Tools with per-source collection progress; persistent phone/server monitoring and alert inbox; local original evidence archives and portfolio bundles; official eTenders opportunities/supplier awards, supporting documents and multiple bid preparation packs. Preserve the 0.1.0 app package/signing identity for updates.

CIPC live access requires an authorised integration. Tender packs require review and submission through each notice's channel. Public search remains best effort with an optional configured Search API key.
