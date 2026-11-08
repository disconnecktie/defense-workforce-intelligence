# TKT-002 — Initial Public Data-Source Ingestion Plan

**Status:** Research recommendation for review; not an implemented collector.  
**Updated:** 2026-11-08  
**Telaryn:** TKT-002 / TKT-MK36-MNAV-A9XD

## Decision and rationale

**Recommended first adapter:** Greenhouse **public Job Board API** (read-only GET).  
**First pilot employer:** Anduril Industries, **candidate** board token `andurilindustries`; live API access from the DWI development machine has **not yet been verified**.

Why Greenhouse first:
- Published job data is structured JSON without a read API key.
- Each published job post has a board-scoped ID, canonical URL, title, location label, update time; descriptions and organization structure can be requested with `content=true`.
- A single adapter can later support additional, individually verified employer boards.
- It directly addresses *contractor* employment, unlike USAJOBS' federal vacancy focus.
- It provides a realistic input for historical snapshots and repeat-run deduplication.

**Key tradeoffs:** no universal list of employers, inconsistent/optional salary and clearance fields, some postings spanning multiple locations, no guarantee that every defense employer uses Greenhouse, and no verified right to bulk republish descriptions. A public GET endpoint alone is not a blanket license to redistribute its content. Start with compact derived summaries and source links; review the terms and retention rules of each source/employer before production use.

## Candidate sources and order

| Source | Data | Access / constraints | Priority |
| --- | --- | --- | --- |
| [Greenhouse Job Board API](https://docs.greenhouse.io/job-board) | Employer public postings, IDs, titles, locations, content, departments | Public GET; board token needed; check source terms and rate/retention constraints; no global employer index | **P1: first adapter** |
| [Lever Postings API](https://github.com/lever/postings-api) | Employer public postings and categories | Public postings; site ID needed; paginated; client-side CORS is domain-restricted, so use server-to-server ingestion | P2: second adapter |
| [USAJOBS Search API](https://developer.usajobs.gov/api-reference/get-api-search) | **Federal civilian** vacancy announcements, salary and duty stations | API key + required request headers, separate category from contractors | P3: federal comparator |
| [O*NET Web Services](https://services.onetcenter.org/) | Occupation/skill reference taxonomy | Credential/usage and attribution review required | Later enrichment |
| [USAspending API](https://api.usaspending.gov/) | Federal awards and recipients | Entity resolution and reporting lag; correlation is not causality | Later intelligence features |

## Greenhouse pilot specification

- **Board landing page:** https://job-boards.greenhouse.io/andurilindustries
- **API request:** `GET https://boards-api.greenhouse.io/v1/boards/andurilindustries/jobs?content=true`
- **Authentication:** none for GET according to the vendor's documentation.
- **API output:** top-level `jobs` collection and `meta.total`.
- **Safety:** read-only, identify our client, respect response errors and backoff, moderate polling, set bounded timeout, do not access applications or candidate data.
- **Pilot region:** record **all** available geography from the board, then measure coverage in Augusta/GA, Fort Meade/MD, and San Antonio/TX; do not invent local postings or assume the pilot employer hires in all three regions.
- **Pilot batch:** start with a metadata request to verify board health and basic counts; fetch a bounded sample of individual postings to assess description, salary and clearance completeness before persisting full payloads.

### Manual validation (PowerShell; workstation with network access)

```powershell
$u = "https://boards-api.greenhouse.io/v1/boards/andurilindustries/jobs"
$r = Invoke-RestMethod -Method Get -Uri $u -TimeoutSec 30
"Count: $($r.jobs.Count); reported total: $($r.meta.total)"
$r.jobs | Select-Object -First 5 id,title,updated_at,absolute_url,
  @{Name='location';Expression={$_.location.name}} | Format-Table
```

If 404, access denied, or the board ID is invalid, select another verified Greenhouse employer before implementation. A third-party listing suggests that this employer has a Greenhouse board, but this research environment could not query the live API endpoint directly. **Do not count the pilot as source-validated until the workstation GET succeeds and the results are reviewed.**

## Collection contract

1. Define source and board identity and review published terms.
2. Fetch published **read-only** job data, bounded timeout, careful retry/backoff for transient 429/5xx, no retries for invalid token 404.
3. Record each ingestion run (`started_at`, `completed_at`, HTTP status, source, observed record count, outcome and error category).
4. Validate fields and log missing/invalid values; store source observations with traceable identifiers and only permitted data.
5. Use idempotent upsert key **(source_platform, board_token, posting_id)**. Do not use only `internal_job_id` because it identifies a job rather than a published post.
6. Save `first_seen_at`, `last_seen_at`, and payload/normalized-content hash; record changes without treating `updated_at` as proof of a newly opened role.
7. Mark postings *absent from source* only after a complete successful board fetch and explicit reconciliation. Do not infer hires or closures from missing/failed responses.
8. Separate unmodified facts, normalized fields, inferred annotations and extraction confidence. Do not infer missing pay values.
9. Provide source attribution, coverage statistics, last checked and filter definitions in any DWI aggregates.
10. Keep raw HTML out of the browser, sanitize rendered text, and follow retention rules.

## Validation / quality checks for first implementation

| Check | Expected outcome |
| --- | --- |
| Successful live GET | HTTP 200 with a `jobs` array; store observed count and timestamp |
| Schema sanity | Each usable posting has a stable `id`, `title` and `absolute_url`; nulls logged |
| Idempotence | Collecting identical input twice does not create duplicate `postings` |
| Change detection | Changed source fields update source hash and last seen time |
| Failure handling | Failed fetch does not clear/close prior postings |
| Data completeness | Report percentages for geographic, description, salary and clearance fields |
| Derived classifications | Extracted skill or clearance term keeps evidence span, method, and confidence |
| Accuracy | A source with no postings for an MVP region shows zero **in covered sample**, not zero market demand |
| Provenance | Every reported aggregate can be traced to source, board and observation date |

## Implementation handoff

Create a new Telaryn development ticket for **Greenhouse Pilot Collector & Data Validation** after reviewing this plan.

Initial acceptance criteria should include successful permitted live API GET, verified board token, schema/type validation, idempotent upsert, run-level logging, first/last seen tracking, and source-coverage reports. Data-source choice is provisional until the access/terms check passes.

## Supporting references

- https://docs.greenhouse.io/job-board — Greenhouse vendor documentation for board GET, IDs and `content=true`.
- https://github.com/lever/postings-api — Lever published postings API and browser CORS constraints.
- https://developer.usajobs.gov/guides/authentication — USAJOBS authentication and headers.
- https://developer.usajobs.gov/api-reference/get-api-search — federal job-search scope.
- https://job-boards.greenhouse.io/andurilindustries — candidate employer job board; validate live.
