# Defense Workforce Intelligence (DWI)

> Public-data analytics for technology workforce demand across the U.S. defense sector.

**Status:** Planning / early development. No production data pipeline or live dashboard exists yet.

## Purpose

Defense Workforce Intelligence (DWI) is a planned data intelligence platform for aggregating, normalizing, and analyzing publicly available defense-sector job postings, skill requirements, advertised compensation, locations, and (in a later phase) federal contract awards.

Its goal is to help analysts, job seekers, and technical leaders understand **what skills employers are seeking, where demand is concentrated, and how patterns change over time**.

## Why it matters

Defense technology hiring information is spread across corporate career sites, federal job boards, and public datasets. DWI aims to transform those fragmented sources into a transparent, reproducible analytical view rather than another job listing site.

The project also demonstrates practical capabilities in Python development, API integration, ETL, data quality, historical analysis, backend engineering, and interactive data visualization.

## Planned initial capabilities (MVP)

- Collect postings from selected public, permitted job feeds.
- Normalize employers, job titles, locations, and technical skills.
- Deduplicate postings while retaining first-seen/last-seen history.
- Explore posting counts by employer, region, skill, and source.
- Compare **advertised** compensation only where available, including salary type, currency, and reporting completeness.
- Drill down to source postings with clear attribution and observation timestamps.
- Display coverage, extraction confidence, and data freshness.

The initial geographic focus is **Augusta, GA / Fort Eisenhower; Fort Meade, MD; and San Antonio, TX**. Coverage will expand based on verified feed availability.

## Planned architecture

```text
Permitted public feeds
       |
       v
Python collectors -> validation / normalization -> PostgreSQL
                                                   |
                                                   v
                                              FastAPI (v1)
                                                   |
                                        +----------+----------+
                                        |                     |
                                   React dashboard     Future Telaryn view
```

**Proposed stack:** Python, FastAPI, PostgreSQL, React, TypeScript, Docker, and automated tests.

**Project management:** Development work is tracked in **Telaryn**. DWI will remain an independent application and repository, with a versioned API suitable for a future Telaryn integration.

## Roadmap

1. **Foundation:** repo standards, local development, database schema, test setup.
2. **Ingestion:** validate source access; ingest, normalize, deduplicate, and retain historical observations.
3. **Analytics API:** source-aware aggregation and filterable summary endpoints.
4. **Dashboard:** geographic, skill, employer, and salary views with transparent data caveats.
5. **Advanced analysis:** historical changes, clearance mention extraction, and careful contract-award correlations.
6. **Deployment and documentation:** public demonstration, repeatable builds, monitoring, and security hardening.

See [project charter](docs/project-charter.md), [architecture](docs/architecture.md), and [source evaluation](docs/data-sources.md).

## Data integrity and limitations

- **Not a comprehensive census:** job-feed availability varies by employer and platform; all charts will disclose collection coverage.
- **Postings are not hires:** posting volume is a proxy for advertised demand, not verified employment growth.
- **Salary coverage is incomplete:** reported salary ranges are not total compensation and should not be treated as an accurate market median without sampling context.
- **Clearance mentions are not clearance verification:** extracted text describes job requirements, not an applicant's status.
- **Contract awards do not prove causation:** relationships to posting activity will be labeled as correlations, with timing and entity-matching limitations.
- **Respect source rules:** use only permitted sources and comply with API terms, rate limits, licensing, and attribution requirements.
- **No sensitive or private data:** never commit secrets, credentials, personal applications, or restricted information.

## Getting started

Implementation instructions will be added with the first scaffold ticket. This repository currently contains project planning artifacts only.

## Contributing and license

Contributions and licensing terms will be established before accepting outside contributions. **Public visibility does not by itself grant an open-source license.**

## Disclaimer

Independent portfolio project. Not affiliated with or endorsed by the U.S. Department of Defense, any federal agency, employer, or recruiting platform.
