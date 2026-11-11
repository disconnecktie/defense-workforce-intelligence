# Historical Activity Dashboard — TKT-011

The React frontend now includes a **Historical activity** panel below the Technology Title Signals Dashboard. It reads `GET /api/v1/ingestion-history` implemented in TKT-010. The API exposes only eligible synthetic CI sources; the feature is a **local development preview**, not a live labor-market product.

## Data semantics

- Ingestion runs represent processing attempts/events, **not vacancies, hires, job openings, closures, or hiring demand**.
- The **Matching runs (all pages)** number is the API's `total` for the exact employer filter.
- Status metrics, processing counters, and the UTC-date activity visualization include **only the current fetched page** (at most 10 rows). Their values should never be represented as historical totals.
- Processing counters (`fetched`, `inserted`, `updated`, `unchanged`, `rejected`, `errors`) may refer to repeated processing of the same underlying posting. They are not distinct job counts.
- Durations and finished timestamps may be missing and are displayed as `Not supplied`.
- The frontend does not fetch other pages to calculate aggregate history; changing the page changes the chart and page metrics.

## Controls and failure handling

The view reuses the Postings Explorer's exact employer filter. Its employer form sets that shared filter, affecting other dashboards as well. Changing employers resets history pagination. Navigation uses the API's `next_offset` and the current page offset, with a fixed page size of 10.

The page distinguishes loading, empty results, HTTP 503 (disabled by default), unexpected API responses, and transport/HTTP errors. No raw backend error messages are requested. The response is checked for `synthetic_only` and `ingestion_runs_not_vacancies` declarations before rendering.

## Local verification (synthetic test database only)

1. On the TKT-011 feature branch, install frontend dependencies with `cd frontend && npm ci`.
2. Run `npm test` for Vitest/React Testing Library tests and `npm run build` for TypeScript and Vite.
3. Start FastAPI locally using an isolated `dwi_ingestion_test` database as `DATABASE_URL`, and opt in **only in that terminal** with `DWI_POSTINGS_API_ENABLED=1`. Do not point to production or real employer data.
4. From `frontend`, run `npm run dev`, open `http://127.0.0.1:5173`, and inspect the Historical activity section.
5. Check that total matching runs comes from the API, while the counters/chart use only the current page. Verify Next/Previous, exact employer filter (including case-insensitive API matching), and no-results behavior.
6. Restart FastAPI with `DWI_POSTINGS_API_ENABLED=0` and confirm that the panel displays its disabled notice rather than data. Restore the opt-in only for further isolated tests.

GitHub Actions runs `npm test` and `npm run build` as part of the existing frontend CI job, alongside the API and database jobs. Do not merge until CI and local checks pass.

## Restrictions

The dashboard adds no ingestion, collection, scheduling, backend writes, migrations, or public-deployment permission. Third-party source-use and retention/redistribution rights remain unresolved. Synthetic CI views must not be enabled publicly.
