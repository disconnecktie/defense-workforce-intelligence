# TKT-003 — Deduplication and Historical Tracking

**Status:** Implemented on the `feature/tkt-003-greenhouse-ingestion` branch with synthetic tests. This is not permission to persist third-party live postings.

## Identity and deduplication

- One posting identity is the **(source_id, external_posting_id)** pair, where a source is uniquely identified by `(platform="greenhouse", board_token)`. Thus the same Greenhouse numeric ID on two different boards represents **two distinct records**.
- A repeated observation of the same posting with the same canonical `content_hash` updates `last_seen_at` and creates an `unchanged` observation, **not another posting or metadata version**.
- Actual metadata changes update the current `postings` row, keep `first_seen_at` intact, advance `last_seen_at`, and record an `updated` observation with a historical snapshot of the changed version.
- Repeated identical IDs **within one feed** are counted as rejected duplicates and stored only once. If the same ID appears in one feed with **different normalized metadata**, the snapshot is ambiguous: the ingestion run **fails and rolls back the entire observation batch** rather than arbitrarily choosing a winner.
- The database unique constraints also protect against accidental duplicate postings and multiple observations for the same posting/run. **Concurrent ingestion of the same board is not supported in the MVP**.

## Historical data model

`postings` stores the most recent accepted metadata, provenance identifiers and `first_seen_at`/`last_seen_at`. `posting_observations` is append-only *by pipeline behavior* and stores one event per successfully observed unique posting per run:

| Event | Meaning | `snapshot` |
| --- | --- | --- |
| `inserted` | First successful observation in DWI for that board/ID | Versioned metadata JSON |
| `unchanged` | The observed metadata hash matches the current accepted version | `null` (prior version is retained) |
| `updated` | The observed metadata hash differs from the current version | Versioned metadata JSON |

The `snapshot` column was added by Alembic revision **`0002_observation_snapshots`**. Its version-1 JSON contains only normalized public-source metadata fields:

- `snapshot_schema_version`, `external_posting_id`, `title_raw`, `source_url`, `location_raw`, `source_internal_job_id`, `requisition_id`, `first_published_at`, `source_updated_at`

Observations independently store `observed_at`, `content_hash`, `event`, and `ingestion_run_id`. No descriptions, applicant data, inferred skills, or inferred compensation are captured. Historical snapshots are written on insertion or change only to limit storage overhead.

**Existing observations made before revision `0002` have `snapshot=NULL`; their old field values cannot be reconstructed from a hash.** New events after migration retain actual changed metadata going forward.

## Absence does not equal closure

- If a posting is absent from a later successful fetch, the MVP **does not** mark it closed or delete it. An absent item might mean removed, restricted, relocated, or missing from an incomplete listing.
- A failed fetch or a conflicting same-ID feed never changes previously committed posting metadata or observation history.
- DWI must never present `last_seen_at` as the actual posting date or assert a vacancy is filled without stronger evidence.

## Tests and operational validation

- `backend/tests/test_deduplication_history.py`: insert → unchanged → changed → unchanged; version-snapshot history; offset-equivalent timestamps; source-scoped identity; identical duplicate count; ambiguous conflicting-ID rollback; no closure on absence.
- `backend/scripts/postgres_smoke.py`: synthetic migrated **PostgreSQL** integration: insert → repeat → update; checks one posting, three observations, snapshots and historical title values. Each invocation uses a unique synthetic board token so rerunning a local smoke test does not collide with prior test rows.
- CI runs both Python unit tests and a PostgreSQL migration + synthetic smoke test.

PowerShell from `C:\dev\defense-workforce-intelligence\backend` (on the feature branch):

```powershell
git pull --ff-only origin feature/tkt-003-greenhouse-ingestion
.\.venv\Scripts\python.exe -m alembic upgrade head
.\.venv\Scripts\python.exe -m alembic current
.\.venv\Scripts\python.exe -m pytest -q

# Use your previously prepared isolated, migrated test DB (never live employer data):
$env:DWI_TEST_DATABASE_URL = "postgresql+psycopg://dwi:dwi_local_only@127.0.0.1:5432/dwi_ingestion_test"
$env:DATABASE_URL = $env:DWI_TEST_DATABASE_URL
.\.venv\Scripts\python.exe -m alembic upgrade head
.\.venv\Scripts\python.exe scripts\postgres_smoke.py
Remove-Item Env:\DWI_TEST_DATABASE_URL
Remove-Item Env:\DATABASE_URL
```

The migration targeting the default dev DB and the isolated test DB are separate steps if both are to be kept current. The script explicitly requires `DWI_TEST_DATABASE_URL`; the configured database should be disposable.

**Live source-use rights remain unresolved.** Keep the default read-only Greenhouse preview and `--persist` approval gate; do not bulk store live employer metadata until authorization is established.
