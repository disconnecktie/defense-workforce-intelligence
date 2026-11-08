# DWI Initial Posting Data Dictionary (TKT-002)

**Scope:** First Greenhouse public-board ingestion slice. This is a design contract, not an implemented schema. **Nullable means missing information stays missing.**

| DWI field | Source / derivation | Requirement | Normalization / caveat |
| --- | --- | --- | --- |
| `source_platform` | Constant `greenhouse` | Required | Explicit source identifier |
| `board_token` | Collector config | Required | Keep original identifier, lower-case for keys |
| `source_posting_id` | `jobs[].id` | Required | Convert to string; combine with platform + board for stable unique key |
| `source_internal_job_id` | `jobs[].internal_job_id` | Nullable | Distinct from published posting ID; may be null |
| `source_requisition_id` | `jobs[].requisition_id` | Nullable | Not globally unique |
| `employer_raw` | Validated board identity/config | Required | Preserve exact source name; avoid guessing subsidiaries |
| `employer_canonical_id` | Controlled alias lookup | Nullable | Canonicalize only when justified by evidence |
| `title_raw` | `jobs[].title` | Required | Preserve original title |
| `title_normalized` | Derived title rules | Nullable | Keep raw and parsing version |
| `source_url` | `jobs[].absolute_url` | Required | Canonical public source hyperlink |
| `location_raw` | `jobs[].location.name` | Nullable | Preserve verbatim, may describe several locations |
| `city`, `state`, `country` | Location parser | Nullable | Do not collapse ambiguous or multi-location records |
| `region_code` | Geo mapping rules | Nullable | Fort Eisenhower/Augusta, Fort Meade/MD, San Antonio/TX; do not equate nearby places without clear rules |
| `work_arrangement` | Explicit source text | Nullable | `on_site`, `hybrid`, `remote`, `unknown`; only when supported |
| `department_raw` | `jobs[].departments` with content | Nullable | Multi-valued taxonomy; no assumption that department denotes role |
| `office_raw` | `jobs[].offices` with content | Nullable | May not equal work location |
| `description_html` | `jobs[].content` with content | Conditional | Retain only if licensing/terms allow; sanitize; never assume safe to render |
| `description_text` | HTML-to-text transformation | Nullable | Normalize whitespace, retain evidence offsets when possible |
| `first_published_at` | Posting detail if returned | Nullable | Do not treat `updated_at` or first seen as publish date |
| `source_updated_at` | `jobs[].updated_at` | Nullable | Source-side edit timestamp, not necessarily opening date |
| `first_seen_at` | Collector timestamp | Required | First successful observation within DWI; not posting date |
| `last_seen_at` | Collector timestamp | Required | Most recent successful observation |
| `content_hash` | Canonicalized selected source fields | Required | Distinguish content changes without duplicates |
| `salary_min`, `salary_max` | Structured field when present, otherwise clearly identified parsed text | Nullable | Numeric amount, units, pay period, currency, source span |
| `salary_period`, `salary_currency` | Source or parse | Nullable | Avoid comparing hourly and annual unnormalized; don't annualize silently |
| `clearance_required_raw` | Explicit posting text | Nullable | Preserve original mention (e.g., TS/SCI); do not infer from employer |
| `clearance_normalized` | Controlled rules | Nullable | Classification = stated requirement, not cleared population |
| `skills_raw_matches` | Explicit posting text | Nullable | Preserve term, evidence and extraction-method version |
| `skills_normalized` | Skill dictionary | Nullable | Aliases (e.g., `K8s` → `Kubernetes`); false-positive checks |
| `ingestion_run_id` | Collector generated | Required | Trace record to source fetch and run |
| `observation_status` | Collection reconciliation | Required | `observed`, `absent_after_successful_fetch`, `unknown`; no assertion of filled job |

## Normalization decisions

### Identity and duplicates
- The **post** is identified by `(source_platform, board_token, source_posting_id)`. Do not merge posts just because their title or internal job ID matches.
- Repeated observations are not new jobs; distinct locations may reflect separate postings or a single multi-location post.
- Store a canonical/normalized content hash and the observed timestamp. Later schema may split postings from their observation history.

### Technical skills (initial seed dictionary)
- `Python`: `python` as a programming language in context; exclude unrelated uses.
- `Kubernetes`: `kubernetes`, `k8s`.
- `AWS`: `aws`, `amazon web services`.
- `Azure`: `microsoft azure`, `azure` in platform context.
- `Docker`: `docker` when software/container context.
- `PostgreSQL`: `postgresql`, `postgres`.
- `React`: `react.js`, `reactjs`, `react` with frontend context.

For every extracted match, save the canonical label, original term, matched evidence, rule version, and confidence. Counts represent postings **mentioning** a skill, not proven employee skill holdings.

### Geospatial rules
- Keep the raw employer location label.
- `Augusta, GA` and `Fort Eisenhower, GA` map to a defined Augusta-area analysis region, but different city strings are not rewritten as the same *place*.
- `Fort Meade, MD` should not implicitly equal all of Baltimore or Washington, DC.
- `San Antonio, TX` maps to its defined local region; remote-only roles remain separate.
- Multi-location postings may contribute to separate regional membership while counting as **one distinct posting** in global totals; report counting methodology.

### Salary and clearance rules
- `salary_min/max` absent = **unknown**, not zero. Never calculate a market median from salary-present postings without coverage and selection warnings.
- Keep hourly/annual period and currency to avoid mixing incomparable figures.
- `TS/SCI`, `Secret`, `Public Trust`, `polygraph` are different requirements and should be recorded as expressly advertised, not inferred.

## Suggested reporting metadata

Every aggregate response should carry `as_of`, `sources_included`, `boards_checked`, `posting_count`, `location_coverage_pct`, `salary_coverage_pct`, `clearance_mention_coverage_pct`, and the applicable deduplication/counting rule.

## Source references

Greenhouse Job Board API field reference: https://docs.greenhouse.io/job-board
