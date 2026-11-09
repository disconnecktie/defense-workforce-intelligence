# TKT-008 — Explicit title-term signals (synthetic-only)

## Purpose

This milestone introduces a **conservative, evidence-backed technical-title keyword API**. The endpoint scans the **current raw posting title** for seven explicitly spelled-out technology names. It does **not** infer job requirements, employee skillsets, occupational taxonomy or market demand.

Existing Greenhouse ingestion retains **metadata only**. Job descriptions and skill requirement sections are **not available** to this API, so do not label its results as "skills required by employers".

## Endpoint

`GET /api/v1/title-signals`

Optional query string:

- `employer`: case-insensitive **exact** employer name, 1–200 characters, must not be blank. Without a filter, scans all eligible synthetic source postings.

The route is disabled by default (`503`) and requires `DWI_POSTINGS_API_ENABLED=1` in the **local backend**. It uses the same synthetic-only source predicate as the postings and coverage APIs: `greenhouse` source platform, board tokens beginning with the **literal** `synthetic_` prefix, and names beginning with `Synthetic CI Employer `. This is a development convention and not third-party-use authorization.

### Response contract

- `data_scope = "synthetic_only"`
- `counting_rule = "distinct_source_postings"`: one row per `(source, external_posting_id)`, **not** historical observation events or distinct job openings across employers.
- `source_field = "title_raw"`
- `interpretation = "explicit_title_mentions_not_verified_skill_requirements"`
- `method_version = "title_keywords_v1"`
- `postings_scanned`: all eligible current source-specific postings, regardless of any match.
- `postings_with_any_term`: postings whose titles contain at least one recognized term.
- `postings_without_any_term`: the remainder.
- `title_mention_rate_pct`: `100 × postings_with_any_term / postings_scanned` rounded to one decimal; `null` if there are no postings. This is not true skills coverage.
- `latest_observed_at`: maximum stored last-observed date among scanned postings, or `null`.
- `terms`: all seven canonical terms are returned, even at zero, with `postings_with_title_mention` counts and up to three auditable examples. Each example includes synthetic source board, platform, external ID, stored title, matched substring, and character offsets.

A posting may mention more than one technology: **term counts can sum to more than `postings_scanned`**. A repeated word/alias in one title contributes one count for that term.

### Controlled v1 dictionary

| Canonical term | Accepted title forms |
| --- | --- |
| Python | `Python` |
| Kubernetes | `Kubernetes`, `K8s` |
| AWS | `AWS`, `Amazon Web Services` |
| Azure | `Azure`, `Microsoft Azure` |
| Docker | `Docker` |
| PostgreSQL | `PostgreSQL`, `Postgres` |
| React | `React`, `React.js`, `ReactJS` |

All matches are case-insensitive and require boundaries so, for example, `Reactivate` does not match `React`, and `Pythonista` does not match `Python`. Evidence preserves original spelling, source title and offsets.

**Important limitation:** This is still a keyword heuristic. Even an explicit title word can be ambiguous or non-representative of all advertised qualifications; it does not establish how many jobs *require* the term. The rule version exists for reproducibility; no model confidence or market representativeness is claimed.

### Example (illustrative only)

```json
{
  "data_scope": "synthetic_only",
  "counting_rule": "distinct_source_postings",
  "source_field": "title_raw",
  "interpretation": "explicit_title_mentions_not_verified_skill_requirements",
  "method_version": "title_keywords_v1",
  "postings_scanned": 2,
  "postings_with_any_term": 2,
  "postings_without_any_term": 0,
  "title_mention_rate_pct": 100.0,
  "latest_observed_at": "2026-11-08T21:00:00Z",
  "terms": [
    {
      "term": "Python",
      "postings_with_title_mention": 1,
      "examples": [
        {
          "posting_id": 1,
          "platform": "greenhouse",
          "board_token": "synthetic_example",
          "external_posting_id": "9090001",
          "title": "Synthetic Python / AWS Platform Engineer",
          "evidence": "Python",
          "match_start": 10,
          "match_end": 16
        }
      ]
    }
  ]
}
```

The single-element `terms` array above is **abridged for readability**; the actual API always returns seven canonical terms, including zero-count ones. All values are synthetic examples.

## Local PowerShell validation

After review/merge, pull `main` and use the same isolated test database as ST-024. Do not connect the enabled development route to a public service.

In your backend PowerShell window (stop Uvicorn first with Ctrl+C if already running):

```powershell
cd C:\dev\defense-workforce-intelligence\backend
$env:DATABASE_URL = "postgresql+psycopg://dwi:dwi_local_only@127.0.0.1:5432/dwi_ingestion_test"
$env:DWI_TEST_DATABASE_URL = $env:DATABASE_URL
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe scripts\postgres_smoke.py
$env:DWI_POSTINGS_API_ENABLED = "1"
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

The enhanced PostgreSQL smoke script now creates **two additional fictitious title fixtures on a new synthetic test board**, and verifies positive keyword matches via a FastAPI request on actual PostgreSQL. Repeating the script inserts a **new test source** and does **not** increase the existing board's posting count.

In a second terminal:

```powershell
Invoke-RestMethod "http://127.0.0.1:8000/api/v1/title-signals" |
    ConvertTo-Json -Depth 10
```

The original four synthetic smoke-test titles (`Synthetic Senior Systems Engineer`) have **no** recognized v1 technology terms, which is expected; the newly added synthetic title fixtures produce literal mentions of Python, AWS, Kubernetes (`K8s`) and React. The API's totals cover all eligible synthetic postings currently in your local test DB.

### Validation and future steps

Automated offline tests verify bounded aliases and negatives, one count per term per distinct source posting, evidence offsets, exact employer filtering, zero records/undefined ratios, no writes, disabled default and exclusion of non-synthetic employer sources. GitHub CI also runs a real PostgreSQL smoke assertion for positive signal counts.

Next: a separate frontend visualization of **title-term mentions**, explicitly labeled as a test-data signal. Actual skill-demand analysis requires authorized descriptions or structured skill fields, extraction evidence and confidence rules, separate geography normalization and data-source coverage caveats. Pending source-use permissions remain an independent blocker; do not set `DWI_SOURCE_USE_APPROVED=1` merely to get more records.

See [data dictionary](data-dictionary.md), [coverage API contract](source-coverage-api.md) and [source-use limitations](source-usage-review.md).
