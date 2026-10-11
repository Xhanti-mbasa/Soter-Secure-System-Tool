# APK releases

Every new Android version is delivered through a published GitHub Release with an attached signed APK and a per-version SHA-256 file. Downloads in a source folder or workflow artifacts alone are insufficient.

1. Build/test the version and verify its APK/signature using the existing signing key. Keep the key outside Git.
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
