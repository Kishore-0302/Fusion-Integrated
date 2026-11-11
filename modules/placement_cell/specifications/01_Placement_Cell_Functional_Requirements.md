# Placement Cell Functional Requirements Specification

**Consolidated & Atomic Requirements Registry (PC-CFR / PC-AFR)**

> *Reading note: Use this specification as the authoritative requirements source for all Placement Cell (PCMS) engineering and verification activities. Each requirement carries a stable identifier: Consolidated Functional Requirements (PC-CFR-xxx) capture high-level institutional capabilities, while Atomic Functional Requirements (PC-AFR-xxx) specify exact testable behaviors. Requirements are grouped by functional area for systematic navigation. Where a requirement refers to 'effective policy' or 'frozen criteria', it designates the immutable rules enforced at runtime.*

## 1. How to Read This Specification

1. Requirement Identifiers: Reference requirements using the stable identifier (e.g., PC-CFR-007 for posting management, PC-AFR-022 for criteria freezing).
2. Granularity: CFR identifiers aggregate related functional capabilities; AFR identifiers denote atomic, single-assertion statements designed for direct automated verification.
3. Cross-Cutting Invariants: Academic performance metrics are ingested exclusively from declared snapshots (ADR-0008). Identity and authorization derive from external IAM sessions (ADR-0002). Module data isolation strictly separates company-scoped views.

## 2. Functional Requirements Registry

### Area 1: Company Registration & Authorization (PC-CFR-014)

| Requirement ID | Requirement Statement |
| --- | --- |
| PC-CFR-014 | The system shall provide comprehensive workflows for corporate employer registration, profile validation, and administrative authorization. |
| PC-AFR-044 | The system shall allow corporate employers to register organization details, point-of-contact information, and hiring domains. |
| PC-AFR-045 | The system shall require TPO authorization and verification before an employer account is permitted to create job postings or participate in drives (PC-BR-007). |


### Area 2: Job Opportunity & Posting Management (PC-CFR-007)

| Requirement ID | Requirement Statement |
| --- | --- |
| PC-CFR-007 | The system shall govern the complete lifecycle of recruitment postings from draft creation, approval gating, and publication through application closure. |
| PC-AFR-017 | The system shall allow authorized TPO staff to create, edit, and publish job postings on behalf of approved companies (PC-BR-005). |
| PC-AFR-018 | The system shall allow approved corporate recruiters to draft job opportunity postings for institute review (PC-BR-006). |
| PC-AFR-019 | The system shall require mandatory posting fields including job title, employment type, description, compensation (CTC), eligibility rule, and application deadline (PC-BR-003). |
| PC-AFR-020 | The system shall validate eligibility criteria using a closed, strict attribute vocabulary (CPI, discipline, batch, active backlogs) (PC-BR-004). |
| PC-AFR-021 | The system shall require company-drafted opportunities to transition to pending approval before TPO publication (PC-UC-015, BW-PC-02). |
| PC-AFR-022 | The system shall freeze eligibility criteria immediately upon posting publication to guarantee fairness to early applicants (PC-BR-002). |


### Area 3: Student Profile, Eligibility & Registration (PC-CFR-001, PC-CFR-002)

| Requirement ID | Requirement Statement |
| --- | --- |
| PC-CFR-001 | The system shall verify student registration, academic eligibility, and profile completeness prior to admitting students to recruitment drives. |
| PC-CFR-002 | The system shall evaluate student eligibility dynamically against posting criteria while preserving academic master data integrity. |
| PC-AFR-001 | The system shall verify student registration and academic standing from the declared IAM academic snapshot before permitting placement participation. |
| PC-AFR-002 | The system shall verify profile completeness against the institutional portal before allowing a student to apply for opportunities (PC-BR-001). |
| PC-AFR-003 | The system shall evaluate student eligibility criteria dynamically against the frozen criteria of published postings without modifying student records. |
| PC-AFR-004 | The system shall fail closed with an explicit disqualification reason whenever an academic attribute is missing or does not satisfy posting criteria. |
| PC-AFR-005 | The system shall enforce placement season registration fees or clearance prerequisites when configured by the placement policy. |
| PC-AFR-006 | The system shall prohibit students under disciplinary debarment or active sanctions from registering or applying. |


### Area 4: Student Application Submission & Tracking (PC-CFR-003, PC-CFR-004)

| Requirement ID | Requirement Statement |
| --- | --- |
| PC-CFR-003 | The system shall allow eligible students to submit applications and track progression across all recruitment stages. |
| PC-CFR-004 | The system shall maintain an immutable lifecycle history for every application from submission through terminal outcome. |
| PC-AFR-007 | The system shall allow eligible students to submit applications to published job postings prior to the application deadline. |
| PC-AFR-008 | The system shall capture student cover notes and attach the verified resume from the profile portal during submission. |
| PC-AFR-009 | The system shall maintain an immutable, chronological audit trail of all state transitions and timestamps for every application (PC-BR-008). |
| PC-AFR-010 | The system shall enforce canonical application lifecycle states: Submitted, Under Review, Shortlisted, Interview Scheduled, Offer Extended, Offer Accepted, Offer Declined, and Rejected. |
| PC-AFR-011 | The system shall permit students to view real-time status and timeline updates for their submitted applications (PC-UC-004). |
| PC-AFR-012 | The system shall allow students to withdraw applications before employer shortlisting begins (PC-UC-005). |


### Area 5: Company Application Review & Shortlisting (PC-CFR-015)

| Requirement ID | Requirement Statement |
| --- | --- |
| PC-CFR-015 | The system shall enable authorized corporate recruiters to inspect applicants and record candidate shortlisting decisions in secure isolation. |
| PC-AFR-046 | The system shall provide approved recruiters access to view applications submitted exclusively to their company's job postings (PC-BR-009). |
| PC-AFR-047 | The system shall allow recruiters to transition applicant status between Under Review, Shortlisted, and Rejected (PC-UC-016). |
| PC-AFR-048 | The system shall enforce mandatory rationale or feedback when an applicant is rejected or placed under hold. |
| PC-AFR-049 | The system shall restrict recruiters from accessing applications or resumes submitted to other employers (PC-BR-009). |


### Area 6: Interview Scheduling & Round Coordination (PC-CFR-009)

| Requirement ID | Requirement Statement |
| --- | --- |
| PC-CFR-009 | The system shall provide structured interview management across multiple sequential assessment rounds. |
| PC-AFR-026 | The system shall allow TPO staff and authorized recruiters to configure sequential interview rounds (screening, technical, HR, presentation). |
| PC-AFR-027 | The system shall enforce mandatory date, time slot, interview mode (online/offline), and venue or virtual meeting link for each round (PC-BR-011). |
| PC-AFR-028 | The system shall populate rounds exclusively from candidates who have achieved shortlisted status in preceding stages. |
| PC-AFR-029 | The system shall notify shortlisted candidates automatically upon round scheduling (PC-BR-012, PC-AFR-054). |
| PC-AFR-030 | The system shall capture candidate attendance, interviewer evaluations, and stage progression outcomes. |


### Area 7: Job Offer Management & Tier Policies (PC-CFR-008)

| Requirement ID | Requirement Statement |
| --- | --- |
| PC-CFR-008 | The system shall manage formal job offer extensions, automated deadline enforcement, and institutional dream tier governance. |
| PC-AFR-023 | The system shall allow recruiters and TPO staff to extend formal job offers specifying role, CTC, joining location, and response deadline (PC-UC-022). |
| PC-AFR-024 | The system shall enforce an automated response expiry deadline on all extended offers, releasing unresponsive candidate allocations (PC-BR-013). |
| PC-AFR-025 | The system shall enforce institutional multiple-offer policies, preventing non-dream upgrades once a primary offer is accepted (PC-BR-015). |


### Area 8: Placement Records & Administrative Clearance (PC-CFR-010)

| Requirement ID | Requirement Statement |
| --- | --- |
| PC-CFR-010 | The system shall maintain verified placement records and administer student placement clearance procedures. |
| PC-AFR-031 | The system shall generate a verified Placement Record automatically upon student offer acceptance or verified off-campus declaration (PC-BR-014). |
| PC-AFR-032 | The system shall provide administrative endpoints for TPO staff to correct erroneous records or deactivate invalid placements with a mandatory audit reason (PC-UC-010, PC-BR-029). |


### Area 9: Reports, Metrics & Analytics (PC-CFR-011, PC-CFR-012)

| Requirement ID | Requirement Statement |
| --- | --- |
| PC-CFR-011 | The system shall generate comprehensive statistical analytics on institutional placement performance, salary metrics, and participation trends. |
| PC-CFR-012 | The system shall provide multi-season comparative reporting for regulatory compliance, accreditation, and student career guidance. |
| PC-AFR-033 | The system shall compute placement percentage, mean CTC, median CTC, and maximum CTC per placement season. |
| PC-AFR-034 | The system shall generate cross-season company participation trends and multi-year recruitment volume metrics (PC-UC-012). |
| PC-AFR-035 | The system shall compute salary package distribution bands while enforcing small-cell floors to preserve student anonymity (PC-BR-016). |
| PC-AFR-036 | The system shall generate discipline-wise and programme-wise employment trends for institutional accreditation. |
| PC-AFR-037 | The system shall maintain pre-computed, materialized statistical snapshots to serve high-volume dashboard requests without live query overhead. |
| PC-AFR-038 | The system shall provide students with historical placement insights filtered by discipline and season (PC-UC-024). |


### Area 10: Announcements & Notice Board (PC-CFR-013)

| Requirement ID | Requirement Statement |
| --- | --- |
| PC-CFR-013 | The system shall provide a targeted notification and announcement notice board for recruitment communication. |
| PC-AFR-039 | The system shall allow TPO staff to publish recruitment notices, drive schedules, and interview alerts (PC-UC-013). |
| PC-AFR-040 | The system shall restrict announcement topics to pre-configured categories (drives, shortlisted, results, general) (PC-BR-017). |
| PC-AFR-041 | The system shall deliver active announcements to enrolled students via real-time student dashboards (PC-UC-020). |
| PC-AFR-042 | The system shall preserve historical versions of modified or retracted notices for administrative transparency (PC-BR-018, PC-AFR-043). |
| PC-AFR-043 | The system shall record retraction rationale whenever an announcement is deactivated. |


### Area 11: Automated Notifications & Communication (PC-CFR-017)

| Requirement ID | Requirement Statement |
| --- | --- |
| PC-CFR-017 | The system shall dispatch guaranteed, automated notifications for all significant recruitment lifecycle events. |
| PC-AFR-050 | The system shall enqueue notifications when a new job posting is published to eligible students. |
| PC-AFR-051 | The system shall enqueue an acknowledgment notification when an application is successfully submitted. |
| PC-AFR-052 | The system shall enqueue a notification when an applicant is shortlisted for further assessment. |
| PC-AFR-053 | The system shall enqueue a notification when an applicant is rejected. |
| PC-AFR-054 | The system shall enqueue a notification when an interview round is scheduled with venue/link details. |
| PC-AFR-055 | The system shall enqueue a notification when a job offer is extended to a student with deadline countdown. |
| PC-AFR-056 | The system shall enqueue a broadcast notification when a critical announcement is released. |
| PC-AFR-057 | The system shall process outbox notifications through background Celery workers, guaranteeing asynchronous, reliable delivery (PC-BR-021). |


### Area 12: Alumni & Historical Access (PC-CFR-018)

| Requirement ID | Requirement Statement |
| --- | --- |
| PC-CFR-018 | The system shall support alumni career continuity through verified placement record access and mentorship participation. |
| PC-AFR-058 | The system shall provide graduated alumni read-only access to their past placement records and clearance letters (PC-UC-017). |
| PC-AFR-059 | The system shall support opt-in alumni mentorship profiles connecting past graduates with current aspirants (PC-BR-019). |
| PC-AFR-060 | The system shall strictly isolate alumni accounts from active recruitment drives, application queues, and interview rounds (PC-BR-020). |


### Area 13: System Access Control, Privacy & Audit (PC-CFR-019)

| Requirement ID | Requirement Statement |
| --- | --- |
| PC-CFR-019 | The system shall enforce rigorous role-based access control, sensitive academic data protection, and immutable operational audit logging. |
| PC-AFR-061 | The system shall enforce role-based access control (RBAC) via module grants and fine-grained permission codes across all endpoints (PC-BR-022). |
| PC-AFR-062 | The system shall restrict student sensitive academic data (CPI/SPI) to authorized TPO staff and verified recruiters (PC-BR-023). |
| PC-AFR-063 | The system shall prohibit modification of academic master data, grades, and external identity records within Placement Cell (PC-BR-025). |
| PC-AFR-064 | The system shall record tamper-evident audit logs capturing timestamp, user ID, client IP, action name, and state changes for all sensitive operations (PC-BR-024). |

