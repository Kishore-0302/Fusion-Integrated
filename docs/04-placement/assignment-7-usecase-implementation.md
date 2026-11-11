# Assignment 7 — Placement Cell Use-Case Implementation

All Assignment 7 code is integrated directly into the **`modules/placement`** Django app,
following the existing architecture (services → API views → URL routes → tests).
No separate app is required.

Formal requirement specification documents (`.docx` and `.md`) are in
`docs/04-placement/specifications/`.

---

## Use-Case Traceability

| Use Case | CFR / AFR Coverage | Business Rules | Workflow | Native Service | HTTP Endpoint |
|---|---|---|---|---|---|
| **PC-UC-015** Company opportunity submission | PC-CFR-007, 014; PC-AFR-018–022, 044, 045 | PC-BR-003, 004, 006, 007 | BW-PC-02, BW-PC-03; CW-PC-01, CW-PC-04 | `services/postings.submit()` | `POST /api/v1/placement/postings/<pk>/submit` |
| **PC-UC-006** TPO posting publication | PC-CFR-007, 017; PC-AFR-017, 020–022, 050 | PC-BR-002, 003, 005, 021 | BW-PC-01, BW-PC-03; CW-PC-01, CW-PC-04 | `services/postings.publish()` | `POST /api/v1/placement/postings/<pk>/publish` |
| **PC-UC-003** Student application submission | PC-CFR-003, 017; PC-AFR-007–009, 051 | PC-BR-001, 002, 021, 022 | BW-PC-01–04; CW-PC-01, CW-PC-02, CW-PC-04 | `services/applications.apply_to()` | `POST /api/v1/placement/applications/apply` |
| **PC-UC-005** Student application withdrawal | PC-CFR-004; PC-AFR-012 | PC-BR-008, 010, 022 | BW-PC-04 | `services/applications.transition(to_status="withdrawn")` | `POST /api/v1/placement/applications/<pk>/transition` |
| **PC-UC-016** Company application review | PC-CFR-015, 017; PC-AFR-046–048, 052, 053 | PC-BR-009, 030 | BW-PC-04–06; CW-PC-02, CW-PC-04 | `services/applications.transition()` | `POST /api/v1/placement/applications/<pk>/transition` |
| **PC-UC-009** Interview round scheduling | PC-CFR-009, 017; PC-AFR-026–028, 054 | PC-BR-011, 012, 021, 030 | BW-PC-05, BW-PC-06; CW-PC-02, CW-PC-04 | `services/interviews.schedule_round()` + `add_candidates()` | `POST /api/v1/placement/interviews/rounds` + `POST /api/v1/placement/interviews/rounds/<pk>/candidates` |
| **PC-UC-022** Extend formal job offer | PC-CFR-008, 017; PC-AFR-023, 024, 055 | PC-BR-009, 013, 021, 030 | BW-PC-07; CW-PC-01 | `services/offers.issue()` | `POST /api/v1/placement/offers/issue` |
| **PC-UC-008** Student responds to offer | PC-CFR-008; PC-AFR-024, 025, 031 | PC-BR-013, 014, 015, 021 | BW-PC-07, BW-PC-08; CW-PC-01 | `services/offers.respond()` | `POST /api/v1/placement/offers/<pk>/respond` |
| **PC-UC-010** Placement record correction | PC-CFR-010; PC-AFR-031, 032 | PC-BR-024, 029 | BW-PC-08; CW-PC-03, CW-PC-04 | `services/clearance.update_placement_record()` | `PATCH /api/v1/placement/records/<pk>/manage` |
| **PC-UC-013** Announcement management | PC-CFR-013, 017; PC-AFR-039–043, 056 | PC-BR-017, 018, 021 | CW-PC-01, CW-PC-04 | `services/announcements.publish()` | `POST /api/v1/placement/announcements` |
| **PC-UC-024** Student anonymised statistics | PC-CFR-011; PC-AFR-035, 038 | PC-BR-016 | CW-PC-04 | `services/stats.student_view()` | `GET /api/v1/placement/stats` |

---

## Code Locations

### New code (Assignment 7 additions)

| File | Purpose |
|---|---|
| `modules/placement/services/postings.py` | Added `submit()` function (PC-UC-015, BW-PC-02); modified `publish()` to enforce TPO-only publication (PC-BR-005) |
| `modules/placement/api/views.py` | Added `PostingSubmitView` (PC-UC-015) |
| `modules/placement/api/urls.py` | Added `postings/<pk>/submit` route |
| `modules/placement/tests/test_assignment7_use_cases.py` | 40+ tests covering all 11 UCs, tracing each to its UC/BR/workflow ID |
| `docs/04-placement/specifications/` | Formal `.docx` + `.md` specification documents |

### Pre-existing code that implements the other UCs

| File | Use Cases Covered |
|---|---|
| `modules/placement/services/applications.py` — `apply_to()`, `transition()` | PC-UC-003, PC-UC-005, PC-UC-016 |
| `modules/placement/services/interviews.py` — `schedule_round()`, `add_candidates()` | PC-UC-009 |
| `modules/placement/services/offers.py` — `issue()`, `respond()` | PC-UC-022, PC-UC-008 |
| `modules/placement/services/clearance.py` — `update_placement_record()` | PC-UC-010 |
| `modules/placement/services/announcements.py` — `publish()` | PC-UC-013 |
| `modules/placement/services/stats.py` — `student_view()`, `staff_view()` | PC-UC-024 |
| `modules/placement/api/views.py` — existing views | All UCs via HTTP |
| `modules/placement/api/urls.py` — existing routes | All UCs via HTTP |
| `modules/placement/selectors/scoping.py` — `postings_for()`, `applications_for()` | Data isolation across all UCs (PC-BR-001, PC-BR-022) |

---

## Key Business Rule Enforcement Points

| BR | Rule | Enforced In |
|---|---|---|
| **PC-BR-002** | Eligibility criteria frozen after publication | `services/postings.update()` checks `eligibility_rule_locked_at` |
| **PC-BR-003** | Posting must have description + eligibility rule + deadline | `services/postings.submit()` and `publish()` |
| **PC-BR-005** | Only TPO/staff may publish | `services/postings.publish()` checks `actor.kind != "recruiter"` |
| **PC-BR-006** | Company must be approved before posting | `services/postings.submit()` and `create()` check `company.can_operate` |
| **PC-BR-007** | Only recruiter may submit for company review | `services/postings.submit()` checks `actor.kind == "recruiter"` |
| **PC-BR-009** | Company review state machine | `domain/state_machine.py` TRANSITIONS + guards |
| **PC-BR-013** | Offer may only be issued to shortlisted applications | `services/offers.issue()` via state machine guard |
| **PC-BR-016** | Anonymised stats with small-cell floor | `services/stats.student_view()` |
| **PC-BR-017** | Only TPO/staff may publish announcements | `services/announcements.publish()` via `require()` |
| **PC-BR-022** | Module grant required | `HasModuleGrant("placement_cell")` on every view class |
| **PC-BR-024** | Mandatory audit reason for record corrections | `services/clearance.update_placement_record()` |
| **PC-BR-029** | Only authorised staff may amend records | `services/clearance.update_placement_record()` via `require()` |
| **PC-BR-030** | Rejection reason required | `services/applications.transition()` guards |

---

## Specification Documents

Stored in `docs/04-placement/specifications/`:

| Document | Contents |
|---|---|
| `00_Placement_Cell_Controlled_Domain_Context.md` | Domain model, actors, terminology |
| `01_Placement_Cell_Functional_Requirements.md` | 19 PC-CFR + 64 PC-AFR requirements |
| `02_Part1_Placement_Cell_Use_Case_Specifications.md` | 22 UCs + 3 scheduled functions (brief form) |
| `03_Part2-3_Placement_Cell_Use_Case_Specifications.md` | Full UC specs with pre/post-conditions and BR cross-refs |
| `04_Part2-3_Placement_Cell_Business_Rule_Specifications.md` | 26 PC-BR + 4 PC-AF-BR rules |
| `05_Part3_Placement_Cell_Workflow_Specifications.md` | 8 BW-PC + 4 CW-PC workflows |

---

## PR #445 (PBI 17) Integration and Tweaks

The features from PR #445 (`Akulachatur:PCMS_17`) have been integrated into `modules/placement` with necessary stability and architectural tweaks:

| Feature from PR #445 | Original PR Approach | Tweaked Implementation |
|---|---|---|
| **Debarment & Clearance Models** | Raw `StudentClearance` & `DebarmentRecord` in `models/students.py` without migrations or exports | Models integrated with clean defaults, indexed tables, exported in `models/__init__.__all__`, and migration `0011_debarmentrecord_studentclearance.py` generated |
| **Eligibility Verification** | `evaluate_student_eligibility` with brittle strict-key checks (`<` on None, empty branches always failing) | Robust defensive evaluation supporting both simplified dict format (`min_cpi`, `eligible_branches`, `max_backlogs`) and native AST rules, case-insensitive branch matching, and safe None handling |
| **State Machine Wrapper** | `transition_application_state` raising bare `ValueError` on failed transition | Exception chaining (`raise ValueError(...) from exc`), verified against state machine rules and roles |
| **Application Queryset Scoping** | `scope_applications_queryset` expecting `user.id` | Handles user object or user ID integer, supports multiple role collection shapes, isolates recruiter applications |
| **Application Submission Service** | `submit_application` using invalid notification kwargs (`event=`) and unauthenticated transition | Atomic submission recording proper `ApplicationTransition` (`DRAFT` -> `SUBMITTED`) and valid outbox notification enqueue |
| **Offer Expiry Celery Task** | `expire_pending_offers` with faulty notification parameters and incomplete state transitions | Registered `@shared_task(name="placement.expire_pending_offers")` delegating to idempotent `offers.expire_overdue()` |
| **Placement Record Update View & Serializer** | `PlacementRecordUpdateSerializer` referencing non-existent model columns (`verified_by_user_id`, `is_accepted`) | Updated serializer and `PlacementRecordUpdateView` mapping audit fields cleanly to existing `PlacementRecord` schema |
| **Reports Page Season Selection** | Standalone `reportspage.tsx` dumped in repo root with disconnected `useStats()` | Integrated directly into `client/src/modules/placement/pages/ReportsPage.tsx` with Mantine `Select`, dynamic season state passed to `useStats(season)` |
| **Specification Documents** | `17-Placement Cell/*.docx` and `*.xlsx` | Downloaded and archived in `17-Placement Cell/` to preserve complete course deliverables |

