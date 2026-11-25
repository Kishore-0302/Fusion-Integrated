"""All writes to an application.

Spec refs: BW-PC-01..04, CW-PC-01, CW-PC-02, CW-PC-04,
           PC-UC-003, PC-BR-001, PC-BR-002, PC-BR-030.

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
from decimal import Decimal

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


def _json_safe(value):
    """Recursively convert Decimal instances to JSON-safe numbers (int or float)."""
    if isinstance(value, Decimal):
        return int(value) if value % 1 == 0 else float(value)
    if isinstance(value, dict):
        return {k: _json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(v) for v in value]
    return value


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
    if getattr(actor, "active_role", None) == "alumni" or getattr(actor, "kind", None) == "alumni":
        raise ConflictError(
            "Alumni cannot participate in active placement workflows such as applying.",
            code="alumni_workflow_prohibited")

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

    snapshot = _json_safe(evaluate_for(posting=posting, user_id=actor.user_id, policy=policy))

    app = Application.objects.create(
        posting=posting, user_id=actor.user_id, status=sm.DRAFT,
        cover_note=cover_note,
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
    return _json_safe({
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
    })


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


def student_status_view(*, user_id: int, actor) -> dict:
    """PC-AFR-010: Student-scoped status view combining applications,
    interviews, offers, and placement-record information."""
    is_staff = scoping.is_staff(actor)
    is_self = getattr(actor, "user_id", None) == user_id
    if not (is_staff or (is_self and actor.has_permission("placement_cell.application.view_self"))):
        raise PermissionDeniedError("Permission denied to view status.")

    apps = list(Application.objects.filter(user_id=user_id)
                .select_related("posting", "posting__company")
                .prefetch_related("transitions")
                .order_by("-created_at"))

    app_list = []
    for app in apps:
        transitions = [
            {
                "from_status": tr.from_status,
                "to_status": tr.to_status,
                "at": tr.at.isoformat(),
                "reason": tr.reason if is_staff else "",
                "actor_label": tr.actor_label if is_staff else "",
            }
            for tr in app.transitions.all()
        ]
        app_list.append({
            "id": app.pk,
            "posting_id": app.posting_id,
            "posting_title": app.posting.title,
            "company_name": app.posting.company.name,
            "status": app.status,
            "applied_at": app.applied_at.isoformat() if app.applied_at else None,
            "created_at": app.created_at.isoformat(),
            "transitions": transitions,
        })

    from modules.placement.models import Offer, PlacementRecord, RoundParticipation

    parts = list(RoundParticipation.objects.filter(application__user_id=user_id)
                 .select_related("round", "round__posting", "round__posting__company")
                 .order_by("round__starts_at"))
    interviews = [
        {
            "round_id": p.round_id,
            "application_id": p.application_id,
            "company_name": p.round.posting.company.name,
            "posting_title": p.round.posting.title,
            "round_seq": p.round.seq,
            "round_kind": p.round.kind,
            "mode": p.round.mode,
            "starts_at": p.round.starts_at.isoformat() if p.round.starts_at else None,
            "ends_at": p.round.ends_at.isoformat() if p.round.ends_at else None,
            "venue": p.round.venue,
            "meeting_url": p.round.meeting_url,
            "outcome": p.outcome,
            "score": str(p.score) if p.score is not None else None,
            "remarks": p.remarks if is_staff else "",
        }
        for p in parts
    ]

    offers = list(Offer.objects.filter(user_id=user_id)
                  .select_related("posting", "posting__company")
                  .order_by("-created_at"))
    offer_list = [
        {
            "id": o.pk,
            "application_id": o.application_id,
            "company_name": o.posting.company.name,
            "posting_title": o.posting.title,
            "ctc_lpa": str(o.ctc_lpa) if o.ctc_lpa is not None else None,
            "status": o.status,
            "issued_at": o.created_at.isoformat(),
            "respond_by": o.respond_by.isoformat() if o.respond_by else None,
        }
        for o in offers
    ]

    records = list(PlacementRecord.objects.filter(user_id=user_id)
                   .select_related("company", "policy")
                   .order_by("-created_at"))
    record_list = [
        {
            "id": r.pk,
            "season": r.policy.season,
            "company_name": r.company.name,
            "source": r.source,
            "kind": r.kind,
            "ctc_lpa": str(r.ctc_lpa) if r.ctc_lpa is not None else None,
            "is_active": r.is_active,
            "has_offer_letter": r.offer_letter_id is not None,
            "not_joining_declared": r.not_joining_declared_at is not None,
            "not_joining_reason": r.not_joining_reason if (is_self or is_staff) else "",
        }
        for r in records
    ]

    active_record = next((r for r in records if r.is_active), None)

    return {
        "user_id": user_id,
        "is_placed": active_record is not None,
        "active_placement": {
            "record_id": active_record.pk,
            "company_name": active_record.company.name,
            "ctc_lpa": str(active_record.ctc_lpa) if active_record.ctc_lpa is not None else None,
            "source": active_record.source,
            "kind": active_record.kind,
        } if active_record else None,
        "applications": app_list,
        "interviews": interviews,
        "offers": offer_list,
        "placement_records": record_list,
    }
