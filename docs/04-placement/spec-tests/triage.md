# Placement Cell spec-test verification

Design commit: `3ada512` (`Add placement spec test designs`).

Assignment submitter: **Kishore** (`@Kishore-0302`).

Implementation: PCMS Assignment 9 implementation by Kishore (`@Kishore-0302`).

Verification command from the repository root:

```powershell
.\.venv\Scripts\python.exe -m pytest -q modules/placement/tests/spec modules/placement/tests/test_fr_student1.py
```

The command completed successfully in this checkout on 2026-11-25. The summary
below reports collected cases; coverage was not collected in this run.

## Results

| Strategy | Cases | Passed | Failed | Skipped |
|----------|------:|-------:|-------:|--------:|
| UC | 71 | 71 | 0 | 0 |
| WF | 8 | 8 | 0 | 0 |
| BR | 42 | 42 | 0 | 0 |
| FR | 60 | 60 | 0 | 0 |
| Regression (`test_fr_student1.py`) | 6 | 6 | 0 | 0 |
| **Total** | **187** | **187** | **0** | **0** |

The frozen FR design has 64 entries. Four entries (PC-AFR-001, PC-AFR-002,
PC-AFR-003, and PC-AFR-005) are excluded from the 60 automated cases by the
design's prior scope interpretation. The supplied v1.3 final specification
lists them as active requirements, so that interpretation remains to be
reconciled; this test result does not establish those requirements as met.

## Defects resolved in the implementation

| Source | Finding | Resolution evidence |
|--------|---------|--------------------|
| PC-UC-003 Exception E2; PC-AFR-008 | Applying with a Decimal CPI raised `TypeError: Object of type Decimal is not JSON serializable` while persisting the eligibility snapshot. | Snapshot values are made JSON-safe in `applications.py`; regression coverage is in `test_lifecycle.py::test_apply_to_ineligible_with_decimal_cpi_snapshot_regression`. |
| PC-AFR-031; PC-AFR-032 | TPO placement-record maintenance for student and alumni records. | `services/clearance.py::update_record` and `test_clearance.py::test_tpo_can_update_student_and_alumni_placement_record`. |

## Clarifications still open

| Source | Open point | Handling |
|--------|------------|----------|
| ISS-PC-025 | Notification recipients for application submission, shortlisting, and rejection are unresolved in the specification. | No recipient behavior is inferred here. |
| ISS-PC-026 | The company-side institutional approver and approval mechanism are unresolved. | No approver or approval workflow is inferred here. |
| PC-AFR-001/002/003/005 | The frozen test design treats these as ERP-owned, while the supplied final requirements list them as active PCMS requirements. | Resolve scope and traceability before claiming requirement coverage. |
