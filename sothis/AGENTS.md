# Sothis release requirements

Every delivered Android version must have a published GitHub Release with the signed APK attached. A file committed under `releases/`, a workflow artifact, or a local download alone does not complete a release.

Keep the existing signing identity for compatible updates. Verify the APK, update `releases/SHA256SUMS`, add release notes and register the exact source commit in `releases/manifest.json`. Keep both checkpoints when delivering a feature version followed by an optimized version.

The Sothis APK releases workflow publishes registered versions on main. Follow `docs/RELEASING.md`, inspect the workflow result and verify the published assets before reporting completion. Include a GitHub Release link in the final response. State any publishing blocker accurately.
