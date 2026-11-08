# Defense Workforce Intelligence (DWI)

> Public-data analytics for technology workforce demand across the U.S. defense sector.

**Status:** TKT-003 Greenhouse ingestion and the versioned, synthetic-only postings read API are merged into `main`. An interactive React Postings Explorer is in development using **only synthetic integration-test records**. Live employer-data persistence remains disabled pending source-use authorization; actual market aggregates and employer-data analytics are not yet implemented.

## Purpose

Defense Workforce Intelligence (DWI) is a planned platform for aggregating, normalizing, and analyzing publicly available defense-sector job postings, skill requirements, advertised compensation, and locations; a later phase may correlate public federal contract awards.

The project demonstrates Python, API integration, ETL, normalization, historical analytics, and interactive visualization. It is independent of **Telaryn**, which manages its development; a future Telaryn view may use DWI's versioned API.

## Repository layout

```text
backend/                 FastAPI app and Python smoke tests
frontend/                React + TypeScript + Vite app
database/                Local PostgreSQL instructions
docs/                    Project charter, architecture, data-source evaluation
.github/workflows/       Continuous integration checks
docker-compose.yml       Local PostgreSQL service
.env.example             Local backend/database settings (sample only)
```

## Prerequisites

- **Python 3.11+** and pip
- **Node.js 22+** and npm
- **Docker** with the Docker Compose plugin (for PostgreSQL)
- Git

These commands assume a terminal in the cloned repository. The API and frontend run as local processes; Docker Compose runs the database only.

## Quick start — Linux, macOS, or Git Bash

```sh
git clone https://github.com/disconnecktie/defense-workforce-intelligence.git
cd defense-workforce-intelligence
cp .env.example .env
docker compose up -d db
docker compose ps
```

In **terminal 1**, start FastAPI:

```sh
cd backend
python -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

On Windows PowerShell, use `.venv\Scripts\Activate.ps1` to activate the venv instead. If activation is restricted, invoke `.venv\Scripts\python.exe` directly.

In **terminal 2** (from repository root), start React:

```sh
cd frontend
cp .env.example .env
npm install
npm run dev
```

Open **http://127.0.0.1:5173**. The page should display **API online** if FastAPI is running. To verify it directly:

```sh
curl http://127.0.0.1:8000/health
# {"status":"ok","service":"dwi-api"}
```

The versioned endpoint is `http://127.0.0.1:8000/api/v1/health`; OpenAPI docs are at `http://127.0.0.1:8000/docs`.

### Windows PowerShell notes

At repository root, use `Copy-Item .env.example .env` instead of `cp` if desired. In `frontend`, run `Copy-Item .env.example .env`. In `backend`, activate with `.venv\Scripts\Activate.ps1`, then use the same `python -m pip` and `python -m uvicorn` commands.

## Verify each component

- **PostgreSQL:** `docker compose exec db pg_isready -U dwi -d dwi` should report `accepting connections`.
- **API:** `curl http://127.0.0.1:8000/health` should return HTTP 200 and the JSON shown above.
- **React:** `http://127.0.0.1:5173` should render the DWI foundation page.
- **Backend tests:** from `backend`, run `python -m pytest -q`.
- **Frontend build:** from `frontend`, run `npm run build`.

A GitHub Actions workflow runs the API tests, frontend type-check/build, and a PostgreSQL smoke test on pull requests.

**Important:** The API health endpoint checks only API liveness, **not** database readiness. PostgreSQL tables and Alembic migrations now exist for the ingestion pipeline, but reporting **API online** still does not imply PostgreSQL is connected.

## Configuration and security

- Root `.env.example` contains disposable PostgreSQL credentials and a future-use database URL; copy it to the untracked `.env` before using Compose.
- `frontend/.env.example` contains `VITE_API_BASE_URL` for the browser (defaults to `http://127.0.0.1:8000`). Vite exposes `VITE_` variables publicly: **never put secrets in them**.
- The backend defaults to CORS for local Vite origins only. Set `DWI_CORS_ORIGINS` in its **process environment** for other origins; root `.env` is not automatically loaded by the FastAPI process.
- The database binds only to `127.0.0.1` on the development machine. Do not use these example credentials for deployment.
- Do not commit real credentials, applicant personal data, or restricted material.

Use `docker compose down` to stop the database and preserve its local data. **`docker compose down -v` deletes the database volume**.

## Experimental postings read API (synthetic only)

The first versioned read endpoint, `GET /api/v1/postings`, supports limit/offset pagination, a case-insensitive exact employer-name filter, and source attribution. It is intentionally **off by default** (`503`) and restricts results to the uniquely labeled synthetic records created by the PostgreSQL smoke harness.

See the [postings API contract and safe local validation walkthrough](docs/postings-api.md). For a local test against the isolated `dwi_ingestion_test` database only, set `DWI_POSTINGS_API_ENABLED=1` in the backend process environment before starting Uvicorn. This flag does **not** grant third-party source-use permission, and the route must not be publicly deployed in this development state.

## React Postings Explorer (synthetic development preview)

The React application now includes a read-only, database-backed synthetic postings explorer with an employer-name filter, page size and Previous/Next controls, source attribution, and explicit disabled/loading/error/empty states.

For setup and a browser validation checklist, see [Postings Explorer](docs/postings-explorer.md). The frontend expects the local FastAPI server to have `DWI_POSTINGS_API_ENABLED=1` and its `DATABASE_URL` to point to your **isolated** `dwi_ingestion_test` database. The route remains disabled by default and must not be enabled for public deployments.

## Planned MVP

1. Collect public job postings from a small cohort of permitted sources.
2. Normalize employers, geography, technical skills, and supplied salary fields.
3. Deduplicate source records while retaining observations over time.
4. Provide source-attributed, versioned analytical API endpoints.
5. Visualize verified employer, region, and skill trends in the React dashboard.

Initial regions: **Augusta / Fort Eisenhower**, **Fort Meade**, and **San Antonio**, subject to source coverage.

See [project charter](docs/project-charter.md), [architecture](docs/architecture.md), and [data-source evaluation](docs/data-sources.md).

## Data limitations and disclaimer

Posting counts represent *advertised positions*, not hires or total labor demand. Salary coverage is incomplete, clearance mentions do not verify clearance status, and contract-award timing cannot establish causation. DWI will disclose coverage and source attribution. No scraping that violates source terms.

Independent portfolio project. Not affiliated with or endorsed by the U.S. Department of Defense or any federal agency. No open-source license has been selected; public visibility does not itself grant reuse rights.

## TKT-003 — Greenhouse collector (merged; live persistence gated)

The merged read-only adapter targets a **configured employer board**, initially `andurilindustries`. It uses Greenhouse's published GET endpoint and fetches **metadata only** (no descriptions, applicant fields, or candidate information). **It is not scheduled** and does not automatically run when FastAPI starts. For the approved technical-validation procedure on synthetic records, see the [ST-024 operator runbook](docs/ingestion-end-to-end-validation.md).

From the repository root (PowerShell):

```powershell
docker compose up -d db
cd backend
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
.\.venv\Scripts\python.exe -m alembic upgrade head
.\.venv\Scripts\python.exe -m app.ingestion --board andurilindustries
.\.venv\Scripts\python.exe -m pytest -q
```

If there is no virtual environment yet, create it from `backend` with `python -m venv .venv`. The default collector command performs a read-only **preview**, prints a posting count and a five-row sample, and **does not write to PostgreSQL**.

### Persistence — explicit review required

A successful public API GET does not imply permission to bulk store and redistribute employer data. Before any full persistence, review [source-use controls](docs/source-usage-review.md) and applicable Greenhouse/employer conditions. Once the review is complete and permission is established, explicitly enable persistence in the backend process:

```powershell
$env:DWI_SOURCE_USE_APPROVED = "1"
.\.venv\Scripts\python.exe -m app.ingestion --board andurilindustries --employer "Anduril Industries" --persist
```

**Do not set the approval flag until the permission/retention review is resolved.** The flag is a local operational control, not evidence of permission. The command is manually invoked; no polling cadence or scheduler is configured. The pilot currently persists only metadata, including title, source URL and location label, not full HTML descriptions.

To inspect a database **after a permitted persistence run** (from repository root):

```powershell
docker compose exec -T db psql -U dwi -d dwi -c "SELECT status, fetched, inserted, updated, unchanged, rejected, errors FROM ingestion_runs ORDER BY id DESC LIMIT 5;"
docker compose exec -T db psql -U dwi -d dwi -c "SELECT COUNT(*) FROM postings;"
```

The local database DSN defaults to `postgresql+psycopg://dwi:dwi_local_only@127.0.0.1:5432/dwi`, matching the sample Compose credentials; override `DATABASE_URL` in the backend's process environment for any non-local environment. Never reuse local example credentials for deployment. The Alembic migration creates `employers`, `sources`, `postings`, `ingestion_runs`, and `posting_observations`.

**Implementation limitations:** No parallel runs against the same employer board; no automatic vacancy closures, job skill extraction, salary inference, or dashboard API. The database stores the first/last **observed** timestamps separately from Greenhouse's `updated_at`. The source is not guaranteed to represent full defense hiring demand.
