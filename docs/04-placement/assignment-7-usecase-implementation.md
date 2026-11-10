# Assignment 7 Placement Cell use-case implementation

Assignment 7 workflow code lives in the dedicated Django app package
modules/placement_cell. Existing Placement Cell models and migrations remain
owned by modules/placement so the two apps do not create duplicate tables.

## Use-case traceability

| Use case | CFR / AFR coverage | Business rules | Workflow coverage |
| --- | --- | --- | --- |
| PC-UC-015 Company opportunity submission | PC-CFR-007, PC-CFR-014; PC-AFR-018–022, PC-AFR-044–045 | PC-BR-003, 004, 006, 007 | BW-PC-02, BW-PC-03; CW-PC-01, CW-PC-04 |
| PC-UC-006 TPO posting publication | PC-CFR-007, PC-CFR-017; PC-AFR-017, 020–022, 050 | PC-BR-003, 004, 005, 021 | BW-PC-01, BW-PC-03; CW-PC-01, CW-PC-04 |
| PC-UC-003 Student application | PC-CFR-003, PC-CFR-017; PC-AFR-007–009, 051 | PC-BR-001, 002, 021, 022 | BW-PC-01–04; CW-PC-01, CW-PC-02, CW-PC-04 |
| PC-UC-016 Company application review | PC-CFR-015, PC-CFR-017; PC-AFR-046–048, 052–053 | PC-BR-009, 030 | BW-PC-04–06; CW-PC-02, CW-PC-04 |
| PC-UC-009 Interview scheduling | PC-CFR-009, PC-CFR-017; PC-AFR-026–028, 054 | PC-BR-011, 012, 021, 030 | BW-PC-05, BW-PC-06; CW-PC-02, CW-PC-04 |

PC-AFR-044/045 cover Company authorization boundaries. The implementation does
not make an institute approval decision on behalf of an external actor.

## Runtime endpoints

The dedicated Assignment 7 routes are mounted under /api/v1/placement-cell/:

- POST opportunities/{id}/submit — Company submits a complete draft into the
  TPO review queue. The implementation validates ownership, approval status,
  required content, eligibility-rule structure and the deadline, then stores
  pending_approval without publishing.
- POST opportunities/{id}/publish — TPO publishes an opportunity only after
  Company submission.
- POST opportunities/{id}/apply — Student submits through the existing profile,
  registration, eligibility and season-policy checks.
- POST applications/{id}/review — owning Company records shortlisted or
  rejected through the application state machine.
- POST opportunities/{id}/interviews — TPO creates a valid future round and
  schedules in-scope shortlisted applications.

## Code locations

- Use-case implementations and orchestration: modules/placement_cell/use_cases.py
- Request validation and HTTP handlers: modules/placement_cell/api/views.py
- Route declarations: modules/placement_cell/api/urls.py
- Django app registration: modules/placement_cell/apps.py, config/settings/base.py
- API mounting: config/urls.py

The new app uses the existing Placement persistence and lower-level domain
services for shared application, state-machine and interview behavior. It
keeps the assignment workflow code in its own folder without duplicating the
Placement Cell database schema.
