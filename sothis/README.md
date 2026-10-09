# Sothis

South African public-records research: an Android client and an independent document-collection/search engine. The Android app uses a bundled local interface, with a native bridge for engine connections, browser handoff, sharing, and file export.

The first version opens without a server using a real, dated snapshot. Live collection runs on a computer/server, not inside the phone. All results refer to indexed evidence; the app does not claim exhaustive coverage or automatically establish a person's identity or business relationships.

## Included

- National government plus all nine provinces, with departmental source entries discovered from official government directories. Municipal sources start with Cape Town.
- Configurable source connectors, host allowlists, optional path scopes, robots.txt checks, request delays, bounded crawl jobs, and explicit source availability.
- HTML and text-bearing PDF ingestion, page-level PDF search, publication/retrieval dates, original links, SHA-256 hashes, raw content archives, and extracted-text version history.
- SQLite FTS search, source/category/province/date filters, optional national inclusion, and reviewed spelling suggestions.
- Device-local and engine investigations, evidence pins, researcher notes, and Markdown/HTML brief export. Device and server investigations are deliberately separate; there is no automatic migration between them.
- CIPC browser handoff and authorised text import, with imported records labelled for authenticity review.

## Install the Android app

Install `releases/sothis-0.1.0.apk` on Android 8.0 or later. This is a development-signed build. The app requests internet access; no contacts, location, camera, or storage-wide permissions are required. Saving a report uses Android's file picker.

Search **Geordin Hill-Lewis**, **Cyril Ramaphosa**, or **Western Cape** to explore the snapshot. Jordan Hill Lewis produces a suggested spelling rather than an automatic identity merge. Open a record to inspect dates, URL, hash and PDF page. Create an investigation, then pin records and export its brief.

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

From Sources in the app, select up to ten enabled public sources, then collect. Collection is bounded to five page requests per selected source through the interface. Status shows unavailable, login-required, or not-indexed entries; successful indexing does not imply a complete website archive.

CLI examples:

```bash
python3 -m engine crawl --province "Western Cape" --pages 5 --depth 1
python3 -m engine search "Geordin Hill-Lewis" --province "Western Cape"
python3 -m engine search "Ramaphosa" --category remuneration
python3 -m engine snapshot
```

`snapshot` refreshes the asset for the next APK build, not already-installed apps. Live searches cache excerpts on the device; the bundled snapshot remains a dated collection. Source directory updates require review:

```bash
python3 -m engine discover --url https://www.gov.za/links/provincial-government
```

Review `directory-candidates.json`, add approved entries to `sources.json`, and rerun `init`. The official directory contains historical links and occasional jurisdiction errors. Directory membership is a discovery signal, not proof that an endpoint works. Each source has its own configuration and status; province is a grouping dimension, not a fictional shared API. Sources sharing a portal can share the same HTTP adapter.

Network environments with a trusted outbound HTTPS proxy that resolves public DNS remotely may explicitly set `ZALENS_TRUST_PROXY_DNS=1`. This delegates DNS checking to that controlled proxy for exact allowlisted hosts. Leave it unset on ordinary hosts. Private/literal/local destinations remain rejected, and redirects are checked against the connector allowlist.

## CIPC / record import

CIPC's search notice redirects enterprise search to BizProfile/BizPortal and requires login: https://eservices.cipc.co.za/Search.aspx . This version does not invent a free API, bypass login, or make automated purchases. Use Sources → CIPC → Open website, perform an authorised lookup, then import record text using Settings. Retain the original disclosure securely; an imported URL/text entry is not automatically authenticated by CIPC.

For bulk manual text import, create JSON records containing `source_id`, `url`, `title`, `text`, and optional `published_at` (`YYYY-MM-DD`) / `page`, then run:

```bash
python3 -m engine import records.json
```

## Scope and next engineering work

The starter snapshot contains 36 searchable passages from 23 URLs. The registry contains 203 source entries, including multiple departments on shared portals; it is not 203 verified integrations. Ten seed connectors were exercised; additional entries still need availability and content review. Current source entries include sites awaiting manual approval for collection.

No general social-media account enumerator, commercial search API, identity resolution engine, relationship graph, OCR pipeline, continuous background scheduler, or LLM narrative generator is included. Social links extracted from a page are publisher links and remain person-ownership candidates. The exported brief is an evidence template with researcher notes, not an automatically verified biography or video essay. National remuneration notices may publish upper limits or pay scales; they do not establish an individual's actual salary. Date filters exclude documents with unknown publication dates.

Recommended next implementation order: document-specific parsers and OCR; broader municipal/gazette coverage; human-reviewed entities and relationships; licensed news/social search connectors; background collection workers; cited narrative drafting from selected verified claims. At scale, move collection to durable queues/object storage and search to a production index, while preserving document IDs, evidence hashes, page references and provenance.

## Build and verify

Import `android/` into Android Studio with JDK 17, Android SDK 35, and Gradle 8.9. The Gradle Android plugin is pinned to 8.7.3. There are no third-party Android libraries. Build the development variant with Gradle, or use the supplied SDK/ECJ build script:

```bash
gradle -p android :app:assembleDebug
python3 -m unittest discover -s tests -v
```

`scripts/build_apk.py` accepts paths to Android SDK build tools 35, `android.jar`, and the Eclipse Java compiler jar. It invokes aapt2, Java compilation, D8, zipalign, and apksigner. A private development signing key is generated only if the supplied path does not exist; keep that key for subsequent compatible updates and use a protected release key for production.

See `VALIDATION.md` for the checks completed for this version. Project code uses the repository's MIT license. Public source records retain their publishers' rights and source terms; they are not relicensed by this project's code license.
