# Placement Cell (PCMS) — Assignment 7 Implementation & Specifications

This directory (`modules/placement_cell/`) contains the complete Assignment 7 delivery for the **Placement Cell Management System (PCMS)** in `Fusion-Integrated`.

It provides:
1. **The Full Requirement Specification Baseline** modeled strictly on institutional standards, provided in both Word (`.docx`) and GitHub-flavored Markdown (`.md`) formats under `modules/placement_cell/specifications/`.
2. **Domain Orchestration & Use Case Services** in `modules/placement_cell/use_cases.py`.
3. **REST API Endpoints & Request Adapters** in `modules/placement_cell/api/views.py` and `modules/placement_cell/api/urls.py`.
4. **Automated Unit & Workflow Test Suites** in `modules/placement_cell/tests/test_use_cases.py`.

---

## 1. Specification Artefacts

The specifications below mirror the formal structure, sections, and tables of the study baseline documents, tailored strictly to the Placement Cell domain:

| Artefact ID | Document Title | Formats | Primary Contents |
|---|---|---|---|
| **00** | [Controlled Domain Context](specifications/00_Placement_Cell_Controlled_Domain_Context.md) | [`.docx`](specifications/00_Placement_Cell_Controlled_Domain_Context.docx) · [`.md`](specifications/00_Placement_Cell_Controlled_Domain_Context.md) | Domain context, architecture invariants (ADR-0002, 0008, 0013), actor/role registry, and controlled glossary. |
| **01** | [Functional Requirements Specification](specifications/01_Placement_Cell_Functional_Requirements.md) | [`.docx`](specifications/01_Placement_Cell_Functional_Requirements.docx) · [`.md`](specifications/01_Placement_Cell_Functional_Requirements.md) | Complete registry of 19 Consolidated (PC-CFR) and 64 Atomic (PC-AFR) functional requirements across 13 functional areas. |
| **02** | [Use Case Specifications (Part 1)](specifications/02_Part1_Placement_Cell_Use_Case_Specifications.md) | [`.docx`](specifications/02_Part1_Placement_Cell_Use_Case_Specifications.docx) · [`.md`](specifications/02_Part1_Placement_Cell_Use_Case_Specifications.md) | Standard format specifications for all 22 active use cases (PC-UC-001 to 024) plus 3 scheduled background functions. |
| **03** | [Use Case Specifications (Part 2-3)](specifications/03_Part2-3_Placement_Cell_Use_Case_Specifications.md) | [`.docx`](specifications/03_Part2-3_Placement_Cell_Use_Case_Specifications.docx) · [`.md`](specifications/03_Part2-3_Placement_Cell_Use_Case_Specifications.md) | Enriched use case specifications with step-by-step cross-references to Applicable Business Rules (PC-BR-001 to 030). |
| **04** | [Business Rule Specifications](specifications/04_Part2-3_Placement_Cell_Business_Rule_Specifications.md) | [`.docx`](specifications/04_Part2-3_Placement_Cell_Business_Rule_Specifications.docx) · [`.md`](specifications/04_Part2-3_Placement_Cell_Business_Rule_Specifications.md) | Comprehensive specifications for all 26 active and 4 retired business rules with formal logic and enforcement points. |
| **05** | [Workflow Specifications](specifications/05_Part3_Placement_Cell_Workflow_Specifications.md) | [`.docx`](specifications/05_Part3_Placement_Cell_Workflow_Specifications.docx) · [`.md`](specifications/05_Part3_Placement_Cell_Workflow_Specifications.md) | Collaboration and lifecycle progression as state transition matrices: 8 Basis (BW-PC) and 4 Composite (CW-PC) workflows. |

---

## 2. Requirements & Traceability Matrix

| Use Case ID & Name | CFR / AFR Coverage | Business Rules | Workflow Coverage | Code Implementation / Endpoint |
|---|---|---|---|---|
| **PC-UC-014** Company Registration & Auth | PC-CFR-014; PC-AFR-044, 045 | PC-BR-007 | BW-PC-01; CW-PC-01 | `services/companies.py::register`, `approve` |
| **PC-UC-015** Company Opportunity Submission | PC-CFR-007, 014; PC-AFR-018–022, 044, 045 | PC-BR-003, 004, 006, 007 | BW-PC-02, 03; CW-PC-01, 04 | `use_cases.py::submit_company_opportunity`<br>`POST opportunities/{id}/submit` |
| **PC-UC-006** TPO Opportunity Publication | PC-CFR-007, 017; PC-AFR-017, 020–022, 050 | PC-BR-002, 003, 005, 021 | BW-PC-01, 03; CW-PC-01, 04 | `use_cases.py::publish_tpo_opportunity`<br>`POST opportunities/{id}/publish` |
| **PC-UC-001** Student Profile Verification | PC-CFR-001; PC-AFR-001, 002 | PC-BR-001, 022, 025 | BW-PC-04; CW-PC-01 | `services/registration.py::register` |
| **PC-UC-002** Browse Opportunities | PC-CFR-002, 007; PC-AFR-003, 017 | PC-BR-002, 003, 004 | BW-PC-03, 04 | `selectors/scoping.py::postings_for` |
| **PC-UC-003** Student Application | PC-CFR-003, 017; PC-AFR-007–009, 051 | PC-BR-001, 002, 021, 022 | BW-PC-01–04; CW-PC-01, 02 | `use_cases.py::apply_to_opportunity`<br>`POST opportunities/{id}/apply` |
| **PC-UC-004** Track Application Status | PC-CFR-004; PC-AFR-011 | PC-BR-008, 022 | BW-PC-04 | `selectors/scoping.py::applications_for` |
| **PC-UC-005** Withdraw Application | PC-CFR-004; PC-AFR-012 | PC-BR-008, 010, 022 | BW-PC-04 | `use_cases.py::withdraw_application`<br>`POST applications/{id}/withdraw` |
| **PC-UC-016** Company Application Review | PC-CFR-015, 017; PC-AFR-046–048, 052, 053 | PC-BR-009, 030 | BW-PC-04–06; CW-PC-02 | `use_cases.py::review_company_application`<br>`POST applications/{id}/review` |
| **PC-UC-009** Interview Scheduling | PC-CFR-009, 017; PC-AFR-026–028, 054 | PC-BR-011, 012, 021, 030 | BW-PC-05, 06; CW-PC-02 | `use_cases.py::schedule_interviews`<br>`POST opportunities/{id}/interviews` |
| **PC-UC-021** Company Coordinate Slots | PC-CFR-009; PC-AFR-026, 027 | PC-BR-011 | BW-PC-06; CW-PC-02 | `services/interviews.py` |
| **PC-UC-022** Extend Job Offer | PC-CFR-008, 017; PC-AFR-023, 024, 055 | PC-BR-009, 013, 021, 030 | BW-PC-07; CW-PC-01 | `use_cases.py::issue_job_offer`<br>`POST applications/{id}/offers` |
| **PC-UC-008** Respond to Job Offer | PC-CFR-008; PC-AFR-024, 025, 031 | PC-BR-013, 014, 015, 021 | BW-PC-07, 08; CW-PC-01 | `use_cases.py::respond_to_offer`<br>`POST offers/{id}/respond` |
| **PC-UC-010** Placement Record Corrections | PC-CFR-010; PC-AFR-031, 032 | PC-BR-024, 029 | BW-PC-08; CW-PC-03, 04 | `use_cases.py::update_placement_record`<br>`PATCH records/{id}/manage` |
| **PC-UC-013** Placement Announcements | PC-CFR-013, 017; PC-AFR-039–043, 056 | PC-BR-017, 018, 021 | CW-PC-01, 04 | `use_cases.py::publish_announcement`<br>`POST announcements` |
| **PC-UC-020** View Announcements | PC-CFR-013; PC-AFR-041 | PC-BR-017, 018 | CW-PC-01 | `selectors/scoping.py::announcements_for` |
| **PC-UC-011** Season Reports & Analytics | PC-CFR-011, 012; PC-AFR-033, 036, 037 | PC-BR-016 | CW-PC-04 | `services/stats.py::rebuild` |
| **PC-UC-012** Company Participation Stats | PC-CFR-011, 012; PC-AFR-034 | PC-BR-016 | CW-PC-04 | `services/stats.py::_by_company` |
| **PC-UC-024** Student Anonymized Statistics | PC-CFR-011; PC-AFR-035, 038 | PC-BR-016 | CW-PC-04 | `use_cases.py::get_student_stats`<br>`GET stats` |
| **PC-UC-017** Alumni Mentorship & History | PC-CFR-018; PC-AFR-058–060 | PC-BR-019, 020 | CW-PC-04 | `selectors/scoping.py::records_for` |
| **PC-UC-023** Sync Resume from Portal | PC-CFR-001; PC-AFR-008 | PC-BR-001 | BW-PC-04 | IAM projection integration |
| **PC-UC-007** Automated Notifications | PC-CFR-017; PC-AFR-050–057 | PC-BR-021 | Across all workflows | `tasks.py::drain_notification_outbox` |

---

## 3. Runtime API Endpoints

All Assignment 7 routes are mounted under `/api/v1/placement-cell/`:

- `POST /api/v1/placement-cell/opportunities/{id}/submit` — Company submits draft opportunity into TPO review queue.
- `POST /api/v1/placement-cell/opportunities/{id}/publish` — TPO publishes opportunity, freezing eligibility criteria.
- `POST /api/v1/placement-cell/opportunities/{id}/apply` — Student applies through profile, eligibility, and season tier checks.
- `POST /api/v1/placement-cell/applications/{id}/withdraw` — Student withdraws an active submitted application.
- `POST /api/v1/placement-cell/applications/{id}/review` — Owning Company records `under_review`, `shortlisted`, or `rejected`.
- `POST /api/v1/placement-cell/opportunities/{id}/interviews` — TPO schedules interview round with shortlisted candidates.
- `POST /api/v1/placement-cell/applications/{id}/offers` — Recruiter extends formal job offer with response deadline.
- `POST /api/v1/placement-cell/offers/{id}/respond` — Student accepts or declines offer (acceptance creates PlacementRecord).
- `PATCH /api/v1/placement-cell/records/{id}/manage` — TPO corrects placement record with mandatory audit justification.
- `POST /api/v1/placement-cell/announcements` — TPO publishes recruitment alerts with bounded topic taxonomy.
- `GET /api/v1/placement-cell/stats` — Student views anonymized salary and hiring statistics with small-cell floor protection.

---

## 4. Key Architecture Invariants Enforced

1. **Academic Snapshot Immutability (ADR-0008, PC-BR-025)**: Placement Cell never calculates CPI or edits grades; it consumes declared snapshots from the Identity Service.
2. **Criteria Freezing on Publish (PC-BR-002)**: At the moment a posting is published, `eligibility_rule_locked_at` is stamped, preventing silent moving of goalposts for early applicants.
3. **Company Data Isolation (PC-BR-009)**: Corporate accounts can only view postings, applicants, and resumes submitted to their own company. Accessing foreign rows returns `NotFoundError` (404).
4. **Reliable Outbox Delivery (ADR-0006, PC-BR-021)**: Notifications are committed transactionally to `NotificationOutbox` inside the triggering domain transaction; Celery workers deliver them asynchronously.
5. **Zero Cross-Module Foreign Keys (ADR-0013)**: Inter-module references (e.g. to student user IDs) use unconstrained integer identifiers.
