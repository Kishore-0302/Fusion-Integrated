"""Post-offer obligations: the signed offer letter and non-joining (rules 22, 24).

Rule 24 makes this module the gate on a no-dues certificate, which is the one
place placement can block a student's graduation paperwork. So the answer names
the company still owing a letter rather than returning a bare "blocked", and
`contracts.get_no_dues_clearances` exposes it to the rest of the platform
without anyone reaching into these tables.
"""
from __future__ import annotations

import logging

from django.db import transaction
from django.utils import timezone

from core.api.exceptions import ConflictError, NotFoundError
from modules.placement.domain import clearance as rules
from modules.placement.models import (
    Company,
    PlacementPolicy,
    PlacementRecord,
    ProfileDocument,
)
from modules.placement.services import notifications
from modules.placement.services.authz import require

log = logging.getLogger("fusion.placement.clearance")

P_MANAGE = "placement_cell.record.manage"
_UNSET = object()


def _states(records) -> tuple[rules.RecordState, ...]:
    return tuple(
        rules.RecordState(
            company=r.company.name,
            has_signed_offer_letter=r.offer_letter_id is not None,
            declared_not_joining=r.not_joining_declared_at is not None,
        ) for r in records)


def no_dues_clearance(*, user_id: int) -> rules.Clearance:
    """Rule 24, for one student. Read-only."""
    records = (PlacementRecord.objects
               .filter(user_id=user_id, is_active=True)
               .select_related("company"))
    return rules.no_dues_clearance(_states(records))


def no_dues_clearances(user_ids) -> dict[int, rules.Clearance]:
    """Batched, for the contract. One query however many students are asked
    about — the academic office checks a whole graduating batch."""
    ids = {int(i) for i in user_ids if i is not None}
    if not ids:
        return {}
    by_user: dict[int, list] = {uid: [] for uid in ids}
    for record in (PlacementRecord.objects
                   .filter(user_id__in=ids, is_active=True)
                   .select_related("company")):
        by_user[record.user_id].append(record)
    return {uid: rules.no_dues_clearance(_states(rows))
            for uid, rows in by_user.items()}


@transaction.atomic
def submit_offer_letter(*, record_id: int, document_id: int,
                        user_id: int) -> PlacementRecord:
    """Attach the signed copy (rule 24).

    Scoped to the caller's own record and their own document, so neither id can
    be used to reach someone else's.
    """
    record = PlacementRecord.objects.select_for_update().filter(
        pk=record_id, user_id=user_id, is_active=True).first()
    if record is None:
        raise NotFoundError("No such placement record.")

    document = ProfileDocument.objects.filter(
        pk=document_id, user_id=user_id, is_active=True).first()
    if document is None:
        raise NotFoundError("No such document.")
    if document.kind != "offer_letter":
        raise ConflictError(
            "Attach the document you uploaded as an offer letter.",
            code="wrong_document_kind")

    record.offer_letter = document
    record.offer_letter_submitted_at = timezone.now()
    record.save(update_fields=["offer_letter", "offer_letter_submitted_at",
                               "updated_at"])
    log.info("placement.clearance.letter_submitted user=%s record=%s",
             user_id, record_id)
    return record


@transaction.atomic
def declare_not_joining(*, record_id: int, user_id: int, reason: str
                        ) -> tuple[PlacementRecord, rules.NonJoiningVerdict]:
    """Rule 22 — the student says they will not join.

    Always accepted, late or not. Refusing a late declaration would leave the
    Placement Cell less informed, which is the opposite of the rule's purpose;
    lateness is recorded because that is what rule 22 attaches consequences to.
    """
    if not (reason or "").strip():
        raise ConflictError(
            "Rule 22 asks for the reason — higher studies, or another genuine "
            "ground.", code="reason_required")

    record = PlacementRecord.objects.select_for_update().filter(
        pk=record_id, user_id=user_id, is_active=True).select_related(
        "policy", "company").first()
    if record is None:
        raise NotFoundError("No such placement record.")
    if record.not_joining_declared_at is not None:
        raise ConflictError("You have already told the Placement Cell.",
                            code="already_declared")

    verdict = rules.assess_non_joining(
        declared_on=timezone.localdate(),
        deadline=record.policy.notify_non_joining_by)

    record.not_joining_declared_at = timezone.now()
    record.not_joining_reason = reason.strip()[:300]
    record.not_joining_was_late = verdict.is_late
    record.save(update_fields=["not_joining_declared_at", "not_joining_reason",
                               "not_joining_was_late", "updated_at"])

    notifications.enqueue(
        topic="record.not_joining",
        dedupe_key=f"record.not_joining:{record.pk}",
        recipient_email="placement-broadcast@invalid",
        subject=f"Not joining {record.company.name}",
        body=(f"A student has declared they will not join "
              f"{record.company.name}. {verdict.message}"),
        payload={"record_id": record.pk, "late": verdict.is_late,
                 "broadcast": True})

    log.info("placement.clearance.not_joining user=%s record=%s late=%s",
             user_id, record_id, verdict.is_late)
    return record, verdict


@transaction.atomic
def record_off_campus(*, season: str, user_id: int, company_id: int,
                      ctc_lpa=None, kind: str = "fte", actor
                      ) -> PlacementRecord:
    """Rules 5 and 24 — an off-campus placement the Cell was told about.

    Rule 24 covers "placed (on/off campus)", so without this the no-dues gate
    would miss the students least likely to have submitted anything.
    """
    require(actor, P_MANAGE)
    policy = PlacementPolicy.objects.filter(season=season).first()
    if policy is None:
        raise ConflictError(f"No placement policy for {season}.",
                            code="policy_missing")
    company = Company.objects.filter(pk=company_id).first()
    if company is None:
        raise NotFoundError("No such company.")

    if PlacementRecord.objects.filter(policy=policy, user_id=user_id,
                                      is_active=True).exists():
        raise ConflictError(
            "This student already has an active placement for the season.",
            code="already_placed")

    record = PlacementRecord.objects.create(
        policy=policy, user_id=user_id, company=company, source="off_campus",
        offer=None, posting=None, ctc_lpa=ctc_lpa, kind=kind,
        is_active=True, recorded_by_user_id=actor.user_id)
    log.info("placement.clearance.off_campus user=%s company=%s by=%s",
             user_id, company_id, actor.user_id)
    return record


@transaction.atomic
def update_placement_record(*, record_id: int, actor, reason: str,
                            company_id: int | None = None,
                            ctc_lpa: object = _UNSET, kind: str | None = None,
                            is_active: bool | None = None) -> PlacementRecord:
    """Correct a recorded placement or deactivate a mistaken record.

    The correction reason is required by the API and included in the audit log.
    Company is editable only for off-campus records; a campus record's company
    comes from its accepted offer and cannot be changed independently.
    """
    require(actor, P_MANAGE)
    record = (PlacementRecord.objects.select_for_update()
              .select_related("policy", "company", "posting")
              .filter(pk=record_id).first())
    if record is None:
        raise NotFoundError("No such placement record.")

    before = {
        "company_id": record.company_id,
        "ctc_lpa": str(record.ctc_lpa) if record.ctc_lpa is not None else None,
        "kind": record.kind,
        "is_active": record.is_active,
    }

    if company_id is not None:
        if record.source != "off_campus":
            raise ConflictError(
                "The company for a campus placement comes from its accepted offer.",
                code="company_from_offer")
        company = Company.objects.filter(pk=company_id).first()
        if company is None:
            raise NotFoundError("No such company.")
        record.company = company

    if ctc_lpa is not _UNSET:
        record.ctc_lpa = ctc_lpa
    if kind is not None:
        record.kind = kind.strip()
    if is_active is not None:
        if is_active and not record.is_active and PlacementRecord.objects.filter(
                policy=record.policy, user_id=record.user_id,
                is_active=True).exclude(pk=record.pk).exists():
            raise ConflictError(
                "This student already has another active placement for the season.",
                code="already_placed")
        record.is_active = is_active

    record.save(update_fields=["company", "ctc_lpa", "kind", "is_active",
                               "updated_at"])
    after = {
        "company_id": record.company_id,
        "ctc_lpa": str(record.ctc_lpa) if record.ctc_lpa is not None else None,
        "kind": record.kind,
        "is_active": record.is_active,
    }
    log.info("placement.record.corrected record=%s user=%s by=%s reason=%s "
             "before=%s after=%s", record.pk, record.user_id, actor.user_id,
             reason.strip()[:300], before, after)
    return record


def outstanding(*, season: str | None = None) -> list[PlacementRecord]:
    """Placed students who still owe a signed letter. The office's worklist."""
    rows = (PlacementRecord.objects
            .filter(is_active=True, offer_letter__isnull=True)
            .select_related("company", "policy"))
    if season:
        rows = rows.filter(policy__season=season)
    return list(rows.order_by("policy__season", "company__name"))
