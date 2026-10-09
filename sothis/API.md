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

Search parameters: `q`, `province`, `category`, `source_id`, `after`, `before`, `include_national=true`, `sort=relevance|recent`, `offset`, `limit` (maximum 100). Dates use `YYYY-MM-DD`. Province-only queries automatically become jurisdiction filters. Text queries match all normalized words; they are not identity verification. Unknown publication dates are excluded by date filters.

Investigation JSON: `title`, `query`, `notes`, `pins` (document IDs). Updates preserve omitted fields. At most 200 unique evidence pins are stored per investigation. Device investigations are local to the APK/browser and are separate from these server records.

Collection JSON: `source_ids` (1–10 registered IDs), `pages` (1–10 page requests per source). One job runs at a time. The worker performs crawl depth one, exact host checks, optional path scopes, robots.txt checks and rate limits. A completed job can contain failures; inspect every result's `indexed`, `fetched` and `errors`.

Import JSON: `source_id`, `url`, `title`, `text`, optional `published_at` / `page`. The URL is provenance, not an instruction to fetch. Imported authenticity/identity remains subject to review. Request body limit: 2 MiB. Collection document limit: 12 MiB / 800 PDF pages; image-only PDFs require a later OCR workflow.

Raw collection bytes are stored under `data/archive/{sha256}`. Text versions are stored in SQLite. Reports reference source URLs and text hashes; this prototype has no raw-archive download endpoint or automatic cryptographic third-party attestation.
