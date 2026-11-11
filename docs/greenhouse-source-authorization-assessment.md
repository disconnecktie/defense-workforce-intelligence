# Greenhouse source-use authorization assessment — TKT-012

**Assessment date:** 2026-11-11  
**Telaryn reference:** TKT-CE8W-WSG2-C3D9  
**Related implementation blocker:** TKT-003 (Greenhouse job ingestion)  
**Intended use:** Personal, noncommercial research, engineering education, and portfolio demonstration. No sale of datasets, paid analytics, commercial service, or competing job board is planned. Public source code is intended; collected records should remain private and the product should direct visitors to original employer/Greenhouse sources rather than substitute for them.\n**Status:** Preliminary research; authorization for live automated collection and retention NOT established.  
**Decision for new live collection, persistence, and public redistribution:** **NO-GO pending source-specific authorization and applicable terms review.**

This assessment evaluates a personal noncommercial portfolio project, not a commercial data business. Public publication of code does not imply publication of real third-party data. This assessment is a project compliance risk control rather than legal advice. It must not be treated as a license to use any data. It does not modify the ingestion pipeline or enable any live persistence.

## Source register (reviewed 2026-11-11)

| Source | Primary evidence | Limits of evidence |
| --- | --- | --- |
| [Official Greenhouse Job Board API documentation](https://docs.greenhouse.io/job-board) | GET requests for public job board data require no authentication; `GET /v1/boards/{board_token}/jobs` lists published posts; optional `content=true` includes richer post content. | Public technical availability does not provide a third-party license for systematic collection, archival, resale, or redistribution. |
| [Greenhouse API overview](https://support.greenhouse.io/hc/en-us/articles/10568627186203-Greenhouse-API-overview) (updated 2026-11-02) | Job Board API intended for custom career sites displaying an organization's posts; requests may be rate-limited. | Does not state a universally applicable numerical rate limit or blanket permission for independent aggregation. |
| [Greenhouse Master Subscription Agreement](https://www.greenhouse.com/master-subscription-agreement) (updated 2026-02-01) | Signed-order-form customers receive limited internal-use rights; agreement sets restrictions on resale, transfer, third-party benefit and competitive use of services. | The MSA defines customer obligations; do not assume DWI is a customer or that these restrictions directly govern all unauthenticated public GET requests. |
| [Greenhouse User Agreement](https://my.greenhouse.io/users/agreement) | Contains restrictions on automated means, competing services, and monetizing service-related data. | Assess its precise coverage of `my.greenhouse.io` users vs public Job Board API before treating it as directly binding DWI. |
| [Greenhouse legal document directory](https://www.greenhouse.com/legal) | Clarifies that the customer MSA is incorporated into subscribing customers' order forms. | Does not itself confer an independent data license. |

No employer-specific terms, signed permissions, or written approval have yet been obtained or verified. Employer-specific reviews are **pending** for each proposed board. Do not infer authorization from a site's lack of explicit restrictions.

## Intended product boundary: analysis, not a substitute job board

DWI is a **personal, noncommercial engineering portfolio and private research tool**. Its goal is to study observed employment signals and demonstrate ETL, provenance tracking, APIs, historical analysis, and dashboard development. It is **not** intended to compete with Greenhouse or to allow visitors to bypass employers' original job boards.

- **Source attribution:** When permitted records are observed, retain the employer name, `platform=greenhouse`, board identifier/token, original source posting ID or URL, and first/last observation timestamps for provenance and auditability. Link users to the employer's original Greenhouse posting for the authoritative current listing, where an outward link is offered.
- **Data minimization:** Prefer a limited metadata inventory for local research. Do not retain or republish full descriptions/HTML, application forms, applicant data, or bulk copies of listings as a portfolio feature.
- **Derived analysis:** Prioritize observed posting counts, technology-title signals, source coverage, and ingestion-operation metrics. Clearly distinguish observed records from verified open vacancies, hires, closures, or measured hiring demand.
- **Public presentation:** Show code, architecture, test fixtures, synthetic examples, and approved aggregates; do not expose a searchable mirror of real live postings or a downloadable employer dataset. Public real-data aggregates still require applicable rights analysis.
- **Permitted-use gate:** Attribution, linkback, lack of monetization, and avoiding duplication **do not by themselves confer authorization** to automate collection or retain data historically. Confirm source-specific rules and any required permission before enabling new live ingestion/persistence.
- **Change control:** If DWI later becomes a hosted service, paid tool, or publicly displays source records, reassess the applicable authorizations and security controls before changing the scope.

## Authorization matrix — as of 2026-11-11

**Interpretation:** “Technical availability” is not permission. “Pending” means not cleared for implementation. “Conservative design proposal” is NOT an agreed legal entitlement.

| Operation / field | Publicly technically available | Authorization for DWI | Decision / condition |
| --- | --- | --- | --- |
| Read published job-post metadata (job ID, title, location, board token, posting URL, source update time) | Yes, documented GET endpoint | **Unconfirmed for independent systematic aggregation** | **NO-GO for new live scheduled or bulk access** pending written clarification and employer-specific review |
| Capture employer name and source attribution | Public board information | **Unconfirmed for persistent analytics** | Preserve source references in synthetic prototype; verify each real employer's terms before live collection |
| Retain raw job descriptions and HTML content | Optional API content parameter | **Unconfirmed; higher reuse and intellectual-property risk** | Exclude from proposed initial authorized inventory |
| Store job-post metadata or historical snapshots | API returns observations, not a grant to archive | **Unconfirmed** | **NO-GO** until permissible duration, removal rules, and scope are documented |
| Publish a searchable listing directory or re-display full job content | Data technically visible on original boards | **Unconfirmed; not needed for stated personal portfolio goal** | **Out of scope for current project**, no public reposting of live employer records |
| Compute personal noncommercial title, technology, or coverage analyses | Could be computed technically | **Automated sourcing and retention permissions unconfirmed** | Keep current live-data gate off pending access and retention review; separate private analysis from public display |
| Rate/frequency of job-board API polling | Requests may be rate-limited | **No universal numeric threshold verified** | Do not assign an invented threshold; obtain permissible request cadence from source owner |
| Source attribution and linkback | Posting URLs supplied by API | **Exact required license/attribution text unconfirmed** | Proposed: preserve employer name, board, original URL, and observation timestamp; confirm written requirements |
| Retention and deletion | API documentation does not authorize archival period | **No permitted duration identified** | Do not invent retention window; obtain approved retention period and takedown process first |
| Personal information in job descriptions/contact fields | May appear in freely formatted content | **Not cleared** | Avoid collection; define minimization and deletion rules before any live data |
| Application forms / applicant or candidate data | Separate POST may require authentication | **Out of scope** | Never ingest applicants, applications, demographic answers, or candidate information |

## Outstanding authorization questions (for Greenhouse and each employer)

1. May an individual developer retrieve published Job Board API listing metadata for personal, noncommercial, local research and a portfolio demonstration?
2. May DWI store limited metadata locally, create historical snapshots, and compute private noncommercial metrics? Does publicly showing only architecture, synthetic examples, or aggregated findings change the permitted use?
3. Which metadata fields are permitted, and are full descriptions, logos, salary information or source URLs restricted?
4. What polling frequency, request-rate ceiling, backoff, and attribution/linkback are required?
5. What retention term, stale-post removal/deletion, correction, and takedown requirements apply?
6. Is written permission required from Greenhouse, the employer, or both? Which contract or policy governs unauthenticated public GET requests?
7. Are there restrictions specific to personal/noncommercial research, and what additional requirements would apply only if the project later became commercial?

Document responses with respondent role, exact scope, date, affected boards, any expiration, and links to the signed permission record; do not commit private correspondence or sensitive contact data to a public repository without authorization.

## Decision logic / next actions

- **Current NO-GO (conservative project gate):** Do not activate TKT-003 automated live persistence, recurring ingestion, or third-party data redistribution before applicable terms and use rights are established. This is not a conclusion that noncommercial research is prohibited.
- **Potential conditional GO:** Only after documented source-level rights, approved field inventory, request limits, retention/deletion policy, and verification of the scope of any required permissions. Scope authorization to each named source and use case.
- **Alternative:** Continue using synthetic fixtures and demonstrate code, testing, architecture, and dashboards without publishing real job records. If live historical data is essential, investigate sources permitting personal research and retention or seek clarification from individual source owners.
- **TKT-003 relationship:** Keep its source-use authorization acceptance criterion open until the approvals are documented; completion of research alone does NOT constitute permission.
- **Technical controls:** Leave current synthetic-only gates and disabled-by-default behavior unchanged; no modification to code or infrastructure is authorized by TKT-012.

## Scope distinctions for decision-making\n\n1. **Public GitHub code and synthetic screenshots:** The stated portfolio goal, with no need to expose real posting records. Continue.\n2. **Personal, noncommercial local analysis of public metadata:** Lower redistribution exposure than a public dataset, but automated access and retention conditions remain to be reviewed. Not assumed automatically permitted or prohibited.\n3. **Publicly hosted dashboard using real employer records:** A separate, optional use case; not part of the currently stated scope. Assess again if pursued.\n4. **Selling data, paid analytics, or a competing product:** Explicitly outside scope. Do not characterize DWI as intending these uses.\n\n## Remaining review required before final sign-off

- Confirm applicable Greenhouse terms for DWI's exact access pattern with the source owner or qualified counsel.
- Review terms of each target employer's own career website/job board, including any robots policy where relevant.
- Obtain written, scoped authorization or select alternative sources with a clear affirmative data license.
- Review and approve any finalized authorization matrix, explicit polling budgets, retention/deletion procedures, and operational controls.
