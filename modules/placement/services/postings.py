"""Job postings (PC-UC-006, PC-UC-015, PC-WF-003, PC-BR-003/004/005/006)."""
from __future__ import annotations

from django.db import transaction
from django.utils import timezone

from core.api.exceptions import ConflictError, NotFoundError
from modules.placement.domain import eligibility as elig
from modules.placement.models import Company, JobPosting
from modules.placement.services import notifications
from modules.placement.services.authz import require

P_MANAGE = "placement_cell.job_posting.manage"

EDITABLE = ("title", "kind", "description", "location", "ctc_lpa", "stipend_pm",
            "bond_months", "seats", "opens_at", "closes_at", "eligibility_rule",
            # Rule 7: a Dream Slot opens the process to placed students too.
            "is_dream_slot", "dream_slot_note")


def validate_rule(rule: dict | None) -> None:
    """Reject, at authoring time, a rule that could not be evaluated as written.

    An unknown operator or a literal of the wrong type would otherwise publish
    a rule that denies every student. Catching it here makes a broken rule the
    author's problem, not a queue of confused students on deadline day.
    """
    problems = elig.validate(rule)
    if problems:
        first = problems[0]
        raise ConflictError(
            f"The eligibility rule is not valid: {first.reason} at {first.path}. "
            "Correct that condition and save the posting again.",
            code="invalid_eligibility_rule",
            details=[{"path": p.path, "field": p.field, "reason": p.reason}
                     for p in problems])


def _guard_published_edit(posting: JobPosting, fields: dict) -> None:
    """After publish the type never changes and the deadline only moves later."""
    if "kind" in fields and fields["kind"] != posting.kind:
        raise ConflictError(
            "A published posting's type cannot change. Create a new posting "
            "for the other type instead.",
            code="posting_kind_locked")
    if "closes_at" in fields:
        new = fields["closes_at"]
        if new is None or (posting.closes_at is not None and new < posting.closes_at):
            raise ConflictError(
                "A published posting's deadline can only be extended. Choose a "
                "time on or after the current one.",
                code="deadline_cannot_shorten")


@transaction.atomic
def create(*, company_id: int, placement_year: str, actor, **fields) -> JobPosting:
    require(actor, P_MANAGE, allow_recruiter=True)
    company = Company.objects.filter(pk=company_id).first()
    if company is None:
        raise NotFoundError("No such company.")
    if not company.can_operate:
        # PC-BR-006: a company may publish only where authorized.
        raise ConflictError("This company is not approved for recruitment yet.",
                            code="company_not_approved")

    data = {k: v for k, v in fields.items() if k in EDITABLE}
    validate_rule(data.get("eligibility_rule"))

    is_recruiter = getattr(actor, "kind", None) == "recruiter"
    return JobPosting.objects.create(
        company=company, placement_year=placement_year, status="draft",
        created_by_user_id=None if is_recruiter else actor.user_id,
        created_by_recruiter_id=actor.account_id if is_recruiter else None,
        **data)


@transaction.atomic
def update(*, posting_id: int, actor, scope=None, **fields) -> JobPosting:
    # `scope` proves the posting is readable, which every student's is.
    require(actor, P_MANAGE, allow_recruiter=True)
    qs = scope if scope is not None else JobPosting.objects.all()
    posting = qs.select_for_update().filter(pk=posting_id).first()
    if posting is None:
        raise NotFoundError("No such posting.")

    if posting.eligibility_rule_locked_at and "eligibility_rule" in fields:
        # PC-BR-002: criteria cannot move under people who already applied.
        raise ConflictError(
            "Eligibility criteria are frozen once the posting is published.",
            code="eligibility_rule_locked")

    if "eligibility_rule" in fields:
        validate_rule(fields["eligibility_rule"])
    if posting.published_at is not None:
        _guard_published_edit(posting, fields)

    touched = []
    for key, value in fields.items():
        if key in EDITABLE:
            setattr(posting, key, value)
            touched.append(key)
    if touched:
        posting.save(update_fields=[*touched, "updated_at"])
    return posting


@transaction.atomic
def publish(*, posting_id: int, actor, scope=None) -> JobPosting:
    """Make a posting visible and freeze its criteria (PC-BR-003)."""
    require(actor, P_MANAGE, allow_recruiter=True)
    qs = scope if scope is not None else JobPosting.objects.all()
    posting = (qs.select_for_update().select_related("company")
               .filter(pk=posting_id).first())
    if posting is None:
        raise NotFoundError("No such posting.")
    if posting.status == "published":
        return posting
    if posting.status not in ("draft", "pending_approval"):
        raise ConflictError(f"A {posting.status} posting cannot be published.",
                            code="not_publishable")
    if not posting.company.can_operate:
        raise ConflictError("This company is not approved for recruitment yet.",
                            code="company_not_approved")

    # PC-BR-003, also a CHECK constraint, so a direct UPDATE cannot bypass it.
    missing = []
    if not (posting.description or "").strip():
        missing.append("description")
    if posting.closes_at is None:
        missing.append("closes_at")
    if not posting.eligibility_rule:
        missing.append("eligibility_rule")
    if missing:
        raise ConflictError(
            "A posting needs a role description, eligibility criteria and an "
            "application deadline before it can be published.",
            code="incomplete_posting",
            details=[{"field": f} for f in missing])
    if posting.closes_at <= timezone.now():
        raise ConflictError("The application deadline is already past.",
                            code="deadline_in_past")
    # A rule stored before authoring checks existed must not go live either.
    validate_rule(posting.eligibility_rule)

    posting.status = "published"
    posting.published_at = timezone.now()
    posting.eligibility_rule_locked_at = timezone.now()
    posting.save(update_fields=["status", "published_at",
                                "eligibility_rule_locked_at", "updated_at"])

    notifications.enqueue(
        topic="posting.published", dedupe_key=f"posting.published:{posting.pk}",
        recipient_email="placement-broadcast@invalid",
        subject=f"New opportunity: {posting.title} at {posting.company.name}",
        body=f"Applications close {posting.closes_at:%d %b %Y %H:%M}.",
        payload={"posting_id": posting.pk, "broadcast": True})
    return posting


@transaction.atomic
def close(*, posting_id: int, actor, scope=None) -> JobPosting:
    require(actor, P_MANAGE, allow_recruiter=True)
    qs = scope if scope is not None else JobPosting.objects.all()
    posting = qs.select_for_update().filter(pk=posting_id).first()
    if posting is None:
        raise NotFoundError("No such posting.")
    posting.status = "closed"
    posting.save(update_fields=["status", "updated_at"])
    return posting
