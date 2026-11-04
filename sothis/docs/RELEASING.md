# APK releases

Every new Android version is delivered through a published GitHub Release with an attached signed APK and a per-version SHA-256 file. Downloads in a source folder or workflow artifacts alone are insufficient.

## Build on GitHub (from 0.8.1)

1. Bump `versionCode`/`versionName` in `android/app/build.gradle` and `AndroidManifest.xml`, add `releases/X.Y.Z.md` and a changelog entry, and merge to main.
2. Run **Actions → Build Sothis APK release → Run workflow** on main. It runs the tests, installs SDK platform 36 and build-tools 36.0.0, builds with `scripts/build_apk.py`, signs with the `SOTHIS_KEYSTORE_B64` / `SOTHIS_KEYSTORE_PASSWORD` secrets, and refuses to continue unless the certificate matches `releases/signing.json` and the packaged assets match source.
3. With **publish** on (default), it commits the APK and `SHA256SUMS`, registers that commit in `manifest.json`, pushes to main and publishes the release with `scripts/publish_releases.py`. With publish off, the signed APK is only uploaded as a workflow artifact.

0.8.1 introduced a new release key (`CN=Sothis Release`); 0.1.0–0.8.0 used a debug key that is no longer available, so 0.8.0 installs must be removed before installing 0.8.1. A backup of the key and its password is kept outside Git by the owner. Losing it forces another reinstall, so never rotate it without recording the new fingerprint.

## Manual steps

1. Build/test the version and verify its APK/signature using the release key. Keep the key outside Git.
2. Commit `releases/sothis-X.Y.Z.apk` and its entry in `releases/SHA256SUMS`, with the matching build version and source assets. Record that full commit SHA.
3. Add `releases/X.Y.Z.md` and an entry in `releases/manifest.json` referring to that exact commit. Set `latest` to the recommended version. Push to main.
4. The **Sothis APK releases** workflow verifies the checksum, committed APK, build version and packaged assets; creates a draft release; attaches and re-downloads both files; then publishes it. Inspect the successful run and release assets before saying delivery is complete.

Tags use `sothis-vX.Y.Z` because this repository also contains Soter. Both the feature and optimized versions receive separate releases. The initial registered versions are 0.7.0 and 0.7.1; older tracked APKs remain historical files.

The workflow uses the runner's GitHub CLI and repository-scoped `GITHUB_TOKEN` with `contents: write`; no additional token or signing secret is required to publish these already-built APKs. It runs for release-file changes on main and can be rerun manually from Actions. It never rebuilds with a different signing identity, replaces existing published binaries or retargets a version tag. Checksum, tag, missing-asset and permission errors fail visibly. Interrupted draft uploads can be resumed safely.

Local verification without network access:

```bash
python3 sothis/scripts/publish_releases.py --dry-run
python3 -m unittest discover -s sothis/tests -p test_releases.py -v
```

For manual publishing, install/authenticate GitHub CLI with appropriate repository permissions and run the script without `--dry-run`. The APKs are currently signed with the existing development identity; release notes retain that distinction and the provider/device limitations.
