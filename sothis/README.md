# Sothis

**Self-hosted website:** the same interface now runs as a private website with browser login, a persistent engine and original-evidence downloads. The default address is `sothis.xhantidaka.online`. See [server and Cloudflare deployment](deploy/README.md) for Docker, Tunnel or HTTPS reverse-proxy setup. The website and Android use the same research interface.

South African public-records research: an Android client and an independent document-collection/search engine. The Android app uses a bundled local interface, with a native bridge for engine connections, browser handoff, sharing, and file export.

Version **0.8.0** refines the established charcoal/blue interface with compact headings, bundled regular-weight vectors, contextual controls, grouped Profile and Settings, and keyboard-safe dialogs. Home owns a direct public-records search, Regions retains its layout switch, and Jobs remembers its filters. Provider and export reliability fixes are documented in [refinement validation](docs/REFINEMENT_VALIDATION.md).

Version **0.7.2** corrects the shared navigation dock, removes redundant Back and Search controls, hides the dock while typing, and restores employment metrics in exported share cards. Home, Regions, Jobs and Profile use fixed-size icons with only the active tab labelled. Native Android Back and browser history retain the research routes.

Version **0.7.1** is the optimized release of the everyday workflows added in **0.7.0**. It includes bounded provider caches with shared in-flight requests, metadata-only offline-library listings, smaller local PDF assets and improved share rendering. Both APKs remain in `releases/`. See [optimization measurements](docs/OPTIMIZATION.md).

Version **0.7.0** adds Home, Opportunities and a local Profile around the existing research tools. Long-press public cards to share PNGs with frosted/liquid glass, solid colours, a local photo, opacity and blur controls. News has dates, local likes/bookmarks and offline downloads; CV imports and municipal report drafts remain local. Tool workspaces run without redirecting to Search.

Version **0.6.0** added a province map and dashboards for news, population, education, employment, activities and public data banks. Salaries remain visible; company declaration details and sourced links to authorised company records sit alongside the member charts. It retains the Nothing-inspired interface with a charcoal palette, Doto dot-matrix headings, blue accents, rounded cards and a floating four-tab dock with a separate search button. Settings is available from the header. Landscape photos and their metadata are loaded locally through the native asset bridge for National and all nine provinces, and representatives use sourced Parliament portraits with initials when the image is unavailable. The native launch fix from 0.3.1 remains in place.

Live search, sourced Party dossiers, alerts, local evidence saving, investigations and tender preparation keep their existing behavior. Android performs public discovery and eTenders queries directly without a hosted engine; an engine provides government collection, shared evidence and server monitoring.

## Install and use

Install the APK attached to [Sothis 0.8.0](https://github.com/Xhanti-mbasa/Soter-Secure-System-Tool/releases/tag/sothis-v0.8.0) on Android 8.0+. [Sothis 0.7.0](https://github.com/Xhanti-mbasa/Soter-Secure-System-Tool/releases/tag/sothis-v0.7.0) is retained as the feature baseline. It uses the same package and development signing key as previous Sothis releases, so it can update that installation while retaining app data. The signing key is excluded from Git. Every new Android version must have an attached APK GitHub Release; see [RELEASING.md](docs/RELEASING.md).

- **Search:** choose Live public web, Social profiles, Live government web, Companies / CIPC, or Saved government collection. Live results show retrieved unique hits, profile candidates, name-match ranking, provider availability, retrieval dates and a platform footprint. Account ownership requires a saved researcher decision. Posts, share links and TikTok discovery pages are not counted as accounts.
- **Party:** search ANC, DA, EFF or another listed party from Search or the Party tab. Browse the captured Parliament roster, filter representatives by name, refresh the official directory, and open member dossiers. Profiles retrieve current public member pages and group live mentions into government, news, remuneration, education, business and social categories. Pin/export a sourced dossier or create a mention alert.
- **Company lookup:** slash, hyphen, spaced and compact enterprise numbers are normalised. Public web and eTenders supplier-index results appear when available. CIPC access is explicitly shown as requiring login. Add an authorised company disclosure, keep business activities/status with provenance, search imported records, and use the company name for supplier award searches.
- **Regions:** select a province from the geographic map or photo cards, or search its name in Live public web. Explore Overview, News, Education, Employment, Activities and Data banks. Switch the map between population, employment absorption and matric results. News has 7/30/90-day publication windows and original-source evidence actions. Export a dated province brief or create an alert.
- **Tools:** public discovery, company lookup, eTenders and the national/provincial source directory. Select up to ten public collectors for jobs, tenders, e-services or departmental sites. Engine progress shows the source, URL, request count and indexed passages.
- **Alerts:** choose web, social profiles, government web, imported CIPC disclosures or open tender notices; select new-hit or changed-text conditions, an optional required phrase and interval. Check now, pause/resume and view the inbox. First successful checks establish baselines. Enable Android notifications from Tools.
- **Investigations:** pin evidence, keep notes and export a structured Markdown/HTML brief. Download a selected original public page or PDF into the phone archive with SHA-256 and retrieval time. Export an evidence ZIP containing the brief, manifest, researcher decisions and downloaded originals. A browser exports a JSON manifest instead of a native ZIP.
- **Tender workspace:** live open/awarded/closed/cancelled notices, keyword/company/CSD/tender-number filters, award recipients and amounts, notice data, supporting document downloads and eSubmission availability. Select open notices to create multiple bid preparation packs with company/CSD details, tender-specific checklists, notes and researcher-recorded receipts. Export the preparation queue and hand off each submission to the prescribed channel.

Public search uses best-effort Brave web results with a DuckDuckGo public fallback on request failure. Providers may block or rate-limit requests and do not index every account. Settings accepts an optional **Brave Search API key**, stored privately on the phone; engine deployments use `SOTHIS_BRAVE_API_KEY`. No key is bundled. API usage/storage remains subject to the provider's account terms. Browser search links are actions, never invented account hits.

The app uses internet access, the normal network-state permission, optional notification permission and a persisted Android job. Background scheduling starts after the local screen loads; an unavailable scheduler leaves the foreground app usable and reports the problem in Tools. It requests no contacts or broad storage access. Province location lookup requests Android location access only when chosen; users can select a province manually. Photo, video and audio capture hand off to the device’s capture apps. Report/ZIP exports use the Android file picker. Background checks depend on network and Android scheduling, may be delayed by battery controls, and stop if the app is force-stopped until it is opened again.

## Included engine foundations

National government plus all nine provinces, HTML/text-bearing PDF ingestion, per-source allowlists/path scopes, robots.txt checks, bounded crawling, SQLite FTS5 search, date/source/category/province filters, PDF page references, version history, raw archives, hashes and traceable report exports. Device and engine investigations/monitoring rules remain separate. There is no automatic migration when connecting or disconnecting.

## Interface and photography

The dock contains Home, Regions, Jobs and Profile. Its separate circle opens Search on screens without an inline search; the header gear opens Settings. People & parties, Tools and Investigations are available from Explore. Photos on region cards identify the pictured place, rather than claiming the source or every document originated there. Home includes public-records search. Search photo cards open Regions and Party. A representative dossier places the portrait, name and sourced details first; native Android Back or browser Back returns to the roster.

The APK includes nine compressed landscape photographs (Pretoria is used for both National and Gauteng), the Doto font and Phosphor icons. Landscape credits, original file pages, licenses and modifications are available in Settings and `android/app/src/main/assets/photo-credits.json`. Images retain their listed Creative Commons licenses. Doto is under the SIL Open Font License; Phosphor icons are under MIT, with license files bundled. Representative portraits are loaded from the official Parliament directory over HTTPS and are optional network assets; missing photos show initials. Portraits do not verify the ownership of a social account.

Rendered screens: [Search](docs/screenshots/home.png), [Regions](docs/screenshots/regions.png), [Representative dossier](docs/screenshots/profile.png), [Tools](docs/screenshots/tools.png). The visual verification checks all six main screens at 320, 360, 390, 412, 720 and 1200 CSS pixels, local asset MIME types, static file boundaries, fonts, photographs, 44-pixel dock targets and JavaScript errors.

## Province evidence and public data banks

Province dashboards keep source periods separate: **Census 2022** provincial population; **QLFS Q2 2026** employment absorption, participation, unemployment and approximate employed counts; **DBE NSC class of 2025** pass rates, candidates who wrote and candidates who achieved. Population is a historic census count, with a link to newer mid-year estimates. Employment absorption is employed people divided by the population aged 15–64; it is not 100 minus unemployment.

Education includes a reviewed directory of **26 public universities and 50 public TVET colleges**, grouped by primary province, and searchable page extracts of the **12 August 2026 private higher-education register** and **16 September 2026 private-college register**. Search by province/locality or use the national register for shared campuses. PDF page counts are not institution counts. Entries from cancelled-registration sections remain included and labelled for review; consult the original section, programme, site and registration conditions. Occupational training accreditation is also linked separately. IEB 2025 NSC is shown as a national measure; missing provincial series for other assessment bodies, primary grades, TVET, CET/AET and higher education stay explicitly unavailable.

News retrieves the current [SAnews South Africa RSS feed](https://www.sanews.gov.za/south-africa-news-stories.xml). The feed contains a limited set of recent publisher items, filtered by province/locality mentions and explicit publication dates; future, old and undated items stay outside the dated count. An empty province feed widens to public-web news candidates, which require their own date verification. Cached feed results retain article retrieval dates. Provider failures remain visible. Android has its own native RSS adapter; the website uses its authenticated server gateway. News metadata can be pinned to a case and the original saved through existing evidence tools.

Data banks link to public statistics, banks/co-operative banks, financial providers, CIPC, listed companies, nonprofits, budgets/public entities, municipal finance, tenders, health, crime aggregates, conservation, tourism and qualifications. These are source directories, not copies of every database or automatic findings about an individual. Activities provide public-notice searches and original tourism/conservation/economic sources. [Province validation and updates](docs/PROVINCE_VALIDATION.md) explains coverage and reproduction. Rendered views: [province map](docs/screenshots/province-map.png) and [province dashboard on mobile](docs/screenshots/province-mobile.png).

Member profiles retain published office remuneration and the dated declaration’s company/interest text. Import an authorised company disclosure, then explicitly link its registration number to a person with a relationship, evidence URL and identity-review note. Company activities, supplied status and disclosure provenance are visible on the profile and in its report. These researcher associations are saved on the current device/browser; they are not inferred from names or presented as automated ownership findings.

## Party analytics

The landing dashboard shows a 400-seat National Assembly tile chart and an interactive South Africa province map. Party pages compare 2019 and 2024 seat allocations, show their share of the Assembly and provincial-ballot percentages. All charts link to Parliament or IEC evidence and show dates. A province’s largest vote share does not identify the governing coalition. Ramaphosa appears separately under ANC leadership; the President is not added to the MP roster or seat total.

Member declarations have a four-section status chart and nominal-ZAR bars when the shares section contains explicit amounts. These charts summarise dated self-disclosures, not CIPC ownership checks. Original text remains expandable. Mentions show local platform/source icons, publication and retrieval dates separately. News view checks up to four source pages for explicit publication metadata; other mentions have a Check article date action. Missing or conflicting dates remain unavailable. A provider page date may be a modified date.

The national outlook has no invented win percentage. Reviewed national voting-intention polls can be installed with sample, population, dates and methodology; the UI retires expired polls or polls for an older completed election. Voting intention is not winning probability. See [analytics validation and updates](docs/ANALYTICS_VALIDATION.md). Browser Back and Android’s native back action share screen history.

## Party sources and coverage

The bundled directory captures **18 parties and 449 Parliament-listed representatives** on 9 October 2026. It covers the published National Assembly/NCOP directory, not every party member nationwide or all provincial/local officeholders. Counts describe the captured directory and are not election seat totals. The primary roster is https://www.parliament.gov.za/members-of-parliament ; its embedded public member JSON gives explicit party codes. Some individual party pages are absent or stale, so they are not used to invent missing members. Refresh validates total count, unique IDs and known party codes before replacing the selected roster. Errors keep the prior capture and display the failure.

The June 2026 public members’ interests register supplies **353 matched business-interest extracts** in this capture. Matching requires an explicit party and the same name tokens, allowing the register’s surname-first ordering. Unmatched members link to the public register for manual review. Extracts retain PDF page ranges, capture date and text hash and include shares, outside remunerated work, directorships/partnerships and consultancies. Residential property/contact details are not included in these extracts. This is a dated self-declaration, not a CIPC certificate or proof of every current company relationship. Original registers: https://www.parliament.gov.za/register-members-Interests .

Gwede Mantashe’s example profile contains public education statements and historical business roles paraphrased from his government biography, with source links. Other members load their public roles from Parliament on opening; the Public education category searches for additional published biographies/qualifications. Private schooling records are not provided. Historical roles stay separate from dated declarations and unverified web mentions.

Executive remuneration uses an explicitly dated gazetted office schedule (published 16 January 2026, effective 1 April 2025), matched only to an explicit Minister, Deputy Minister or Deputy President title. These are annual office remuneration figures, not personal payslips or a claim about subsequent rates. No ordinary MP salary is guessed from a roster entry; unmatched offices link to the official determinations. Gazette: https://www.gov.za/sites/default/files/gcis_document/202601/53965gon7004.pdf . Live Salary records searches can find later material for review.

Phone rosters/member summaries and dossier evidence persist locally. The engine keeps refreshed party data for its running session; restart returns to the bundled capture. Web grouping is a text-based suggestion, not verified identity or affiliation. Party alerts monitor public mentions through the existing selected services; they are not a comprehensive party membership-change feed. Dossiers export source links, capture dates, salary period, declaration page locators and retrieved mentions. Evidence bundles include downloaded originals referenced by the selected dossier.

To update the next APK’s capture, run `python3 scripts/update_party_snapshot.py`. To rebuild business-interest extracts as well, provide `--interests-pdf /path/to/official-register.pdf`; verify the register URL/period constants before using a newer publication. The script validates public roster data and does not import private records.

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

Everyday features and source limits are documented in [DAILY_VALIDATION.md](docs/DAILY_VALIDATION.md). The website uses the same interface and provider services; deploy the updated repository using the existing server guide.

Dock and native-navigation corrections in 0.7.2 are documented in [DOCK_VALIDATION.md](docs/DOCK_VALIDATION.md).
