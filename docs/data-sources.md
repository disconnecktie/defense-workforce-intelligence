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
