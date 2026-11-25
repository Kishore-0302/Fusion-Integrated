"""Offers and placement records.

Spec refs: BW-PC-07, BW-PC-08, CW-PC-03, CW-PC-04,
           PC-BR-013/014/015, PC-UC-005, PC-UC-022.

Two tabs accepting two offers at once is stopped three times over: a
`select_for_update` mutex on the registration row, the policy re-evaluated
inside that lock, and a partial unique index on PlacementRecord that holds
even if this service is bypassed entirely.
"""
from __future__ import annotations

from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from core.api.exceptions import ConflictError, NotFoundError
from modules.placement.domain import offer_policy as pol
from modules.placement.domain import state_machine as sm
from modules.placement.models import (
    Application,
    ApplicationTransition,
    Offer,
    PlacementPolicy,
    PlacementRecord,
    PlacementRegistration,
)
from modules.placement.services import notifications
from modules.placement.services.authz import require

P_ISSUE = "placement_cell.offer.issue"


def policy_spec(policy: PlacementPolicy) -> pol.PolicySpec:
    """The stored policy as the pure spec the rules operate on.

    A season with no categories falls back to the signed defaults, so a
    half-configured season still enforces something.
    """
    rows = list(policy.categories.all())
    categories = tuple(
        pol.CategorySpec(
            group=c.group, number=c.number,
            ctc_min=c.ctc_min, ctc_max=c.ctc_max,
            switch_multiplier=c.switch_multiplier,
            switch_floor=c.switch_floor, exit_above=c.exit_above,
            max_switches=c.max_switches,
        ) for c in rows
    ) or pol.default_categories()

    return pol.PolicySpec(
        season=policy.season,
        categories=categories,
        group_map=policy.discipline_groups or dict(pol.DEFAULT_GROUP_MAP),
        mandatory_from=policy.mandatory_from,
        min_cpi_to_register=policy.min_cpi_to_register,
        allow_backlog_registration=policy.allow_backlog_registration,
    )


def student_state(registration: PlacementRegistration | None,
                  held: Offer | None, *,
                  discipline: str | None = None) -> pol.StudentState:
    if registration is None:
        return pol.StudentState(discipline=discipline, is_registered=False)
    return pol.StudentState(
        discipline=discipline,
        is_registered=registration.status == "registered",
        is_debarred=registration.status == "debarred",
        category_number=registration.category_number,
        accepted_offer_count=registration.offer_count,
        switches_used=registration.switches_used,
        held_ctc_lpa=registration.best_accepted_ctc_lpa,
        held_offer_id=held.pk if held else None,
        held_is_marquee=registration.held_is_marquee,
        held_sector=registration.held_sector_kind or None,
    )


def offer_spec(offer: Offer) -> pol.OfferSpec:
    company = offer.posting.company
    return pol.OfferSpec(
        offer_id=offer.pk, ctc_lpa=offer.ctc_lpa,
        is_marquee=company.is_marquee,
        is_dream_slot=offer.posting.is_dream_slot,
        sector=company.sector_kind,
    )


def _discipline_of(user_id: int) -> str | None:
    """From the IAM directory — the switch rules are per discipline group."""
    from modules.directory import contracts as directory
    person = directory.get_users([user_id]).get(user_id)
    return getattr(person, "discipline", None) or None


_spec = policy_spec
_student_state = student_state


@transaction.atomic
def issue(*, application_id: int, actor, ctc_lpa=None, tier_rank=None,
          respond_by=None, letter_id: int | None = None, scope=None) -> Offer:
    """Extend an offer (PC-UC-022). Always carries a response deadline.

    Both gates: `require` is the authority, `scope` is the reach.
    """
    require(actor, P_ISSUE, allow_recruiter=True)
    qs = scope if scope is not None else Application.objects.all()
    app = (qs.select_for_update()
           .select_related("posting", "posting__company")
           .filter(pk=application_id).first())
    if app is None:
        raise NotFoundError("No such application.")

    posting = app.posting
    if not posting.company.can_operate:
        raise ConflictError("This company is not currently authorized.",
                            code="company_not_approved")
    if Offer.objects.filter(application=app).exists():
        raise ConflictError("This application already has an offer.",
                            code="offer_exists")

    policy = _policy_for(posting.placement_year)
    if respond_by is None:
        # PC-BR-013: without a deadline the offer never expires and blocks the pool.
        respond_by = timezone.now() + timedelta(
            hours=policy.default_offer_response_hours)
    if respond_by <= timezone.now():
        raise ConflictError("The response deadline must be in the future.",
                            code="deadline_in_past")

    offer = Offer.objects.create(
        application=app, posting=posting, user_id=app.user_id,
        ctc_lpa=ctc_lpa if ctc_lpa is not None else posting.ctc_lpa,
        tier_rank=tier_rank if tier_rank is not None else posting.company.tier_rank,
        respond_by=respond_by, status="issued", letter_id=letter_id,
        issued_by_user_id=getattr(actor, "user_id", None),
        issued_by_recruiter_id=getattr(actor, "account_id", None)
        if getattr(actor, "kind", None) == "recruiter" else None,
    )
    # Rule 7: "dream" is declared per posting, not derived from a CTC.
    if posting.is_dream_slot:
        offer.is_dream = True
        offer.save(update_fields=["is_dream"])

    _move(app, sm.OFFER_ISSUED, actor, reason="Offer issued")

    notifications.enqueue(
        topic="offer.issued", dedupe_key=f"offer.issued:{offer.pk}",
        recipient_user_id=app.user_id,
        subject=f"Offer from {posting.company.name}",
        body=(f"You have an offer for {posting.title}. "
              f"Respond by {respond_by:%d %b %Y %H:%M}."),
        payload={"offer_id": offer.pk, "posting_id": posting.pk,
                 "respond_by": respond_by.isoformat()},
    )
    return offer


def respond(*, offer_id: int, accept: bool, actor) -> Offer:
    """A student accepts or declines (PC-UC-005).

    A policy refusal leaves the atomic block normally and raises afterwards:
    the reason is persisted for an appeal, and raising inside the transaction
    would roll back the very record the appeal needs.
    """
    denial = _decide_and_apply(offer_id=offer_id, accept=accept, actor=actor)
    if denial is None:
        return (Offer.objects.select_related("posting", "posting__company")
                .get(pk=offer_id))

    offer_pk, decision = denial
    Offer.objects.filter(pk=offer_pk).update(
        policy_decision=decision.as_json(), updated_at=timezone.now())
    raise ConflictError(decision.message, code=decision.rule,
                        details=[decision.facts])


@transaction.atomic
def _decide_and_apply(*, offer_id: int, accept: bool, actor):
    """None when applied, or (offer_pk, Decision) when policy refused.

    The registration row is locked for the whole block: every acceptance for a
    student contends on the same row, so two tabs cannot both read "0 held".
    """
    # Scoped by user_id, so another's offer is not found rather than refused.
    offer = (Offer.objects.select_for_update()
             .select_related("application", "posting", "posting__company")
             .filter(pk=offer_id, user_id=actor.user_id).first())
    if offer is None:
        raise NotFoundError("No such offer.")
    if offer.status != "issued":
        raise ConflictError(f"This offer is already {offer.status}.",
                            code="offer_not_open")
    if timezone.now() > offer.respond_by:
        raise ConflictError("The response deadline for this offer has passed.",
                            code="offer_expired")

    policy = _policy_for(offer.posting.placement_year)

    if not accept:
        offer.status = "declined"
        offer.responded_at = timezone.now()
        offer.policy_decision = {"allowed": True, "rule": "declined_by_student"}
        offer.save(update_fields=["status", "responded_at", "policy_decision",
                                  "updated_at"])
        _move(offer.application, sm.OFFER_DECLINED, actor, reason="Declined")
        return None

    # -- acceptance -------------------------------------------------------
    registration = (PlacementRegistration.objects.select_for_update()
                    .filter(policy=policy, user_id=actor.user_id).first())
    held = (Offer.objects.filter(user_id=actor.user_id, status="accepted",
                                 posting__placement_year=policy.season)
            .order_by("-ctc_lpa").first())

    spec = policy_spec(policy)
    state = student_state(registration, held,
                          discipline=_discipline_of(actor.user_id))
    decision = pol.can_accept(spec, state, offer_spec(offer))

    if not decision.allowed:
        return (offer.pk, decision)     # caller persists the reason and raises

    offer.policy_decision = decision.as_json()
    offer.status = "accepted"
    offer.responded_at = timezone.now()
    offer.save(update_fields=["status", "responded_at", "policy_decision",
                              "updated_at"])
    _move(offer.application, sm.OFFER_ACCEPTED, actor, reason="Accepted")

    if decision.supersedes_offer_id:
        _supersede(decision.supersedes_offer_id)

    PlacementRecord.objects.create(
        policy=policy, offer=offer, company=offer.posting.company,
        posting=offer.posting, user_id=actor.user_id, ctc_lpa=offer.ctc_lpa,
        kind=offer.posting.kind, is_active=True,
        recorded_by_user_id=actor.user_id,
    )

    if registration is not None:
        _record_acceptance(registration, offer, decision, spec, state)

    _auto_withdraw_others(user_id=actor.user_id, policy=policy, spec=spec,
                          state=state, keep_application_id=offer.application_id)
    return None


def _record_acceptance(registration, offer, decision, spec, state) -> None:
    """Update the counters the policy reads on the next decision.

    `category_number` locks on the first acceptance (rule 2.A) and never
    changes — moving up ends the season under rule 3 instead. `switches_used`
    counts only acceptances that REPLACED a held offer; counting a first offer
    would halve everyone's allowance.
    """
    company = offer.posting.company
    fields = ["offer_count", "best_accepted_ctc_lpa", "best_accepted_tier_rank",
              "held_is_marquee", "held_sector_kind", "updated_at"]

    registration.offer_count += 1
    registration.best_accepted_ctc_lpa = offer.ctc_lpa
    registration.best_accepted_tier_rank = offer.tier_rank
    registration.held_is_marquee = company.is_marquee
    registration.held_sector_kind = company.sector_kind

    if decision.supersedes_offer_id:
        registration.switches_used += 1
        fields.append("switches_used")

    if registration.category_number is None:
        group = pol.group_for(state.discipline, spec.group_map)
        category = spec.category_for_offer(group, offer.ctc_lpa)
        if category is not None:
            registration.category_number = category.number
            registration.category_locked_at = timezone.now()
            fields += ["category_number", "category_locked_at"]

    registration.save(update_fields=fields)


def _supersede(offer_id: int) -> None:
    """An upgrade retires the earlier offer and its record."""
    Offer.objects.filter(pk=offer_id, status="accepted").update(
        status="superseded")
    PlacementRecord.objects.filter(offer_id=offer_id, is_active=True).update(
        is_active=False)


def _auto_withdraw_others(*, user_id: int, policy: PlacementPolicy, spec, state,
                          keep_application_id: int) -> int:
    """Close only the applications this student may no longer pursue.

    Not a blanket sweep: a dream slot stays open to placed students (rule 7),
    a non-CSE student holding IT may still sit for Core (rule 10), and an
    unspent switch allowance keeps everything open (rule 2). Each application
    is asked the same question the student would be, and the reason is
    recorded per application.
    """
    # State AFTER the acceptance — the pre-acceptance state would close nothing.
    registration = PlacementRegistration.objects.filter(
        policy=policy, user_id=user_id).first()
    held = (Offer.objects.filter(user_id=user_id, status="accepted",
                                 posting__placement_year=policy.season)
            .order_by("-ctc_lpa").first())
    after = student_state(registration, held, discipline=state.discipline)

    others = (Application.objects
              .select_related("posting", "posting__company")
              .filter(user_id=user_id,
                      posting__placement_year=policy.season,
                      status__in=sm.IN_FLIGHT)
              .exclude(pk=keep_application_id))

    rows, closing, n = [], [], 0
    for app in others:
        company = app.posting.company
        verdict = pol.can_apply(spec, after, pol.OfferSpec(
            ctc_lpa=app.posting.ctc_lpa,
            is_marquee=company.is_marquee,
            is_dream_slot=app.posting.is_dream_slot,
            sector=company.sector_kind))
        if verdict.allowed:
            continue
        closing.append(app.pk)
        rows.append(ApplicationTransition(
            application=app, from_status=app.status,
            to_status=sm.AUTO_WITHDRAWN, actor_user_id=None,
            actor_label="system",
            reason=f"Closed by policy after an offer was accepted: "
                   f"{verdict.message}"[:300]))
        n += 1

    if rows:
        Application.objects.filter(pk__in=closing).update(
            status=sm.AUTO_WITHDRAWN)
        ApplicationTransition.objects.bulk_create(rows)
    return n


def expire_overdue(*, now=None) -> int:
    """Sweep for offers whose deadline passed (PC-BR-013). Idempotent."""
    now = now or timezone.now()
    n = 0
    for offer in (Offer.objects.select_related("application")
                  .filter(status="issued", respond_by__lt=now)):
        with transaction.atomic():
            locked = Offer.objects.select_for_update().get(pk=offer.pk)
            if locked.status != "issued":
                continue                       # answered in the interim
            locked.status = "expired"
            locked.save(update_fields=["status", "updated_at"])
            app = locked.application
            ApplicationTransition.objects.create(
                application=app, from_status=app.status,
                to_status=sm.OFFER_EXPIRED, actor_label="system",
                reason="Response deadline passed.")
            Application.objects.filter(pk=app.pk).update(
                status=sm.OFFER_EXPIRED)
            notifications.enqueue(
                topic="offer.expired", dedupe_key=f"offer.expired:{locked.pk}",
                recipient_user_id=locked.user_id,
                subject="An offer has expired",
                body="You did not respond before the deadline.",
                payload={"offer_id": locked.pk})
            n += 1
    return n


def _policy_for(season: str) -> PlacementPolicy:
    policy = PlacementPolicy.objects.filter(season=season).first()
    if policy is None:
        raise ConflictError(
            f"No placement policy is configured for {season}.",
            code="policy_missing")
    return policy


def _move(app: Application, to_status: str, actor, *, reason: str) -> None:
    """The application-side transition, via the same state machine everything
    else obeys."""
    from modules.placement.services.applications import resolve_or_raise

    actor_kind = _actor_kind(actor, app)
    resolve_or_raise(app.status, to_status, actor_kind)
    frm, app.status = app.status, to_status
    app.save(update_fields=["status", "updated_at"])
    ApplicationTransition.objects.create(
        application=app, from_status=frm, to_status=to_status,
        actor_user_id=getattr(actor, "user_id", None),
        actor_recruiter_id=getattr(actor, "account_id", None)
        if actor_kind == sm.RECRUITER else None,
        actor_label=actor_kind, reason=reason)


def _actor_kind(actor, application=None) -> str:
    """One definition of the actor lane, including the self-approval guard."""
    from modules.placement.services.applications import actor_kind
    return actor_kind(actor, application)
