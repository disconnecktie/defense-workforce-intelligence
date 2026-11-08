# Database service

For local development, PostgreSQL 17 runs through the root `docker-compose.yml`:

```sh
docker compose up -d db
docker compose ps
docker compose exec db pg_isready -U dwi -d dwi
```

The container maps port 5432 to **127.0.0.1 only**, and stores its data in the
`postgres_data` Docker volume. The default password is only for disposable
local development; override it in the untracked root `.env` file.

**Current status:** TKT-001 established PostgreSQL availability. TKT-003 has
since implemented the initial Greenhouse ingestion schema through Alembic
revisions `0001_initial_ingestion`, `0002_observation_snapshots` and
`0003_ingestion_run_metrics`; migrations are executed separately, not at
FastAPI startup. Database-backed *analytical API endpoints* remain future work.
The `/health` endpoint reports API liveness, **not** DB readiness.

For a safe, reproducible synthetic ingestion test in an **isolated local**
`dwi_ingestion_test` database, use the
[ST-024 operator runbook](../docs/ingestion-end-to-end-validation.md).
Do not run the testing script or `alembic downgrade` against a non-disposable
database. Live employer-data persistence remains blocked pending source-use
authorization.

To stop the service without deleting data: `docker compose down`.
Use `docker compose down -v` **only** when you intend to delete local database data.
