# Greenhouse source-use authorization assessment — TKT-012

**Assessment date:** 2026-11-11  
**Telaryn reference:** TKT-CE8W-WSG2-C3D9  
**Related implementation blocker:** TKT-003 (Greenhouse job ingestion)  
**Status:** Preliminary research; authorization NOT established.  
**Decision for new live collection, persistence, and public redistribution:** **NO-GO pending source-specific authorization and applicable terms review.**

This assessment is a product/compliance risk control rather than legal advice. It must not be treated as a license to use any data. It does not modify the ingestion pipeline or enable any live persistence.

## Source register (reviewed 2026-11-11)

| Source | Primary evidence | Limits of evidence |
| --- | --- | --- |
| [Official Greenhouse Job Board API documentation](https://docs.greenhouse.io/job-board) | GET requests for public job board data require no authentication; `GET /v1/boards/{board_token}/jobs` lists published posts; optional `content=true` includes richer post content. | Public technical availability does not provide a third-party license for systematic collection, archival, resale, or redistribution. |
| [Greenhouse API overview](https://support.greenhouse.io/hc/en-us/articles/10568627186203-Greenhouse-API-overview) (updated 2026-11-02) | Job Board API intended for custom career sites displaying an organization's posts; requests may be rate-limited. | Does not state a universally applicable numerical rate limit or blanket permission for independent aggregation. |
| [Greenhouse Master Subscription Agreement](https://www.greenhouse.com/master-subscription-agreement) (updated 2026-02-01) | Signed-order-form customers receive limited internal-use rights; agreement sets restrictions on resale, transfer, third-party benefit and competitive use of services. | The MSA defines customer obligations; do not assume DWI is a customer or that these restrictions directly govern all unauthenticated public GET requests. |
| [Greenhouse User Agreement](https://my.greenhouse.io/users/agreement) | Contains restrictions on automated means, competing services, and monetizing service-related data. | Assess its precise coverage of `my.greenhouse.io` users vs public Job Board API before treating it as directly binding DWI. |
| [Greenhouse legal document directory](https://www.greenhouse.com/legal) | Clarifies that the customer MSA is incorporated into subscribing customers' order forms. | Does not itself confer an independent data license. |

No employer-specific terms, signed permissions, or written approval have yet been obtained or verified. Employer-specific reviews are **pending** for each proposed board. Do not infer authorization from a site's lack of explicit restrictions.

## Authorization matrix — as of 2026-11-11

**Interpretation:** “Technical availability” is not permission. “Pending” means not cleared for implementation. “Conservative design proposal” is NOT an agreed legal entitlement.

| Operation / field | Publicly technically available | Authorization for DWI | Decision / condition |
| --- | --- | --- | --- |
| Read published job-post metadata (job ID, title, location, board token, posting URL, source update time) | Yes, documented GET endpoint | **Unconfirmed for independent systematic aggregation** | **NO-GO for new live scheduled or bulk access** pending written clarification and employer-specific review |
| Capture employer name and source attribution | Public board information | **Unconfirmed for persistent analytics** | Preserve source references in synthetic prototype; verify each real employer's terms before live collection |
| Retain raw job descriptions and HTML content | Optional API content parameter | **Unconfirmed; higher reuse and intellectual-property risk** | Exclude from proposed initial authorized inventory |
| Store job-post metadata or historical snapshots | API returns observations, not a grant to archive | **Unconfirmed** | **NO-GO** until permissible duration, removal rules, and scope are documented |
| Publish a searchable job listing directory or re-display postings | Data technically visible on original boards | **Unconfirmed** | **NO-GO** until explicit redistribution/public display rights are established |
| Produce derived title, technology, coverage, or hiring analytics | Could be computed technically | **Unconfirmed for published commercial/public-facing outputs** | **NO-GO** for live-derived public output until permitted use is agreed and privacy/IP risk reviewed |
| Rate/frequency of job-board API polling | Requests may be rate-limited | **No universal numeric threshold verified** | Do not assign an invented threshold; obtain permissible request cadence from source owner |
| Source attribution and linkback | Posting URLs supplied by API | **Exact required license/attribution text unconfirmed** | Proposed: preserve employer name, board, original URL, and observation timestamp; confirm written requirements |
| Retention and deletion | API documentation does not authorize archival period | **No permitted duration identified** | Do not invent retention window; obtain approved retention period and takedown process first |
| Personal information in job descriptions/contact fields | May appear in freely formatted content | **Not cleared** | Avoid collection; define minimization and deletion rules before any live data |
| Application forms / applicant or candidate data | Separate POST may require authentication | **Out of scope** | Never ingest applicants, applications, demographic answers, or candidate information |

## Outstanding authorization questions (for Greenhouse and each employer)

1. May an independent commercial or public-facing third-party product automatically retrieve the published Job Board API job listing metadata for that employer?
2. May DWI store metadata persistently, create historical snapshots, compute aggregate metrics, and publish derived analyses? Does this differ from reproducing listings?
3. Which metadata fields are permitted, and are full descriptions, logos, salary information or source URLs restricted?
4. What polling frequency, request-rate ceiling, backoff, and attribution/linkback are required?
5. What retention term, stale-post removal/deletion, correction, and takedown requirements apply?
6. Is written permission required from Greenhouse, the employer, or both? Which contract or policy governs unauthenticated public GET requests?
7. May DWI provide paid/monetized analytics derived from permitted data?

Document responses with respondent role, exact scope, date, affected boards, any expiration, and links to the signed permission record; do not commit private correspondence or sensitive contact data to a public repository without authorization.

## Decision logic / next actions

- **Current NO-GO:** Do not activate TKT-003 live persistence, recurring ingestion, any public employer-data dashboards, or redistribution.
- **Potential conditional GO:** Only after documented source-level rights, approved field inventory, request limits, retention/deletion policy, and verification of the scope of any required permissions. Scope authorization to each named source and use case.
- **Alternative:** Evaluate data providers offering an explicit redistribution/analytics license or establish direct employer partnerships if Greenhouse rights cannot be confirmed.
- **TKT-003 relationship:** Keep its source-use authorization acceptance criterion open until the approvals are documented; completion of research alone does NOT constitute permission.
- **Technical controls:** Leave current synthetic-only gates and disabled-by-default behavior unchanged; no modification to code or infrastructure is authorized by TKT-012.

## Remaining review required before final sign-off

- Confirm applicable Greenhouse terms for DWI's exact access pattern with the source owner or qualified counsel.
- Review terms of each target employer's own career website/job board, including any robots policy where relevant.
- Obtain written, scoped authorization or select alternative sources with a clear affirmative data license.
- Review and approve any finalized authorization matrix, explicit polling budgets, retention/deletion procedures, and operational controls.
