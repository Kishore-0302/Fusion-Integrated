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
def update_record(*, record_id: int, actor, **fields) -> PlacementRecord:
    """PC-BR-029: TPO may update placement records for Students and Alumni.

    Exceptions / Exclusions: Does not grant Alumni write access.
    """
    require(actor, P_MANAGE)
    record = PlacementRecord.objects.select_for_update().filter(pk=record_id).first()
    if record is None:
        raise NotFoundError("No such placement record.")

    allowed = {"ctc_lpa", "kind", "is_active"}
    touched = []
    for key, val in fields.items():
        if key in allowed:
            setattr(record, key, val)
            touched.append(key)
    if touched:
        record.save(update_fields=[*touched, "updated_at"])
    return record


def outstanding(*, season: str | None = None) -> list[PlacementRecord]:
    """Placed students who still owe a signed letter. The office's worklist."""
    rows = (PlacementRecord.objects
            .filter(is_active=True, offer_letter__isnull=True)
            .select_related("company", "policy"))
    if season:
        rows = rows.filter(policy__season=season)
    return list(rows.order_by("policy__season", "company__name"))


def placement_outcomes_view(*, actor, season: str | None = None) -> dict:
    """PC-AFR-030: TPO-scoped view for tracking placement outcomes and final placement status."""
    require(actor, P_MANAGE, "placement_cell.report.view")
    from modules.directory import contracts as directory

    qs = PlacementRecord.objects.select_related("company", "policy", "offer_letter")
    if season:
        qs = qs.filter(policy__season=season)
    records = list(qs.order_by("-created_at"))

    user_ids = [r.user_id for r in records]
    people = directory.get_users(user_ids)

    total = len(records)
    active = sum(1 for r in records if r.is_active)
    campus = sum(1 for r in records if r.source == "campus")
    off_campus = sum(1 for r in records if r.source == "off_campus")
    fte = sum(1 for r in records if r.kind == "fte")
    internship = sum(1 for r in records if r.kind == "internship")
    with_letter = sum(1 for r in records if r.offer_letter_id is not None)
    not_joining = sum(1 for r in records if r.not_joining_declared_at is not None)

    results = []
    for r in records:
        person = people.get(r.user_id)
        if not r.is_active:
            final_status = "inactive"
        elif r.not_joining_declared_at is not None:
            final_status = "not_joining"
        else:
            final_status = "placed"

        results.append({
            "record_id": r.pk,
            "user_id": r.user_id,
            "student_name": getattr(person, "display_name", "") or getattr(
                person, "name", "") or "",
            "username": getattr(person, "username", "") or "",
            "programme": getattr(person, "programme", "") or "",
            "discipline": getattr(person, "discipline", "") or "",
            "season": r.policy.season,
            "company_id": r.company_id,
            "company_name": r.company.name,
            "ctc_lpa": str(r.ctc_lpa) if r.ctc_lpa is not None else None,
            "source": r.source,
            "kind": r.kind,
            "is_active": r.is_active,
            "final_status": final_status,
            "has_offer_letter": r.offer_letter_id is not None,
            "offer_letter_submitted_at": (
                r.offer_letter_submitted_at.isoformat()
                if r.offer_letter_submitted_at else None
            ),
            "declared_not_joining": r.not_joining_declared_at is not None,
            "not_joining_declared_at": (
                r.not_joining_declared_at.isoformat()
                if r.not_joining_declared_at else None
            ),
            "not_joining_reason": r.not_joining_reason,
            "not_joining_was_late": r.not_joining_was_late,
        })

    return {
        "season": season or "all",
        "total_records": total,
        "active_placements": active,
        "on_campus_count": campus,
        "off_campus_count": off_campus,
        "fte_count": fte,
        "internship_count": internship,
        "with_offer_letter_count": with_letter,
        "not_joining_count": not_joining,
        "results": results,
    }
