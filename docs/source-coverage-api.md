# TKT-006 — Synthetic Source Coverage and Field Completeness API

## Intent

`GET /api/v1/coverage` is the first *data-quality analytical* endpoint. It reports what is currently stored, how complete certain metadata fields are, and which test sources contributed the records.

**This is NOT a labor-market coverage estimate.** Without a licensed, understood sampling frame, DWI cannot estimate what percentage of real defense-sector jobs the database represents. The endpoint does not identify hiring, active vacancies, cleared workforce demand, salaries, regional skills or the actual number of jobs available.

## Scope and safety

- **Disabled by default** and uses the same `DWI_POSTINGS_API_ENABLED=1` local development gate as `GET /api/v1/postings`. This gate does not authorize live collection or public exposure.
- Filters database records by **all three synthetic-source predicates**: Greenhouse source platform, board token prefixed with literal `synthetic_`, and employer name prefixed with `Synthetic CI Employer `. Live or non-synthetic employer records are excluded.
- **Read-only**: no ingestion, network calls, stored aggregates, schema changes or schedulers.
- Never enable this development API on an Internet-facing service. The source naming convention is not an authentication or permission system.
- Live employer-data persistence, retention and republication remain blocked by the [source-use review](source-usage-review.md).

## GET contract

`GET /api/v1/coverage?limit=25&offset=0&employer=Synthetic%20CI%20Employer%20...`

| Parameter | Default | Validation | Meaning |
| --- | --- | --- | --- |
| `limit` | 25 | integer 1–100 | Maximum **source rows** on this page |
| `offset` | 0 | integer 0–100000 | Source-row offset (does not change global totals) |
| `employer` | omitted | nonblank 1–200 chars | Case-insensitive **exact employer name**, identical to postings API |

Top-level response:

- `data_scope="synthetic_only"`, `counting_rule="distinct_source_postings"`.
- `total_sources`: number of eligible configured synthetic board sources after the optional employer filter, **including sources with zero postings**.
- `total_employers`: distinct eligible employer IDs represented by those sources (includes zero-posting employers).
- `totals`: metrics over **all** eligible current posting rows after the employer filter, regardless of source pagination.
- `latest_observed_at`: maximum `postings.last_seen_at` in that filtered dataset, or `null` if no records.
- `limit`, `offset`, `next_offset`: source-level pagination; sources sorted by employer name, platform, board token and source ID.
- `sources`: current page of source rows, each with `platform`, `board_token`, `employer`, own `metrics` and nullable `latest_observed_at`.

Each `metrics` object contains:

| Field | Meaning |
| --- | --- |
| `posting_count` | Count of **distinct current rows**, identified by board source and external posting ID; not observation events |
| `location_present` | Rows with a nonempty stored raw location label |
| `first_published_at_present` | Rows with an explicitly provided source publication timestamp |
| `source_updated_at_present` | Rows with an explicit source update timestamp |
| `location_coverage_pct` | `100 × location_present / posting_count`, rounded to one decimal |
| `published_date_coverage_pct` | `100 × first_published_at_present / posting_count`, rounded to one decimal |
| `source_update_coverage_pct` | `100 × source_updated_at_present / posting_count`, rounded to one decimal |

If `posting_count = 0`, coverage percentages are **null**, not zero: there is no denominator. For any nonempty source where a field is absent from every record, the corresponding coverage is `0.0`.

Raw source labels are not geocoded. `source_updated_at` is **not** the publication date, and the latest observation timestamp is **not** evidence of a still-open job. Repeated observations or multiple historic versions of a source posting do not increase `posting_count`. Missing data is not imputed.

## Illustrative synthetic result

```json
{
  "data_scope": "synthetic_only",
  "counting_rule": "distinct_source_postings",
  "total_sources": 1,
  "total_employers": 1,
  "totals": {
    "posting_count": 1,
    "location_present": 1,
    "first_published_at_present": 0,
    "source_updated_at_present": 1,
    "location_coverage_pct": 100.0,
    "published_date_coverage_pct": 0.0,
    "source_update_coverage_pct": 100.0
  },
  "latest_observed_at": "2026-11-08T21:00:00Z",
  "limit": 25,
  "offset": 0,
  "next_offset": null,
  "sources": [
    {
      "platform": "greenhouse",
      "board_token": "synthetic_abc123",
      "employer": "Synthetic CI Employer synthetic_abc123",
      "metrics": {
        "posting_count": 1,
        "location_present": 1,
        "first_published_at_present": 0,
        "source_updated_at_present": 1,
        "location_coverage_pct": 100.0,
        "published_date_coverage_pct": 0.0,
        "source_update_coverage_pct": 100.0
      },
      "latest_observed_at": "2026-11-08T21:00:00Z"
    }
  ]
}
```

The numbers above are illustrative; actual synthetic test-source counts vary by local smoke-run history.

## Validate on your Windows development machine

Once the PR is reviewed and merged, update your local `main` branch. **Use the previously validated isolated PostgreSQL database** only.

From the repository root in PowerShell:

```powershell
cd C:\dev\defense-workforce-intelligence
git switch main
git pull --ff-only origin main
docker compose up -d db
cd backend
$env:DATABASE_URL = "postgresql+psycopg://dwi:dwi_local_only@127.0.0.1:5432/dwi_ingestion_test"
$env:DWI_TEST_DATABASE_URL = $env:DATABASE_URL
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe scripts\postgres_smoke.py
$env:DWI_POSTINGS_API_ENABLED = "1"
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

In a second terminal:

```powershell
Invoke-RestMethod "http://127.0.0.1:8000/api/v1/coverage?limit=5" |
    ConvertTo-Json -Depth 10
```

Verify `data_scope=synthetic_only`, that totals are consistent with `GET /api/v1/postings`, and that each source row refers to a synthetic CI board. You can also inspect the endpoint's schema at `http://127.0.0.1:8000/docs`.

When finished, press Ctrl+C in the server terminal and remove the test-only environment variables, or restore their previous values. Do not use `docker compose down -v`; it deletes the database volume.

## Next planned slice

Integrate these quality and source metrics into the React explorer, then design genuinely useful analytics for employer, skill and geography **only when authorized data and defensible normalization rules exist**. Do not misrepresent synthetic coverage percentages as defense-market statistics.
