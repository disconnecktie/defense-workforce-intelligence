# TKT-007 — Synthetic Data Quality Dashboard

The DWI React development UI now consumes the **`GET /api/v1/coverage`** endpoint in addition to the existing postings listing. The dashboard summarizes stored source-specific synthetic records and their **metadata completeness**, not actual labor-market coverage.

## Dashboard elements

- **Stored postings:** distinct current source-specific posting rows (not historical observation events, active vacancies or hires).
- **Synthetic sources:** all matching source boards, **including zero-posting sources**.
- **Synthetic employers:** distinct matching employer entities.
- **Completeness bars** for nonempty raw location, explicit source publication date and source update timestamp. Each displays the numerator, denominator and percentage provided by the backend.
- **Source breakdown** with one row per synthetic board showing its own posting count, three completeness rates and latest observation timestamp. Paged at five sources per page.
- The exact-employer filter from the Postings Explorer applies to both panels; clicking a source employer filters the entire view to that employer.
- Explicit **loading**, **disabled**, **unavailable** and **empty** states. Network requests are aborted when filters, page or refresh state changes.
- Clear distinction between **global filtered metrics** and the **current source page**, and a visible synthetic-data warning.

### Interpreting percentages

`100%` raw location completeness says that *every stored row has some source-provided location text*. It does **not** prove that those labels are resolved to a geographic region or that the source covers the whole market.

`0%` source publication date completeness says no stored row has an explicit publication date. **First-seen** timestamps are not substituted for that field. `null` percentage in the API is displayed as **N/A**, meaning there is no denominator. A real `0.0%` is displayed as `0.0%`.

All values originate from the locally configured synthetic-only coverage endpoint. The React application performs no collection, writes, field inference, or public source API calls.

## Local PowerShell walkthrough

The user previously validated the API on `127.0.0.1:8000` with `dwi_ingestion_test`, returning four synthetic records across four boards; that is a **test-fixture snapshot**, not a required fixed count.

After reviewing and merging this frontend PR, from the repository root:

```powershell
cd C:\dev\defense-workforce-intelligence
git switch main
git pull --ff-only origin main
```

**API terminal:** Use the isolated development database only; do not point the enabled synthetic API at a production database.

```powershell
cd C:\dev\defense-workforce-intelligence\backend
$env:DATABASE_URL = "postgresql+psycopg://dwi:dwi_local_only@127.0.0.1:5432/dwi_ingestion_test"
$env:DWI_POSTINGS_API_ENABLED = "1"
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

**Frontend terminal:**

```powershell
cd C:\dev\defense-workforce-intelligence\frontend
npm install
npm run build
npm run dev
```

Open `http://127.0.0.1:5173`. Expected for the four-record synthetic snapshot (unless more smoke data was inserted):

| Field | Expected |
| --- | ---: |
| Matching stored postings | 4 |
| Synthetic sources | 4 |
| Synthetic employers | 4 |
| Raw location completeness | 100.0% (4 of 4) |
| Source publication date completeness | 0.0% (0 of 4) |
| Source updated timestamp completeness | 100.0% (4 of 4) |

### Browser acceptance checklist

1. Verify these totals and percentages match `Invoke-RestMethod "http://127.0.0.1:8000/api/v1/coverage?limit=5"`.
2. Confirm the source table lists **four** synthetic boards with matching board tokens, and that its count is **not** mislabeled as defense-sector market coverage.
3. Click an employer in either table; verify both panels filter to that **exact** synthetic employer and percentages/totals recompute. Clear the filter and verify they restore.
4. Confirm the source pagination works when there are more than five sources (rerun **synthetic** PostgreSQL smoke as needed; no live ingest).
5. Stop FastAPI and confirm both panels display an error. Restart without `DWI_POSTINGS_API_ENABLED=1` and confirm the `503` disabled states.
6. Verify horizontal scrolling and keyboard focus on a narrow browser viewport. Review missing data as `0.0%` where a denominator exists and `N/A` only for zero-posting sources.

When done, stop the development processes and unset any test-only environment variables or restore previous values. Never run `docker compose down -v` as routine cleanup, and never enable the local development API publicly.

See [coverage API contract](source-coverage-api.md), [postings explorer](postings-explorer.md), and [source-use review](source-usage-review.md).
