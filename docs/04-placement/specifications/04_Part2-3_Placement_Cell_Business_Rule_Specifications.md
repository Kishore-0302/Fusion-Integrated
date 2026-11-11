# Placement Cell Business Rule Specifications

**Comprehensive Business Rule Specifications & Formal Logic (PC-BR-001 to 030)**

> *Reading note: Each Business Rule has a stable identifier (PC-BR-xxx). Use the Related Use Cases / Workflows field for cross-references to the accompanying Use Case and Workflow Specifications. Retired rules are clearly noted with their superseding requirement IDs.*

## 1. Business Rule Index

| Rule ID | Rule Name | Rule Classification |
| --- | --- | --- |
| PC-BR-001 | Profile Completeness Before Applying | Eligibility / Profile Gate |
| PC-BR-002 | Eligibility Criteria Verification and Freezing | Eligibility / Integrity Invariant |
| PC-BR-003 | Mandatory Job Posting Content | Validation / Data Completeness |
| PC-BR-004 | Closed Eligibility Vocabulary | Schema Validation / Integrity |
| PC-BR-005 | TPO Posting Authority | Authorization / Governance |
| PC-BR-006 | Company Posting Authority | Authorization / Scoping |
| PC-BR-007 | Company Approval Gate | State Gate / Operational Authorization |
| PC-BR-008 | Application History and Audit Trail | Audit / Traceability (Retired -> PC-AFR-009) |
| PC-BR-009 | Company Application Scope Isolation | Data Isolation / Security Invariant |
| PC-BR-010 | TPO Universal Application Scope | Authorization / Governance |
| PC-BR-011 | Mandatory Interview Details | Validation / Operational Completeness |
| PC-BR-012 | Interview Candidate Notification | Notification / State Event |
| PC-BR-013 | Offer Expiry Deadline and Sweeper | Temporal Gate / Lifecycle Automation |
| PC-BR-014 | Placement Record Creation on Acceptance | Data Integrity / Lifecycle Invariant |
| PC-BR-015 | Multiple-Offer Policy and Dream Upgrades | Institutional Policy / Tier Governance |
| PC-BR-016 | Anonymized Statistics and Small-Cell Floor | Privacy / Statistical Protection |
| PC-BR-017 | Bounded Announcement Topics | Validation / Taxonomy |
| PC-BR-018 | Announcement Versioning and Deactivation | Audit / Lifecycle (Retired -> PC-AFR-043) |
| PC-BR-019 | Alumni Read-Only Mentorship Slice | Authorization / Scoping |
| PC-BR-020 | Exclusion of Alumni from Active Workflows | State Isolation / Governance |
| PC-BR-021 | Reliable Notification Dispatch via Outbox | Integration / Architectural Invariant |
| PC-BR-022 | Role-Restricted RBAC and Scoping | Authorization / Security |
| PC-BR-023 | Sensitive Academic Data View Protection | Privacy / Data Protection |
| PC-BR-024 | Sensitive Placement Data Modify Restriction | Security / Audit Integrity |
| PC-BR-025 | Academic Master Data External Read-Only Invariant | Architectural Invariant (ADR-0008) |
| PC-BR-026 | IAM External Authentication Authority Invariant | Architectural Invariant (ADR-0002) |
| PC-BR-029 | Placement Record Administrative Correction | Administrative Audit / Data Quality |
| PC-BR-030 | Institutional Autonomy in Selection Decisions | Governance / Security Boundary |


## 2. Detailed Business Rule Specifications

### PC-BR-001 — Profile Completeness Before Applying

| Attribute | Specification Detail |
| --- | --- |
| **Rule ID** | PC-BR-001 |
| **Rule Name** | Profile Completeness Before Applying |
| **Rule Classification** | Eligibility / Profile Gate |


**Operational Description / Policy Statement:**
A student must possess a 100% verified complete profile on the institutional ERP portal before submitting any placement application.

**Formal Operational & Enforcement Logic:**
```text
Pre-state: Student initiates application to job posting.
Guard: iam_user.profile_completed is True and primary resume reference exists.
Post-state: Application proceeds to eligibility verification; if False, application rejected with error 'profile_incomplete'.
Enforcement: modules/placement/services/applications.py::apply_to and modules/placement_cell/use_cases.py.
```

**Related Use Cases / Workflows / Traceability:** PC-UC-001, PC-UC-003, PC-UC-023; PC-AFR-002; BW-PC-04

### PC-BR-002 — Eligibility Criteria Verification and Freezing

| Attribute | Specification Detail |
| --- | --- |
| **Rule ID** | PC-BR-002 |
| **Rule Name** | Eligibility Criteria Verification and Freezing |
| **Rule Classification** | Eligibility / Integrity Invariant |


**Operational Description / Policy Statement:**
A student's eligibility is evaluated against the posting's criteria frozen at publication time. A posting's criteria cannot be altered after publication.

**Formal Operational & Enforcement Logic:**
```text
Pre-state: Job posting transitions to 'published' status.
Guard: eligibility_rule_locked_at is stamped with current UTC timestamp; DB CheckConstraint enforces immutability.
Evaluation: core.rules.engine evaluates student snapshot against frozen JSON AST. Must fail closed (reject if missing attribute).
Enforcement: modules/placement/domain/eligibility.py, modules/placement/models/postings.py.
```

**Related Use Cases / Workflows / Traceability:** PC-UC-002, PC-UC-003, PC-UC-006; PC-AFR-003, PC-AFR-022; BW-PC-03, BW-PC-04

### PC-BR-003 — Mandatory Job Posting Content

| Attribute | Specification Detail |
| --- | --- |
| **Rule ID** | PC-BR-003 |
| **Rule Name** | Mandatory Job Posting Content |
| **Rule Classification** | Validation / Data Completeness |


**Operational Description / Policy Statement:**
A job posting cannot be submitted or published without job title, kind (fte/intern), description, compensation (CTC), valid eligibility rule, and a future application deadline.

**Formal Operational & Enforcement Logic:**
```text
Pre-state: Recruiter submits draft (PC-UC-015) or TPO publishes (PC-UC-006).
Guard: title non-empty, kind in ('fte', 'intern', 'ppo'), description non-empty, closes_at > now(), eligibility_rule valid.
Post-state: If valid, moves to 'pending_approval' or 'published'; if invalid, raises ConflictError with 'incomplete_posting'.
Enforcement: modules/placement_cell/use_cases.py::submit_company_opportunity, modules/placement/services/postings.py.
```

**Related Use Cases / Workflows / Traceability:** PC-UC-006, PC-UC-015; PC-AFR-019, PC-AFR-021; BW-PC-02, BW-PC-03

### PC-BR-004 — Closed Eligibility Vocabulary

| Attribute | Specification Detail |
| --- | --- |
| **Rule ID** | PC-BR-004 |
| **Rule Name** | Closed Eligibility Vocabulary |
| **Rule Classification** | Schema Validation / Integrity |


**Operational Description / Policy Statement:**
Posting eligibility rules must strictly use attributes from the approved closed vocabulary: cpi, discipline, batch_year, and active_backlogs.

**Formal Operational & Enforcement Logic:**
```text
Validation: Posting creation or edit parses rule JSON. Any attribute outside ('cpi', 'discipline', 'batch_year', 'active_backlogs') raises SchemaValidationError.
Runtime: Unknown attributes during evaluation immediately evaluate to False (fail-closed).
Enforcement: modules/placement/services/postings.py::validate_rule, modules/placement/domain/eligibility.py.
```

**Related Use Cases / Workflows / Traceability:** PC-UC-003, PC-UC-006, PC-UC-015; PC-AFR-020; BW-PC-02

### PC-BR-005 — TPO Posting Authority

| Attribute | Specification Detail |
| --- | --- |
| **Rule ID** | PC-BR-005 |
| **Rule Name** | TPO Posting Authority |
| **Rule Classification** | Authorization / Governance |


**Operational Description / Policy Statement:**
Only authorized institutional Placement Cell staff may publish job postings and release them to the student body.

**Formal Operational & Enforcement Logic:**
```text
Guard: Actor must possess 'placement_cell.job_posting.manage' permission and actor.kind != 'recruiter'.
Post-state: Posting published with frozen rules; recruiter cannot publish unilaterally.
Enforcement: modules/placement_cell/use_cases.py::publish_tpo_opportunity, modules/placement/services/authz.py.
```

**Related Use Cases / Workflows / Traceability:** PC-UC-006; PC-AFR-017; BW-PC-03

### PC-BR-006 — Company Posting Authority

| Attribute | Specification Detail |
| --- | --- |
| **Rule ID** | PC-BR-006 |
| **Rule Name** | Company Posting Authority |
| **Rule Classification** | Authorization / Scoping |


**Operational Description / Policy Statement:**
A company recruiter may create and edit draft postings exclusively for their own verified company account.

**Formal Operational & Enforcement Logic:**
```text
Guard: actor.company_id == posting.company_id and posting.company.approval_status == 'approved'.
Post-state: Draft saved or submitted for TPO review. Foreign company posting modifications raise PermissionDeniedError.
Enforcement: modules/placement/selectors/scoping.py, modules/placement_cell/use_cases.py.
```

**Related Use Cases / Workflows / Traceability:** PC-UC-014, PC-UC-015; PC-AFR-018; BW-PC-02

### PC-BR-007 — Company Approval Gate

| Attribute | Specification Detail |
| --- | --- |
| **Rule ID** | PC-BR-007 |
| **Rule Name** | Company Approval Gate |
| **Rule Classification** | State Gate / Operational Authorization |


**Operational Description / Policy Statement:**
A company must be formally approved by TPO staff (approval_status='approved' and can_operate=True) before posting opportunities, reviewing candidates, or scheduling interviews.

**Formal Operational & Enforcement Logic:**
```text
Guard: company.approval_status == 'approved' and company.can_operate is True.
Post-state: Recruiter allowed to submit postings. If unapproved, raises ConflictError('company_not_approved').
Enforcement: modules/placement/models/companies.py, modules/placement_cell/use_cases.py.
```

**Related Use Cases / Workflows / Traceability:** PC-UC-014, PC-UC-015; PC-AFR-045; BW-PC-01, BW-PC-02

### PC-BR-008 — Application History and Audit Trail

| Attribute | Specification Detail |
| --- | --- |
| **Rule ID** | PC-BR-008 |
| **Rule Name** | Application History and Audit Trail |
| **Rule Classification** | Audit / Traceability (Retired -> PC-AFR-009) |


**Operational Description / Policy Statement:**
Every lifecycle transition on an application must be recorded with actor identity, timestamp, from_status, to_status, and reason.

**Formal Operational & Enforcement Logic:**
```text
Invariant: Direct UPDATE statements on Application status without writing ApplicationHistory are prohibited.
Enforcement: modules/placement/services/applications.py::transition, modules/placement/models/applications.py.
```

**Related Use Cases / Workflows / Traceability:** PC-UC-003, PC-UC-004, PC-UC-016; PC-AFR-009, PC-AFR-010; BW-PC-04, BW-PC-05

### PC-BR-009 — Company Application Scope Isolation

| Attribute | Specification Detail |
| --- | --- |
| **Rule ID** | PC-BR-009 |
| **Rule Name** | Company Application Scope Isolation |
| **Rule Classification** | Data Isolation / Security Invariant |


**Operational Description / Policy Statement:**
A corporate recruiter can query and access applications submitted exclusively to job postings owned by their verified company.

**Formal Operational & Enforcement Logic:**
```text
Filter: QuerySet is scoped with .filter(posting__company_id=actor.company_id).
Attempt to query out-of-scope application returns 404 NotFoundError rather than 403 to prevent employer enumeration.
Enforcement: modules/placement/selectors/scoping.py::applications_for.
```

**Related Use Cases / Workflows / Traceability:** PC-UC-016, PC-UC-021, PC-UC-022; PC-AFR-046, PC-AFR-049; BW-PC-05

### PC-BR-010 — TPO Universal Application Scope

| Attribute | Specification Detail |
| --- | --- |
| **Rule ID** | PC-BR-010 |
| **Rule Name** | TPO Universal Application Scope |
| **Rule Classification** | Authorization / Governance |


**Operational Description / Policy Statement:**
Authorized TPO administrative staff have global visibility across all applications, drives, and student records in the module.

**Formal Operational & Enforcement Logic:**
```text
Filter: TPO QuerySet includes all active and historical applications without company boundary restrictions.
Enforcement: modules/placement/selectors/scoping.py::applications_for.
```

**Related Use Cases / Workflows / Traceability:** PC-UC-005, PC-UC-006, PC-UC-009, PC-UC-010; PC-AFR-010

### PC-BR-011 — Mandatory Interview Details

| Attribute | Specification Detail |
| --- | --- |
| **Rule ID** | PC-BR-011 |
| **Rule Name** | Mandatory Interview Details |
| **Rule Classification** | Validation / Operational Completeness |


**Operational Description / Policy Statement:**
Scheduling an interview round requires round sequence number, category (screening/tech/hr), starts_at in the future, mode (online/offline), and venue or virtual meeting link.

**Formal Operational & Enforcement Logic:**
```text
Guard: starts_at > now(), mode in ('online', 'offline'). If mode=='online', meeting_url non-empty; if 'offline', venue non-empty.
Enforcement: modules/placement/models/interviews.py, modules/placement_cell/use_cases.py::schedule_interviews.
```

**Related Use Cases / Workflows / Traceability:** PC-UC-009, PC-UC-021; PC-AFR-027; BW-PC-06

### PC-BR-012 — Interview Candidate Notification

| Attribute | Specification Detail |
| --- | --- |
| **Rule ID** | PC-BR-012 |
| **Rule Name** | Interview Candidate Notification |
| **Rule Classification** | Notification / State Event |


**Operational Description / Policy Statement:**
Assigning candidates to an interview round must immediately enqueue invitation notifications containing venue/link and timing details.

**Formal Operational & Enforcement Logic:**
```text
Post-state: Upon adding candidates, NotificationOutbox rows are enqueued with event='interview_scheduled'.
Enforcement: modules/placement/services/interviews.py::add_candidates, modules/placement_cell/use_cases.py.
```

**Related Use Cases / Workflows / Traceability:** PC-UC-009; PC-AFR-029, PC-AFR-054; BW-PC-06

### PC-BR-013 — Offer Expiry Deadline and Sweeper

| Attribute | Specification Detail |
| --- | --- |
| **Rule ID** | PC-BR-013 |
| **Rule Name** | Offer Expiry Deadline and Sweeper |
| **Rule Classification** | Temporal Gate / Lifecycle Automation |


**Operational Description / Policy Statement:**
Every extended job offer must possess an expires_at deadline. Unanswered offers past the deadline are automatically expired by a 5-minute background sweep.

**Formal Operational & Enforcement Logic:**
```text
Creation Guard: expires_at > now().
Sweep Execution: modules/placement/tasks.py::expire_stale_offers queries offers where status=='extended' and expires_at <= now(), transitions them to 'expired', and releases pool allocations.
Enforcement: modules/placement/services/offers.py, modules/placement/tasks.py.
```

**Related Use Cases / Workflows / Traceability:** PC-UC-008, PC-UC-022; PC-AFR-024, PC-SCHED-01; BW-PC-07

### PC-BR-014 — Placement Record Creation on Acceptance

| Attribute | Specification Detail |
| --- | --- |
| **Rule ID** | PC-BR-014 |
| **Rule Name** | Placement Record Creation on Acceptance |
| **Rule Classification** | Data Integrity / Lifecycle Invariant |


**Operational Description / Policy Statement:**
Accepting a job offer automatically creates an active verified PlacementRecord and transitions student status to Placed.

**Formal Operational & Enforcement Logic:**
```text
Post-state: Inside database transaction, PlacementRecord.objects.create(user_id=student_id, company=company, ctc_lpa=offer.ctc_lpa, is_active=True). Student is debarred from non-dream postings.
Enforcement: modules/placement/services/offers.py::accept_offer, modules/placement/domain/state_machine.py.
```

**Related Use Cases / Workflows / Traceability:** PC-UC-008; PC-AFR-031; BW-PC-07, BW-PC-08

### PC-BR-015 — Multiple-Offer Policy and Dream Upgrades

| Attribute | Specification Detail |
| --- | --- |
| **Rule ID** | PC-BR-015 |
| **Rule Name** | Multiple-Offer Policy and Dream Upgrades |
| **Rule Classification** | Institutional Policy / Tier Governance |


**Operational Description / Policy Statement:**
A student holding an accepted placement offer may only apply for or accept another offer if the new opportunity qualifies as a higher-tier 'Dream Offer' according to the season tier policy.

**Formal Operational & Enforcement Logic:**
```text
Evaluation: modules/placement/domain/offer_policy.py::can_accept_offer checks existing active record CTC vs new offer CTC and tier multiplier (e.g. CTC >= 1.5 * current_ctc). If not met, decision denied with reason logged.
Enforcement: modules/placement/domain/offer_policy.py, modules/placement/services/applications.py.
```

**Related Use Cases / Workflows / Traceability:** PC-UC-003, PC-UC-008; PC-AFR-025; BW-PC-04, BW-PC-07

### PC-BR-016 — Anonymized Statistics and Small-Cell Floor

| Attribute | Specification Detail |
| --- | --- |
| **Rule ID** | PC-BR-016 |
| **Rule Name** | Anonymized Statistics and Small-Cell Floor |
| **Rule Classification** | Privacy / Statistical Protection |


**Operational Description / Policy Statement:**
Public and student-facing reports must suppress salary aggregations (mean, median, max) for any reporting cell with fewer than 5 placed students.

**Formal Operational & Enforcement Logic:**
```text
Evaluation: If cohort count < 5, salary fields are returned as None / redacted in API responses.
Enforcement: modules/placement/services/stats.py::student_view, modules/placement/selectors/stats.py.
```

**Related Use Cases / Workflows / Traceability:** PC-UC-011, PC-UC-012, PC-UC-024; PC-AFR-035, PC-AFR-038

### PC-BR-017 — Bounded Announcement Topics

| Attribute | Specification Detail |
| --- | --- |
| **Rule ID** | PC-BR-017 |
| **Rule Name** | Bounded Announcement Topics |
| **Rule Classification** | Validation / Taxonomy |


**Operational Description / Policy Statement:**
Announcement topics must strictly belong to the allowed taxonomy: 'drives', 'shortlists', 'results', or 'general'.

**Formal Operational & Enforcement Logic:**
```text
Guard: topic in ('drives', 'shortlists', 'results', 'general'). Invalid choice raises ValidationError.
Enforcement: modules/placement/models/announcements.py, modules/placement/services/announcements.py.
```

**Related Use Cases / Workflows / Traceability:** PC-UC-013, PC-UC-020; PC-AFR-040

### PC-BR-018 — Announcement Versioning and Deactivation

| Attribute | Specification Detail |
| --- | --- |
| **Rule ID** | PC-BR-018 |
| **Rule Name** | Announcement Versioning and Deactivation |
| **Rule Classification** | Audit / Lifecycle (Retired -> PC-AFR-043) |


**Operational Description / Policy Statement:**
Retracting an announcement sets is_active=False and records withdrawal rationale; hard deletes are prohibited to maintain audit records.

**Formal Operational & Enforcement Logic:**
```text
Post-state: announcement.is_active = False, announcement.withdrawn_at = now(). Retains original posting record.
Enforcement: modules/placement/services/announcements.py::withdraw.
```

**Related Use Cases / Workflows / Traceability:** PC-UC-013; PC-AFR-042, PC-AFR-043

### PC-BR-019 — Alumni Read-Only Mentorship Slice

| Attribute | Specification Detail |
| --- | --- |
| **Rule ID** | PC-BR-019 |
| **Rule Name** | Alumni Read-Only Mentorship Slice |
| **Rule Classification** | Authorization / Scoping |


**Operational Description / Policy Statement:**
Graduated alumni have access only to a read-only historical slice of their own placement records and verified clearance documents.

**Formal Operational & Enforcement Logic:**
```text
Scoping: When actor.role == 'alumni', queries return only historical placement clearance records for that user.
Enforcement: modules/placement/selectors/scoping.py::records_for.
```

**Related Use Cases / Workflows / Traceability:** PC-UC-017; PC-AFR-058, PC-AFR-059

### PC-BR-020 — Exclusion of Alumni from Active Workflows

| Attribute | Specification Detail |
| --- | --- |
| **Rule ID** | PC-BR-020 |
| **Rule Name** | Exclusion of Alumni from Active Workflows |
| **Rule Classification** | State Isolation / Governance |


**Operational Description / Policy Statement:**
Alumni are strictly excluded from live job postings, active drive applications, and interview scheduling workflows.

**Formal Operational & Enforcement Logic:**
```text
Guard: If actor.role == 'alumni', scoping.postings_for(actor) returns JobPosting.objects.none(). Application creation is refused.
Enforcement: modules/placement/selectors/scoping.py.
```

**Related Use Cases / Workflows / Traceability:** PC-UC-001, PC-UC-017; PC-AFR-060

### PC-BR-021 — Reliable Notification Dispatch via Outbox

| Attribute | Specification Detail |
| --- | --- |
| **Rule ID** | PC-BR-021 |
| **Rule Name** | Reliable Notification Dispatch via Outbox |
| **Rule Classification** | Integration / Architectural Invariant |


**Operational Description / Policy Statement:**
All email and system alerts must be written atomically to the NotificationOutbox table inside the same database transaction as the triggering domain event.

**Formal Operational & Enforcement Logic:**
```text
Invariant: Domain services never make synchronous HTTP/SMTP calls during request handling. They write to NotificationOutbox. Celery worker drains outbox asynchronously.
Enforcement: modules/placement/services/notifications.py, modules/placement/tasks.py.
```

**Related Use Cases / Workflows / Traceability:** PC-UC-003, PC-UC-006, PC-UC-007, PC-UC-008, PC-UC-009, PC-UC-013, PC-UC-022; PC-AFR-050–057; PC-SCHED-02

### PC-BR-022 — Role-Restricted RBAC and Scoping

| Attribute | Specification Detail |
| --- | --- |
| **Rule ID** | PC-BR-022 |
| **Rule Name** | Role-Restricted RBAC and Scoping |
| **Rule Classification** | Authorization / Security |


**Operational Description / Policy Statement:**
Access to Placement Cell endpoints requires a verified module grant ('placement_cell') and fine-grained permission codes verified against the active session.

**Formal Operational & Enforcement Logic:**
```text
Guard: request.principal has HasModuleGrant('placement_cell') and required HasPermission(code).
Enforcement: fusion_auth.permissions, modules/placement/services/authz.py.
```

**Related Use Cases / Workflows / Traceability:** All Use Cases; PC-AFR-061

### PC-BR-023 — Sensitive Academic Data View Protection

| Attribute | Specification Detail |
| --- | --- |
| **Rule ID** | PC-BR-023 |
| **Rule Name** | Sensitive Academic Data View Protection |
| **Rule Classification** | Privacy / Data Protection |


**Operational Description / Policy Statement:**
Student CPI and grade transcripts are confidential and may only be viewed by authorized TPO staff and recruiters evaluating submitted applicants.

**Formal Operational & Enforcement Logic:**
```text
Scoping: Student CPI is never exposed on public dashboards or to other students. Recruiters see CPI only for candidates who actively submitted to their postings.
Enforcement: modules/placement/selectors/scoping.py, modules/placement/api/serializers.py.
```

**Related Use Cases / Workflows / Traceability:** PC-UC-003, PC-UC-016; PC-AFR-062

### PC-BR-024 — Sensitive Placement Data Modify Restriction

| Attribute | Specification Detail |
| --- | --- |
| **Rule ID** | PC-BR-024 |
| **Rule Name** | Sensitive Placement Data Modify Restriction |
| **Rule Classification** | Security / Audit Integrity |


**Operational Description / Policy Statement:**
Modifications to placement records, offer decisions, and interview evaluations require explicit write permissions and generate permanent audit log entries.

**Formal Operational & Enforcement Logic:**
```text
Guard: Writes require specific manage permissions. Every update logs actor ID, action name, before-state, after-state, and justification.
Enforcement: modules/placement/services/authz.py::require, modules/placement/services/clearance.py.
```

**Related Use Cases / Workflows / Traceability:** PC-UC-010; PC-AFR-064

### PC-BR-025 — Academic Master Data External Read-Only Invariant

| Attribute | Specification Detail |
| --- | --- |
| **Rule ID** | PC-BR-025 |
| **Rule Name** | Academic Master Data External Read-Only Invariant |
| **Rule Classification** | Architectural Invariant (ADR-0008) |


**Operational Description / Policy Statement:**
Placement Cell never computes, alters, or stores independent academic master data (CPI, course credits). It reads declared snapshots from IAM.

**Formal Operational & Enforcement Logic:**
```text
Invariant: No SQL writes to academic tables from Placement Cell. Standings are read via iam_client.get_academic_standings().
Enforcement: core/iam integration, modules/placement/domain/eligibility.py.
```

**Related Use Cases / Workflows / Traceability:** PC-UC-001, PC-UC-003; PC-AFR-063

### PC-BR-026 — IAM External Authentication Authority Invariant

| Attribute | Specification Detail |
| --- | --- |
| **Rule ID** | PC-BR-026 |
| **Rule Name** | IAM External Authentication Authority Invariant |
| **Rule Classification** | Architectural Invariant (ADR-0002) |


**Operational Description / Policy Statement:**
User authentication, credentials, passwords, and sessions are governed strictly by the Central Identity Service; Placement Cell does not store passwords.

**Formal Operational & Enforcement Logic:**
```text
Invariant: Placement Cell validates request.principal provided by fusion_auth middleware.
Enforcement: fusion_auth, config/settings/base.py.
```

**Related Use Cases / Workflows / Traceability:** All Use Cases; PC-AFR-061

### PC-BR-029 — Placement Record Administrative Correction

| Attribute | Specification Detail |
| --- | --- |
| **Rule ID** | PC-BR-029 |
| **Rule Name** | Placement Record Administrative Correction |
| **Rule Classification** | Administrative Audit / Data Quality |


**Operational Description / Policy Statement:**
TPO staff may correct clerical errors on existing placement records (CTC, category, active status) provided an explicit non-blank correction justification is submitted.

**Formal Operational & Enforcement Logic:**
```text
Guard: Actor has 'placement_cell.record.manage'; reason string is non-empty; company is editable only for off-campus records (campus company is tied to accepted offer).
Post-state: Record updated, audit event logged with before and after state.
Enforcement: modules/placement/services/clearance.py::update_placement_record, modules/placement/api/clearance.py.
```

**Related Use Cases / Workflows / Traceability:** PC-UC-010; PC-AFR-032; BW-PC-08

### PC-BR-030 — Institutional Autonomy in Selection Decisions

| Attribute | Specification Detail |
| --- | --- |
| **Rule ID** | PC-BR-030 |
| **Rule Name** | Institutional Autonomy in Selection Decisions |
| **Rule Classification** | Governance / Security Boundary |


**Operational Description / Policy Statement:**
Candidate shortlisting, interview progression, and offer decisions must be recorded strictly from deliberate employer or TPO actions; external automated overrides are prohibited.

**Formal Operational & Enforcement Logic:**
```text
Invariant: State machine transitions require explicit actor authentication; automated transitions occur solely for temporal timeouts (offer expiry).
Enforcement: modules/placement/domain/state_machine.py, modules/placement_cell/use_cases.py.
```

**Related Use Cases / Workflows / Traceability:** PC-UC-009, PC-UC-016, PC-UC-022; PC-AFR-047
