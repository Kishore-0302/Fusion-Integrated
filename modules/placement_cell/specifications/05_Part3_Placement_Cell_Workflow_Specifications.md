# Placement Cell Workflow Specifications

**Collaboration and Lifecycle Progression Expressed as State Transitions (BW-PC / CW-PC)**

> *Reading note: Read each state-transition row from From state through Actor/role, Use Case/Function, and Guard/outcome to Resulting state. Use the Use Case/Function and Business Rule identifiers as cross-references to the accompanying specifications (Documents 01, 02, 03, and 04).*

## 1. Workflow Index

| Workflow ID | Workflow Name | Type | Operational Purpose |
| --- | --- | --- | --- |
| BW-PC-01 | Company Registration and Verification Workflow | Basis Workflow | Coordinate corporate partner onboarding from initial registration through administrative verification and recruiter credential generation. |
| BW-PC-02 | Job Opportunity Creation and Submission Workflow | Basis Workflow | Coordinate the preparation of recruitment job postings by approved employers, validation of mandatory fields, and submission for TPO review. |
| BW-PC-03 | TPO Review and Opportunity Publication Workflow | Basis Workflow | Coordinate TPO compliance verification of submitted job postings, freezing of eligibility criteria, and publication to students. |
| BW-PC-04 | Student Application and Eligibility Workflow | Basis Workflow | Coordinate student job applications, dynamic eligibility evaluation, dream tier validation, and immutable submission recording. |
| BW-PC-05 | Application Review and Shortlisting Workflow | Basis Workflow | Coordinate corporate recruiter evaluation of applicant profiles and recording of screening decisions. |
| BW-PC-06 | Interview Round Scheduling and Execution Workflow | Basis Workflow | Coordinate creation of interview rounds, candidate slot assignment, invitation dispatch, and stage progression tracking. |
| BW-PC-07 | Job Offer Issuance and Student Response Workflow | Basis Workflow | Coordinate formal employment offer extension, response deadline enforcement, acceptance validation, and automated expiry sweeps. |
| BW-PC-08 | Placement Record Recording and Audit Workflow | Basis Workflow | Coordinate verified placement record persistence, off-campus placement documentation, and TPO administrative corrections. |
| CW-PC-01 | End-to-End Campus Recruitment Drive Composite Workflow | Composite Workflow | Orchestrates the entire institutional campus drive across multiple basis workflows: Company Onboarding (BW-PC-01) -> Job Posting (BW-PC-02, 03) -> Student Application (BW-PC-04) -> Review & Interviews (BW-PC-05, 06) -> Offer & Placement (BW-PC-07, 08). |
| CW-PC-02 | Multi-Stage Candidate Evaluation Pipeline Composite Workflow | Composite Workflow | Orchestrates candidate progression across multiple sequential evaluation barriers (Resume Screening -> Online Technical Test -> Technical Interview -> HR Interview -> Final Shortlist). |
| CW-PC-03 | Off-Campus Placement Recording and Verification Composite Workflow | Composite Workflow | Governs the declaration, evidence submission, administrative verification, and clearance of student employment offers obtained outside campus drives. |
| CW-PC-04 | Placement Season Clearance and Audit Composite Workflow | Composite Workflow | Coordinates end-of-season institutional governance: clearance verification, sanction resolution, offer letter archiving, and statistical snapshot freezing. |


## 2. Detailed Workflow Specifications

### BW-PC-01 — Company Registration and Verification Workflow

| Field | Specification Details |
| --- | --- |
| **Workflow ID** | BW-PC-01 |
| **Workflow Name** | Company Registration and Verification Workflow |
| **Classification** | Basis Workflow |
| **Operational Purpose** | Coordinate corporate partner onboarding from initial registration through administrative verification and recruiter credential generation. |
| **Initial State** | Unregistered / Draft |


#### State Transition Matrix

| Step | From State | Actor / Entity | Use Case / Function | Guard / Outcome | Resulting State | Applicable Business Rules |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | Draft / Unregistered | Corporate Employer | PC-UC-014 (Submit Profile) | Complete contact, domain, and organizational details | Pending TPO Approval | PC-BR-007 |
| 2 | Pending TPO Approval | TPO Staff | PC-UC-014 (Review & Approve) | Legitimate enterprise, past hiring compliance verified | Approved | PC-BR-007 |
| 3 | Pending TPO Approval | TPO Staff | PC-UC-014 (Reject Profile) | Incomplete documentation or policy violation | Rejected | PC-BR-007 |
| 4 | Approved | Placement Cell | PC-UC-014 (Enable Recruiter) | can_operate set to True; recruiter invitation issued | Operational / Ready | PC-BR-006, PC-BR-007 |


**Terminal States and Outcomes:**
Approved and Operational (recruiter can create postings); or Rejected.

### BW-PC-02 — Job Opportunity Creation and Submission Workflow

| Field | Specification Details |
| --- | --- |
| **Workflow ID** | BW-PC-02 |
| **Workflow Name** | Job Opportunity Creation and Submission Workflow |
| **Classification** | Basis Workflow |
| **Operational Purpose** | Coordinate the preparation of recruitment job postings by approved employers, validation of mandatory fields, and submission for TPO review. |
| **Initial State** | Non-existent / Draft |


#### State Transition Matrix

| Step | From State | Actor / Entity | Use Case / Function | Guard / Outcome | Resulting State | Applicable Business Rules |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | Non-existent | Recruiter | PC-UC-015 (Create Draft) | Company is approved and operational (can_operate=True) | Draft | PC-BR-006, PC-BR-007 |
| 2 | Draft | Recruiter | PC-UC-015 (Configure Criteria) | Rule adheres to closed vocabulary (cpi, discipline, batch) | Draft (Configured) | PC-BR-004 |
| 3 | Draft (Configured) | Recruiter | PC-UC-015 (Submit Opportunity) | All mandatory fields present; closes_at > now() | Pending Approval | PC-BR-003, PC-BR-006 |
| 4 | Draft (Configured) | Recruiter | PC-UC-015 (Submit Opportunity) | Missing required description, rules, or deadline | Draft (Incomplete) | PC-BR-003 |


**Terminal States and Outcomes:**
Pending Approval (queued for TPO review); or Draft (retained for correction).

### BW-PC-03 — TPO Review and Opportunity Publication Workflow

| Field | Specification Details |
| --- | --- |
| **Workflow ID** | BW-PC-03 |
| **Workflow Name** | TPO Review and Opportunity Publication Workflow |
| **Classification** | Basis Workflow |
| **Operational Purpose** | Coordinate TPO compliance verification of submitted job postings, freezing of eligibility criteria, and publication to students. |
| **Initial State** | Pending Approval |


#### State Transition Matrix

| Step | From State | Actor / Entity | Use Case / Function | Guard / Outcome | Resulting State | Applicable Business Rules |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | Pending Approval | TPO Staff | PC-UC-006 (Review Posting) | Staff has manage permission; terms and CTC verified | Under Review | PC-BR-005 |
| 2 | Under Review | TPO Staff | PC-UC-006 (Publish Posting) | Validation passes; closes_at strictly in future | Published | PC-BR-002, PC-BR-003, PC-BR-005 |
| 3 | Under Review | TPO Staff | PC-UC-006 (Request Changes) | Compensation discrepancy or invalid criteria | Draft (Returned) | PC-BR-003 |
| 4 | Published | Placement Cell | PC-UC-006 (Lock Criteria) | eligibility_rule_locked_at stamped with timestamp | Published (Frozen) | PC-BR-002 |
| 5 | Published (Frozen) | Placement Cell | PC-UC-007 (Broadcast Alert) | Enqueues outbox notifications for eligible cohort | Published (Active) | PC-BR-021 |


**Terminal States and Outcomes:**
Published (Active for student applications); or Draft (Returned to employer).

### BW-PC-04 — Student Application and Eligibility Workflow

| Field | Specification Details |
| --- | --- |
| **Workflow ID** | BW-PC-04 |
| **Workflow Name** | Student Application and Eligibility Workflow |
| **Classification** | Basis Workflow |
| **Operational Purpose** | Coordinate student job applications, dynamic eligibility evaluation, dream tier validation, and immutable submission recording. |
| **Initial State** | Published (Active) |


#### State Transition Matrix

| Step | From State | Actor / Entity | Use Case / Function | Guard / Outcome | Resulting State | Applicable Business Rules |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | Published (Active) | Student | PC-UC-003 (Initiate Apply) | Student authenticated; profile_completed is True | Evaluating Eligibility | PC-BR-001, PC-BR-022 |
| 2 | Evaluating Eligibility | Placement Cell | PC-UC-003 (Evaluate Criteria) | Declared academic standing satisfies frozen AST | Eligibility Verified | PC-BR-002, PC-BR-025 |
| 3 | Evaluating Eligibility | Placement Cell | PC-UC-003 (Evaluate Criteria) | CPI below cutoff, branch disallowed, or backlogs | Ineligible (Denied) | PC-BR-002, PC-BR-004 |
| 4 | Eligibility Verified | Placement Cell | PC-UC-003 (Tier Policy Check) | Student unplaced OR posting is valid Dream Upgrade | Ready to Submit | PC-BR-015 |
| 5 | Eligibility Verified | Placement Cell | PC-UC-003 (Tier Policy Check) | Student already placed in non-dream tier | Tier Disallowed | PC-BR-015 |
| 6 | Ready to Submit | Student | PC-UC-003 (Confirm Submission) | current_time < closes_at deadline | Submitted | PC-BR-003, PC-BR-008 |
| 7 | Submitted | Student | PC-UC-005 (Withdraw Application) | Prior to recruiter shortlisting commencement | Withdrawn | PC-BR-010 |
| 8 | Submitted | Placement Cell | PC-UC-007 (Enqueue Acknowledgment) | Atomic write to NotificationOutbox table | Submitted (Acknowledged) | PC-BR-021 |


**Terminal States and Outcomes:**
Submitted (Candidate active in pool); Ineligible; Tier Disallowed; or Withdrawn.

### BW-PC-05 — Application Review and Shortlisting Workflow

| Field | Specification Details |
| --- | --- |
| **Workflow ID** | BW-PC-05 |
| **Workflow Name** | Application Review and Shortlisting Workflow |
| **Classification** | Basis Workflow |
| **Operational Purpose** | Coordinate corporate recruiter evaluation of applicant profiles and recording of screening decisions. |
| **Initial State** | Submitted |


#### State Transition Matrix

| Step | From State | Actor / Entity | Use Case / Function | Guard / Outcome | Resulting State | Applicable Business Rules |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | Submitted | Recruiter | PC-UC-016 (Open Applicant) | Application belongs to recruiter's own company posting | Under Review | PC-BR-009, PC-BR-010 |
| 2 | Under Review | Recruiter | PC-UC-016 (Record Shortlist) | Candidate qualifies for subsequent rounds | Shortlisted | PC-BR-008, PC-BR-030 |
| 3 | Under Review | Recruiter | PC-UC-016 (Record Rejection) | Candidate does not meet employer bar; reason captured | Rejected | PC-BR-008, PC-BR-030 |
| 4 | Shortlisted | Placement Cell | PC-UC-007 (Enqueue Alert) | Outbox notification enqueued for shortlisted student | Shortlisted (Notified) | PC-BR-021 |
| 5 | Rejected | Placement Cell | PC-UC-007 (Enqueue Alert) | Outbox notification enqueued for rejected student | Rejected (Terminal) | PC-BR-021 |


**Terminal States and Outcomes:**
Shortlisted (Eligible for interviews); or Rejected (Terminal).

### BW-PC-06 — Interview Round Scheduling and Execution Workflow

| Field | Specification Details |
| --- | --- |
| **Workflow ID** | BW-PC-06 |
| **Workflow Name** | Interview Round Scheduling and Execution Workflow |
| **Classification** | Basis Workflow |
| **Operational Purpose** | Coordinate creation of interview rounds, candidate slot assignment, invitation dispatch, and stage progression tracking. |
| **Initial State** | Shortlisted |


#### State Transition Matrix

| Step | From State | Actor / Entity | Use Case / Function | Guard / Outcome | Resulting State | Applicable Business Rules |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | Shortlisted | TPO Staff / Recruiter | PC-UC-009 (Create Round) | Round sequence, kind, starts_at > now, mode/venue valid | Round Created | PC-BR-011 |
| 2 | Round Created | TPO Staff | PC-UC-009 (Assign Candidates) | Candidates selected strictly from shortlisted pool | Interview Scheduled | PC-BR-011, PC-BR-030 |
| 3 | Interview Scheduled | Placement Cell | PC-UC-007 (Send Invitations) | Notification enqueued with slot time and venue/link | Interview Scheduled (Alerted) | PC-BR-012, PC-BR-021 |
| 4 | Interview Scheduled (Alerted) | Interviewer / Recruiter | PC-UC-009 (Record Attendance) | Candidate attends interview session | Interview Completed | PC-BR-030 |
| 5 | Interview Completed | Recruiter | PC-UC-016 (Progress to Next Round) | Next round configured; candidate advanced | Shortlisted (Next Round) | PC-BR-010 |
| 6 | Interview Completed | Recruiter | PC-UC-016 (Eliminate Candidate) | Candidate fails round assessment | Rejected | PC-BR-008, PC-BR-030 |


**Terminal States and Outcomes:**
Shortlisted (Advanced to subsequent round or offer); or Rejected.

### BW-PC-07 — Job Offer Issuance and Student Response Workflow

| Field | Specification Details |
| --- | --- |
| **Workflow ID** | BW-PC-07 |
| **Workflow Name** | Job Offer Issuance and Student Response Workflow |
| **Classification** | Basis Workflow |
| **Operational Purpose** | Coordinate formal employment offer extension, response deadline enforcement, acceptance validation, and automated expiry sweeps. |
| **Initial State** | Interview Completed / Shortlisted |


#### State Transition Matrix

| Step | From State | Actor / Entity | Use Case / Function | Guard / Outcome | Resulting State | Applicable Business Rules |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | Interview Completed | Recruiter | PC-UC-022 (Extend Offer) | Role, CTC, joining terms, and future deadline specified | Offer Extended | PC-BR-009, PC-BR-013 |
| 2 | Offer Extended | Placement Cell | PC-UC-007 (Offer Alert) | Urgent notification enqueued with deadline countdown | Offer Extended (Active) | PC-BR-021 |
| 3 | Offer Extended (Active) | Student | PC-UC-008 (Accept Offer) | current_time < expires_at AND satisfies tier policy | Offer Accepted | PC-BR-013, PC-BR-014, PC-BR-015 |
| 4 | Offer Extended (Active) | Student | PC-UC-008 (Decline Offer) | current_time < expires_at; student explicitly declines | Offer Declined | PC-BR-013 |
| 5 | Offer Extended (Active) | System Scheduler | PC-SCHED-01 (Expire Offer) | current_time >= expires_at without response | Offer Expired | PC-BR-013 |
| 6 | Offer Accepted | Placement Cell | PC-UC-008 (Create Placement) | PlacementRecord created; status updated to Placed | Placed | PC-BR-014 |


**Terminal States and Outcomes:**
Placed (PlacementRecord created); Offer Declined; or Offer Expired.

### BW-PC-08 — Placement Record Recording and Audit Workflow

| Field | Specification Details |
| --- | --- |
| **Workflow ID** | BW-PC-08 |
| **Workflow Name** | Placement Record Recording and Audit Workflow |
| **Classification** | Basis Workflow |
| **Operational Purpose** | Coordinate verified placement record persistence, off-campus placement documentation, and TPO administrative corrections. |
| **Initial State** | Offer Accepted / Off-Campus Declared |


#### State Transition Matrix

| Step | From State | Actor / Entity | Use Case / Function | Guard / Outcome | Resulting State | Applicable Business Rules |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | Offer Accepted | Placement Cell | PC-UC-008 (Persist Record) | Automatic atomic creation from on-campus offer | Active Record | PC-BR-014 |
| 2 | Off-Campus Declared | Student / TPO Staff | PC-UC-010 (Record Off-Campus) | Offer letter and verified employer CTC attached | Pending Verification | PC-BR-029 |
| 3 | Pending Verification | TPO Staff | PC-UC-010 (Verify Off-Campus) | TPO confirms authenticity of external employment | Active Record | PC-BR-029 |
| 4 | Active Record | TPO Staff | PC-UC-010 (Correct Clerical Error) | Correction reason provided; CTC or active flag modified | Corrected Record | PC-BR-024, PC-BR-029 |
| 5 | Active Record | TPO Staff | PC-UC-010 (Deactivate Record) | Student opt-out, higher education, or revoked offer | Deactivated Record | PC-BR-029 |


**Terminal States and Outcomes:**
Active Record; Corrected Record; or Deactivated Record.

### CW-PC-01 — End-to-End Campus Recruitment Drive Composite Workflow

| Field | Specification Details |
| --- | --- |
| **Workflow ID** | CW-PC-01 |
| **Workflow Name** | End-to-End Campus Recruitment Drive Composite Workflow |
| **Classification** | Composite Workflow |
| **Operational Purpose** | Orchestrates the entire institutional campus drive across multiple basis workflows: Company Onboarding (BW-PC-01) -> Job Posting (BW-PC-02, 03) -> Student Application (BW-PC-04) -> Review & Interviews (BW-PC-05, 06) -> Offer & Placement (BW-PC-07, 08). |
| **Initial State** | Season Planning |


#### State Transition Matrix

| Step | From State | Actor / Entity | Use Case / Function | Guard / Outcome | Resulting State | Applicable Business Rules |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | Season Planning | TPO / Recruiter | BW-PC-01 (Company Verification) | Company vetted and authorized | Company Ready | PC-BR-007 |
| 2 | Company Ready | Recruiter / TPO | BW-PC-02, BW-PC-03 (Publish Posting) | Draft submitted and published with frozen rules | Opportunity Live | PC-BR-002, PC-BR-003, PC-BR-005 |
| 3 | Opportunity Live | Students | BW-PC-04 (Application Window) | Eligible students apply before deadline | Applications Closed | PC-BR-001, PC-BR-003 |
| 4 | Applications Closed | Recruiter / TPO | BW-PC-05, BW-PC-06 (Selection Pipeline) | Shortlisting, technical, and HR rounds executed | Interviews Finalized | PC-BR-009, PC-BR-011, PC-BR-030 |
| 5 | Interviews Finalized | Recruiter / Students | BW-PC-07 (Offer & Acceptance) | Offers extended and accepted before deadline | Drive Complete (Placed) | PC-BR-013, PC-BR-014, PC-BR-015 |
| 6 | Drive Complete | Placement Cell | BW-PC-08 (Record Persistence) | PlacementRecords created and statistics refreshed | Archived Drive | PC-BR-014, PC-BR-016 |


**Terminal States and Outcomes:**
Archived Drive with complete audit log, verified placement records, and institutional statistics.

### CW-PC-02 — Multi-Stage Candidate Evaluation Pipeline Composite Workflow

| Field | Specification Details |
| --- | --- |
| **Workflow ID** | CW-PC-02 |
| **Workflow Name** | Multi-Stage Candidate Evaluation Pipeline Composite Workflow |
| **Classification** | Composite Workflow |
| **Operational Purpose** | Orchestrates candidate progression across multiple sequential evaluation barriers (Resume Screening -> Online Technical Test -> Technical Interview -> HR Interview -> Final Shortlist). |
| **Initial State** | Candidate Pool (Submitted) |


#### State Transition Matrix

| Step | From State | Actor / Entity | Use Case / Function | Guard / Outcome | Resulting State | Applicable Business Rules |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | Candidate Pool | Recruiter | BW-PC-05 (Resume Screening) | Profile evaluated against role requirements | Screening Cleared | PC-BR-009, PC-BR-030 |
| 2 | Screening Cleared | TPO / Recruiter | BW-PC-06 (Round 1: Online Test) | Test scheduled, invitations dispatched, scores recorded | Test Shortlisted | PC-BR-011, PC-BR-012 |
| 3 | Test Shortlisted | Recruiter | BW-PC-06 (Round 2: Tech Interview) | Technical panel evaluates domain competency | Tech Shortlisted | PC-BR-011, PC-BR-030 |
| 4 | Tech Shortlisted | Recruiter | BW-PC-06 (Round 3: HR Interview) | Cultural fit and compensation discussion | Final Selection Roster | PC-BR-011, PC-BR-030 |
| 5 | Final Selection Roster | Recruiter | BW-PC-07 (Formal Offer Extension) | Formal offers generated for selected candidates | Offer Pipeline Active | PC-BR-013 |


**Terminal States and Outcomes:**
Offer Pipeline Active for selected candidates; Rejected for eliminated candidates.

### CW-PC-03 — Off-Campus Placement Recording and Verification Composite Workflow

| Field | Specification Details |
| --- | --- |
| **Workflow ID** | CW-PC-03 |
| **Workflow Name** | Off-Campus Placement Recording and Verification Composite Workflow |
| **Classification** | Composite Workflow |
| **Operational Purpose** | Governs the declaration, evidence submission, administrative verification, and clearance of student employment offers obtained outside campus drives. |
| **Initial State** | Off-Campus Offer Received |


#### State Transition Matrix

| Step | From State | Actor / Entity | Use Case / Function | Guard / Outcome | Resulting State | Applicable Business Rules |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | Offer Received | Student | PC-UC-010 (Submit Declaration) | Uploads signed offer letter, company info, and CTC proof | Declaration Submitted | PC-BR-029 |
| 2 | Declaration Submitted | TPO Staff | PC-UC-010 (Inspect Documentation) | TPO verifies employer authenticity and compensation | Under Verification | PC-BR-029 |
| 3 | Under Verification | TPO Staff | BW-PC-08 (Approve Declaration) | Verified documentation approved | Off-Campus Placed | PC-BR-014, PC-BR-029 |
| 4 | Off-Campus Placed | Placement Cell | PC-UC-010 (Generate Clearance) | Student marked placed; debarment from campus drives applied | Clearance Issued | PC-BR-015, PC-BR-029 |


**Terminal States and Outcomes:**
Clearance Issued and verified PlacementRecord created; or Declaration Rejected.

### CW-PC-04 — Placement Season Clearance and Audit Composite Workflow

| Field | Specification Details |
| --- | --- |
| **Workflow ID** | CW-PC-04 |
| **Workflow Name** | Placement Season Clearance and Audit Composite Workflow |
| **Classification** | Composite Workflow |
| **Operational Purpose** | Coordinates end-of-season institutional governance: clearance verification, sanction resolution, offer letter archiving, and statistical snapshot freezing. |
| **Initial State** | Season Closing |


#### State Transition Matrix

| Step | From State | Actor / Entity | Use Case / Function | Guard / Outcome | Resulting State | Applicable Business Rules |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | Season Closing | TPO Staff | PC-UC-010 (Outstanding Letter Sweep) | Audits placed students who have not uploaded signed letters | Audit Complete | PC-BR-024 |
| 2 | Audit Complete | TPO Staff | PC-UC-010 (Issue Final Clearance) | All obligations, fees, and clearance papers satisfied | Clearance Sealed | PC-BR-029 |
| 3 | Clearance Sealed | System Scheduler | PC-SCHED-03 (Freeze Snapshots) | Materializes final institutional statistics for NIRF/AICTE | Snapshots Frozen | PC-BR-016 |
| 4 | Snapshots Frozen | TPO Staff | PC-UC-011 (Publish Annual Report) | Official institute placement report released | Season Closed / Archived | PC-BR-016 |


**Terminal States and Outcomes:**
Season Closed / Archived with complete compliance audit and frozen statistical snapshots.
