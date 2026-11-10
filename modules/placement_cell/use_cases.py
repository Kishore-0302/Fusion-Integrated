"""Application workflows for five Assignment 7 Placement Cell use cases."""
from __future__ import annotations

from django.db import transaction
from django.utils import timezone

from core.api.exceptions import ConflictError, NotFoundError, PermissionDeniedError
from modules.placement.domain import state_machine as states
from modules.placement.models import Application, InterviewRound, JobPosting
from modules.placement.selectors import scoping
from modules.placement.services import applications, interviews, postings
from modules.placement.services.authz import require

P_POSTING = "placement_cell.job_posting.manage"
P_APPLY = "placement_cell.application.create"
P_REVIEW = "placement_cell.application.review"
P_SCHEDULE = "placement_cell.interview.schedule"


def _recruiter(actor) -> bool:
    return getattr(actor, "kind", None) == "recruiter"


@transaction.atomic
def submit_company_opportunity(*, posting_id: int, actor) -> JobPosting:
    """PC-UC-015: submit a complete company draft for TPO review."""
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


@transaction.atomic
def publish_tpo_opportunity(*, posting_id: int, actor) -> JobPosting:
    """PC-UC-006: TPO publishes a company-submitted opportunity."""
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


@transaction.atomic
def apply_to_opportunity(
    *, posting_id: int, actor, cover_note: str = "", resume_id: int | None = None
) -> Application:
    """PC-UC-003: student applies through eligibility and policy checks."""
    require(actor, P_APPLY)
    if getattr(actor, "user_id", None) is None:
        raise PermissionDeniedError("A student identity is required.",
                                    code="student_identity_required")
    return applications.apply_to(
        posting_id=posting_id, actor=actor,
        cover_note=cover_note, resume_id=resume_id,
    )


@transaction.atomic
def review_company_application(
    *, application_id: int, actor, decision: str, reason: str = ""
) -> Application:
    """PC-UC-016: company records a shortlist or rejection for its applicant."""
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


@transaction.atomic
def schedule_interviews(
    *, posting_id: int, actor, application_ids: list[int], mode: str,
    starts_at, kind: str = "tech", seq: int | None = None, ends_at=None,
    venue: str = "", meeting_url: str = "", capacity=None,
    instructions: str = "",
) -> tuple[InterviewRound, int]:
    """PC-UC-009: TPO schedules shortlisted applicants into an interview round."""
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
