# Province evidence and validation · 0.6.0

The Regions map opens a province dashboard rather than an empty indexed search. Its six sections are Overview, News, Education, Employment, Activities and Data banks. Visible Back, browser history and Android’s existing native-back handler preserve the selected province. The existing indexed-source search remains a separate action. Salaries and company declaration details remain readable in people’s profiles.

## Reviewed evidence

| Dataset | Reporting period | Original evidence |
| --- | --- | --- |
| Provincial population | Census 2022, released 10 October 2023 | [Stats SA table 2.1, PDF p. 15](https://census.statssa.gov.za/assets/documents/2022/P03014_Census_2022_Statistical_Release.pdf#page=15) |
| Labour measures | Q2 2026, released 11 August 2026 | [Stats SA QLFS table 2.3, PDF pp. 34–45](https://www.statssa.gov.za/publications/P0211/P02112ndQuarter2026.pdf) |
| DBE NSC outcomes | Class of 2025, announced 12 January 2026 | [DBE report, PDF p. 6](https://www.education.gov.za/Portals/0/Documents/Reports/2025%20NSC%20Examination%20Report.pdf#page=6) |
| Independent assessment | IEB 2025 NSC, national 98.31% | [IEB announcement](https://www.ieb.co.za/post/2025-ieb-national-senior-certificate-results) |
| Public universities | 26 institutions, primary province | [Universities South Africa directory](https://usaf.ac.za/prospective-students/) |
| Public TVET colleges | 50 institutions, reviewed directory | [DHET Careerhelp directory](https://www.careerhelp.org.za/content/education-system-south-africa/tvet-and-university) |
| Private higher education | Register updated 12 August 2026, 212 PDF pages | [DHET register](https://www.dhet.gov.za/Registers_DocLib/Register%20Phei%20%2012%20August.pdf) |
| Private colleges | Register updated 16 September 2026, 99 PDF pages | [DHET register](https://www.dhet.gov.za/Registers_DocLib/Register%20of%20Private%20Colleges%20%2016%20September%202026.pdf) |
| Current public news | Live retrieval, source publication dates | [SAnews current South Africa feed](https://www.sanews.gov.za/south-africa-news-stories.xml) |

Population is not presented as a 2026 headcount. A newer Stats SA mid-year-estimate publication is linked separately; its provincial table has not been imported. Labour counts are rounded in the source and the UI labels derived counts approximate. Absorption and participation use the working-age population, while unemployment uses the labour force. NSC outcomes use the DBE’s candidates who wrote, not every learner who started school.

Private-provider results are **PDF page matches**, including explanatory notes and cancellation sections. They do not assign a registration status to each text match. The UI keeps programme/qualification text, original-page links, PDF hashes, page-text hashes and capture dates. Personal telephone/email contact lines are omitted from displayed extracts. Province filtering uses explicit province/locality terms in a page; shared sites and differently named localities can be missed. National-register search remains available. The source’s section, conditions, programme and delivery site must be read before stating that an institution is registered. Occupational providers can have a different accreditation/registration route.

Earlier school grades, SACAI, TVET programme certification, CET/AET and higher-education course/cohort outcomes have source links and explicit missing-provincial-series states. No universal all-sector pass rate is invented. Directories for banks, financial entities, companies, nonprofits, budgets, public entities, municipalities, procurement, health, crime, tourism, conservation and qualifications identify their publisher and access limitations.

## News and evidence

The publisher’s HTML advertises a legacy `rss-old.xml` endpoint whose newest returned article was from February 2025. It is excluded. The current footer-linked feed was retrieved and parsed on 10 October 2026: 10 items, latest publication `2026-10-10T13:57:47Z`, with matching Eastern Cape and Gauteng items. This verifies the publisher response, not every province’s coverage or continuing uptime.

The engine uses an approved-host, bounded Fetcher for the feed. The build environment’s guarded direct-DNS path could not resolve the publisher; the publisher response was independently retrieved through the environment’s available HTTP transport. Android and the deployed server need working public DNS. Errors are surfaced and empty feeds widen to ordinary public-index candidates. API and UI behavior are tested with controlled fixtures rather than assuming provider availability.

Python and native Android adapters accept only known province names and supported windows. They bound response size, reject XML entity/DOCTYPE input, retain publisher URLs and publication/retrieval dates, deduplicate URLs and exclude future/old/undated items from the dated count. Location mentions identify relevance, not jurisdiction. Index candidates remain separate, with the existing explicit publication-metadata checker. Feed/article metadata can be pinned; downloading an original uses the existing archive and hash path.

Member charts remain alongside readable declaration sections. Company linking requires an imported record, an explicit relationship, HTTPS evidence URL and identity-review note. Associations are researcher supplied, removable, retained on the device/browser and included in member reports. They are not automated registry ownership claims.

## Verification

Validated on 10 October 2026: **63 Python tests**, all **six shared UI suites**, and the authenticated website flow passed. APK SHA-256: `44ca0717fa09f72a24352ff0cb950e10b07539b06ad54db840d1ed0acc225bd9`. All 48 packaged assets match the source files. The signer certificate SHA-256 remains `b981c1a75e2b49360ec80241354760b20c50e1533edbed1b8e1d2febb09f04e3`.

- Python checks cover nine sourced provincial records, employment denominators, NSC numerators, education inventories/register dates, feed host restrictions, dates/windows, URL deduplication, hashes, XML rejection, cache behavior, fallback and the authenticated website gateway.
- Province browser checks cover map measures, exact province search, both map/card selection, dashboard sections, news windows/evidence, public/private institution filtering, national register search, source directories, exports, visible/history/native Back and four widths: 320, 390, 720 and 1280 px.
- Company import, source association/removal, salary retention and member report content are exercised through the UI. The native file-origin fixture provides the actual asset bridges and confirms the `/api/device/province/news` route.
- Existing search, Party analytics, evidence/cases, alerts, tender preparation, assets and layouts remain covered. The website test uses real sessions/CSRF, the WSGI gateway and a controlled publisher reader; news documents persist in the actual engine store.
- Android is compiled against SDK 35 with minimum 26 and versionCode 7, preserving the signing key and launch-scheduling fix. Signature and packaged-asset equality are checked. No physical-device or emulator installation is claimed.

Reproduce:

```bash
python3 -m unittest discover -s tests -q
python3 scripts/check_ui.py --chrome /path/to/chrome --playwright /path/to/playwright
python3 scripts/check_web.py --chrome /path/to/chrome --playwright /path/to/playwright
```

The province manifest generator is `scripts/update_province_snapshot.py`. To rebuild private extracts, supply `--register-dir` containing verified `phei.pdf` and `private-colleges.pdf` files and install `pypdf`. Constants and evidence dates must be reviewed against the new source before changing a reporting period. Captures are bundled and updated through app/server releases; they are not an automatic statistics refresh. Future ingestion can add additional reviewed indicators without changing dashboard routes.

This update prepares both Android and the self-hosted website. No production server or Cloudflare DNS change was made. Use the existing [deployment instructions](../deploy/README.md) to redeploy the website on your server.
