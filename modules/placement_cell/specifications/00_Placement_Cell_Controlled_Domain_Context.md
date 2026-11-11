# Placement Cell (PCMS) Controlled Domain Context

**Study RS1 / Assignment 7 — Domain Context & Vocabulary Baseline**

> *Reading note: This document intentionally contains only the domain vocabulary, architectural invariants, and role context shared across all Placement Cell (PCMS) specification artefacts. It establishes the baseline for actors, terminology, and system boundaries. Entitlements, validation gates, lifecycle transitions, and workflow sequences are governed by the accompanying Functional Requirements, Use Case, Business Rule, and Workflow Specifications.*

## 1. Domain Context

Fusion is the core institute Enterprise Resource Planning (ERP) platform for IIITDM Jabalpur, delivering comprehensive administrative, academic, student lifecycle, and placement services. Within Fusion, the Placement Cell (Placement Cell Management System — PCMS) manages end-to-end recruitment operations for graduating students across undergraduate (B.Tech), postgraduate (M.Tech, M.Des), and doctoral (Ph.D.) programmes.

The Placement Cell module orchestrates collaboration among three primary stakeholder communities: (1) Enrolled Students seeking employment, internships, and pre-placement offers; (2) Training and Placement Office (TPO) Officers and staff who administer institutional placement policies, schedule drives, verify records, and oversee compliance; and (3) Corporate Recruiters and employer organizations who register, draft opportunities, shortlist candidates, execute interview rounds, and extend job offers.

Key Architectural Invariants: As mandated by platform architecture decisions (ADR-0002, ADR-0008, ADR-0010, ADR-0013):
- Placement Cell never computes or recalculates academic grades, SPI, or CPI; it ingests an immutable declared academic snapshot from the identity and academic services (ADR-0008).
- User authentication, session management, and credential verification are externalized to the Central Identity Service (ADR-0002).
- Cross-module database foreign keys are strictly prohibited; inter-module references use invariant integer IDs (ADR-0013).
- Company recruiters operate in strict isolation, seeing only opportunities and applicants associated with their own verified company account.

## 2. Operational and Specification Scope

The specification baseline encompasses all campus placement drives, off-campus placement verifications, company onboarding workflows, student application lifecycles, interview coordination rounds, job offer governance, and institutional reporting. Specific capabilities include:
1. Corporate partner registration, profile verification, and TPO authorization.
2. Job opportunity creation, eligibility criteria specification, approval gating, and publishing.
3. Automated student eligibility validation against declared academic performance (CPI, branch, backlogs).
4. Application tracking through canonical states (Draft, Submitted, Under Review, Shortlisted, Interview Scheduled, Offer Extended, Placed).
5. Multi-stage interview scheduling (Screening, Technical, HR) with automated candidate notifications.
6. Offer extension, response deadline enforcement, multiple-offer / dream tier policies, and placement record generation.
7. Off-campus placement declaration and administrative verification.
8. Institutional placement statistics, historical trend analysis, small-cell floor privacy preservation, and administrative clearance.

## 3. Actor and Role Registry

| Role / Actor | Classification | Neutral Operational Description |
| --- | --- | --- |
| Student | Primary / Internal | An enrolled student (B.Tech, M.Tech, M.Des, Ph.D.) registered with the Placement Cell who browses postings, applies for eligible opportunities, attends interviews, and responds to offers. |
| Placement Officer / TPO Staff | Administrative / Internal | Authorized administrative staff and officers of the Training & Placement Cell who manage policies, review company drafts, schedule interview rounds, verify off-campus placements, correct records, and generate institute reports. |
| Company Recruiter / Employer | External Partner | Verified representative of an external corporate or public organization authorized to draft job opportunities, review applicant profiles, conduct interviews, and extend employment offers. |
| Alumni | Secondary / External | Graduated former student who has completed degree requirements; has read-only access to historical placement records and optional participation in student career mentorship. |
| System Scheduler / Time Event | System / Automated | Automated background execution daemon responsible for scheduled sweeps: expired job offer reclamation (5-minute beat), notification queue dispatching (1-minute beat), and statistical snapshot materialization. |


## 4. Controlled Glossary

| Term / Acronym | Full Expression | Controlled Operational Definition |
| --- | --- | --- |
| TPO | Training and Placement Officer / Office | The administrative department and officers responsible for campus placements and corporate relations. |
| CPI | Cumulative Performance Index | Cumulative academic grading metric (0.00–10.00). Read exclusively from declared academic snapshots; never calculated by Placement Cell. |
| SPI | Semester Performance Index | Academic grade index for an individual semester. Read exclusively from declared academic snapshots. |
| CTC | Cost to Company | Total annual gross financial package offered to a candidate, expressed in Lakhs Per Annum (LPA). |
| FTE | Full-Time Employment | Permanent regular employment category offered to graduating candidates. |
| PPO | Pre-Placement Offer | Job offer extended to a student following an internship before regular campus placement commences. |
| Frozen Criteria | Eligibility Criteria Immutability | Rule freezing eligibility conditions at the exact moment of job posting publication to protect applicant rights (PC-BR-002). |
| Closed Vocabulary | Strict Eligibility Attribute Set | The bounded dictionary of student attributes (cpi, discipline, batch, active_backlogs) allowed in posting criteria (PC-BR-004). |
| Tier Policy | Tiered Offer Governance | Institutional rules governing when a placed student may accept a higher-tier or 'Dream' job offer (PC-BR-015). |
| Small-Cell Floor | Statistical Anonymization Floor | Reporting safeguard suppressing salary aggregations for categories with fewer than 5 placed students to protect individual privacy (PC-BR-016). |
| Outbox Delivery | Transactional Notification Outbox | Reliable event dispatch mechanism persisting notification tasks atomically with domain writes before background dispatch (PC-BR-021). |
| Debarment | Disciplinary Sanction | Administrative sanction barring a student from placement activities due to policy violations, unexcused absence, or misconduct. |
| Clearance Certificate | Placement Clearance | Formal institutional clearance confirming that a student has fulfilled placement obligations, signed offer letters, or cleared off-campus documentation. |

