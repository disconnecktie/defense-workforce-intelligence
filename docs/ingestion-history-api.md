# Synthetic ingestion history API — TKT-010

`GET /api/v1/ingestion-history` provides a read-only, latest-first list of **ingestion attempts**, including insert, update, unchanged, rejected, and error counters. These are **processing events**, not unique current vacancies, hires, hiring demand, or verified job openings. Repeated ingestion of the same posting produces multiple run observations, not additional job positions.

## Guardrails

- Disabled by default: requires `DWI_POSTINGS_API_ENABLED=1` on the **local** FastAPI process and an isolated disposable synthetic database.
- The same strict synthetic-only source and employer predicates as `GET /api/v1/postings` apply. The source-use approval flag is **not** sufficient to enable the endpoint.
- No writes, fetching, scheduler, schema migrations, or new dependencies.
- Excludes raw errors, rejection reasons, source posting contents, and other potentially sensitive diagnostics.
- Third-party source-use, retention, and redistribution approval remains unresolved. Do not enable publicly.

## Request

```http
GET /api/v1/ingestion-history?limit=25&offset=0
GET /api/v1/ingestion-history?employer=Synthetic%20CI%20Employer%20Alpha&limit=10
```

Parameters: `limit` 1–100 (default 25); `offset` 0–100000 (default 0); optional `employer` is an exact case-insensitive name filter, with surrounding whitespace ignored. Empty or whitespace-only values return HTTP 422. An API that has not been enabled returns HTTP 503.

Response: `data_scope=synthetic_only`, `counting_rule=ingestion_runs_not_vacancies`, `total`, `limit`, `offset`, `next_offset` (nullable), and `items`. Each item includes run ID, employer, platform, board token, start/finish timestamps, status, fetched/inserted/updated/unchanged/rejected/error counts, and duration in milliseconds (nullable). Sorting is descending by run start and ID.

Counts are scoped to the filtered source population **before** pagination. Historical runs are not grouped into daily job counts and should not be charted as labor-market demand.

## Developer validation

In an isolated `dwi_ingestion_test` database, run Alembic migrations, the existing synthetic PostgreSQL smoke, and backend pytest. Start the backend with `DWI_POSTINGS_API_ENABLED=1` and `DATABASE_URL` targeting only that test database. Query the endpoint in the browser or PowerShell and verify that the returned run counters match the existing synthetic ingestion runs. Repeat with a case-insensitive exact employer filter and a two-item page size. Confirm 503 after disabling the flag.

The new SQLite contract tests are `backend/tests/test_ingestion_history_api.py`. CI is necessary but does not replace local operator validation. A subsequent feature may visualize this endpoint, with prominent labels preventing interpretation as real-world hiring trends.
