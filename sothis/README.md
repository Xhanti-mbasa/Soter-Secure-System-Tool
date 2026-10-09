# Sothis

South African public-records research: an Android client and an independent document-collection/search engine. The Android app uses a bundled local interface, with a native bridge for engine connections, browser handoff, sharing, and file export.

Version **0.2.0** fixes the snapshot-only search limitation. A name or registration-number search defaults to live public discovery. Android performs public discovery and eTenders queries directly without a hosted engine; an engine still provides government collection, shared evidence and server monitoring.

## Install and use

Install `releases/sothis-0.2.0.apk` on Android 8.0+. It uses the same package and development signing key as 0.1.0, so it can update that installation while retaining app data. The signing key is excluded from Git.

- **Search:** choose Live public web, Social profiles, Live government web, Companies / CIPC, or Saved government collection. Live results show retrieved unique hits, profile candidates, name-match ranking, provider availability, retrieval dates and a platform footprint. Account ownership requires a saved researcher decision. Posts, share links and TikTok discovery pages are not counted as accounts.
- **Company lookup:** slash, hyphen, spaced and compact enterprise numbers are normalised. Public web and eTenders supplier-index results appear when available. CIPC access is explicitly shown as requiring login. Add an authorised company disclosure, keep business activities/status with provenance, search imported records, and use the company name for supplier award searches.
- **Tools:** public discovery, company lookup, eTenders and the national/provincial source directory. Select up to ten public collectors for jobs, tenders, e-services or departmental sites. Engine progress shows the source, URL, request count and indexed passages.
- **Alerts:** choose web, social profiles, government web, imported CIPC disclosures or open tender notices; select new-hit or changed-text conditions, an optional required phrase and interval. Check now, pause/resume and view the inbox. First successful checks establish baselines. Enable Android notifications from Tools.
- **Investigations:** pin evidence, keep notes and export a structured Markdown/HTML brief. Download a selected original public page or PDF into the phone archive with SHA-256 and retrieval time. Export an evidence ZIP containing the brief, manifest, researcher decisions and downloaded originals. A browser exports a JSON manifest instead of a native ZIP.
- **Tender workspace:** live open/awarded/closed/cancelled notices, keyword/company/CSD/tender-number filters, award recipients and amounts, notice data, supporting document downloads and eSubmission availability. Select open notices to create multiple bid preparation packs with company/CSD details, tender-specific checklists, notes and researcher-recorded receipts. Export the preparation queue and hand off each submission to the prescribed channel.

Public search uses best-effort Brave web results with a DuckDuckGo public fallback on request failure. Providers may block or rate-limit requests and do not index every account. Settings accepts an optional **Brave Search API key**, stored privately on the phone; engine deployments use `SOTHIS_BRAVE_API_KEY`. No key is bundled. API usage/storage remains subject to the provider's account terms. Browser search links are actions, never invented account hits.

The app uses internet access, optional notification permission and a persisted Android job. It requests no contacts, location, camera or broad storage access. Report/ZIP exports use the Android file picker. Background checks depend on network and Android scheduling, may be delayed by battery controls, and stop if the app is force-stopped until it is opened again.

## Included engine foundations

National government plus all nine provinces, HTML/text-bearing PDF ingestion, per-source allowlists/path scopes, robots.txt checks, bounded crawling, SQLite FTS5 search, date/source/category/province filters, PDF page references, version history, raw archives, hashes and traceable report exports. Device and engine investigations/monitoring rules remain separate. There is no automatic migration when connecting or disconnecting.

## Start the engine

Requires Python 3.10+ with SQLite FTS5. PDF ingestion uses pypdf; the remainder uses Python's standard library.

```bash
cd sothis
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -r requirements.txt
python3 -m engine init
python3 -m engine serve
```

Open `http://127.0.0.1:8765` to use the same interface on a computer. `init` registers sources and, for a new empty database, imports the bundled snapshot while preserving its original capture times. It does not overwrite an existing index.

For a phone on the same network, generate an access token in a separate terminal and keep the terminal/session protected:

```bash
export ZALENS_API_TOKEN="$(python3 -c 'import secrets; print(secrets.token_urlsafe(32))')"
python3 -m engine serve --host 0.0.0.0 --port 8765
```

Put your computer's private LAN address, such as `http://192.168.1.20:8765`, and that token into the Android app's Settings. Retrieve the token from your local shell/configuration without publishing it in logs or Git. Remote access requires an HTTPS reverse proxy and that same token. The built-in HTTP server is a small, single-user development service, not a hardened public production deployment.

Engine credentials are held in the Android app's private preferences. Browser use stores its configuration in that browser's local storage. App backup is disabled. There is no telemetry or external model call.

## Collect and search

From Tools in the app, select up to ten enabled public sources, then collect. Collection is bounded to five page requests per selected source through the interface. Status shows unavailable, login-required, or not-indexed entries; successful indexing does not imply a complete website archive.

CLI examples:

```bash
python3 -m engine crawl --province "Western Cape" --pages 5 --depth 1
python3 -m engine search "Geordin Hill-Lewis" --province "Western Cape"
python3 -m engine search "Ramaphosa" --category remuneration
python3 -m engine snapshot
```

`snapshot` refreshes the asset for the next APK build, not already-installed apps. Indexed searches cache excerpts on the device; the bundled snapshot remains a dated collection. Source directory updates require review:

```bash
python3 -m engine discover --url https://www.gov.za/links/provincial-government
```

Review `directory-candidates.json`, add approved entries to `sources.json`, and rerun `init`. The official directory contains historical links and occasional jurisdiction errors. Directory membership is a discovery signal, not proof that an endpoint works. Each source has its own configuration and status; province is a grouping dimension, not a fictional shared API. Sources sharing a portal can share the same HTTP adapter.

Network environments with a trusted outbound HTTPS proxy that resolves public DNS remotely may explicitly set `ZALENS_TRUST_PROXY_DNS=1`. This delegates DNS checking to that controlled proxy for exact allowlisted hosts. Leave it unset on ordinary hosts. Private/literal/local destinations remain rejected, and redirects are checked against the connector allowlist.

## CIPC / record import

CIPC's official search notice redirects enterprise lookup to BizProfile/BizPortal and requires login: https://eservices.cipc.co.za/Search.aspx . No authenticated CIPC connector or licensed registry feed is configured in this version. A public-web miss does not mean an enterprise is unregistered. CIPC alerts watch **imported disclosures in the engine**, not the live national register, and a name mention does not establish directorship. Use the official portal for an authorised lookup, then add the disclosure in Companies / CIPC or import its text through Settings. Researcher-supplied authenticity, activities and status remain labelled for review. Local import anchors identify separate disclosures from a shared portal URL; they are Sothis identifiers, not official CIPC record identifiers.

For bulk manual text import, create JSON records containing `source_id`, `url`, `title`, `text`, and optional `published_at` (`YYYY-MM-DD`) / `page`, then run:

```bash
python3 -m engine import records.json
```

## Scope and next engineering work

The starter snapshot contains 36 searchable passages from 23 URLs. The registry contains 203 source entries, including multiple departments on shared portals; it is not 203 verified integrations. Ten seed connectors were exercised; additional entries still need availability and content review. Current source entries include sites awaiting manual approval for collection.

Discovery retrieves indexed public candidates rather than enumerating all private/platform accounts. Ranking measures name-text relevance, not identity probability. The footprint shows retrieved candidates per platform rather than a complete map of a person's online existence. Remuneration scales remain scales unless separate evidence establishes actual personal pay; unknown publication dates are excluded by collection date filters. Live web discovery has no reliable publication-date filter and remains separate from the collection's date/source filters.

Monitoring runs while the engine is running, or through Android JobScheduler for device rules. Errors preserve a service's previous baseline. New results are deduplicated and first-run results do not flood the inbox. CIPC registry events require a future authorised feed. Government document collection still runs on the server; phone-only monitoring does not crawl the entire government directory.

The official eTenders public endpoints were verified from its own page/scripts. Supplier awards use the portal's `TenderFilter` company/CSD fields, not an unrelated keyword-only query. A registration number may need a verified company name or CSD number before award matching. Not every notice supports eSubmission. **Bulk bid preparation is implemented; automatic bulk submission is not.** Requirements, eligibility, pricing, attachments, login and final submission must be reviewed for each tender. A local receipt/status is researcher recorded; the app does not claim that a bid was submitted without official acknowledgement. Original source links remain intact under the portal's publication policy: https://data.etenders.gov.za/Home/LearnMore .

OCR, comprehensive municipal/source coverage, entity verification, relationship graphs and cited AI narrative drafting remain future work. The brief is structured evidence plus researcher notes, not an automatically verified biography. At scale, move collection/monitoring to durable queues and search to a production index while preserving provenance and hashes.

## Build and verify

Import `android/` into Android Studio with JDK 17, Android SDK 35, and Gradle 8.9. The Gradle Android plugin is pinned to 8.7.3. There are no third-party Android libraries. Build the development variant with Gradle, or use the supplied SDK/ECJ build script:

```bash
gradle -p android :app:assembleDebug
python3 -m unittest discover -s tests -v
```

`scripts/build_apk.py` accepts paths to Android SDK build tools 35, `android.jar`, and the Eclipse Java compiler jar. It invokes aapt2, Java compilation, D8, zipalign, and apksigner. A private development signing key is generated only if the supplied path does not exist; keep that key for subsequent compatible updates and use a protected release key for production.

See `VALIDATION.md` for the checks completed for this version. Project code uses the repository's MIT license. Public source records retain their publishers' rights and source terms; they are not relicensed by this project's code license.
