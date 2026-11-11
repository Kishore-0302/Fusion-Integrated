# Placement Cell Use Case Specifications (Part 1)

**Detailed Use Case Specifications — Standard Format (PC-UC-001 to 024)**

> *Reading note: Use the actor, goal, trigger, scenario, alternative/exception, postcondition, and Conditions and Constraints fields when evaluating use case behavior. Scheduled system functions are detailed in Section 3.*

## 1. Use Case Index

| ID | Use Case Name | Primary Actor |
| --- | --- | --- |
| PC-UC-001 | Student Registration and Profile Verification | Student |
| PC-UC-002 | Browse Job Opportunities | Student |
| PC-UC-003 | Apply for Opportunity | Student |
| PC-UC-004 | Track Application Status and History | Student |
| PC-UC-005 | Withdraw Application | Student |
| PC-UC-006 | Publish Job Posting | Placement Officer / TPO Staff |
| PC-UC-007 | Dispatch Automated Notifications | System Scheduler / Time Event |
| PC-UC-008 | Respond to Job Offer | Student |
| PC-UC-009 | Schedule Interview Rounds | Placement Officer / TPO Staff |
| PC-UC-010 | Manage and Correct Placement Records | Placement Officer / TPO Staff |
| PC-UC-011 | Generate Season Placement Reports | Placement Officer / TPO Staff |
| PC-UC-012 | View Company Participation Statistics | Placement Officer / TPO Staff |
| PC-UC-013 | Placement Cell Announcements Management | Placement Officer / TPO Staff |
| PC-UC-014 | Company Registration and Authorization | Recruiter / Employer |
| PC-UC-015 | Submit Company Opportunity Draft | Recruiter / Employer |
| PC-UC-016 | Review Application and Shortlist | Recruiter / Employer |
| PC-UC-017 | Alumni Mentorship and Past Records Access | Alumni |
| PC-UC-020 | View Announcements | Student |
| PC-UC-021 | Company Coordinate Interview Slots | Recruiter / Employer |
| PC-UC-022 | Extend Job Offer | Recruiter / Employer |
| PC-UC-023 | Synchronize Resume from Portal | Student |
| PC-UC-024 | View Anonymized Student Statistics | Student |


## 2. Detailed Use Case Specifications

### PC-UC-001 — Student Registration and Profile Verification

| Field | Specification Details |
| --- | --- |
| **Primary Actor** | Student |
| **Supporting Actors / Systems** | ERP Identity Service; Directory Service; TPO Staff |
| **Goal** | Verify placement eligibility, sync student portal profile, and register for the active placement season. |
| **Trigger** | Student accesses the Placement Cell module at the beginning of an academic year or drive. |
| **Preconditions** | Student is authenticated in Fusion and enrolled in an active graduating programme. |


#### Main Success Scenario

| Step | Responsible Actor / Entity | Activity / Operational Outcome |
| --- | --- | --- |
| 1 | Student | Navigates to the Placement Cell registration portal. |
| 2 | Placement Cell | Queries declared academic standing snapshot (CPI, branch, batch, backlogs) from IAM. |
| 3 | Placement Cell | Validates profile completeness status from the institutional portal. |
| 4 | Student | Confirms contact details, primary resume link, and career preferences. |
| 5 | Placement Cell | Checks for active disciplinary sanctions or debarment records. |
| 6 | Placement Cell | Records active placement season registration and unlocks opportunity browsing. |


**Alternative and Exception Behavior:**
If the student profile is incomplete, registration is blocked with guidance to complete mandatory portal fields (PC-BR-001).
If the student has active debarment sanctions, registration is refused and referred to TPO administration.

**Postcondition:**
Student profile is registered for the current placement season and authorized to browse live postings.

**Conditions and Constraints Embedded in this Use Case:**
Academic data is read-only and immutable within Placement Cell (PC-BR-025).
Only students with a verified profile_completed flag may participate in recruitment drives (PC-BR-001).

### PC-UC-002 — Browse Job Opportunities

| Field | Specification Details |
| --- | --- |
| **Primary Actor** | Student |
| **Supporting Actors / Systems** | TPO Placement Catalog; Company Service |
| **Goal** | Browse and filter published recruitment opportunities matching the student's academic background. |
| **Trigger** | Student views available job postings on the placement dashboard. |
| **Preconditions** | Student is registered for the active placement season. |


#### Main Success Scenario

| Step | Responsible Actor / Entity | Activity / Operational Outcome |
| --- | --- | --- |
| 1 | Student | Requests the catalog of current employment opportunities. |
| 2 | Placement Cell | Filters postings to show only published, open drives (drafts and pending approval excluded). |
| 3 | Placement Cell | Evaluates student academic profile against frozen eligibility criteria of each posting. |
| 4 | Placement Cell | Renders opportunity cards with clear eligibility status (Eligible vs Ineligible with reason). |
| 5 | Student | Inspects posting details: role description, CTC breakdown, selection rounds, and deadline. |


**Alternative and Exception Behavior:**
If deadline has passed, the opportunity is marked applications_closed and apply action is disabled.
If the student is ineligible, the exact failing criterion (e.g. CPI below cutoff, branch mismatch) is displayed.

**Postcondition:**
Student reviews verified, relevant postings with full transparency of eligibility gates.

**Conditions and Constraints Embedded in this Use Case:**
Only published postings are visible to students; draft and pending postings are hidden (PC-BR-003).
Eligibility is evaluated against criteria frozen at publication time (PC-BR-002).

### PC-UC-003 — Apply for Opportunity

| Field | Specification Details |
| --- | --- |
| **Primary Actor** | Student |
| **Supporting Actors / Systems** | IAM Identity Service; Notification Outbox |
| **Goal** | Submit a formal employment application to a published job posting. |
| **Trigger** | Student clicks Apply on an eligible job posting. |
| **Preconditions** | Student is registered, profile is complete, posting is published, and current time is prior to deadline. |


#### Main Success Scenario

| Step | Responsible Actor / Entity | Activity / Operational Outcome |
| --- | --- | --- |
| 1 | Student | Selects an eligible posting and initiates application. |
| 2 | Placement Cell | Validates that current timestamp is strictly before the posting closes_at deadline. |
| 3 | Placement Cell | Re-evaluates frozen eligibility rules against declared academic snapshot. |
| 4 | Placement Cell | Checks existing accepted offers against institutional dream tier upgrade policy. |
| 5 | Student | Enters optional cover note and confirms resume attachment. |
| 6 | Placement Cell | Creates Application record in 'submitted' state with immutable timestamp. |
| 7 | Placement Cell | Enqueues application submission notification into the outbox for delivery. |


**Alternative and Exception Behavior:**
If current time is past closes_at, request is rejected with deadline_passed.
If student already holds an offer and new posting does not qualify as a Dream upgrade, application is denied (PC-BR-015).
If duplicate application is attempted, system rejects with already_applied.

**Postcondition:**
Application is recorded in 'submitted' state; student and employer receive automated confirmation.

**Conditions and Constraints Embedded in this Use Case:**
Applications cannot be accepted after closes_at under any circumstances (PC-BR-003).
Eligibility criteria evaluated at application time must match the frozen published criteria (PC-BR-002).

### PC-UC-004 — Track Application Status and History

| Field | Specification Details |
| --- | --- |
| **Primary Actor** | Student |
| **Supporting Actors / Systems** | Audit Trail Service |
| **Goal** | Inspect the real-time progress and historical event timeline of all submitted applications. |
| **Trigger** | Student opens their My Applications tracking page. |
| **Preconditions** | Student is authenticated and has submitted at least one application. |


#### Main Success Scenario

| Step | Responsible Actor / Entity | Activity / Operational Outcome |
| --- | --- | --- |
| 1 | Student | Requests personal application history list. |
| 2 | Placement Cell | Retrieves applications belonging exclusively to the requesting student. |
| 3 | Placement Cell | Loads canonical lifecycle state and timestamp for each application. |
| 4 | Student | Selects a specific application to view full audit event timeline. |
| 5 | Placement Cell | Renders timeline entries showing state transitions, interview schedules, and decisions. |


**Alternative and Exception Behavior:**
Internal staff notes or confidential recruiter commentary are filtered out from student view.

**Postcondition:**
Student possesses accurate, chronological visibility into their recruitment standing.

**Conditions and Constraints Embedded in this Use Case:**
A student may only access their own applications; cross-student application data is inaccessible (PC-BR-022).

### PC-UC-005 — Withdraw Application

| Field | Specification Details |
| --- | --- |
| **Primary Actor** | Student |
| **Supporting Actors / Systems** | Notification Outbox; Audit Service |
| **Goal** | Retract an active application before employer review or shortlisting occurs. |
| **Trigger** | Student decides not to pursue a previously submitted application. |
| **Preconditions** | Application exists in 'submitted' state; shortlisting or interview scheduling has not commenced. |


#### Main Success Scenario

| Step | Responsible Actor / Entity | Activity / Operational Outcome |
| --- | --- | --- |
| 1 | Student | Initiates withdrawal of a submitted application. |
| 2 | Placement Cell | Verifies that application status is strictly 'submitted'. |
| 3 | Placement Cell | Transitions application status to 'withdrawn' and records cancellation timestamp. |
| 4 | Placement Cell | Enqueues withdrawal notification to recruiter and placement records. |


**Alternative and Exception Behavior:**
If application has advanced to 'under_review', 'shortlisted', or 'interview_scheduled', withdrawal is disallowed without TPO intervention.

**Postcondition:**
Application is marked 'withdrawn'; candidate is excluded from company applicant pool.

**Conditions and Constraints Embedded in this Use Case:**
Self-withdrawal is prohibited once review stages have commenced (PC-BR-010).

### PC-UC-006 — Publish Job Posting

| Field | Specification Details |
| --- | --- |
| **Primary Actor** | Placement Officer / TPO Staff |
| **Supporting Actors / Systems** | Postings Service; Rules Engine; Notification Outbox |
| **Goal** | Approve and publish a recruitment posting, locking its eligibility criteria and opening student applications. |
| **Trigger** | TPO reviews a company-submitted posting in 'pending_approval' status. |
| **Preconditions** | TPO staff possesses 'placement_cell.job_posting.manage' permission; posting has complete content. |


#### Main Success Scenario

| Step | Responsible Actor / Entity | Activity / Operational Outcome |
| --- | --- | --- |
| 1 | TPO Staff | Selects a posting pending approval and reviews terms, CTC, and eligibility rules. |
| 2 | Placement Cell | Validates that all mandatory fields (title, kind, description, rules, deadline) are present. |
| 3 | Placement Cell | Validates that eligibility rule conforms to closed attribute schema. |
| 4 | TPO Staff | Approves publication. |
| 5 | Placement Cell | Transitions posting to 'published' status and locks eligibility rule. |
| 6 | Placement Cell | Broadcasts job alert notification to all eligible registered students via outbox. |


**Alternative and Exception Behavior:**
If posting content is incomplete or deadline is in the past, publication fails with validation errors (PC-BR-003).
If TPO rejects the draft, posting is returned to company with correction comments.

**Postcondition:**
Posting is published, visible to students, and eligibility criteria are immutable.

**Conditions and Constraints Embedded in this Use Case:**
Recruiters cannot publish directly; publication requires TPO administrative authorization (PC-BR-005).
Eligibility criteria cannot be altered once published (PC-BR-002).

### PC-UC-007 — Dispatch Automated Notifications

| Field | Specification Details |
| --- | --- |
| **Primary Actor** | System Scheduler / Time Event |
| **Supporting Actors / Systems** | Notification Worker; SMTP Gateway |
| **Goal** | Drain the transactional notification outbox and deliver reliable email/system alerts for all placement events. |
| **Trigger** | Periodic 1-minute Celery beat timer triggers outbox processing task. |
| **Preconditions** | Outbox has pending notification rows. |


#### Main Success Scenario

| Step | Responsible Actor / Entity | Activity / Operational Outcome |
| --- | --- | --- |
| 1 | Scheduler | Triggers drain_notification_outbox periodic background task. |
| 2 | Placement Cell | Queries batch of pending outbox events ordered by priority and creation time. |
| 3 | Placement Cell | Formats notification message using event payload and recipient preferences. |
| 4 | Placement Cell | Dispatches email via external institute SMTP service. |
| 5 | Placement Cell | Marks outbox rows as 'sent' with dispatch timestamp, or increments retry count on failure. |


**Alternative and Exception Behavior:**
If delivery fails due to SMTP timeout, record enters exponential backoff retry loop up to max limit.

**Postcondition:**
Pending notifications are delivered reliably without losing event history.

**Conditions and Constraints Embedded in this Use Case:**
All notification events must originate from domain state transitions persisted in the outbox (PC-BR-021).

### PC-UC-008 — Respond to Job Offer

| Field | Specification Details |
| --- | --- |
| **Primary Actor** | Student |
| **Supporting Actors / Systems** | Offer Service; Placement Policy Engine; Audit Log |
| **Goal** | Accept or decline an extended formal job offer before the specified response deadline. |
| **Trigger** | Student receives a job offer and opens the offer review dialog. |
| **Preconditions** | Offer is in 'extended' state and current time is before the offer's expires_at deadline. |


#### Main Success Scenario

| Step | Responsible Actor / Entity | Activity / Operational Outcome |
| --- | --- | --- |
| 1 | Student | Inspects formal offer details (company, role, CTC, joining terms, deadline). |
| 2 | Placement Cell | Verifies that current timestamp is prior to the offer expires_at deadline. |
| 3 | Student | Submits decision ('accept' or 'decline'). |
| 4 | Placement Cell | If accepted: evaluates multiple-offer policy to ensure compliance with dream tier rules. |
| 5 | Placement Cell | If accepted: automatically generates a verified Placement Record for the student. |
| 6 | Placement Cell | Transitions application status to 'offer_accepted' (or 'offer_declined'). |
| 7 | Placement Cell | Enqueues confirmation notifications to student, company recruiter, and TPO staff. |


**Alternative and Exception Behavior:**
If deadline has expired, decision is refused and offer is marked expired by the system sweeper (PC-BR-013).
If acceptance violates multiple-offer policy (student already placed at higher or equal tier), acceptance is rejected (PC-BR-015).

**Postcondition:**
Offer status is updated; if accepted, placement record is created and student's placement status is updated.

**Conditions and Constraints Embedded in this Use Case:**
Offer acceptance automatically creates a PlacementRecord and updates season statistics (PC-BR-014).

### PC-UC-009 — Schedule Interview Rounds

| Field | Specification Details |
| --- | --- |
| **Primary Actor** | Placement Officer / TPO Staff |
| **Supporting Actors / Systems** | Interviews Service; Notification Outbox |
| **Goal** | Create an assessment interview round and assign shortlisted candidates to specific slots. |
| **Trigger** | TPO staff configures interview dates for a live recruitment drive. |
| **Preconditions** | Staff possesses 'placement_cell.interview.schedule' permission; posting has shortlisted applicants. |


#### Main Success Scenario

| Step | Responsible Actor / Entity | Activity / Operational Outcome |
| --- | --- | --- |
| 1 | TPO Staff | Selects job posting and initiates interview round scheduling. |
| 2 | TPO Staff | Inputs round type (screening/tech/hr), sequence number, date/time, mode, and venue/URL. |
| 3 | Placement Cell | Validates that starts_at is strictly in the future and required mode/venue details are present. |
| 4 | TPO Staff | Selects candidates from the pool of shortlisted applicants. |
| 5 | Placement Cell | Creates InterviewRound and RoundParticipation records. |
| 6 | Placement Cell | Transitions selected applications to 'interview_scheduled'. |
| 7 | Placement Cell | Enqueues interview invitations with slot and venue information to candidates. |


**Alternative and Exception Behavior:**
If candidate list is empty, scheduling is rejected with candidates_required.
If starts_at is in the past, rejected with interview_time_in_past (PC-BR-011).

**Postcondition:**
Interview round is persisted; candidate status is updated to 'interview_scheduled'; alerts are dispatched.

**Conditions and Constraints Embedded in this Use Case:**
Mandatory fields: round type, sequence, starts_at, mode, and venue or meeting link (PC-BR-011).
Candidates must be in shortlisted status for that posting (PC-BR-030).

### PC-UC-010 — Manage and Correct Placement Records

| Field | Specification Details |
| --- | --- |
| **Primary Actor** | Placement Officer / TPO Staff |
| **Supporting Actors / Systems** | Clearance Service; Audit Logging Engine |
| **Goal** | Correct clerical errors (CTC, company, active flag) on recorded placements with mandatory audit justification. |
| **Trigger** | TPO receives verified correction paperwork for a student placement. |
| **Preconditions** | Actor holds 'placement_cell.record.manage' permission; placement record exists. |


#### Main Success Scenario

| Step | Responsible Actor / Entity | Activity / Operational Outcome |
| --- | --- | --- |
| 1 | TPO Staff | Locates placement record by student ID or record ID. |
| 2 | TPO Staff | Submits correction payload with revised CTC, category, or active status and mandatory reason. |
| 3 | Placement Cell | Validates that correction reason is non-empty and well-formed. |
| 4 | Placement Cell | Applies updates within database transaction. |
| 5 | Placement Cell | Writes structured audit log recording actor, timestamp, before-state, after-state, and justification. |
| 6 | Placement Cell | Returns updated placement record summary. |


**Alternative and Exception Behavior:**
If reason is omitted, patch is rejected with 400 Bad Request (PC-BR-029).
If reactivating a record would create duplicate active placements for the student in one season, rejected with already_placed.

**Postcondition:**
Record is updated; audit log is permanently stored for institutional compliance.

**Conditions and Constraints Embedded in this Use Case:**
Every modification requires an explicit non-blank reason string (PC-BR-029).
Campus placement company cannot be altered independently of accepted offer (PC-BR-029).

### PC-UC-011 — Generate Season Placement Reports

| Field | Specification Details |
| --- | --- |
| **Primary Actor** | Placement Officer / TPO Staff |
| **Supporting Actors / Systems** | Stats Aggregator; Reporting Engine |
| **Goal** | Generate consolidated metrics on placement percentage, package distributions, and recruiter counts. |
| **Trigger** | TPO staff prepares official placement statistics for institute administration or accreditation. |
| **Preconditions** | Actor holds TPO management permissions. |


#### Main Success Scenario

| Step | Responsible Actor / Entity | Activity / Operational Outcome |
| --- | --- | --- |
| 1 | TPO Staff | Selects placement season and requests institutional analytics. |
| 2 | Placement Cell | Aggregates total registered students, placed count, placement percentage, mean, median, max CTC. |
| 3 | Placement Cell | Breaks down figures across academic disciplines and programmes. |
| 4 | Placement Cell | Generates salary package distribution bands. |
| 5 | TPO Staff | Exports verified report for administrative and NIRF reporting. |


**Alternative and Exception Behavior:**
If small cohorts have fewer than 5 students, granular data is masked to protect identity (PC-BR-016).

**Postcondition:**
Verified institutional statistics are compiled and exported.

**Conditions and Constraints Embedded in this Use Case:**
Aggregations must respect small-cell floor privacy thresholds (PC-BR-016).

### PC-UC-012 — View Company Participation Statistics

| Field | Specification Details |
| --- | --- |
| **Primary Actor** | Placement Officer / TPO Staff |
| **Supporting Actors / Systems** | Stats Service; Company Catalog |
| **Goal** | Analyze multi-year corporate engagement, hiring volume per employer, and industry trends. |
| **Trigger** | TPO evaluates employer relationship trends across recruitment cycles. |
| **Preconditions** | Actor holds administrative viewing permissions. |


#### Main Success Scenario

| Step | Responsible Actor / Entity | Activity / Operational Outcome |
| --- | --- | --- |
| 1 | TPO Staff | Requests company engagement analytics. |
| 2 | Placement Cell | Computes total participating companies, offers issued per company, and acceptance ratios. |
| 3 | Placement Cell | Renders comparison chart across active and past seasons. |


**Alternative and Exception Behavior:**
Unapproved or inactive companies are excluded from statistical counts.

**Postcondition:**
Employer engagement trends are displayed.

**Conditions and Constraints Embedded in this Use Case:**
Raw student identities are decoupled from corporate participation statistics (PC-BR-016).

### PC-UC-013 — Placement Cell Announcements Management

| Field | Specification Details |
| --- | --- |
| **Primary Actor** | Placement Officer / TPO Staff |
| **Supporting Actors / Systems** | Notice Board Service; Outbox Queue |
| **Goal** | Draft, publish, and withdraw placement announcements and drive alerts. |
| **Trigger** | TPO staff needs to notify student body of upcoming drives, schedules, or policy updates. |
| **Preconditions** | Actor holds announcement management permissions. |


#### Main Success Scenario

| Step | Responsible Actor / Entity | Activity / Operational Outcome |
| --- | --- | --- |
| 1 | TPO Staff | Creates announcement specifying title, body, topic, and optional target discipline. |
| 2 | Placement Cell | Validates that topic belongs to configured set (drives, shortlist, results, general). |
| 3 | TPO Staff | Publishes announcement. |
| 4 | Placement Cell | Saves notice as active and enqueues broadcast notification to targeted cohorts. |


**Alternative and Exception Behavior:**
If announcement is retracted, system flags it inactive while maintaining history rather than hard deleting (PC-BR-018).

**Postcondition:**
Announcement is published on student boards; notification alerts are queued.

**Conditions and Constraints Embedded in this Use Case:**
Topics are strictly restricted to bounded choices (PC-BR-017).
History is preserved on withdrawal (PC-BR-018).

### PC-UC-014 — Company Registration and Authorization

| Field | Specification Details |
| --- | --- |
| **Primary Actor** | Recruiter / Employer |
| **Supporting Actors / Systems** | TPO Staff; Company Service; Email Outbox |
| **Goal** | Register a new corporate entity, submit point-of-contact info, and undergo TPO verification. |
| **Trigger** | Corporate partner registers for campus hiring participation. |
| **Preconditions** | Organization details are complete and contact email is valid. |


#### Main Success Scenario

| Step | Responsible Actor / Entity | Activity / Operational Outcome |
| --- | --- | --- |
| 1 | Recruiter | Submits company registration form with corporate name, hiring domain, and contact details. |
| 2 | Placement Cell | Creates Company record in 'draft' or 'pending' state; creates initial recruiter user account. |
| 3 | TPO Staff | Reviews corporate profile, legitimacy, and past hiring track record. |
| 4 | TPO Staff | Approves company record, setting approval_status='approved' and stamping approved_by_user_id. |
| 5 | Placement Cell | Enables company operational flag (can_operate=True) and sends invitation to recruiter. |


**Alternative and Exception Behavior:**
If TPO rejects company, status is set to 'rejected' with reason; recruiter access is denied.

**Postcondition:**
Company is approved and authorized to post job opportunities.

**Conditions and Constraints Embedded in this Use Case:**
Companies cannot post opportunities or view students until approved by TPO (PC-BR-007).

### PC-UC-015 — Submit Company Opportunity Draft

| Field | Specification Details |
| --- | --- |
| **Primary Actor** | Recruiter / Employer |
| **Supporting Actors / Systems** | Postings Service; Rules Engine |
| **Goal** | Submit a completed job posting draft for TPO administrative review and publication. |
| **Trigger** | Approved company recruiter finishes drafting job posting details. |
| **Preconditions** | Recruiter is authenticated; company has approval_status='approved' and can_operate=True; posting is in 'draft'. |


#### Main Success Scenario

| Step | Responsible Actor / Entity | Activity / Operational Outcome |
| --- | --- | --- |
| 1 | Recruiter | Selects a draft opportunity and initiates submission for review. |
| 2 | Placement Cell | Verifies company authorization and ownership of the posting. |
| 3 | Placement Cell | Validates presence of mandatory description, eligibility rule, and valid future closes_at deadline. |
| 4 | Placement Cell | Validates eligibility rule against closed vocabulary. |
| 5 | Placement Cell | Transitions posting status from 'draft' to 'pending_approval'. |
| 6 | Placement Cell | Alerts TPO staff that a new opportunity is awaiting review. |


**Alternative and Exception Behavior:**
If company is not approved, rejected with company_not_approved (PC-BR-007).
If posting missing description, criteria, or deadline, rejected with incomplete_posting (PC-BR-003).
If deadline is past, rejected with deadline_in_past.

**Postcondition:**
Posting is in 'pending_approval' state; recruiter cannot edit fields during review.

**Conditions and Constraints Embedded in this Use Case:**
Only approved companies may submit drafts (PC-BR-007).
Submitting freezes recruiter editing until TPO decision (PC-BR-003).

### PC-UC-016 — Review Application and Shortlist

| Field | Specification Details |
| --- | --- |
| **Primary Actor** | Recruiter / Employer |
| **Supporting Actors / Systems** | Applications Service; State Machine; Audit Log |
| **Goal** | Inspect applicant resumes and record candidate screening decisions (Under Review, Shortlisted, Rejected). |
| **Trigger** | Recruiter reviews candidate profiles submitted to their company's job posting. |
| **Preconditions** | Recruiter is authenticated; application belongs to a posting owned by the recruiter's company. |


#### Main Success Scenario

| Step | Responsible Actor / Entity | Activity / Operational Outcome |
| --- | --- | --- |
| 1 | Recruiter | Navigates to applicant roster for their job posting. |
| 2 | Placement Cell | Filters applications strictly scoped to the recruiter's company ID. |
| 3 | Recruiter | Inspects applicant cover note, portal resume link, and academic summary. |
| 4 | Recruiter | Records screening decision ('shortlisted' or 'rejected') with optional feedback. |
| 5 | Placement Cell | Validates transition against application state machine. |
| 6 | Placement Cell | Updates application status, writes audit entry, and enqueues candidate notification. |


**Alternative and Exception Behavior:**
If recruiter attempts to view applications belonging to another company, access is rejected with NotFoundError (PC-BR-009).
If illegal state transition is attempted, rejected by state machine.

**Postcondition:**
Candidate application state is updated; notification alert is queued.

**Conditions and Constraints Embedded in this Use Case:**
A company sees only applications to its own postings (PC-BR-009).
Decisions must adhere strictly to valid state transitions (PC-BR-030).

### PC-UC-017 — Alumni Mentorship and Past Records Access

| Field | Specification Details |
| --- | --- |
| **Primary Actor** | Alumni |
| **Supporting Actors / Systems** | Directory Service; Placement Clearance Service |
| **Goal** | Access historical placement verification documents and optionally offer career mentorship to students. |
| **Trigger** | Alumnus logs in to access graduation placement clearance letters. |
| **Preconditions** | User is a verified institute graduate. |


#### Main Success Scenario

| Step | Responsible Actor / Entity | Activity / Operational Outcome |
| --- | --- | --- |
| 1 | Alumnus | Accesses historical placement records portal. |
| 2 | Placement Cell | Presents read-only view of historical placement record and clearance letters. |
| 3 | Alumnus | Reviews records or opts in to participate in career mentorship sessions. |


**Alternative and Exception Behavior:**
Alumni attempting to browse live drives or submit applications are blocked by scoping filters (PC-BR-020).

**Postcondition:**
Alumnus obtains historical documents without touching active workflows.

**Conditions and Constraints Embedded in this Use Case:**
Alumni are strictly excluded from active recruitment drives and workflow objects (PC-BR-020).

### PC-UC-020 — View Announcements

| Field | Specification Details |
| --- | --- |
| **Primary Actor** | Student |
| **Supporting Actors / Systems** | Notice Board Service |
| **Goal** | Read current recruitment notices, interview schedules, and placement office directives. |
| **Trigger** | Student checks the Placement Cell notice board. |
| **Preconditions** | Student is authenticated. |


#### Main Success Scenario

| Step | Responsible Actor / Entity | Activity / Operational Outcome |
| --- | --- | --- |
| 1 | Student | Accesses announcements feed. |
| 2 | Placement Cell | Queries active announcements matching student's discipline/batch. |
| 3 | Student | Views announcement details and attached instructions. |


**Alternative and Exception Behavior:**
Withdrawn announcements are omitted from student view.

**Postcondition:**
Student is informed of recruitment events.

**Conditions and Constraints Embedded in this Use Case:**
Inactive and retracted notices are hidden from students (PC-BR-018).

### PC-UC-021 — Company Coordinate Interview Slots

| Field | Specification Details |
| --- | --- |
| **Primary Actor** | Recruiter / Employer |
| **Supporting Actors / Systems** | TPO Coordination Service |
| **Goal** | Submit requested interview slots and technical round requirements to TPO. |
| **Trigger** | Recruiter finalizes shortlist and prepares for interview round execution. |
| **Preconditions** | Posting has shortlisted candidates. |


#### Main Success Scenario

| Step | Responsible Actor / Entity | Activity / Operational Outcome |
| --- | --- | --- |
| 1 | Recruiter | Specifies interview format, number of panels, and preferred date/time ranges. |
| 2 | Placement Cell | Transmits coordination request to TPO scheduling desk. |
| 3 | TPO Staff | Validates venue/platform availability and schedules formal rounds (PC-UC-009). |


**Alternative and Exception Behavior:**
If requested slot conflicts with existing drives, TPO suggests alternate time windows.

**Postcondition:**
Interview slots are coordinated and finalized with TPO.

**Conditions and Constraints Embedded in this Use Case:**
Formal slot confirmation and venue allocation are finalized through TPO (PC-BR-011).

### PC-UC-022 — Extend Job Offer

| Field | Specification Details |
| --- | --- |
| **Primary Actor** | Recruiter / Employer |
| **Supporting Actors / Systems** | Offers Service; State Machine; Notification Outbox |
| **Goal** | Issue a formal employment offer to a successfully interviewed candidate. |
| **Trigger** | Candidate successfully clears all interview rounds. |
| **Preconditions** | Candidate application is in 'interview_scheduled' or 'shortlisted'; offer terms are finalized. |


#### Main Success Scenario

| Step | Responsible Actor / Entity | Activity / Operational Outcome |
| --- | --- | --- |
| 1 | Recruiter | Selects candidate and initiates job offer extension. |
| 2 | Recruiter | Enters offer details: job role, CTC (LPA), joining location, and response deadline. |
| 3 | Placement Cell | Validates that response deadline is in the future. |
| 4 | Placement Cell | Creates JobOffer record in 'extended' state. |
| 5 | Placement Cell | Transitions application status to 'offer_extended'. |
| 6 | Placement Cell | Enqueues urgent offer notification to student with response deadline countdown. |


**Alternative and Exception Behavior:**
If deadline is omitted or in the past, offer issuance is rejected (PC-BR-013).

**Postcondition:**
Formal offer is recorded; response countdown timer begins.

**Conditions and Constraints Embedded in this Use Case:**
Offers must specify a response deadline to prevent blocking candidate allocations (PC-BR-013).

### PC-UC-023 — Synchronize Resume from Portal

| Field | Specification Details |
| --- | --- |
| **Primary Actor** | Student |
| **Supporting Actors / Systems** | ERP Student Portal; Directory Service |
| **Goal** | Synchronize updated resume link and profile facts from central ERP into placement applications. |
| **Trigger** | Student updates their professional resume on the institute portal. |
| **Preconditions** | Student maintains their primary resume on the ERP portal. |


#### Main Success Scenario

| Step | Responsible Actor / Entity | Activity / Operational Outcome |
| --- | --- | --- |
| 1 | Student | Updates resume URL on the central Fusion profile portal. |
| 2 | Placement Cell | Ingests projected profile fact through Directory IAM client. |
| 3 | Placement Cell | Associates updated verified resume reference with subsequent job applications. |


**Alternative and Exception Behavior:**
Applications already submitted retain the snapshot resume active at submission time for audit integrity.

**Postcondition:**
Latest resume is attached to new applications.

**Conditions and Constraints Embedded in this Use Case:**
Resumes are maintained upstream on the central ERP portal, avoiding duplicate maintenance (PC-BR-001).

### PC-UC-024 — View Anonymized Student Statistics

| Field | Specification Details |
| --- | --- |
| **Primary Actor** | Student |
| **Supporting Actors / Systems** | Stats Service; Reporting Cache |
| **Goal** | Inspect historical salary trends and placement benchmarks without exposing peer identities. |
| **Trigger** | Student views placement statistics tab. |
| **Preconditions** | Placement statistics snapshots are published. |


#### Main Success Scenario

| Step | Responsible Actor / Entity | Activity / Operational Outcome |
| --- | --- | --- |
| 1 | Student | Selects placement year and discipline. |
| 2 | Placement Cell | Queries materialized statistical snapshot. |
| 3 | Placement Cell | Applies small-cell floor filter (suppresses salary metrics if placed count < 5). |
| 4 | Student | Views overall placement rate, median/mean CTC, and participating company list. |


**Alternative and Exception Behavior:**
If data cells have fewer than 5 records, salary values are replaced with confidentiality indicator (PC-BR-016).

**Postcondition:**
Student gains realistic placement insights while peer privacy is strictly preserved.

**Conditions and Constraints Embedded in this Use Case:**
Students receive anonymized aggregates only; raw individual placement records are never disclosed (PC-BR-016).

## 3. Scheduled / Background Functions

| Function ID | Name | Trigger Frequency | Operational Purpose |
| --- | --- | --- | --- |
| PC-SCHED-01 | Sweep Expired Offers | Periodic 5-minute Celery beat timer | Identify extended job offers whose response deadline has elapsed without student acceptance, release candidates, and notify stakeholders. |
| PC-SCHED-02 | Drain Notification Outbox Worker | Periodic 1-minute Celery beat timer | Read pending notifications from the transactional outbox table, deliver via SMTP gateway, record delivery receipts, and handle retries. |
| PC-SCHED-03 | Materialize Placement Statistics Snapshots | Nightly batch cron job (02:00 AM) | Aggregate placement figures, compute salary percentiles, apply small-cell floor filters, and materialize public dashboard snapshots. |

