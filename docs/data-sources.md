# Candidate Public Data Sources

Sources must be evaluated individually for access, permitted use, coverage, rate limits, and attribution **before ingestion**.

| Candidate | Intended use | Validation required |
| --- | --- | --- |
| [USAJOBS API](https://developer.usajobs.gov/) | Public federal technology vacancies | API registration, filters, usage policy, federal vs contractor scope |
| [Greenhouse job-board API](https://developers.greenhouse.io/job-board.html) | Employer postings with public job-board feeds | Verify employer board identifiers and terms |
| [Lever Postings API](https://github.com/lever/postings-api) | Public employer postings | Verify participating employers and API policy |
| [O*NET Web Services](https://services.onetcenter.org/) | Skills and occupational taxonomy | API account/terms and proper attribution |
| [USAspending API](https://api.usaspending.gov/) | Later-stage contract award signals | Entity matching, update lag, and correlation caveats |

## Initial data-collection strategy

1. Identify a small, documented cohort of employers with allowed public access.
2. Sample feeds and record field-level completeness, especially geography, salary, and posting ID.
3. Build one reproducible collector with observable run logs and retries.
4. Expand only after deduplication and history retention work end-to-end.
5. Publish coverage metrics alongside every market visualization.

## External source restrictions

No bypass of access controls, no scraping contrary to published terms, and no publication of private applicant or contact information. Retain only data necessary for the analysis and follow applicable source retention requirements.

## TKT-002 source selection (2026-11-08)

**First adapter: Greenhouse public Job Board API.** Candidate pilot employer: Anduril Industries (`andurilindustries` board token), subject to verifying the live source and acceptable access/retention conditions. This choice is based on API structure, lack of GET authentication, public posting identifiers, and optional description/office/department content—not on an assumption of complete defense-market coverage.

- [Detailed ingestion plan](ingestion-plan.md) — source comparison, request, validation and error handling, success conditions.
- [Initial data dictionary](data-dictionary.md) — source fields, nullable values, identity/deduplication, skill/clearance/location normalization.
- **Next validation gate:** make a real read-only GET from the development workstation, inspect field completeness, and record source terms. This environment has **not** directly confirmed the current Greenhouse feed response.

**Caveat:** Other employers may use Lever, Workday, or proprietary systems. USAJOBS covers federal civilian hiring and should not be mixed into defense-contractor counts without separate source labels. No historical trend should be shown until DWI has accumulated real dated observations.
