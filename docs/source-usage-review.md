# Source-use review and collection controls (TKT-003)

**Status: unresolved third-party reuse rights — do not enable bulk persistence yet.**  
**Reviewed:** 2026-11-08

## Verified technical capabilities

- [Greenhouse Job Board API](https://docs.greenhouse.io/job-board) says **GET** endpoints for public job-board data do not require authentication.
- The documented `GET /v1/boards/{board_token}/jobs` endpoint returns a `jobs` array and `meta.total`; its `content=true` option adds job descriptions, office/department details. This collector deliberately **does not request `content=true`**.
- [Greenhouse API overview](https://support.greenhouse.io/hc/en-us/articles/10568627186203-Greenhouse-API-overview) states the Job Board API is primarily designed for a company's own public job board/career site; **requests may be rate-limited for security and traffic reasons**.
- On 2026-11-08, the DWI developer performed a **manual read-only GET** to Anduril's public board API token `andurilindustries` and observed 2,600 jobs, sample IDs, titles, source URLs and update times. This validates *connectivity*, not redistribution permissions.

## Outstanding authorization questions

1. Identify the actual applicable Greenhouse public Job Board API usage rules for **independent third-party analytics**, and the actual employer/job-board terms for the proposed dataset.
2. Confirm whether retaining posting metadata and storing repeated historical observations is permitted; determine retention, deletion, attribution and redistribution constraints.
3. Confirm acceptable polling frequency and rate caps. A public endpoint and successful HTTP 200 do **not** establish an unrestricted access or republication license.
4. Confirm any restrictions on salary/clearance extraction, if future work expands beyond metadata.
5. Record evidence and review date before setting `DWI_SOURCE_USE_APPROVED=1`; do not treat setting this flag as proof of permission. If permissions cannot be established, switch to an explicitly licensed data source or data set.

## Implemented safeguards

- **Read-only GET** for published job metadata; no application endpoints, candidate fields or descriptions.
- Manual command by default produces a preview with no database writes.
- Persistence explicitly requires both `--persist` and the `DWI_SOURCE_USE_APPROVED=1` process environment variable, **after review**.
- No scheduler or automatic polling in the repo.
- Board token validated, fixed known Greenhouse API host, request timeout, bounded retries and response structure validation.
- No data deletion or "job filled/closed" inference on failed or incomplete responses.
- Source URL and source-side update timestamp preserved for attribution.
- Automated tests use synthetic job data; CI does not fetch employer postings.

## Suggested approval record

Source/employer, URLs and terms reviewed, date, reviewer, allowed fields and frequency, retention/deletion requirement, attribution/citation requirement, and decision (approved/restricted/not approved).

**Disposition:** Initial collector development and synthetic DB testing may proceed. Do not mark the source-permission acceptance criterion complete until the actual conditions have been assessed.
