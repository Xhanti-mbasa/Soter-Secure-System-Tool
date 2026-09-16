# Secure frontend design QA

## Scope

- Product correction: replace the seeded demo dashboard with an account and product setup flow.
- Visual target: retain the approved BountyOps-inspired dark operations language.
- First-run state: blank account fields, blank authorized target, explicit consent.
- Post-setup state: one user-entered target and an empty operational workspace.

## Browser verification

- Opened the first-run experience at `http://terminal.local:4173/`.
- Confirmed all setup inputs render blank with no example values or placeholders.
- Completed both onboarding steps and verified the user-entered organization, operator, and target carry into the workspace.
- Confirmed the findings table contains zero rows and the metrics use em dashes rather than fabricated counts.
- Confirmed History shows a truthful no-scans state.
- Confirmed Targets shows only the target supplied during setup.
- Confirmed the production build completes successfully.

## Product findings resolved

- P0: Removed the fake vulnerability findings and evidence.
- P0: Removed the pre-running fake scan, elapsed time, and scanner-stage results.
- P1: Removed the default `example.com` target and pre-checked authorization.
- P1: Replaced placeholder milestone pages with useful empty states.
- P1: Added accountable first-run setup for operator, organization, and authorized target.
- P1: Prevented the disconnected frontend from pretending that a live scan started.
- P2: Added an account menu and a reset path for the browser-local workspace.
- P2: Disabled findings controls until real result data exists.

## Visual review

The revised flow preserves the selected visual language: dark slate surfaces, compact hierarchy, Inter plus IBM Plex Mono, restrained cyan accents, Phosphor interface icons, technical values in monospace, clear focus states, and dense operational structure. The setup page reads as a product onboarding surface rather than a marketing mockup.

## Known boundary

Account and workspace setup are stored locally in the browser because the current backend has no user or organization identity endpoints. The UI states this directly. The frontend does not expose an administrative API key and does not fabricate scan completion.

## Final result

final result: passed
