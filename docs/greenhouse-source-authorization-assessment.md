# Greenhouse source-use authorization assessment — TKT-012

**Assessment date:** 2026-11-11  
**Telaryn reference:** TKT-CE8W-WSG2-C3D9  
**Related implementation blocker:** TKT-003 (Greenhouse job ingestion)  
**Intended use:** Personal, noncommercial research, engineering education, and portfolio demonstration. No sale of datasets, paid analytics, commercial service, or competing job board is planned. Public source code is intended; collected records should remain private and the product should direct visitors to original employer/Greenhouse sources rather than substitute for them.  
**Status:** Preliminary research; authorization for live automated collection and retention NOT established.  
**Decision:** Continue engineering toward a manually initiated, opt-in, local metadata pilot. Verify applicable source conditions before requests and keep recurring harvesting and public redistribution disabled. Greenhouse clarification is pending; this is risk acceptance, **not verified authorization**.

This assessment evaluates a personal noncommercial portfolio project, not a commercial data business. Public publication of code does not imply publication of real third-party data. This assessment is a project compliance risk control rather than legal advice. It must not be treated as a license to use any data. It does not modify the ingestion pipeline or enable any live persistence.

## Source register (reviewed 2026-11-11)

| Source | Primary evidence | Limits of evidence |
| --- | --- | --- |
| [Official Greenhouse Job Board API documentation](https://docs.greenhouse.io/job-board) | GET requests for public job board data require no authentication; `GET /v1/boards/{board_token}/jobs` lists published posts; optional `content=true` includes richer post content. | Public technical availability does not provide a third-party license for systematic collection, archival, resale, or redistribution. |
| [Greenhouse API overview](https://support.greenhouse.io/hc/en-us/articles/10568627186203-Greenhouse-API-overview) (updated 2026-11-02) | Job Board API intended for custom career sites displaying an organization's posts; requests may be rate-limited. | Does not state a universally applicable numerical rate limit or blanket permission for independent aggregation. |
| [Greenhouse Master Subscription Agreement](https://www.greenhouse.com/master-subscription-agreement) (updated 2026-02-01) | Signed-order-form customers receive limited internal-use rights; agreement sets restrictions on resale, transfer, third-party benefit and competitive use of services. | The MSA defines customer obligations; do not assume DWI is a customer or that these restrictions directly govern all unauthenticated public GET requests. |
| [My Greenhouse User Agreement](https://my.greenhouse.io/users/agreement) (effective 2025-01-29) | Section 3 restricts automated means, competing products, and monetization of the **My Greenhouse** service. | Section introduction explicitly defines the governed service as My Greenhouse; these restrictions must not be automatically extended to unauthenticated Job Board API GET endpoints without further authority. |
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

## Limited research collection design — proposed, not yet authorized

- **Purpose:** Individual, noncommercial local analysis for an engineering portfolio; show public code and synthetic examples rather than a replica of employer job boards.
- **Access path:** The documented GET `/v1/boards/{board_token}/jobs` endpoint; no authenticated Harvest endpoints, job application POSTs, scraping behind controls, or candidate data.
- **Proposed fields:** Source employer name, `platform`, `board_token`, job-post `id`, title, location name, `updated_at`, `absolute_url`, and local observation timestamp. Do not fetch `content=true`, full descriptions, application questions, free-text fields, or candidate data.
- **Attribution:** Preserve exact source identity and original URL; distinguish first/last observation from actual job creation/closure or hiring. Link out rather than mirror live postings.
- **Storage:** Private local database only if source-specific historical retention is permitted. No real records in public Git history, test fixtures, publicly hosted dashboards, or downloadable datasets.
- **Polling:** No numeric allowance has been established. If permission is granted, define a narrow, explicit interval, honor rate limits and `429`/`Retry-After`, apply exponential backoff, and stop on objections.
- **Retention:** No authorized number of days has been established. Obtain explicit retention/deletion conditions before persisting real records, including removal on source withdrawal and correction/takedown handling.
- **Public output:** Synthetic demo data and code only as the default. Real-data aggregates would require a separate confirmation of permissible publication.

**Gate:** These are minimization and engineering proposals, not permissions. TKT-003's live-data persistence authorization remains open.

## Outstanding authorization questions (for Greenhouse and each employer)

1. May an individual developer retrieve published Job Board API listing metadata for personal, noncommercial, local research and a portfolio demonstration?
2. May DWI store limited metadata locally, create historical snapshots, and compute private noncommercial metrics? Does publicly showing only architecture, synthetic examples, or aggregated findings change the permitted use?
3. Which metadata fields are permitted, and are full descriptions, logos, salary information or source URLs restricted?
4. What polling frequency, request-rate ceiling, backoff, and attribution/linkback are required?
5. What retention term, stale-post removal/deletion, correction, and takedown requirements apply?
6. Is written permission required from Greenhouse, the employer, or both? Which contract or policy governs unauthenticated public GET requests?
7. Are there restrictions specific to personal/noncommercial research, and what additional requirements would apply only if the project later became commercial?

Document responses with respondent role, exact scope, date, affected boards, any expiration, and links to the signed permission record; do not commit private correspondence or sensitive contact data to a public repository without authorization.

## Source-owner clarification request (not yet sent)

Subject: Public Job Board API — personal noncommercial metadata research

Hello Greenhouse team,

I'm developing Defense Workforce Intelligence (DWI), a personal, noncommercial engineering portfolio project. I would like to analyze a small number of published job-post metadata records using your documented public Job Board API. DWI is not intended to replace Greenhouse job boards, sell datasets, or provide job applications. Public demonstrations would use synthetic data and link to original employer listings rather than republish full descriptions.

Could you clarify whether periodic unauthenticated GET requests for selected employers' public job-post metadata are allowed for this personal research, including local retention of titles, identifiers, location, source URLs, update and observation timestamps for historical analysis? If allowed, are there applicable restrictions on which fields may be stored, polling frequency, duration of retention, attribution, deletion on withdrawal, and publication of aggregated findings? Does approval need to come from Greenhouse, each employer, or both? Please direct me to any terms governing third-party use of public Job Board API data.

Thank you.

**Send status:** Draft only; no outreach has been sent by this repository update. Preserve any reply privately and record only non-sensitive scope/decision metadata in the public assessment.

## Decision logic / next actions

- **Current NO-GO (conservative project gate):** Do not activate TKT-003 automated live persistence, recurring ingestion, or third-party data redistribution before applicable terms and use rights are established. This is not a conclusion that noncommercial research is prohibited.
- **Potential conditional GO:** Only after applicable source conditions are resolved for this personal noncommercial use, with an approved field inventory, request limits, retention/deletion policy, and any required authorization. Scope clearance to named sources and this specific use case; do not treat noncommercial status alone as a license.
- **Alternative:** Continue using synthetic fixtures and demonstrate code, testing, architecture, and dashboards without publishing real job records. If live historical data is essential, investigate sources permitting personal research and retention or seek clarification from individual source owners.
- **TKT-003 relationship:** Keep its source-use authorization acceptance criterion open until the approvals are documented; completion of research alone does NOT constitute permission.
- **Technical controls:** Leave current synthetic-only gates and disabled-by-default behavior unchanged; no modification to code or infrastructure is authorized by TKT-012.

## Scope distinctions for decision-making\n\n1. **Public GitHub code and synthetic screenshots:** The stated portfolio goal, with no need to expose real posting records. Continue.\n2. **Personal, noncommercial local analysis of public metadata:** Lower redistribution exposure than a public dataset, but automated access and retention conditions remain to be reviewed. Not assumed automatically permitted or prohibited.\n3. **Publicly hosted dashboard using real employer records:** A separate, optional use case; not part of the currently stated scope. Assess again if pursued.\n4. **Selling data, paid analytics, or a competing product:** Explicitly outside scope. Do not characterize DWI as intending these uses.\n\n## Owner-directed pilot decision (2026-11-11)

The owner confirmed that DWI is intended as personal, noncommercial research and portfolio demonstration, not a commercial data service or competing job board. An inquiry was sent to Greenhouse and a support ticket was requested; the outcome remains pending. Examples of other products using the API **do not grant rights** to DWI.

The owner wants development to proceed toward a small, limited local pilot rather than freeze progress. This is **documented acceptance of unresolved source-use uncertainty**, not a legal determination of permission.

**Required controls before any pilot run:**

1. Use only documented public GET endpoints for boards whose applicable rules permit the intended access; do not bypass authentication, robots restrictions, rate limits, or other access controls.
2. Use an explicit employer/board allowlist and manual execution. Default off; no background scheduling or unrestricted crawling.
3. Minimize fields to employer, board identifier, source posting ID, title, location, source URL, source update time, and observation timestamps. Do not fetch descriptions, application forms, candidate information, or personal contact data.
4. Store raw observations in a private local database only. Never commit collected data, make downloadable datasets, or expose a real-data search UI.
5. Preserve provenance, original links, and a clear disclaimer that observed listings are not verified vacancies, closures, hires, or demand.
6. Use cautious pacing and 429/5xx backoff; no arbitrary claim of an approved request quota.
7. Implement a per-source stop switch and deletion path before activation; respond promptly to Greenhouse/employer objections or restrictions.
8. Keep a record of applicable terms and any correspondence before broadening board coverage. Review Greenhouse's response before scheduling recurring runs or publicly showing live-data aggregates.

**Current decision boundary:** Build the opt-in pilot and its safeguards; do not treat this ticket as a source license. Public site remains synthetic-only, and production/recurring ingestion is out of scope.

## Remaining review required before final sign-off

- Confirm applicable Greenhouse terms for DWI's exact access pattern with the source owner or qualified counsel; draft outreach is included above but not sent.
- Review terms of each target employer's own career website/job board, including any robots policy where relevant.
- Obtain written, scoped authorization or select alternative sources with a clear affirmative data license.
- Review and approve any finalized authorization matrix, explicit polling budgets, retention/deletion procedures, and operational controls.
