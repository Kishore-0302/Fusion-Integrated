"""All writes to an application (PC-WF-004, PC-WF-005).

Raises domain errors, never DRF exceptions, so it stays callable from a task
or a management command. Three checks must all pass:

    state machine   which kind of actor may drive this edge
    permission      whether this institute user holds the right
    scope           whether they may touch THIS application, supplied by the
                    caller as a queryset so a foreign one is a 404
"""
from __future__ import annotations

import logging
from collections.abc import Sequence
from dataclasses import dataclass

from django.db import transaction
from django.utils import timezone

from core.api.exceptions import ConflictError, DomainError, NotFoundError, PermissionDeniedError
from modules.directory import contracts as directory
from modules.placement.domain import eligibility as elig
from modules.placement.domain import state_machine as sm
from modules.placement.models import (
    Application,
    ApplicationTransition,
    JobPosting,
    PlacementPolicy,
    PlacementRegistration,
    RoundParticipation,
)
from modules.placement.selectors import scoping
from modules.placement.services import facts as facts_service
from modules.placement.services import notifications

log = logging.getLogger("fusion.placement.applications")


def actor_kind(actor, application=None) -> str:
    """Which lane of the state machine this caller is in.

    Follows what they were granted, not `principal.kind` — a student placement
    coordinator is a real role and would otherwise be locked out of the job
    they were appointed to do. Acting on their OWN application drops them back
    to the student lane, which is the self-approval guard.
    """
    if actor is None:
        return sm.SYSTEM
    if getattr(actor, "kind", None) == "recruiter":
        return sm.RECRUITER
    if scoping.is_staff(actor):
        own = (application is not None
               and application.user_id == getattr(actor, "user_id", None))
        return sm.STUDENT if own else sm.STAFF
    return sm.STUDENT


def _guard_conduct_sanction(application) -> None:
    """Rule 19's first tier bars the next two drives, not the season, so the
    season-wide debarred flag cannot express it."""
    from modules.placement.services import conduct as conduct_service

    registration = PlacementRegistration.objects.filter(
        policy__season=application.posting.placement_year,
        user_id=application.user_id).first()
    if registration is None:
        return
    if conduct_service.bars_posting(registration, application.posting):
        raise ConflictError(
            registration.debarred_reason
            or "A placement sanction is in force against your registration.",
            code="conduct_sanction")


def resolve_or_raise(frm: str, to: str, kind: str):
    """`sm.resolve` with its errors translated. Every path into the state
    machine must use this, or an illegal move surfaces as a 500."""
    try:
        return sm.resolve(frm, to, kind)
    except sm.InvalidTransition as exc:
        raise ConflictError(
            f"An application cannot move from '{exc.frm}' to '{exc.to}'.",
            code="invalid_transition",
            details=[{"from": exc.frm, "to": exc.to,
                      "allowed": sm.allowed_targets(exc.frm, kind)}],
        ) from exc
    except sm.ActorNotAllowed as exc:
        raise PermissionDeniedError(
            "Your role cannot make that change.", code="actor_not_allowed",
            details=[{"from": exc.frm, "to": exc.to, "actor": exc.actor_kind}],
        ) from exc


def _guard(name: str, *, application, reason: str, actor) -> None:
    posting = application.posting
    now = timezone.now()

    if name == "has_reason" and not (reason or "").strip():
        raise ConflictError("A reason is required for this decision.",
                            code="reason_required")

    if name == "window_open":
        if posting.status != "published":
            raise ConflictError("This posting is not open for applications.",
                                code="posting_not_published")
        if posting.opens_at and now < posting.opens_at:
            raise ConflictError("Applications for this posting have not opened.",
                                code="window_not_open")
        if posting.closes_at and now > posting.closes_at:
            raise ConflictError("Applications for this posting have closed.",
                                code="window_closed")

    if name == "profile_complete":
        # PC-BR-001, answered by the ERP portal, which owns the one profile.
        person = directory.get_users([application.user_id]).get(application.user_id)
        if not getattr(person, "profile_completed", False):
            raise ConflictError(
                "Complete your profile on the Fusion portal before applying.",
                code="profile_incomplete")

    if name == "is_eligible":
        snapshot = application.eligibility_snapshot or {}
        if not snapshot.get("is_eligible"):
            raise ConflictError("You are not eligible for this posting.",
                                code="not_eligible",
                                details=snapshot.get("failed", []))

    if name == "may_apply":
        decision = (application.eligibility_snapshot or {}).get("season_decision")
        if decision and not decision.get("allowed"):
            raise ConflictError(decision.get("message", "You may not apply."),
                                code=decision.get("rule", "not_allowed"))
        _guard_conduct_sanction(application)

    if name == "has_scheduled_round" and not RoundParticipation.objects.filter(
            application=application).exists():
        raise ConflictError(
            "Schedule the candidate into an interview round first.",
            code="no_round_scheduled")

    if name == "company_authorized" and not posting.company.can_operate:
        raise ConflictError("This company is not currently authorized.",
                            code="company_not_approved")


@transaction.atomic
def transition(*, application_id: int, to_status: str, actor,
               reason: str = "", scope=None) -> Application:
    """Move one application. `scope` makes an out-of-scope one a 404."""
    qs = scope if scope is not None else Application.objects.all()
    app = (qs.select_for_update().select_related("posting", "posting__company")
           .filter(pk=application_id).first())
    if app is None:
        raise NotFoundError("No such application.")

    kind = actor_kind(actor, app)
    t = resolve_or_raise(app.status, to_status, kind)

    # Recruiters hold no codes; the company-scoped queryset is their authority.
    if kind in (sm.STAFF, sm.STUDENT) and not actor.has_permission(t.permission):
        raise PermissionDeniedError(f"This action needs {t.permission}.",
                                    code="permission_denied")

    for g in t.guards:
        _guard(g, application=app, reason=reason, actor=actor)

    frm, app.status = app.status, to_status
    touched = ["status", "updated_at"]
    if to_status == sm.SUBMITTED:
        app.applied_at = timezone.now()
        touched.append("applied_at")
    if to_status in (sm.WITHDRAWN, sm.AUTO_WITHDRAWN) and reason:
        app.withdrawn_reason = reason[:300]
        touched.append("withdrawn_reason")
    app.save(update_fields=touched)

    ApplicationTransition.objects.create(
        application=app, from_status=frm, to_status=to_status,
        actor_user_id=getattr(actor, "user_id", None),
        actor_recruiter_id=getattr(actor, "account_id", None)
        if kind == sm.RECRUITER else None,
        actor_label=kind, reason=reason,
    )

    _notify_transition(app, to_status)
    return app


def _notify_transition(app: Application, to_status: str) -> None:
    topics = {
        sm.SHORTLISTED: ("application.shortlisted", "You have been shortlisted"),
        sm.REJECTED: ("application.rejected", "Update on your application"),
        sm.SUBMITTED: ("application.submitted", "Application received"),
    }
    entry = topics.get(to_status)
    if entry is None:
        return
    topic, subject = entry
    notifications.enqueue(
        topic=topic, dedupe_key=f"{topic}:{app.pk}:{to_status}",
        recipient_user_id=app.user_id,
        subject=f"{subject} — {app.posting.title}",
        body=f"Your application for {app.posting.title} is now {to_status}.",
        payload={"application_id": app.pk, "status": to_status},
    )


# -- Creating an application ---------------------------------------------------
@transaction.atomic
def apply_to(*, posting_id: int, actor, cover_note: str = "",
             resume_id: int | None = None) -> Application:
    """Create and submit in one step (PC-UC-003).

    Eligibility is frozen onto the row, so the decision stays reproducible
    after a CPI or rule change. That snapshot is what an appeal is judged on.
    """
    posting = (JobPosting.objects.select_related("company")
               .filter(pk=posting_id).first())
    if posting is None:
        raise NotFoundError("No such posting.")

    policy = PlacementPolicy.objects.filter(season=posting.placement_year).first()
    if policy is None:
        raise ConflictError(
            f"No placement policy is configured for {posting.placement_year}.",
            code="policy_missing")

    if Application.objects.filter(posting=posting, user_id=actor.user_id).exists():
        raise ConflictError("You have already applied to this posting.",
                            code="already_applied")

    snapshot = evaluate_for(posting=posting, user_id=actor.user_id, policy=policy)

    app = Application.objects.create(
        posting=posting, user_id=actor.user_id, status=sm.DRAFT,
        cover_note=cover_note, resume_id=resume_id,
        cpi_at_apply=snapshot.get("cpi"),
        semester_at_apply=snapshot.get("semester"),
        standing_declared_seq_at_apply=snapshot.get("declared_seq"),
        eligibility_snapshot=snapshot,
    )
    return transition(application_id=app.pk, to_status=sm.SUBMITTED, actor=actor)


def evaluate_for(*, posting: JobPosting, user_id: int,
                 policy: PlacementPolicy) -> dict:
    """The eligibility verdict for one student against one posting."""
    from modules.placement.domain import offer_policy as pol

    all_facts = facts_service.gather([user_id], policy=policy)
    f = all_facts.get(user_id, {})
    outcome = elig.evaluate(posting.eligibility_rule, f)

    from modules.placement.services import offers as offer_service

    registration = PlacementRegistration.objects.filter(
        policy=policy, user_id=user_id).first()
    held = None
    if registration and registration.offer_count:
        from modules.placement.models import Offer
        held = (Offer.objects.filter(user_id=user_id, status="accepted",
                                     posting__placement_year=policy.season)
                .order_by("-ctc_lpa").first())

    season = pol.can_apply(
        offer_service.policy_spec(policy),
        offer_service.student_state(
            registration, held, discipline=f.get("discipline")),
        pol.OfferSpec(
            ctc_lpa=posting.ctc_lpa,
            is_marquee=posting.company.is_marquee,
            is_dream_slot=posting.is_dream_slot,
            sector=posting.company.sector_kind))

    standing = f.get("_standing") or {}
    return {
        "is_eligible": outcome.is_eligible and season.allowed,
        "failed": elig.failure_reasons(outcome),
        "error": outcome.error,
        "season_decision": {"allowed": season.allowed, "rule": season.rule,
                            "message": season.message},
        "cpi": str(f["cpi"]) if f.get("cpi") is not None else None,
        "semester": standing.get("semester"),
        "declared_seq": standing.get("declared_seq"),
        "standing": standing,
        "evaluated_at": timezone.now().isoformat(),
    }


#: A convenience, not a migration tool, and N queries per item.
MAX_BULK = 200


@dataclass(frozen=True)
class BulkOutcome:
    application_id: int
    moved: bool
    #: The refusal a single transition would have given, verbatim.
    error: str = ""
    code: str = ""


def bulk_transition(*, application_ids: Sequence[int], to_status: str, actor,
                    reason: str = "", scope=None) -> list[BulkOutcome]:
    """Move several applications, reporting each one's fate.

    Each item goes through `transition` — the same scope, permission, state
    machine and guards. A separate bulk path is precisely where one of those
    checks gets forgotten, so there isn't one.

    Deliberately NOT all-or-nothing: a TPO shortlisting forty candidates should
    not be blocked because one of them withdrew an hour ago. Each item commits
    on its own and the caller is told exactly which did not, so a partial run
    can never read as a complete one.
    """
    ids = list(dict.fromkeys(int(i) for i in application_ids))
    if not ids:
        raise ConflictError("Select at least one application.",
                            code="nothing_selected")
    if len(ids) > MAX_BULK:
        raise ConflictError(
            f"Up to {MAX_BULK} applications at a time; {len(ids)} were sent.",
            code="too_many")

    outcomes: list[BulkOutcome] = []
    for application_id in ids:
        try:
            # Its own transaction, so one refusal does not roll back the rest.
            with transaction.atomic():
                transition(application_id=application_id, to_status=to_status,
                           actor=actor, reason=reason, scope=scope)
            outcomes.append(BulkOutcome(application_id, moved=True))
        except DomainError as exc:
            outcomes.append(BulkOutcome(application_id, moved=False,
                                        error=exc.message, code=exc.code))

    moved = sum(1 for o in outcomes if o.moved)
    log.info("placement.applications.bulk to=%s moved=%d refused=%d by=%s",
             to_status, moved, len(outcomes) - moved,
             getattr(actor, "user_id", None))
    return outcomes


# -- Submit an application (PR 445 / PBI 17) -----------------------------------
@transaction.atomic
def submit_application(user_id: int, posting_id: int, facts: dict) -> Application:
    """Submit an application for a job posting.

    Args:
        user_id: The ID of the user applying.
        posting_id: The ID of the job posting.
        facts: Facts about the student (cpi, discipline, active_backlogs, etc.).

    Returns:
        The created and submitted Application.

    Raises:
        NotFoundError: If the job posting does not exist.
        ValidationError: If the application window is closed, student is ineligible,
                         or student has already applied.
        ConflictError: If the placement policy for the posting's season is missing.
    """
    from django.core.exceptions import ValidationError

    from modules.placement.domain.eligibility import evaluate_student_eligibility

    posting = JobPosting.objects.filter(pk=posting_id).first()
    if posting is None:
        raise NotFoundError("No such posting.")
    if posting.status != "published" or (posting.closes_at and timezone.now() > posting.closes_at):
        raise ValidationError("The application window has closed.")

    policy = PlacementPolicy.objects.filter(season=posting.placement_year).first()
    if policy is None:
        raise ConflictError(
            f"No placement policy is configured for {posting.placement_year}.",
            code="policy_missing",
        )

    is_eligible, errors = evaluate_student_eligibility(facts, posting.eligibility_rule)
    if not is_eligible:
        raise ValidationError(errors[0] if errors else "Student is not eligible.")

    if Application.objects.filter(posting=posting, user_id=user_id).exists():
        raise ValidationError("You have already applied to this posting.")

    application = Application.objects.create(
        posting=posting,
        user_id=user_id,
        status=sm.SUBMITTED,
        cpi_at_apply=facts.get("cpi"),
        semester_at_apply=facts.get("semester"),
        standing_declared_seq_at_apply=facts.get("declared_seq"),
        eligibility_snapshot=facts,
    )

    ApplicationTransition.objects.create(
        application=application,
        from_status=sm.DRAFT,
        to_status=sm.SUBMITTED,
        actor_label="student",
        reason="Application submitted",
    )

    notifications.enqueue(
        topic="application.submitted",
        dedupe_key=f"application.submitted:{application.pk}:{sm.SUBMITTED}",
        subject=f"Application received — {posting.title}",
        body=f"Your application for {posting.title} has been submitted.",
        recipient_user_id=user_id,
        payload={
            "application_id": application.pk,
            "posting_id": posting_id,
            "title": posting.title,
        },
    )

    return application

