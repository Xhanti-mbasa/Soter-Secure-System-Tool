# Self-hosted website validation

Validated 10 October 2026. Website release 1 adds a production WSGI gateway over the existing Sothis 0.4.0 research engine and interface. Android code and its APK remain unchanged.

## Passed

- **46 Python tests**: 34 existing engine/services/Party tests and 12 website tests. Website checks cover absent default credentials, HTTPS configuration, authenticated APIs and archives, Secure HttpOnly cookies, nonce-based script policy, origin/CSRF rejection, host/static-file boundaries, JSON size/type limits, persisted cases/rules/sessions after restart, password-reset revocation, expiry/logout, persisted login rate limits, original delivery, ZIP hash verification and SQLite backup/restore.
- **Actual browser flow** through the WSGI gateway: wrong-password feedback, login, engine connection, bundled-font/photo loading, indexed Ramaphosa search, evidence review, server investigation creation, pinning, Markdown and ZIP downloads, authenticated archived-original delivery, rule creation/pause, Party directory, ten geographic categories, reload persistence and logout with cache clearing.
- Search, Party, Regions, Tools, Cases and Settings checked at **320, 390, 720 and 1280 pixels**, with no horizontal page overflow. No uncaught JavaScript errors or script-policy violations. Login/home/mobile screenshots were captured under `docs/screenshots/web-*.png`.
- **Actual Gunicorn 26.2.0 process** using the committed single-worker gthread configuration: startup, health check, login, authenticated HTML and seeded engine API passed. The process was started without `--preload` and terminated after the check.
- Compose YAML parsed; verified loopback app port, persistent data mount, Tunnel token file, optional Tunnel/HTTPS profiles and Python compilation. `git diff --check` passed.

## Scope and limits

Tests use an isolated throwaway login/database and the dated bundled public collection. One already-downloaded original is a fixture for delivery checks; no private user evidence is used. Browser checks do not assert the availability of external search providers, CIPC access or every live Parliament/eTenders endpoint. Existing service tests cover provider parsing and ranking with controlled fixtures.

A Docker daemon is unavailable in the build environment, so the Docker image, certificate issuance and tunnel connector were **not executed here**. Production process startup was tested directly with Gunicorn. The user's server and Cloudflare account were not accessed; this is a server-ready implementation, **not a verified live deployment** at the chosen domain. Follow the deployment guide and verify health, HTTPS, login and a backup after installation.

The workspace has one login; browser-specific reviews/drafts remain local as described in the deployment guide. Alerts are an in-app inbox, not closed-browser push delivery. Government indexing and public discovery retain their stated coverage limits. The engine's existing bounded collectors do not acquire login-gated CIPC records automatically.

## Reproduce

```bash
cd sothis
python3 -m pip install -r requirements-web.txt
python3 -m unittest discover -s tests -q
python3 scripts/check_web.py --chrome /path/to/chrome --playwright /path/to/playwright
```

`--chrome-zip /path/to/headless-shell.zip` can substitute for `--chrome`. Supply `--screenshots /path/to/output` to save browser captures. Credentials and sessions are generated in temporary storage and discarded after the browser run. See `deploy/README.md` for real-server installation and recovery.
