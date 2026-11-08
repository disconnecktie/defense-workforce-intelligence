# TKT-003 — Ingestion Logging and Metrics

**Status:** Implemented and covered by synthetic CI tests on `feature/tkt-003-greenhouse-ingestion`. This does not authorize persisting employer job data.

## Run lifecycle

Each manually invoked `ingest_board(...)` creates an `ingestion_runs` record with `started_at` and `status="running"` before collection. The run terminates with `status="succeeded"` or `status="failed"`, plus `finished_at` and `duration_ms` (a non-negative elapsed time from Python's monotonic clock).

New fields are added by Alembic revision `0003_ingestion_run_metrics`:

- `duration_ms`: wall-time duration, including fetch, validation, storage, and run bookkeeping
- `rejection_reasons`: JSON dictionary of safe aggregate reason codes to counts

Earlier runs migrated from revision 0002 legitimately have `NULL` for both new fields. Do not backfill guessed timing or rejection reasons.

## Persisted outcome counters

`ingestion_runs` already has `fetched`, `inserted`, `updated`, `unchanged`, `rejected`, and `errors`.

- **Fetched:** raw elements in a successfully returned jobs array. Persisted in a separate transaction *before* the posting batch so it survives a later rollback.
- **Inserted:** new current posting created for this source and external ID.
- **Updated:** existing posting with a genuinely changed canonical content hash.
- **Unchanged:** valid repeated current version; it creates an observation, not a new posting/version.
- **Rejected:** malformed posting elements or repeated identical IDs *within the same feed*. Every rejection increments exactly one safe `rejection_reasons` category.
- **Errors:** run-level failure count (0 for successful runs, 1 for failed runs in this MVP). A rejected malformed record alone is **not** a run-level error.

For a **successful** batch, `fetched = inserted + updated + unchanged + rejected`, and `sum(rejection_reasons.values()) = rejected`. A successfully fetched batch that later **fails** rolls back all posting/observation/counter changes; its persisted run retains the original `fetched` count, `errors=1`, and no speculative partial counters. If the fetch itself fails, `fetched=0`.

### Rejection categories

`invalid_posting_id`, `invalid_title`, `invalid_url`, `invalid_location`, `invalid_timestamp`, `invalid_optional_id`, `malformed_record`, `duplicate_in_feed`. They describe field-level validation failures; none includes the raw rejected value.

A feed with contradictory content for the same posting ID fails atomically; it is **not** counted as a normal per-record rejection. Failed fetches and failed batches never mark previously observed jobs closed or inactive.

## Structured logs

The logger `dwi.ingestion` emits JSON objects with `event` values:

- `ingestion_started` (INFO): run/source IDs and board token
- `ingestion_succeeded` (INFO): run/source IDs, elapsed milliseconds, six counts, and aggregated rejection reasons
- `ingestion_failed` (ERROR): run/source IDs, elapsed milliseconds, failure phase, exception class, errors=1
- `ingestion_failure_record_error` (ERROR): the failure status itself could not be written to the database

When a permitted `--persist` run is manually invoked, the CLI configures these JSON objects on **stderr**, while printing its final `RunSummary` JSON on **stdout**.

Logs and persisted `error_message` **must not contain** job titles, source URLs, raw payloads, exception messages, applicant details, authorization tokens, or connection strings. A failed run stores only a safe exception type and a generic failure label, except the fixed `Conflicting records for posting ID` label (without the ID). Rejection-reason codes are derived from known validator categories, not untrusted data.

The collector's normal read-only preview remains unchanged; `--persist` still requires source-use approval and the explicit `DWI_SOURCE_USE_APPROVED=1` gate. No scheduler or monitoring UI is enabled.

## Validate with synthetic data only

From `C:\dev\defense-workforce-intelligence\backend`:

```powershell
git pull --ff-only origin feature/tkt-003-greenhouse-ingestion
.\.venv\Scripts\python.exe -m pytest -q
$env:DWI_TEST_DATABASE_URL = "postgresql+psycopg://dwi:dwi_local_only@127.0.0.1:5432/dwi_ingestion_test"
$env:DATABASE_URL = $env:DWI_TEST_DATABASE_URL
.\.venv\Scripts\python.exe -m alembic upgrade head
.\.venv\Scripts\python.exe -m alembic current
.\.venv\Scripts\python.exe scripts\postgres_smoke.py
Remove-Item Env:\DWI_TEST_DATABASE_URL
Remove-Item Env:\DATABASE_URL
```

Expected Alembic revision: `0003_ingestion_run_metrics` (head). Expected smoke output: `Synthetic PostgreSQL ingestion: insert/repeat/update/history/metrics PASS`.

The test suite uses synthetic records only. The PostgreSQL smoke requires an explicitly configured **isolated test database**, not live employer data or production. It uses a distinct synthetic board token for every run.

After a smoke test, inspect the **isolated test DB** if desired:

```sql
SELECT id, status, fetched, inserted, updated, unchanged, rejected,
       errors, duration_ms, rejection_reasons
FROM ingestion_runs ORDER BY id DESC LIMIT 5;
```

## MVP limitations

- Failure diagnostics are intentionally generic to protect privacy. For deeper debugging, reproduce with synthetic records and inspect local exception output; do not send real job payloads to telemetry.
- Logging is per-run rather than per-posting to limit log volume. There are no retries/schedules/alerts or a public analytics endpoint in this subtask.
- Successful partial-quality feeds record rejection counts but remain `succeeded`; downstream users must consider `rejected` alongside coverage when interpreting job totals.
- Concurrent runs for the same Greenhouse board remain unsupported.
