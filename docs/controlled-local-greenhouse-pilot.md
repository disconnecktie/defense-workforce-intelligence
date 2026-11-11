# TKT-013 — Controlled Local Greenhouse Metadata Pilot

**Telaryn:** TKT-2CN8-5EYG-9R66  
**Related:** TKT-003, TKT-012  
**Status:** Implementation in progress; do not treat a technical feature as source authorization.

## Purpose

This feature supports a personal, noncommercial local research pilot. DWI is not a replacement for Greenhouse or participating employers' job boards. Preserve employer/board/source identifiers and original URLs; do not redistribute collected live records or full descriptions. Public API and frontend output must remain synthetic-only.

## Phase 1: local policy module

`app.ingestion.pilot_policy` includes:

- `parse_allowlist`: parses an explicit JSON object mapping board tokens to employer names, rejecting malformed input, empty sources and duplicate normalized tokens.
- `require_pilot_source`: requires `DWI_PILOT_ENABLED=1`, an allowlisted token and exact employer match, and rejects sources listed in `DWI_PILOT_SUSPENDED_BOARDS`.
- `require_private_pilot_database`: requires an explicitly configured localhost PostgreSQL database whose name ends in `_pilot`, distinct from the application database. This check cannot replace operating-system, network, or PostgreSQL access controls.

Example *configuration only* (not authorization to execute against the named board):

```powershell
$env:DWI_PILOT_ENABLED = "1"
$env:DWI_PILOT_ALLOWLIST = '{"exampleboard":"Example Employer"}'
$env:DWI_PILOT_SUSPENDED_BOARDS = ""
$env:DWI_PILOT_DATABASE_URL = "postgresql+psycopg://pilot_user:local_password@127.0.0.1:5432/dwi_local_pilot"
```

Do not commit actual credentials or data. The manual entrypoint `python -m app.ingestion.pilot_cli` now uses these controls. The original ingestion CLI and `DWI_SOURCE_USE_APPROVED` persistence gate remain unchanged. No source requests or database writes have been performed by these repository updates.

## Manual entrypoint

- Run `python -m app.ingestion.pilot_cli --board exampleboard --employer "Example Employer" --dry-run --execute` to fetch and validate metadata **without database writes**, after checking applicable access conditions and configuring the allowlist.
- Persistence uses `--persist --execute` instead of `--dry-run --execute` and additionally requires `DWI_SOURCE_USE_APPROVED=1` and a dedicated `DWI_PILOT_DATABASE_URL` pointing at a separate local `_pilot` PostgreSQL database with migrations applied.
- Both modes require `DWI_PILOT_ENABLED=1`, source allowlisting, and no suspension. Never put live records in public API or GitHub.
- The dry-run prints aggregate validation counts only, not titles or job records. **Operator approval flags do not grant third-party rights.**

## Source-specific purge

Use `python -m app.ingestion.pilot_purge_cli` on the dedicated private pilot database. It makes **no external network requests** and works even when collection is suspended. It requires an exact entry in `DWI_PILOT_ALLOWLIST` and the separate `DWI_PILOT_DATABASE_URL` (database name ending `_pilot`).

```powershell
# Preview counts, with no database changes:
.\.venv\Scripts\python.exe -m app.ingestion.pilot_purge_cli --board exampleboard --employer "Example Employer"

# Irreversibly delete that source, its posting observations, posts and ingestion runs:
.\.venv\Scripts\python.exe -m app.ingestion.pilot_purge_cli --board exampleboard --employer "Example Employer" --confirm exampleboard
```

Deletion occurs in a single transaction, children first, and leaves records from other boards untouched. Orphan employers are removed only if no remaining source refers to them. The purge is designed for a quiescent source; suspend all ingestion for that board before executing it. This deletes application database records, **not external backups, logs, archives, or Git history**; those require separate retention review.

## Remaining implementation

1. Verify applicable source conditions and approved fields before live requests; evaluate whether explicit board-specific approval records are needed.
2. Audit field minimization, private PostgreSQL migrations and public API isolation.
3. Verify purge behavior against an isolated PostgreSQL instance and strengthen protection against concurrent ingestion during purge.
4. Complete offline and PostgreSQL integration tests, verify CI, and review before merging.

## Outstanding rights question

Greenhouse has been contacted about noncommercial, local metadata research and historical retention. Its response remains pending. Use of publicly accessible API endpoints by other projects is not proof of authorization for this project.
