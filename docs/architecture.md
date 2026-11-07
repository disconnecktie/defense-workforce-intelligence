# Initial Architecture (Proposed)

## Components

1. **Source adapters:** independent collectors with source-specific access rules and rate limiting.
2. **Raw record store:** original public posting payloads plus source URL, retrieved timestamp, and payload hash.
3. **Normalization pipeline:** employer names, location identifiers, skills taxonomy, compensation fields, and clearance text labels.
4. **Analytical database:** PostgreSQL normalized entities, posting identity, and first/last-seen observation history.
5. **API:** FastAPI `/api/v1/...` endpoints for filterable aggregates, records, and data quality metadata.
6. **UI:** React/TypeScript dashboard consuming the same API as potential future Telaryn integrations.

## Candidate domain model

- `sources`: platform, base URL, terms and usage metadata
- `employers`: canonical organization plus source-specific aliases
- `postings`: source ID/URL, employer, title, body metadata, posted date (when supplied)
- `posting_observations`: posting ID, observed-at timestamp, normalized content hash, active/absent status
- `locations`: normalized city/state/region, remote/hybrid signal, raw location text
- `skills`: canonical name, synonyms, taxonomy grouping
- `posting_skills`: many-to-many with extraction evidence and method
- `compensation`: supplied min/max, unit, currency, description, extraction provenance
- `ingestion_runs`: status, start/end, record counts, errors, and source health

This model is a design candidate, not a locked schema. Confirm before writing migrations.

## Data principles

- Record source and observation timestamps for all facts.
- Do not equate disappearance from a feed with a confirmed filled position.
- Separate raw source facts from inferred/normalized classifications.
- Surface missing salary and skill coverage rather than silently imputing it.
- Use idempotent upserts and stable source keys for repeatability.
- Keep credentials in environment variables / secure secret stores, never in Git.
- Maintain API versioning so a future Telaryn consumer can be independent of frontend deployment.

## Delivery boundaries

- One deployable DWI backend and one independent UI, with Docker-based local development.
- Telaryn manages work items and acceptance criteria; DWI itself does not depend on Telaryn for collection or operation.
