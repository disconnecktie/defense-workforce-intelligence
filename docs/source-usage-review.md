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

## TKT-003 Python collector live preview validation (developer workstation, 2026-11-08)

Developer ran:
```powershell
.\.venv\Scripts\python.exe -m app.ingestion --board andurilindustries
```

Reported CLI JSON confirmed `mode: "read-only preview (no database writes)"`, `board: "andurilindustries"`, `fetched: 2600`, and five sample posting ID/title pairs:

| Source ID | Title |
| --- | --- |
| 4802172007 | 2026 Early Career Electrical Engineer |
| 5176254007 | 2026 Early Career Manufacturing Engineer |
| 4802167007 | 2026 Early Career Mechanical Engineer |
| 4802146007 | 2026 Early Career Software Engineer |
| 5271672007 | 2027 Business Operations Engineer Intern |

This establishes that the **TKT-003 Python collector**, not merely an ad hoc PowerShell GET from TKT-002, successfully retrieved live public listing metadata from the selected board. The invocation did not request persistence or write to PostgreSQL. It does not resolve third-party bulk storage or redistribution permissions. The developer has also reported 17 passing local pytest tests. Local Alembic revision remains to be separately verified; GitHub CI passed its PostgreSQL migration and synthetic ingestion checks.

## Public terms research — preliminary, not legal approval (2026-11-08)

- [Greenhouse Job Board API](https://docs.greenhouse.io/job-board): publicly available GET responses require **no authentication**. The documentation presents the API primarily for publishing a company's own careers pages. It does **not** expressly grant third-party historical storage, bulk aggregation, or redistribution rights.
- [Greenhouse API overview (updated November 2, 2026)](https://support.greenhouse.io/hc/en-us/articles/10568627186203-Greenhouse-API-overview): the Job Board API is designed for a company's own career/application site; Greenhouse warns that requests **may be rate limited** for traffic/security reasons.
- [Greenhouse User Agreement](https://my.greenhouse.io/users/agreement): contains restrictions on automated access, resale, and certain uses of the service for covered users. Its applicability to an unauthenticated public board GET by an unaffiliated researcher is **not established** by this review.
- [Greenhouse Master Subscription Agreement](https://www.greenhouse.com/master-subscription-agreement): contains API limits and customer/fair-use provisions for contracting customers. **Do not claim this proves authorization or prohibition for an unaffiliated user of public GET endpoints** without a more specific terms analysis.
- Employer-specific conditions and permission for DWI's proposed reuse of the Anduril board have **not** been confirmed.

**Decision:** retain the default preview-only mode and manual, synthetic-data tests. Do not represent TKT-003's source-authorization acceptance criterion as complete. Before production collection, seek clear authorization/licensing for storing historical metadata and derived analytics, including employer restrictions and polling cadence. Consider a documented permissively licensed alternative if this cannot be established.
