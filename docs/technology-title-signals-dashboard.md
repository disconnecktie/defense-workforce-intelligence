# TKT-009 — Technology Title Signals Dashboard (synthetic-only)

## Purpose

The DWI React application now visualizes the existing read-only GET /api/v1/title-signals API as a **Technology title mentions** panel below Postings Explorer and Source Coverage. This measures **literal technology names in synthetic posting titles**, not advertised skill requirements, active jobs, real employer demand, or market trends. The title keyword rule set is versioned as title_keywords_v1.

This slice does **not** require a migration, new frontend packages, live collection, or API changes.

## Design and interaction

- **Summary:** current distinct source postings scanned, number of titles matching at least one of the recognized terms, number without a recognized term, and the percentage of titles with at least one match.
- **Seven-term comparison:** separate bars for Python, Kubernetes, AWS, Azure, Docker, PostgreSQL, and React, including zero-count categories. Each bar's width is its share of **all scanned titles**, not its share of total mentions.
- **Non-additivity:** one title can mention multiple technologies. Term counts/percentages can add up to more than the number/percentage of matched titles.
- **Source evidence:** for each term with matches, native keyboard-friendly expandable examples show up to three source posting references, full stored title, literal highlighted match span and character offsets. They are a sample, not a paginated listing of all matches.
- **Shared employer scope:** the exact-employer filter in Postings Explorer already applies to Source Coverage and also filters Technology title mentions; clearing it restores all matching synthetic records.
- **Refresh:** a panel-level button refreshes technology signals. The postings explorer's existing full-page refresh also refreshes this panel.
- **Error handling:** loading, disabled backend (503), unexpected payload/network error, zero-posting dataset, and zero-count terms are separately represented. Requests are aborted on filter/refresh changes.
- **Scope:** all seven terms and the exact available evidence are supplied by the backend. No frontend text mining, count inference, or independent data enrichment.

## Local acceptance walkthrough (PowerShell)

Use only the isolated local PostgreSQL test database. Do not enable synthetic development API routes on a public endpoint.

When reviewing this branch before merging:

1. From your repository root, ensure your working tree is clean; fetch and switch to the feature branch:

   ~~~powershell
   git fetch origin
   git switch --track origin/feature/tkt-009-title-signals-dashboard
   ~~~

2. Keep Docker's database container running: docker compose up -d db.
3. In one terminal, from backend, set DATABASE_URL to your existing **dwi_ingestion_test** connection and enable the synthetic-only API:

   ~~~powershell
   cd C:\dev\defense-workforce-intelligence\backend
   $env:DATABASE_URL = "postgresql+psycopg://dwi:dwi_local_only@127.0.0.1:5432/dwi_ingestion_test"
   $env:DWI_POSTINGS_API_ENABLED = "1"
   .\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
   ~~~

4. In another terminal:

   ~~~powershell
   cd C:\dev\defense-workforce-intelligence\frontend
   npm install
   npm run build
   npm run dev
   ~~~

5. Open http://127.0.0.1:5173 and scroll to **Technology title mentions**.

For the operator's observed snapshot of seven synthetic postings across five test boards, including two explicit-term fixture titles, the expected metrics are:

| Measure | Expected |
| --- | ---: |
| Stored titles scanned | 7 |
| Titles with a recognized term | 2 |
| Titles without any recognized term | 5 |
| Title mention rate | 28.6% |
| Python / Kubernetes / AWS / React | 1 title each |
| Azure / Docker / PostgreSQL | 0 |

A newer synthetic smoke run adds test records and changes these totals; rely on the API rather than fixed counts if you rerun it.

### Verify evidence and filtering

- Expand Python: the sample should show "Synthetic Python / AWS Platform Engineer" with only "Python" highlighted. The backend evidence offsets should match the highlight.
- Expand Kubernetes: the sample should show "Synthetic K8s and React.js Developer", highlighting "K8s". Expand React: the same posting should highlight "React.js".
- Apply the exact employer name from the row that contains those two fixtures using the Postings Explorer. Confirm the title-signal summary changes to **two scanned / two matched / 100.0%**, and source coverage is filtered to the same employer. Clear the filter to restore all entries.
- Choose an employer whose only title is "Synthetic Senior Systems Engineer"; verify **one scanned / zero matched / 0.0%**, and all seven bars display zero.
- Enter an unmatched employer; expect zero scanned, a distinct no-results state, and **N/A** instead of a fabricated percentage.
- Stop FastAPI; expect network-error messaging. Restart without DWI_POSTINGS_API_ENABLED; expect the disabled/503 banner instead.
- Check keyboard operation of source example expanders and mobile responsiveness.

After testing, stop your local development processes with Ctrl+C and unset or restore the test-only backend environment variables. Do not set DWI_SOURCE_USE_APPROVED=1, persist live employer data, or use Docker Compose down -v as routine cleanup.

## Interpretation constraints

The seven-term v1 dictionary is intentionally small. **No-match does not mean a job requires no technology skills**, and a literal title mention does not prove a term is required or used daily. Since descriptions are not ingested, DWI must not describe these numbers as comprehensive "skill demand" or "skills required".

Source naming conventions are **not** access control or permission to redistribute real employer postings. Third-party source-use, rate and retention authorization remains an independent blocker; see [source-use review](source-usage-review.md).

Refer to [Title Signals API](title-signals-api.md), [Data Quality Dashboard](data-quality-dashboard.md), and [initial data dictionary](data-dictionary.md).
