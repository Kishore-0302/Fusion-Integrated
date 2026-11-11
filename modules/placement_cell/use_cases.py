"""Application workflows and domain orchestration for Placement Cell use cases.

This module implements and orchestrates the primary use cases and business rules
specified in the Assignment 7 Placement Cell requirements baseline:
- Opportunity Submission & Publication: PC-UC-015, PC-UC-006 (PC-BR-002..007, BW-PC-02, BW-PC-03)
- Student Application & Lifecycle: PC-UC-003, PC-UC-005 (PC-BR-001, PC-BR-002, PC-BR-010, BW-PC-04)
- Recruiter Review & Shortlisting: PC-UC-016 (PC-BR-009, PC-BR-030, BW-PC-05)
- Interview Scheduling: PC-UC-009, PC-UC-021 (PC-BR-011, PC-BR-012, BW-PC-06)
- Offer Extension & Response: PC-UC-022, PC-UC-008 (PC-BR-013..015, BW-PC-07)
- Placement Record Management: PC-UC-010 (PC-BR-024, PC-BR-029, BW-PC-08)
- Announcements & Statistics: PC-UC-013, PC-UC-024 (PC-BR-016..018, PC-BR-021)
"""
from __future__ import annotations

from django.db import transaction
from django.utils import timezone

from core.api.exceptions import ConflictError, NotFoundError, PermissionDeniedError
from modules.placement.domain import state_machine as states
from modules.placement.models import (
    Announcement,
    Application,
    InterviewRound,
    JobPosting,
    Offer,
    PlacementRecord,
)
from modules.placement.selectors import scoping
from modules.placement.services import (
    announcements,
    applications,
    clearance,
    interviews,
    offers,
    postings,
    stats,
)
from modules.placement.services.authz import require

# Module permission identifiers (PC-BR-022)
P_POSTING = "placement_cell.job_posting.manage"
P_APPLY = "placement_cell.application.create"
P_REVIEW = "placement_cell.application.review"
P_SCHEDULE = "placement_cell.interview.schedule"
P_OFFER_ISSUE = "placement_cell.offer.issue"
P_OFFER_RESPOND = "placement_cell.offer.respond"
P_RECORD_MANAGE = "placement_cell.record.manage"
P_ANNOUNCEMENT_PUBLISH = "placement_cell.announcement.publish"


def _recruiter(actor) -> bool:
    return getattr(actor, "kind", None) == "recruiter"


# ---------------------------------------------------------------------------
# PC-UC-015: Company Opportunity Submission (BW-PC-02)
# ---------------------------------------------------------------------------
@transaction.atomic
def submit_company_opportunity(*, posting_id: int, actor) -> JobPosting:
    """PC-UC-015: Submit a complete company draft for TPO review.

    Governed by: PC-BR-003, PC-BR-004, PC-BR-006, PC-BR-007; BW-PC-02.
    """
    require(actor, P_POSTING, allow_recruiter=True)
    if not _recruiter(actor):
        raise PermissionDeniedError(
            "Only a Company/Recruiter can submit an opportunity.",
            code="company_submission_required",
        )
    posting = (
        scoping.postings_for(actor).select_for_update()
        .select_related("company").filter(pk=posting_id).first()
    )
    if posting is None:
        raise NotFoundError("No such posting.")
    if posting.status != "draft":
        raise ConflictError("Only a draft opportunity can be submitted.",
                            code="not_submittable")
    if not posting.company.can_operate:
        raise ConflictError("This company is not approved for recruitment yet.",
                            code="company_not_approved")

    missing = []
    if not (posting.description or "").strip():
        missing.append("description")
    if not posting.eligibility_rule:
        missing.append("eligibility_rule")
    if posting.closes_at is None:
        missing.append("closes_at")
    if missing:
        raise ConflictError(
            "Add a description, eligibility criteria and deadline before submitting.",
            code="incomplete_posting",
            details=[{"field": field} for field in missing],
        )
    if posting.closes_at <= timezone.now():
        raise ConflictError("The application deadline is already past.",
                            code="deadline_in_past")
    postings.validate_rule(posting.eligibility_rule)
    posting.status = "pending_approval"
    posting.save(update_fields=["status", "updated_at"])
    return posting


# ---------------------------------------------------------------------------
# PC-UC-006: TPO Posting Publication (BW-PC-03)
# ---------------------------------------------------------------------------
@transaction.atomic
def publish_tpo_opportunity(*, posting_id: int, actor) -> JobPosting:
    """PC-UC-006: TPO publishes a company-submitted opportunity.

    Governed by: PC-BR-002, PC-BR-003, PC-BR-005, PC-BR-021; BW-PC-03.
    """
    if _recruiter(actor):
        raise PermissionDeniedError("Only Placement Cell staff can publish.",
                                    code="tpo_publication_required")
    require(actor, P_POSTING)
    scope = scoping.postings_for(actor)
    posting = scope.select_for_update().filter(pk=posting_id).first()
    if posting is None:
        raise NotFoundError("No such posting.")
    if posting.status != "pending_approval":
        raise ConflictError("Submit the opportunity before TPO publication.",
                            code="submission_required")
    return postings.publish(posting_id=posting_id, actor=actor, scope=scope)


# ---------------------------------------------------------------------------
# PC-UC-003: Student Application Submission (BW-PC-04)
# ---------------------------------------------------------------------------
@transaction.atomic
def apply_to_opportunity(
    *, posting_id: int, actor, cover_note: str = "", resume_id: int | None = None
) -> Application:
    """PC-UC-003: Student applies through eligibility and policy checks.

    Governed by: PC-BR-001, PC-BR-002, PC-BR-008, PC-BR-021, PC-BR-022; BW-PC-04.
    """
    require(actor, P_APPLY)
    if getattr(actor, "user_id", None) is None:
        raise PermissionDeniedError("A student identity is required.",
                                    code="student_identity_required")
    return applications.apply_to(
        posting_id=posting_id, actor=actor,
        cover_note=cover_note, resume_id=resume_id,
    )


# ---------------------------------------------------------------------------
# PC-UC-005: Student Application Withdrawal (BW-PC-04)
# ---------------------------------------------------------------------------
@transaction.atomic
def withdraw_application(*, application_id: int, actor, reason: str = "") -> Application:
    """PC-UC-005: Student withdraws an active application before review completion.

    Governed by: PC-BR-008, PC-BR-010, PC-BR-022; BW-PC-04.
    """
    scope = scoping.applications_for(actor)
    app = scope.select_for_update().filter(pk=application_id).first()
    if app is None:
        raise NotFoundError("No such application.")
    if getattr(actor, "user_id", None) != app.user_id and not scoping.is_staff(actor):
        raise PermissionDeniedError("You may only withdraw your own applications.",
                                    code="cannot_withdraw_others")
    return applications.transition(
        application_id=application_id,
        to_status=states.WITHDRAWN,
        actor=actor,
        reason=reason or "Withdrawn by student",
        scope=scope,
    )


# ---------------------------------------------------------------------------
# PC-UC-016: Company Application Review (BW-PC-05)
# ---------------------------------------------------------------------------
@transaction.atomic
def review_company_application(
    *, application_id: int, actor, decision: str, reason: str = ""
) -> Application:
    """PC-UC-016: Company records a shortlist or rejection for its applicant.

    Governed by: PC-BR-009, PC-BR-030; BW-PC-05.
    """
    require(actor, P_REVIEW, allow_recruiter=True)
    if not _recruiter(actor):
        raise PermissionDeniedError("A Company/Recruiter account is required.",
                                    code="company_review_required")
    if decision not in (states.UNDER_REVIEW, states.SHORTLISTED, states.REJECTED):
        raise ConflictError("Decision must be under_review, shortlisted or rejected.",
                            code="invalid_company_decision")
    scope = scoping.applications_for(actor)
    if not scope.filter(pk=application_id).exists():
        raise NotFoundError("No such application.")
    return applications.transition(
        application_id=application_id, to_status=decision, actor=actor,
        reason=reason, scope=scope,
    )


# ---------------------------------------------------------------------------
# PC-UC-009: Interview Scheduling (BW-PC-06)
# ---------------------------------------------------------------------------
@transaction.atomic
def schedule_interviews(
    *, posting_id: int, actor, application_ids: list[int], mode: str,
    starts_at, kind: str = "tech", seq: int | None = None, ends_at=None,
    venue: str = "", meeting_url: str = "", capacity=None,
    instructions: str = "",
) -> tuple[InterviewRound, int]:
    """PC-UC-009: TPO schedules shortlisted applicants into an interview round.

    Governed by: PC-BR-011, PC-BR-012, PC-BR-021, PC-BR-030; BW-PC-06.
    """
    if _recruiter(actor):
        raise PermissionDeniedError("Placement Cell staff must schedule interviews.",
                                    code="staff_scheduling_required")
    require(actor, P_SCHEDULE)
    if starts_at <= timezone.now():
        raise ConflictError("Interview start time must be in the future.",
                            code="interview_time_in_past")
    if not application_ids:
        raise ConflictError("Select at least one shortlisted application.",
                            code="candidates_required")
    round_ = interviews.schedule_round(
        posting_id=posting_id, actor=actor, mode=mode, starts_at=starts_at,
        kind=kind, seq=seq, ends_at=ends_at, venue=venue,
        meeting_url=meeting_url, capacity=capacity, instructions=instructions,
        scope=scoping.postings_for(actor),
    )
    count = interviews.add_candidates(
        round_id=round_.pk, application_ids=application_ids, actor=actor,
        scope=scoping.applications_for(actor),
    )
    return round_, count


# ---------------------------------------------------------------------------
# PC-UC-022: Extend Formal Job Offer (BW-PC-07)
# ---------------------------------------------------------------------------
@transaction.atomic
def issue_job_offer(
    *, application_id: int, actor, ctc_lpa=None, tier_rank=None,
    respond_by=None, letter_id: int | None = None,
) -> Offer:
    """PC-UC-022: Recruiter or TPO extends a formal job offer with a response deadline.

    Governed by: PC-BR-009, PC-BR-013, PC-BR-021, PC-BR-030; BW-PC-07.
    """
    require(actor, P_OFFER_ISSUE, allow_recruiter=True)
    scope = scoping.applications_for(actor)
    return offers.issue(
        application_id=application_id,
        actor=actor,
        ctc_lpa=ctc_lpa,
        tier_rank=tier_rank,
        respond_by=respond_by,
        letter_id=letter_id,
        scope=scope,
    )


# ---------------------------------------------------------------------------
# PC-UC-008: Student Respond to Job Offer (BW-PC-07)
# ---------------------------------------------------------------------------
def respond_to_offer(*, offer_id: int, accept: bool, actor) -> Offer:
    """PC-UC-008: Student accepts or declines an extended job offer.

    Governed by: PC-BR-013, PC-BR-014, PC-BR-015, PC-BR-021; BW-PC-07.
    Acceptance automatically generates a verified PlacementRecord and enforces tier upgrades.
    """
    require(actor, P_OFFER_RESPOND)
    return offers.respond(offer_id=offer_id, accept=accept, actor=actor)


# ---------------------------------------------------------------------------
# PC-UC-010: Placement Record Administrative Correction (BW-PC-08)
# ---------------------------------------------------------------------------
def update_placement_record(
    *, record_id: int, actor, reason: str, company_id: int | None = None,
    ctc_lpa=None, kind: str | None = None, is_active: bool | None = None,
) -> PlacementRecord:
    """PC-UC-010: TPO corrects clerical errors on a recorded placement with mandatory audit justification.

    Governed by: PC-BR-024, PC-BR-029; BW-PC-08.
    """
    kwargs = {}
    if ctc_lpa is not None:
        kwargs["ctc_lpa"] = ctc_lpa
    return clearance.update_placement_record(
        record_id=record_id,
        actor=actor,
        reason=reason,
        company_id=company_id,
        kind=kind,
        is_active=is_active,
        **kwargs,
    )


# ---------------------------------------------------------------------------
# PC-UC-013: Announcements Management (PC-BR-017, PC-BR-018)
# ---------------------------------------------------------------------------
def publish_announcement(
    *, actor, title: str, body: str, topic: str = "general",
    audience: str = "students", placement_year: str = "",
) -> Announcement:
    """PC-UC-013: TPO publishes a targeted recruitment alert.

    Governed by: PC-BR-017, PC-BR-018, PC-BR-021.
    """
    require(actor, P_ANNOUNCEMENT_PUBLISH)
    return announcements.publish(
        actor=actor,
        title=title,
        body=body,
        topic=topic,
        audience=audience,
        placement_year=placement_year,
    )


# ---------------------------------------------------------------------------
# PC-UC-024: Student View Anonymized Placement Statistics (PC-BR-016)
# ---------------------------------------------------------------------------
def get_student_stats(*, season: str) -> dict:
    """PC-UC-024: Return anonymized placement figures with small-cell floor suppression.

    Governed by: PC-BR-016.
    """
    return stats.student_view(season=season)
