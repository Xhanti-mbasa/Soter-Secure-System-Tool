# Engine API

Base path: `/api/`. JSON responses; mutation bodies must use `Content-Type: application/json`. If `ZALENS_API_TOKEN` is set, **all** API calls require `Authorization: Bearer <token>`. Do not put tokens in URLs. No CORS permissions are granted. Native Android connects through its scoped API bridge; the browser interface is served from the engine's own origin.

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/health` | Version, index counts, collection date, province/category vocabulary |
| GET | `/api/sources` | Registry, source status, dates and indexed-passage counts |
| GET | `/api/search` | Search indexed documents |
| GET | `/api/documents/{id}` | Extracted text, provenance, page and version hashes |
| GET / POST | `/api/cases` | List / create investigations |
| GET / POST | `/api/cases/{id}` | Read / update a saved investigation |
| GET | `/api/cases/{id}/export?format=md` | Markdown brief as JSON `content`; use `format=html` for printable HTML |
| POST | `/api/crawl` | Start one bounded collection job |
| GET | `/api/jobs` | Current/most recent job and per-source results |
| POST | `/api/import` | Import authorised text into a registered source |
| POST | `/api/discover` | Live public index hits and profile candidates; persisted index metadata |
| POST | `/api/tenders` | Official eTenders notices, supplier awards and pagination |
| GET / POST | `/api/monitors` | List / create or update persistent rules |
| POST | `/api/monitors/check` | Run one rule; first successful service checks establish baselines |
| GET / POST | `/api/alerts` | List alert inbox / mark existing alerts read |
| POST | `/api/evidence` | Archive one selected public original on the engine |

Search parameters: `q`, `province`, `category`, `source_id`, `after`, `before`, `include_national=true`, `sort=relevance|recent`, `offset`, `limit` (maximum 100). Dates use `YYYY-MM-DD`. Province-only queries automatically become jurisdiction filters. Text queries match all normalized words; they are not identity verification. Unknown publication dates are excluded by date filters.

Investigation JSON: `title`, `query`, `notes`, `pins` (document IDs). Updates preserve omitted fields. At most 200 unique evidence pins are stored per investigation. Device investigations are local to the APK/browser and are separate from these server records.

Collection JSON: `source_ids` (1–10 registered IDs), `pages` (1–10 page requests per source). One job runs at a time. The worker performs crawl depth one, exact host checks, optional path scopes, robots.txt checks and rate limits. A completed job can contain failures; inspect every result's `indexed`, `fetched` and `errors`.

Import JSON: `source_id`, `url`, `title`, `text`, optional `published_at` / `page`. The URL is provenance, not an instruction to fetch. Imported authenticity/identity remains subject to review. Request body limit: 2 MiB. Collection document limit: 12 MiB / 800 PDF pages; image-only PDFs require a later OCR workflow.

Raw collection bytes are stored under `data/archive/{sha256}`. Text versions are stored in SQLite. Reports reference source URLs and text hashes; this prototype has no raw-archive download endpoint or automatic cryptographic third-party attestation.

## Live services and monitoring

Discovery JSON: `query` (2–160 characters), `scope=all|social|government|company`. Returns `results`, `hit_count`, `account_count`, `statuses`, `registration_number`, `companies`, `cipc`, `retrieved_at` and coverage. `platform` is set only for recognised profile URL shapes. `match_score` measures lexical relevance, not person identity. `document_id` is the engine evidence ID; `id` is the stable public-hit ID. Index metadata is distinguished from downloaded source text. Five-minute caching avoids repeated public-provider requests. Set `SOTHIS_BRAVE_API_KEY` for the official Search API.

Tender JSON: `query`, `status=open|awarded|closed|cancelled`, `start` (30 per page), `search_by=keyword|company|supplier|number`. Returns official portal fields, including `id`, `tender_No`, `description`, `closing_Date`, `eSubmission`, `supportDocument` and `awards`, plus source URL/count/offset/retrieval time. Company/supplier/number queries use `/Home/TenderFilter/`; keyword queries use `/Home/PaginatedTenderOpportunities`. Provider availability and schema can change independently of Sothis.

Monitor JSON: optional `id` to update, `query`, `services` from `web|social|government|cipc|tenders`, `condition=new_hit|changed_hit`, `required_text`, `interval_minutes` (15–10080), `enabled`. Editing query/services/condition/required phrase resets the baseline. Rules and alerts persist in SQLite. The scheduler checks due rules every 30 seconds while the process runs. Checks serialize; provider failures preserve baselines. CIPC checks only imported indexed disclosures. Alert JSON includes stable `id`, `rule_id`, `service`, `condition`, `hit`, `created_at`, `read`.

Import accepts optional `record_key` (1–80 alphanumeric/underscore/hyphen characters) to distinguish disclosures sharing a portal source URL. The resulting `#sothis-import-...` anchor is explicitly local provenance, not an official CIPC ID.

Evidence JSON: `url`. The engine enforces public-host, robots and bounded fetch rules, archives raw bytes and returns SHA-256, MIME, length and retrieval time. Android has a separate native `/api/device/evidence` route with a 16 MiB limit, public-address/HTTPS redirect checks and a device-private archive. Native `/api/device/discover`, `/tenders`, `/monitors`, `/monitors/check` and `/alerts` bypass unavailable engine configuration for phone-local services. These routes are a bridge contract, not exposed engine endpoints. Native ZIP export includes only selected archived originals. Device rules use JobScheduler and optional notifications; they do not synchronize with engine rules.
