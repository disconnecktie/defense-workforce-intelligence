# TKT-005 — Local Synthetic Postings Explorer

## Purpose and scope

The React frontend now consumes the merged, versioned `GET /api/v1/postings` endpoint rather than only reporting API liveness. This is a **development-only explorer of synthetic CI smoke-test records**, not an authorized real-employer job board or a market-demand dashboard.

The explorer adds:

- Display of current posting title, source posting ID and reference URL, employer, source board, original location label, and local-time last-observed timestamp.
- Source-specific count, number of boards **on the visible page**, and latest observation timestamp for the filtered dataset.
- Case-insensitive **exact employer-name** filter, including click-to-filter on an employer in any result row.
- Five, ten, and twenty-five rows per page, with Previous/Next navigation respecting `next_offset`.
- Explicit states for loading, no results, failed network/API response and the intentionally disabled `503` endpoint.
- Abortable browser requests, so quick filter changes or navigating between pages does not present a stale response.
- Responsive layout with a horizontally scrollable, keyboard-accessible table.
- Persistent synthetic-data warnings. No claims about real vacancies, hiring, clearance demand or salaries.

## Local Windows validation

The React app and the API are separate local processes. Make sure you are on the updated branch or after review and merge on `main`. **Do not enable this development route on an Internet-facing deployment.**

1. Start PostgreSQL from the repository root: `docker compose up -d db`.
2. In **terminal A**, from `backend`, use the isolated test DB and enable only the synthetic postings API:

   ```powershell
   $env:DATABASE_URL = "postgresql+psycopg://dwi:dwi_local_only@127.0.0.1:5432/dwi_ingestion_test"
   $env:DWI_POSTINGS_API_ENABLED = "1"
   .\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
   ```

3. In **terminal B**, from `frontend`, run:

   ```powershell
   npm install
   npm run build
   npm run dev
   ```

4. Open `http://127.0.0.1:5173`. The explorer should display **four** synthetic postings if the same four isolated smoke-run records are still present. The count can increase after additional smoke runs.
5. Click a displayed employer. Confirm the table narrows to that exact synthetic employer and the count reflects the filter.
6. Clear the employer filter. Choose `5` rows and run more synthetic smoke tests if you need enough items to exercise Next/Previous. No live employer data should be returned.
7. Stop the local processes with Ctrl+C. Remove the test-only environment variables from terminal A (or restore their original values):

   ```powershell
   Remove-Item Env:\DWI_POSTINGS_API_ENABLED -ErrorAction SilentlyContinue
   Remove-Item Env:\DATABASE_URL -ErrorAction SilentlyContinue
   ```

Do not use `docker compose down -v` to clean up; that deletes the local volume.

### Expected safety checks

- With `DWI_POSTINGS_API_ENABLED` absent from the **backend process**, the frontend reports that the postings endpoint is disabled. An API liveness check alone does not guarantee access to postings.
- With the flag present and an isolated test DB selected, the table shows only synthetic-source records. The flag is not sufficient to authorize real data.
- Source links on synthetic records generally point to `https://example.org/`, not real job listings.
- An unmatched exact employer filter shows a zero-results message; clearing the filter restores records.
- If the backend is stopped, the explorer shows an error instead of fabricating results.

## Service contract

Uses existing `GET /api/v1/postings` and `/health`. The frontend does not insert or update postings, collect data, infer skills/clearance/salary, or invent market statistics. See [postings API contract](postings-api.md) and the [source-use review](source-usage-review.md).

Before any actual third-party source persistence or public display, resolve source-use permissions and retention, add appropriate authentication/authorization and production deployment controls, and design a separately reviewed non-synthetic API.
