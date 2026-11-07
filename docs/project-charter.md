# Project Charter — Defense Workforce Intelligence

## Mission

Produce an explainable, repeatable analytical view of publicly advertised technology work in the U.S. defense sector.

## Problem statement

Relevant employment signals are fragmented across public job feeds, federal vacancy data, and government contract records. This fragmentation makes it difficult to compare demand across employers, regions, technologies, and time periods.

## Audience

- Technical professionals evaluating the defense job market
- Recruiters and workforce analysts comparing advertised demand
- Software and data engineering reviewers evaluating the platform itself

## MVP outcome

A working, source-attributed dashboard answering: **Which technical skills appear most often in verified defense-related job postings for the Augusta, Fort Meade, and San Antonio markets, and how does that vary by employer and over time?**

## Success criteria

1. A documented, repeatable data collection process using at least one permitted feed.
2. Persisted source records and observation timestamps, with repeat-run deduplication.
3. Normalized skill, employer, and location fields, including provenance.
4. A versioned FastAPI read endpoint returning truthful aggregates and coverage statistics.
5. A React dashboard with working filtering and drilldowns.
6. Data validation tests, basic run instructions, and no committed secrets.

## Non-goals for MVP

- Comprehensive coverage of all cleared positions
- Automated applications or applicant tracking
- Claims about verified hiring, compensation, or government contract causality
- Scraping sources that prohibit automation
- AI-generated estimates presented as measured facts

## Ownership and integration

DWI is an independent codebase. Telaryn tracks its development lifecycle; a future Telaryn dashboard may consume DWI's public or authenticated API.
