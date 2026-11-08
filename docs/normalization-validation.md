# TKT-003 — Posting validation and normalization rules

**Scope:** Greenhouse public Job Board **metadata** from the manually executed read-only collector. This document describes what the current code validates before inserting to PostgreSQL. It does **not** authorize live data persistence.

## Input contract and field treatment

| Field | Required? | Validation and normalization | Invalid case |
| --- | --- | --- | --- |
| `id` | Yes | Positive ASCII decimal identifier, at most 100 characters; converted to a string for source-scoped identity | Reject record: missing, zero, float, bool, non-ASCII numerals, symbols, overlong |
| `title` | Yes | Non-blank string, up to 4,000 characters; preserve raw source text including outer whitespace | Reject record |
| `absolute_url` | Yes | HTTPS public DNS hostname, no credentials, controls, backslashes, local names or IP literals; up to 4,096 characters | Reject record |
| `location.name` | No | String up to 4,000 chars, preserves source label *as-is*, including multiple locations; empty/blank becomes null | Reject record for wrong type or overlong |
| `internal_job_id` | No | Text/integer up to 100 chars, stored as a string; empty becomes null | Reject record for bool, float, object/list, overlong |
| `requisition_id` | No | Text/integer up to 100 chars, stored as a string; empty becomes null | Reject record for bool, float, object/list, overlong |
| `first_published` | No | If present, ISO timestamp with explicit timezone; normalized to UTC. Missing = null | Reject record for malformed or timezone-naive value |
| `updated_at` | No | If present, ISO timestamp with explicit timezone; normalized to UTC. Missing = null | Reject record for malformed or timezone-naive value |

**Why UTC?** The same instant may be written with a `-05:00` offset or `Z`. Both should produce the same normalized value and content hash. This prevents false change events when the offset representation changes.

**Why no guessed fields?** The collector does not infer salary, clearance, technical skills, office location, city/state or a hire date from title/location text. Those are separate future enrichments requiring attribution and evidence. A Greenhouse `updated_at` timestamp is **not** an actual job-opened timestamp, and `first_seen_at` means first observed by DWI.

## Hash, identity and error policy

- Normalize the source data first; compute a SHA-256 content hash from the actual stored source fields (with stable key ordering and UTC-normalized timestamps).
- The database uniqueness key is **(Greenhouse source board, posting ID)**, not job title or requisition ID.
- Optional field omissions stay null. Invalid supplied types count as **rejected** rather than silently storing `"False"`, `"{}"`, or other fabricated strings.
- Reject malformed individual postings and report rejection counts, while accepting other valid records in the completed source batch. Invalid records never cause existing postings to be deleted or marked filled.
- The client checks the `meta.total` count when present. A partial feed with mismatching reported count fails before ingesting.
- Any successful run records one observation per accepted, unique posting. Failed fetches do not imply vacancy closures.
- Both incoming `title_raw` and `location_raw` retain source wording; parsing geography and titles is **out of scope** for this subtask.

## Synthetic edge-case regression tests

`backend/tests/test_normalization_validation.py` covers omitted optional data, Unicode/invalid/oversized IDs, invalid URLs (local/IP/credentials/insecure schemes/invalid ports), malformed titles/location/optional identifiers, timezone-naive timestamps, equivalent UTC timestamps, and batches mixing valid and invalid records.

All tests use **synthetic data and no external API calls**. PR CI checks also run an isolated synthetic PostgreSQL insertion/repeated-ingestion smoke test.

## Known limits and follow-on work

- No salary, skills, clearance or geolocation inference is performed; no HTML descriptions are retrieved or retained.
- URL checks validate the **shape** of a source link, not whether that link is truthful, accessible or owned by the employer. We never fetch or follow those source URL values.
- This MVP does not have per-record rejection-reason logs or rejected-payload retention; the ingest run tracks an aggregate rejected count. More diagnostic observability belongs to the TKT-003 logging subtask.
- No concurrent ingestion for the same board. No automated scheduler or production ingestion.
- Live metadata persistence remains blocked by the source-use review described in [source-usage-review.md](source-usage-review.md).

## Validation commands (PowerShell from backend)

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m pytest -q tests/test_normalization_validation.py
```
