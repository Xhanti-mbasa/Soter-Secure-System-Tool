# Dock correction — 0.7.2

The corrected design uses a 272 × 64 px four-tab pill and a separate 56 px Search button in a 336 px container. Tabs are 52 px; the active tab is 92 px. Only its 10 px Roboto Mono label is displayed. Icons use a fixed 20 px mask with the source asset viewBox, so original vector dimensions cannot widen the tab. Below 360 px, idle targets remain 44 px and the active target is 76 px.

The active label is #f4f4f1 on #1e1e1e, the active icon #719aff, and the border #7a7a7a on #303030. Decorative bottom shading ignores pointer events. Existing dock CSS has been removed in favour of one shared stylesheet.

Search, Jobs, Tools, Tenders and party-directory/roster views own inline searches and omit the global Search orb. Member dossiers expose it. The remaining pill stays centred without reserving a blank Search slot. Settings selects Profile; research screens leave all four primary tabs unselected.

Visible Back buttons were removed from their creation sites. The existing history stack and Android Back bridge still support province, party and member routes. Keyboard opening hides both dock and shade. Android retains adjustResize so fields remain reachable; its window visibility signal handles WebViews whose layout viewport shrinks with the keyboard. Browser viewport checks ignore pinch zoom.

The employment exporter now reads chart-metric blocks and the publication-period paragraph instead of omitting numbers and mistaking a metric label for a date. Northern Cape's 36.3% absorption and 28.7% unemployment remain separate measures with their definitions.

Verified: 83 Python checks; all eight shared browser suites; authenticated website suite; 320, 360, 390, 412, 720 and 1280 px dock widths; accessible tab names/current-page state; zero Back controls; fixed icon bounds; source-search visibility; province/member history; native IME callback and browser resize hiding; local font delivery; employment share payloads; startup boundary; production Java/DEX compilation; compatible certificate; v2/v3 signatures; all packaged assets equal source.

No physical-device or emulator installation was available. IME tests simulate native visibility and viewport changes, so device-specific keyboard behaviour remains a device check. Production hosting is unchanged.
