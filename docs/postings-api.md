# First read API — GET /api/v1/postings (synthetic development slice)

**Status:** Proposed in the first versioned analytical API PR. This is a *current posting record listing*, **not** a labor-market aggregate, job closure tracker, or live employer-data launch.

## Safety boundary

- The route is **disabled by default** (`503`); it must be explicitly enabled with `DWI_POSTINGS_API_ENABLED=1` in the API process environment.
- Even when enabled, the database query **only selects the synthetic records created by the CI smoke harness**: `source.platform = greenhouse`, board tokens prefixed by the literal `synthetic_`, and employer names prefixed by `Synthetic CI Employer `. Both source and employer markers are required; real employer board data is excluded.
- This is a **local testing convention**, not a general-purpose authorization or provenance system. It cannot justify public exposure. **Do not deploy the enabled route to a publicly reachable service.**
- The route performs **no writes, network fetching, scheduled collection, or schema changes**. It does not set or bypass `DWI_SOURCE_USE_APPROVED` (the separate ingestion persistence gate).
- Third-party Greenhouse historical storage and redistribution rights remain unresolved. Supporting permitted real employer data in an API requires a separate review, explicit authorization and a new implementation—not simply toggling this flag.

## GET contract

`GET /api/v1/postings?limit=25&offset=0&employer=Synthetic%20CI%20Employer%20...`

Query parameters:

| Parameter | Default | Validation | Semantics |
| --- | --- | --- | --- |
| `limit` | 25 | integer, 1–100 | Maximum number of current posting records on the page |
| `offset` | 0 | integer, 0–100000 | Number of matching records to skip |
| `employer` | omitted | 1–200 characters, nonblank | Case-insensitive **exact employer name**; not a substring search |

Responses:

- `200`: JSON with `data_scope="synthetic_only"`, `counting_rule="distinct_source_postings"`, `total`, `limit`, `offset`, nullable `next_offset`, nullable `latest_observed_at`, `page_sources`, and `items`.
- `422`: invalid query or a blank employer filter.
- `503`: feature flag not enabled. The disabled route does not open the database.
- Standard API failure if the configured database is absent or has not been migrated; do not interpret `/health` as database readiness.

Each item includes:

```json
{
  "id": 1,
  "employer": {"id": 1, "name": "Synthetic CI Employer synthetic_abc123"},
  "title": "Synthetic Senior Systems Engineer",
  "location_raw": "Synthetic Remote Region",
  "source": {
    "platform": "greenhouse",
    "board_token": "synthetic_abc123",
    "external_posting_id": "8080001",
    "url": "https://example.org/jobs/8080001"
  },
  "first_published_at": null,
  "source_updated_at": "2026-11-08T13:00:00+00:00",
  "first_seen_at": "2026-11-08T21:00:00+00:00",
  "last_seen_at": "2026-11-08T21:00:01+00:00"
}
```

All values above are **illustrative synthetic values**, not actual records. Null dates remain null and timestamps are serialized as UTC. `first_seen_at` is the first time DWI observed a record; it is **not** a posting/opening date.

The `total` count is calculated over **all filtered current posting rows**, independent of `offset`; `page_sources` lists only sources on the returned page, so an empty out-of-range page has no `page_sources`. `latest_observed_at` reflects the maximum stored `last_seen_at` within the filtered set, **not a promise that sources are current**. Ordering is stable for a fixed dataset: `last_seen_at DESC, postings.id DESC`, but offsets may shift if concurrent ingestion updates the dataset; keyset pagination can be added later.

A `200` response never means the advertised job is still open or was filled. DWI has no active/closed inference, no compensation or clearance estimation, no skills classifier, and no anonymous live-source API.

## Local PowerShell walkthrough (disposable database only)

Do this only on your own workstation, using the isolated `dwi_ingestion_test` database verified in ST-024. From repository root:

```powershell
cd C:\dev\defense-workforce-intelligence
git switch feature/tkt-004-readonly-postings-api
git pull --ff-only origin feature/tkt-004-readonly-postings-api
docker compose up -d db
cd backend
$env:DATABASE_URL = "postgresql+psycopg://dwi:dwi_local_only@127.0.0.1:5432/dwi_ingestion_test"
$env:DWI_TEST_DATABASE_URL = $env:DATABASE_URL
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
.\.venv\Scripts\python.exe -m alembic current
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe scripts\postgres_smoke.py
```

The smoke test creates its own unique **synthetic** employer and board token (not a live Greenhouse request). Expected output includes:

```text
Synthetic PostgreSQL ingestion: insert/repeat/update/history/metrics PASS
Synthetic PostgreSQL API: filtered source-attributed GET /api/v1/postings PASS
```

To view the data through the local API, **in this same backend PowerShell session**:

```powershell
$env:DWI_POSTINGS_API_ENABLED = "1"
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

In a second PowerShell window:

```powershell
Invoke-RestMethod "http://127.0.0.1:8000/api/v1/postings?limit=2" | ConvertTo-Json -Depth 10
```

For the exact employer filter, copy one synthetic employer name from the returned results and pass it in a URL-encoded `employer` query parameter. No real employer source will appear even if other sources are present in the same database.

When finished, stop Uvicorn with Ctrl+C; in the first shell:

```powershell
Remove-Item Env:\DWI_POSTINGS_API_ENABLED -ErrorAction SilentlyContinue
Remove-Item Env:\DWI_TEST_DATABASE_URL -ErrorAction SilentlyContinue
Remove-Item Env:\DATABASE_URL -ErrorAction SilentlyContinue
```

Restore any prior values if you had previously set them. These commands **do not delete** PostgreSQL test data. Do not run `docker compose down -v` unless you deliberately intend to erase the local volume.

## Test evidence and follow-on work

- New offline FastAPI tests seed synthetic records with the real ingestion pipeline and verify total/counting rules, stable pages, employer matching, source-scoped IDs, missing data, rejected filters, source exclusion, disabled-by-default behavior and read-only operation.
- Existing CI PostgreSQL smoke now exercises the GET endpoint against **real local PostgreSQL**, with synthetic source tokens and an explicit disposable DB. This catches backend-specific SQL semantics not represented by SQLite alone.
- No schema migration required; uses merged TKT-003 tables `employers`, `sources`, `postings`.
- Next independently scoped API slices: source coverage/quality stats, time-series aggregates, authorized non-synthetic data, and a React dashboard (after provenance and source-use design review).

See [ST-024 validation runbook](ingestion-end-to-end-validation.md), [source-use limitations](source-usage-review.md), and [project charter](project-charter.md).
