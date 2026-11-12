# TKT-014 — Isolated local pilot PostgreSQL environment

This is a **separate PostgreSQL 17 container**, not another database in DWI's existing development server. It binds exclusively to host `127.0.0.1:5434`, uses its own Docker volume and admin password, and provisions a non-superuser `pilot_app` account. Nothing here enables live Greenhouse collection.

## Initial setup (Windows PowerShell, repository root)

1. Ensure Docker Desktop is running. Do **not** run `docker compose down -v` against existing DWI services.
2. Generate two distinct, strong local passwords and store them in `.env.pilot` in the repository root (already ignored by `.gitignore`):

   ```dotenv
   PILOT_ADMIN_PASSWORD=<unique random admin password>
   PILOT_APP_PASSWORD=<different unique random app password>
   ```

   Never commit, paste into tickets or share those values. Keep `.env.pilot` on your workstation only.
3. Start the dedicated service:

   ```powershell
   docker compose --env-file .env.pilot -f docker-compose.pilot.yml up -d
   docker compose --env-file .env.pilot -f docker-compose.pilot.yml ps
   ```

   The app account is provisioned only when the pilot volume is first initialized. Subsequent changes to `.env.pilot` **do not rotate existing database credentials**.
4. Set `DWI_PILOT_DATABASE_URL` to `postgresql+psycopg://pilot_app:<URL-encoded app password>@127.0.0.1:5434/dwi_local_pilot`. Avoid printing URLs containing passwords. The host port **must be 5434**.
5. Migrate the **pilot database only** using the existing Alembic migrations:

   ```powershell
   cd backend
   $env:DATABASE_URL = $env:DWI_PILOT_DATABASE_URL
   .\.venv\Scripts\python.exe -m alembic upgrade head
   .\.venv\Scripts\python.exe -m alembic current
   Remove-Item Env:DATABASE_URL
   ```

   Only perform this after verifying `DWI_PILOT_DATABASE_URL` targets the correct isolated instance. This temporary `DATABASE_URL` override is for Alembic; the public API **must never** use it. Restore any previous `DATABASE_URL` if you had set one.

## Security model

- `pilot_admin` is the container's bootstrap administrator and is **not** used by the ingestion service.
- `pilot_app` is a separate PostgreSQL role with CONNECT on `dwi_local_pilot` and schema USAGE/CREATE for the existing Alembic migrations and ingestion tables. It has **no superuser role** and no access to DWI's independent development PostgreSQL server.
- Public database CONNECT is revoked on `dwi_local_pilot`. A second PostgreSQL container separates authentication, volumes, and server-side roles from the main `db` container.
- No pilot port is bound to a public interface; the container remains on an independent Docker Compose project network.
- The pilot URL configuration validator rejects non-local hosts, non-pilot database names, connection query overrides, and ports other than 5434.
- `DWI_PILOT_ENABLED` and `DWI_SOURCE_USE_APPROVED` remain disabled unless the operator explicitly enables them. Do not turn them on as part of TKT-014.
- Neither local-only port binding nor separate Docker storage proves host firewall/network configuration or that backups are inaccessible. Validate these separately before using any real source.

## Synthetic verification

From the repository root, verify the container is healthy with `docker compose --env-file .env.pilot -f docker-compose.pilot.yml ps`. After migration, set `DWI_TEST_DATABASE_URL` to the pilot app URL, and execute the **synthetic-only** test:

```powershell
cd backend
$env:DWI_TEST_DATABASE_URL = $env:DWI_PILOT_DATABASE_URL
.\.venv\Scripts\python.exe scripts/postgres_pilot_purge_smoke.py
Remove-Item Env:DWI_TEST_DATABASE_URL
```

The smoke test creates synthetic sources, verifies observations and source-specific deletion, and removes only its own fixtures. It never contacts Greenhouse. Use the database only when it is still intended for disposable synthetic test records.

## Validate credential separation

Test the connection permissions with local `psql` or a short `psycopg.connect` check **without printing passwords**. The pilot app role must connect to `dwi_local_pilot`; a DWI main-app role should fail to authenticate to port 5434, and `pilot_app` should fail to authenticate to the **main** PostgreSQL server on port 5432. Confirm `current_user` is `pilot_app` and `rolsuper` is false.

## Stop, restore and reset

- Stop without deleting data: `docker compose --env-file .env.pilot -f docker-compose.pilot.yml stop`.
- Resume: `docker compose --env-file .env.pilot -f docker-compose.pilot.yml up -d`.
- The volume is persistent. Backups require separate controlled handling; a SQL dump can include retained employer data. Keep backups private and define a retention/deletion policy before any real-data use.
- **Destructive reset:** only after explicit operator approval, `docker compose --env-file .env.pilot -f docker-compose.pilot.yml down -v` erases the pilot volume. Never use this on the main DWI Compose project.
- For source-specific removal, use the existing `pilot_purge_cli` with the matching allowlist and URL. Purge does not clear backups.

## Troubleshooting

- Port 5434 already occupied: stop the other process; do not silently change to port 5432.
- `pilot_app` login fails: check the original `.env.pilot` values and whether the volume was already initialized; editing Compose environment does not rotate credentials.
- Migration errors: check `alembic current` on the pilot URL and verify the `pilot_app` schema CREATE grant.
- Tests report a connection failure: inspect container health and make sure `DWI_TEST_DATABASE_URL` targets the pilot instance, not the main database.
- The public API must continue to use its existing `DATABASE_URL`, not `DWI_PILOT_DATABASE_URL`.

## Outstanding dependency

Greenhouse source-use and retention clarification remains pending. This ticket uses synthetic records only and does not grant approval for any live ingestion.
