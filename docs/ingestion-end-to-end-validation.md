# TKT-003 / ST-024 — Operator runbook and end-to-end validation

**Status:** Pipeline merged into `main` via [PR #3](https://github.com/disconnecktie/defense-workforce-intelligence/pull/3). CI [run #42523352488](https://github.com/disconnecktie/defense-workforce-intelligence/actions/runs/42523352488) passed API, frontend, and PostgreSQL checks on the merge commit. **Independent workstation validation and source-use approval remain outstanding.**

**Scope:** Validate the installed API, migration state, and synthetic data ingestion. **Never perform these tests against real employer data or a production database.** This runbook does not approve third-party collection, historical retention, or redistribution.

## 1. Safety and prerequisites

- Windows PowerShell; project checkout at `C:\dev\defense-workforce-intelligence`.
- Python 3.11+ with the backend virtual environment at `backend\.venv`; Docker Desktop running; Docker Compose available.
- Use the repository's local-only PostgreSQL development instance on `127.0.0.1:5432`. These are *disposable development credentials*, not deployment secrets.
- Set `DWI_TEST_DATABASE_URL` only to the explicitly created `dwi_ingestion_test` database. Never point it at the main `dwi` database, production, or a remote PostgreSQL service.
- Keep `DWI_SOURCE_USE_APPROVED` unset. This validation relies entirely on synthetic test fixtures; `--persist` against live boards is not needed.
- **Do not use `docker compose down -v`**: it would delete the existing local PostgreSQL volume.

### Check source tree and local database

From PowerShell:

```powershell
cd C:\dev\defense-workforce-intelligence
git switch main
git pull --ff-only origin main
git status
docker compose up -d db
docker compose exec -T db pg_isready -U dwi -d dwi
```

Confirm the working tree is clean and PostgreSQL reports `accepting connections`. If Docker or `pg_isready` fails, stop and resolve it before proceeding.

### Create the isolated test database if needed

Run these commands from the repository root:

```powershell
$testDb = (docker compose exec -T db psql -U dwi -d dwi -tAc "SELECT 1 FROM pg_database WHERE datname = 'dwi_ingestion_test';").Trim()
if ($LASTEXITCODE -ne 0) { throw "Could not check the local PostgreSQL test database." }
if ($testDb -ne "1") {
    docker compose exec -T db createdb -U dwi dwi_ingestion_test
    if ($LASTEXITCODE -ne 0) { throw "Could not create the isolated test database." }
}
```

Do **not** drop/recreate an existing database. If `dwi_ingestion_test` already has important data, use a different disposable test database and adjust the DSN only after explicit review.

## 2. Run migrations and deterministic synthetic tests

From the repository root:

```powershell
cd backend
$env:DATABASE_URL = "postgresql+psycopg://dwi:dwi_local_only@127.0.0.1:5432/dwi_ingestion_test"
$env:DWI_TEST_DATABASE_URL = $env:DATABASE_URL

.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
.\.venv\Scripts\python.exe -m alembic upgrade head
.\.venv\Scripts\python.exe -m alembic current
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe scripts\postgres_smoke.py
```

**Expected results:**

- `alembic current` reports **`0003_ingestion_run_metrics (head)`**.
- `pytest` passes the complete offline suite (122 tests passed on the last reviewed merge commit).
- Synthetic PostgreSQL smoke prints **`Synthetic PostgreSQL ingestion: insert/repeat/update/history/metrics PASS`**.
- Smoke-test rows are limited to uniquely named synthetic employers and source tokens; no Greenhouse network access is made.

Stop and inspect any failure before proceeding. Do not enable source-use approval or use a production database as a workaround.

### Inspect the resulting synthetic records

From the repository root in a **new** PowerShell prompt or after `cd ..`:

```powershell
docker compose exec -T db psql -U dwi -d dwi_ingestion_test -c "SELECT status, fetched, inserted, updated, unchanged, rejected, errors, duration_ms, rejection_reasons FROM ingestion_runs ORDER BY id DESC LIMIT 4;"
docker compose exec -T db psql -U dwi -d dwi_ingestion_test -c "SELECT COUNT(*) AS postings FROM postings;"
docker compose exec -T db psql -U dwi -d dwi_ingestion_test -c "SELECT event, COUNT(*) FROM posting_observations GROUP BY event ORDER BY event;"
```

Expected smoke-run progression for the most recent unique synthetic source: `inserted`, `unchanged`, `updated`, then an unchanged record plus counted duplicate and invalid record; it verifies normalized history and counter reconciliation. There may be earlier synthetic rows from previous smoke runs, so do not expect global table counts to be exactly one.

### Restore your shell environment

In the **same** PowerShell prompt that set the URLs:

```powershell
Remove-Item Env:\DWI_TEST_DATABASE_URL -ErrorAction SilentlyContinue
Remove-Item Env:\DATABASE_URL -ErrorAction SilentlyContinue
```

If those environment variables were previously configured for another purpose, **restore their prior values** instead of simply removing them. You can stop Docker without deleting the volume with `docker compose down` from the project root.

## 3. Verify the API and frontend separately

From `backend`, launch the API:

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

In another terminal:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/health
Invoke-RestMethod http://127.0.0.1:8000/api/v1/health
```

Both return `status: ok` and `service: dwi-api`. These endpoints check liveness only, **not PostgreSQL readiness**.

From `frontend`, run `npm install`, `npm run build`, then `npm run dev`. Open `http://127.0.0.1:5173`. The initial page reports API connectivity; the dashboard and analytical API are not yet implemented.

## 4. Release/acceptance checklist

| Check | Evidence / expected result | Status |
| --- | --- | --- |
| Source GET connectivity | Earlier manual preview of a public pilot board returned 2,600 metadata records with no DB writes | Prior evidence; optional recheck, not needed for synthetic tests |
| Fixed Greenhouse HTTP contract | Offline mocked 429/5xx retries, permanent-error behavior, redirect refusal, complete-feed validation | Automated CI passed |
| Data normalization | Strict IDs, public HTTPS URLs, UTC dates, nullable optional metadata | Automated CI passed |
| Deduplication/history | Stable identity by source+posting, insert/update/unchanged observations, immutable change snapshots | Automated CI passed |
| Atomicity | Failed fetch or conflict does not modify existing posting history; failed run is recorded | Automated CI passed |
| Run metrics/diagnostics | Counts reconcile, safe categorized rejection reasons and elapsed duration | Automated CI passed |
| PostgreSQL migrations | 0001 → 0002 → 0003 on disposable DB, schema/current revision verified | CI passed; local rerun pending |
| PostgreSQL synthetic smoke | Insert/repeat/update/history/metrics, no live employer records | CI passed; local rerun pending |
| Runtime smoke | API health endpoints, React build/start | CI passed; optional local confirmation |
| Source-use authorization | Actual third-party storage/retention/redistribution rights, rate limits and employer terms reviewed | **BLOCKED / NOT APPROVED** |

### Interpretation and release decision

- The code is merged, and offline CI supports **technical completion** of the initial ingestion pipeline.
- Do not mark authorization criteria fulfilled because a public endpoint responds or a test run passes.
- Do not use `DWI_SOURCE_USE_APPROVED=1` or invoke `--persist` against live employer boards until the actual [source-use review](source-usage-review.md) establishes permitted scope.
- Keep the TKT-003 source-use acceptance criterion open and document the blocker. A code merge is **not** proof of source-use permission.
- Future improvements (source registry, licensed alternative feeds, analytics API, UI) belong in separate follow-on tickets. Avoid inferring salary, geography, security clearance, posting closure or hiring outcomes beyond actual source evidence.

## 5. Troubleshooting without exposing private data

| Symptom | Safe next check |
| --- | --- |
| `docker compose` fails | Confirm Docker Desktop running; `docker compose ps`; inspect local compose configuration |
| `pg_isready` fails | Confirm container health and whether local port 5432 is occupied |
| Alembic connection fails | Confirm `DATABASE_URL` points to `dwi_ingestion_test` on `127.0.0.1`, not production |
| Alembic head mismatch | Confirm you pulled merged `main`; use `python -m alembic history`; do not blindly downgrade |
| PostgreSQL smoke fails | Share the sanitized traceback and recent *synthetic* test run counters; do not paste passwords/DSNs |
| CI and local test counts differ | Reinstall backend editable package after pulling current `main`; verify virtual environment |
| Live preview works but persistence is blocked | **Expected** until source-use approval; never set flag simply to make test pass |

**Operational handoff:** Record the merge SHA, CI run, local PostgreSQL revision, smoke result and source-use disposition in Telaryn ST-024. Close the technical subtask only after local validation if local confirmation is required; retain an open source-use gate independently.
