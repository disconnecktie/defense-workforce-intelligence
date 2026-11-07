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

**Scope of TKT-001:** PostgreSQL availability, not application table creation.
Schema migrations and database-backed API endpoints will be implemented in later
tickets. The `/health` endpoint reports API liveness, **not** DB readiness.

To stop the service without deleting data: `docker compose down`.
Use `docker compose down -v` **only** when you intend to delete local database data.
