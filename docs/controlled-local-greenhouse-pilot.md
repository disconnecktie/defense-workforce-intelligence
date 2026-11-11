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

Do not commit actual credentials or data. **This phase does not wire those settings to the ingestion CLI, run network requests, connect to PostgreSQL, or enable any live ingestion.** The existing `DWI_SOURCE_USE_APPROVED` persistence gate is unchanged.

## Remaining implementation

1. Wire the manual command into these fail-closed controls while preserving existing CLI behavior and tests.
2. Require explicit source terms review and avoid new live requests until applicable source conditions are met; provide a non-persistent offline/synthetic test mode.
3. Restrict retained fields; verify private database migrations and prevent public endpoints from selecting real records.
4. Add stop/purge operations for a single source, with dependency-safe deletion ordering and operator confirmation.
5. Test retry/backoff, data minimization, source attribution, dry run, PostgreSQL persistence, and end-to-end isolation. Verify CI before merging.

## Outstanding rights question

Greenhouse has been contacted about noncommercial, local metadata research and historical retention. Its response remains pending. Use of publicly accessible API endpoints by other projects is not proof of authorization for this project.
