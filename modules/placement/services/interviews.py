"""Interview scheduling and tracking.

Spec refs: PC-UC-009, PC-UC-021, BW-PC-05, BW-PC-06, CW-PC-02, PC-BR-011/012.
"""
from __future__ import annotations

from django.db import transaction

from core.api.exceptions import ConflictError, NotFoundError
from modules.placement.domain import state_machine as sm
from modules.placement.models import Application, InterviewRound, JobPosting, RoundParticipation
from modules.placement.services import applications as app_service
from modules.placement.services import notifications
from modules.placement.services.authz import require

P_SCHEDULE = "placement_cell.interview.schedule"
P_REVIEW = "placement_cell.application.review"


@transaction.atomic
def schedule_round(*, posting_id: int, actor, mode: str, starts_at,
                   kind: str = "tech", seq: int | None = None, ends_at=None,
                   venue: str = "", meeting_url: str = "", capacity=None,
                   instructions: str = "", scope=None) -> InterviewRound:
    """PC-BR-011: date, time slot and mode are all required."""
    require(actor, P_SCHEDULE, allow_recruiter=True)
    qs = scope if scope is not None else JobPosting.objects.all()
    posting = qs.filter(pk=posting_id).first()
    if posting is None:
        raise NotFoundError("No such posting.")

    if mode not in ("online", "offline"):
        raise ConflictError("Mode must be online or offline.", code="bad_mode")
    if mode == "online" and not meeting_url:
        raise ConflictError("An online round needs a meeting link.",
                            code="meeting_url_required")
    if mode == "offline" and not venue:
        raise ConflictError("An offline round needs a venue.",
                            code="venue_required")

    if seq is None:
        seq = (InterviewRound.objects.filter(posting=posting).count() or 0) + 1

    is_recruiter = getattr(actor, "kind", None) == "recruiter"
    return InterviewRound.objects.create(
        posting=posting, seq=seq, kind=kind, mode=mode, starts_at=starts_at,
        ends_at=ends_at, venue=venue, meeting_url=meeting_url,
        capacity=capacity, instructions=instructions,
        scheduled_by_user_id=None if is_recruiter else actor.user_id,
        scheduled_by_recruiter_id=actor.account_id if is_recruiter else None,
    )


@transaction.atomic
def add_candidates(*, round_id: int, application_ids: list[int], actor,
                   scope=None) -> int:
    """Put shortlisted candidates into a round and notify them (PC-BR-012).

    `scope` stops a recruiter reaching a candidate who never applied to them;
    a student's own application is in their scope, hence the permission gate.
    """
    require(actor, P_SCHEDULE, allow_recruiter=True)
    round_ = (InterviewRound.objects.select_related("posting", "posting__company")
              .filter(pk=round_id).first())
    if round_ is None:
        raise NotFoundError("No such interview round.")

    apps_qs = scope if scope is not None else Application.objects.all()
    apps = list(apps_qs.filter(pk__in=application_ids,
                               posting_id=round_.posting_id))
    if len(apps) != len(set(application_ids)):
        # Scheduling only the allowed subset would hide a mistake; say so instead.
        raise ConflictError(
            "Some applications are not available for this posting.",
            code="applications_out_of_scope",
            details=[{"requested": len(set(application_ids)),
                      "available": len(apps)}])

    if round_.capacity is not None:
        already = RoundParticipation.objects.filter(round=round_).count()
        if already + len(apps) > round_.capacity:
            raise ConflictError(
                f"This round holds {round_.capacity}; {already} are already "
                f"scheduled.", code="round_full")

    created = 0
    for app in apps:
        _, made = RoundParticipation.objects.get_or_create(
            round=round_, application=app, defaults={"outcome": "pending"})
        if not made:
            continue
        created += 1
        if app.status == sm.SHORTLISTED:
            app_service.transition(
                application_id=app.pk, to_status=sm.INTERVIEW_SCHEDULED,
                actor=actor, reason=f"Scheduled into round {round_.seq}",
                scope=apps_qs)
        notifications.enqueue(
            topic="interview.scheduled",
            dedupe_key=f"interview.scheduled:{round_.pk}:{app.pk}",
            recipient_user_id=app.user_id,
            subject=f"Interview scheduled — {round_.posting.title}",
            body=(f"{round_.get_kind_display()} on "
                  f"{round_.starts_at:%d %b %Y %H:%M} ({round_.mode}). "
                  f"{round_.venue or round_.meeting_url}"),
            payload={"round_id": round_.pk, "application_id": app.pk,
                     "starts_at": round_.starts_at.isoformat(),
                     "mode": round_.mode})
    return created


@transaction.atomic
def record_outcome(*, round_id: int, application_id: int, outcome: str,
                   actor, score=None, remarks: str = "", scope=None) -> RoundParticipation:
    # Without this a student marks their own interview "passed".
    require(actor, P_SCHEDULE, P_REVIEW, allow_recruiter=True)
    valid = {c for c, _ in RoundParticipation.OUTCOME}
    if outcome not in valid:
        raise ConflictError(f"Outcome must be one of {sorted(valid)}.",
                            code="bad_outcome")

    apps_qs = scope if scope is not None else Application.objects.all()
    participation = (RoundParticipation.objects.select_for_update()
                     .select_related("application")
                     .filter(round_id=round_id,
                             application_id=application_id,
                             application__in=apps_qs).first())
    if participation is None:
        raise NotFoundError("No such candidate in this round.")

    participation.outcome = outcome
    participation.score = score
    participation.remarks = remarks
    participation.save(update_fields=["outcome", "score", "remarks", "updated_at"])
    return participation


def interview_progress_view(*, actor, posting_id: int | None = None,
                            season: str | None = None) -> list[dict]:
    """PC-AFR-029: TPO-scoped view for tracking interview progress and status."""
    require(actor, "placement_cell.report.view", P_SCHEDULE, allow_recruiter=True)
    is_recruiter = getattr(actor, "kind", None) == "recruiter"
    qs = (InterviewRound.objects
          .select_related("posting", "posting__company")
          .prefetch_related("participants"))

    if is_recruiter:
        qs = qs.filter(posting__company_id=actor.company_id)
    if posting_id:
        qs = qs.filter(posting_id=posting_id)
    if season:
        qs = qs.filter(posting__placement_year=season)

    rounds = list(qs.order_by("-posting__created_at", "seq"))
    results = []
    for r in rounds:
        parts = list(r.participants.all())
        total = len(parts)
        pending = sum(1 for p in parts if p.outcome == "pending")
        passed = sum(1 for p in parts if p.outcome == "passed")
        failed = sum(1 for p in parts if p.outcome == "failed")
        attended = sum(1 for p in parts if p.outcome in ("attended", "passed", "failed"))
        absent = sum(1 for p in parts if p.outcome == "absent")

        candidates = [
            {
                "participation_id": p.pk,
                "application_id": p.application_id,
                "outcome": p.outcome,
                "score": str(p.score) if p.score is not None else None,
                "remarks": p.remarks,
                "updated_at": p.updated_at.isoformat() if p.updated_at else None,
            }
            for p in parts
        ]

        results.append({
            "round_id": r.pk,
            "posting_id": r.posting_id,
            "posting_title": r.posting.title,
            "company_name": r.posting.company.name,
            "season": r.posting.placement_year,
            "seq": r.seq,
            "kind": r.kind,
            "mode": r.mode,
            "starts_at": r.starts_at.isoformat() if r.starts_at else None,
            "ends_at": r.ends_at.isoformat() if r.ends_at else None,
            "venue": r.venue,
            "meeting_url": r.meeting_url,
            "capacity": r.capacity,
            "stats": {
                "total_candidates": total,
                "attended_candidates": attended,
                "pending_candidates": pending,
                "passed_candidates": passed,
                "failed_candidates": failed,
                "absent_candidates": absent,
            },
            "candidates": candidates,
        })
    return results
