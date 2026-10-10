# Sothis website on your server

Default address: **https://sothis.xhantidaka.online**. This leaves your existing main domain available. Setup accepts another hostname, including `xhantidaka.online` if you want Sothis at the root. A URL path such as `/sothis` is not supported in this release.

This is **one private research workspace with one configured login**. It includes the NothingOS-inspired interface, photos, Party, public discovery, government collectors, eTenders, investigations, monitoring, reports and original-evidence downloads. Your server runs both the website and engine.

## 1. Server setup

Use a Linux server with Docker Engine, Docker Compose v2, Git and Python 3.10+ for setup. Start with 2 GB RAM and disk space for your evidence archive. On your server:

```bash
git clone https://github.com/Xhanti-mbasa/Soter-Secure-System-Tool.git
cd Soter-Secure-System-Tool/sothis
python3 -m web.setup
docker compose up -d --build app
docker compose ps
curl --fail http://127.0.0.1:8780/healthz
```

If Soter is already cloned, update that checkout instead. Setup prompts for a hostname, username and password of at least 12 characters. It saves a salted scrypt hash in private `.env`; it does not store your plaintext password. No default login is shipped. Choose a hosting route below before signing in: production cookies require HTTPS.

The app port binds only to **127.0.0.1:8780**. Data persists in Docker volume `sothis_research-data`. Private configuration, credentials, databases and backups are excluded from Git and the image build. No APK or Android build tools are required.

## 2A. Cloudflare Tunnel (recommended)

Tunnel works behind NAT without a public server IP or inbound ports. Cloudflare provides the public hostname and browser HTTPS.

1. In your Cloudflare account create a **remotely managed Cloudflare Tunnel** using the `cloudflared` connector. Select Docker in its setup instructions and copy only the tunnel token from the displayed command.
2. Save the token privately and start the connector on your server:

   ```bash
   python3 -m web.setup --tunnel-token
   docker compose --profile tunnel up -d app tunnel
   ```

3. Add a public hostname/published application route to the tunnel:

   | Field | Value |
   | --- | --- |
   | Subdomain | `sothis` |
   | Domain | `xhantidaka.online` |
   | Service type | `HTTP` |
   | Service URL | `app:8000` |

   Use `app:8000`, because the connector shares the app's Docker network. `localhost` would mean the connector itself. The browser still uses HTTPS. Omit the subdomain if you configured the main domain instead.

4. Let Cloudflare create the tunnel DNS record for that hostname. Replace only a conflicting record for `sothis` if one already exists; keep your main domain and mail records intact.
5. Open **https://sothis.xhantidaka.online**, sign in and check Settings for `SERVER CONNECTED`.

The token is a mounted secret file, not a command argument. Its host directory is private (mode 700); its file is readable by the non-root connector inside the container. Do not enable tunnel debug logging: it can expose private headers. The connector image follows Cloudflare's `latest` tag; pull/recreate it during updates, or substitute a tested release/digest for pinned infrastructure.

Official instructions: [Tunnel setup](https://developers.cloudflare.com/tunnel/get-started/) and [token-file parameter](https://developers.cloudflare.com/tunnel/reference/run-parameters/#token-file).

## 2B. Public IP and HTTPS reverse proxy

Use this route with a public server IP and available TCP ports 80/443. **If a proxy already owns those ports, use it rather than starting bundled Caddy.**

Create this Cloudflare DNS record with your real server address:

| Type | Name | Target | Proxy |
| --- | --- | --- | --- |
| A | `sothis` | Your server's public IPv4 address | Initially DNS only |

Only add AAAA if the server actually accepts IPv6. Allow TCP 80/443, then run:

```bash
docker compose --profile https up -d app caddy
docker compose logs --tail=30 caddy
```

Caddy obtains an origin certificate and serves HTTPS. After HTTPS works with the DNS-only record, turn on Cloudflare's orange-cloud proxy and select **SSL/TLS → Full (strict)**. Enable HTTP-to-HTTPS redirect. Exclude Sothis from "Cache Everything" rules; its authenticated responses send `Cache-Control: no-store`. Interactive bot challenges on API routes can interrupt research requests.

For an existing Nginx/Caddy/Traefik proxy, run app-only Compose and add a virtual host for your chosen hostname, forwarding to `http://127.0.0.1:8780`. Preserve the original `Host`, terminate HTTPS and forward request bodies. A proxy in another container needs a shared Docker network and `app:8000` instead of host loopback.

References: [Full (strict)](https://developers.cloudflare.com/ssl/origin-configuration/ssl-modes/full-strict/), [Caddy HTTPS](https://caddyserver.com/docs/automatic-https), [reverse proxy](https://caddyserver.com/docs/caddyfile/directives/reverse_proxy).

## Search and source coverage

Optionally set `SOTHIS_BRAVE_API_KEY` in private `.env`, then recreate the app. The browser never receives this key. Without it, the existing public search provider runs on a best-effort basis and reports rate limits or blocking. Results are candidates for review; the site cannot guarantee everything online.

CIPC/BizProfile still requires authorised access. Import disclosures you obtain legitimately; there is no assumed public CIPC API or guaranteed live director-registration feed. eTenders offers notice/award research and bid preparation; submission remains on the specified official platform with its required documents and confirmations. Party coverage and dated office remuneration are described in the main README.

## Persistence and alerts

Indexed documents, original archives, investigations/notes/pins, monitoring rules and alerts live on the server volume. Enabled rules continue while the app is running, even with the browser closed. The first successful check establishes a baseline. This release delivers changes to its in-app inbox, not closed-browser push, email or SMS.

Account selections, candidate verification notes, company draft profiles, bid drafts and the list of originals downloaded in a browser use browser storage. Export these before signing out or switching browsers; sign-out clears these caches. Saved server investigations survive sign-out. Geographic photos/fonts are local; representative portraits may load from Parliament.

## Backup and restore

Create a private backup and copy it to another protected location:

```bash
umask 077
mkdir -p backups
docker compose exec -T app python -m web.backup > backups/sothis-backup.zip
python3 -m zipfile -t backups/sothis-backup.zip
```

The backup uses SQLite's online backup API and includes downloaded originals and the session database. It excludes `.env`, tunnel credentials and browser-only drafts. Protect your configuration separately. Pause collection for a fully quiescent archive; live collection can add originals during backup. Back up before updates and regularly. The command does not schedule backups.

For a restore, **stop the app**, preserve the existing backup, and use a backup generated by this app that remains in your control:

```bash
docker compose stop app
docker compose run --rm --no-deps -T -v "$PWD/backups:/restore:ro" app python -c 'import shutil, zipfile; from pathlib import Path; root=Path("/var/lib/sothis"); [p.unlink() for p in root.glob("*.sqlite3*")]; shutil.rmtree(root/"archive",ignore_errors=True); zipfile.ZipFile("/restore/sothis-backup.zip").extractall(root)'
docker compose up -d app
```

Restore replaces the current research database/archive. Do not use `docker compose down -v`, which deletes volumes. Changing the Compose project name does not automatically migrate an existing volume.

## Maintenance

After backing up, run `git pull --ff-only`, then update the profile you selected:

```bash
docker compose --profile tunnel pull tunnel
docker compose --profile tunnel up -d --build app tunnel
```

For Caddy use `--profile https` and `app caddy`; for an existing proxy use `docker compose up -d --build app`. The app pins the Gunicorn version tested in this release. Review dependency/image updates during maintenance.

Password reset: `python3 -m web.setup --reset-password`, followed by `docker compose up -d --force-recreate app`. Existing browser sessions are revoked when the new password configuration starts.

- `docker compose ps` and `docker compose logs --tail=50 app` show startup health. Normal research queries/bodies are not logged.
- Hostname errors: match `SOTHIS_PUBLIC_ORIGIN` to your browser's hostname and preserve `Host` through the proxy.
- Repeated failed login: wait 10 minutes. Connections through a proxy share a conservative limit; user-supplied IP headers are ignored.
- Tunnel 502: verify app health and service address `http://app:8000`.
- Direct-route 526: verify the origin certificate and Full (strict).

Use **one Gunicorn worker with eight threads**. Its process owns the monitoring scheduler and collection job. Do not enable `--preload`, add workers or scale replicas without moving scheduling/job ownership into separate services. Login uses HttpOnly Secure cookies, server-side revocation and origin/CSRF checks. Keep the host patched and backups private.

## Development and verification

Install `requirements-web.txt` into a virtual environment. Load login configuration through your IDE/service manager; for local HTTP set `SOTHIS_DEV=1`, `SOTHIS_PUBLIC_ORIGIN=http://127.0.0.1:8000` and `SOTHIS_DATA=./data`. Run `gunicorn --config deploy/gunicorn.conf.py 'web.app:create_app()'`. HTTP development mode is restricted to loopback and must not be used on the public server.

Python checks: `python3 -m unittest discover -s tests -q`. Browser checks: `python3 scripts/check_web.py --chrome /path/to/chrome --playwright /path/to/playwright`. These exercise real login, sessions, source search, cases, alerts, download, logout and responsive layout. See `docs/WEB_VALIDATION.md` for the release's actual results and deployment limits.
