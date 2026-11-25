"""Company registration and authorization.

Spec refs: PC-UC-014, PC-BR-007, PC-AFR-044, PC-AFR-045, PC-AFR-046.
"""
from __future__ import annotations

from django.db import IntegrityError, OperationalError, transaction
from django.utils import timezone
from django.utils.text import slugify

from core.api.exceptions import ConflictError, NotFoundError
from modules.placement.models import Company, CompanyContact, RecruiterSession
from modules.placement.services import notifications
from modules.placement.services.authz import require

P_MANAGE = "placement_cell.company.manage"
SLUG_ATTEMPTS = 5


def _unique_slug(name: str) -> str:
    base = slugify(name)[:70] or "company"
    slug, n = base, 1
    while Company.objects.filter(slug=slug).exists():
        n += 1
        slug = f"{base}-{n}"[:80]
    return slug


def _is_slug_clash(exc: Exception) -> bool:
    diag = getattr(getattr(exc, "__cause__", None), "diag", None)
    if getattr(diag, "constraint_name", None) == f"{Company._meta.db_table}_slug_key":
        return True
    msg = str(exc).lower()
    return "placement_company.slug" in msg or ("slug" in msg and "unique" in msg) or "locked" in msg


def _create_with_unique_slug(**fields) -> Company:
    # Two registrations of one name can both see a slug as free; the unique index picks the winner.
    for _ in range(SLUG_ATTEMPTS):
        try:
            with transaction.atomic():
                return Company.objects.create(slug=_unique_slug(fields["name"]), **fields)
        except (IntegrityError, OperationalError) as exc:
            if not _is_slug_clash(exc):
                raise
    raise ConflictError(
        "Several companies with this name are being registered right now. Submit it again.",
        code="company_slug_contention")


@transaction.atomic
def register(*, name: str, sector: str = "", website: str = "",
             hq_city: str = "", contact: dict | None = None,
             registered_by_user_id: int | None = None, actor=None) -> Company:
    """Record a registration request. It grants nothing until approved, but
    is still gated — otherwise any student can fill the table."""
    if actor is not None:
        require(actor, P_MANAGE)
    name = (name or "").strip()
    if not name:
        raise ConflictError("A company name is required.", code="name_required")

    company = _create_with_unique_slug(
        name=name, sector=sector, website=website,
        hq_city=hq_city, approval_status="pending", status="prospect",
        registered_by_user_id=registered_by_user_id,
    )
    if contact:
        CompanyContact.objects.create(
            company=company, name=contact.get("name", ""),
            designation=contact.get("designation", ""),
            email=contact.get("email", ""), phone=contact.get("phone", ""),
            is_primary=True)
    return company


@transaction.atomic
def approve(*, company_id: int, actor, note: str = "") -> Company:
    company = Company.objects.select_for_update().filter(pk=company_id).first()
    if company is None:
        raise NotFoundError("No such company.")
    if company.approval_status == "approved":
        return company

    company.approval_status = "approved"
    company.status = "active"
    company.approval_note = note
    company.approved_by_user_id = actor.user_id
    company.approved_at = timezone.now()
    company.save(update_fields=["approval_status", "status", "approval_note",
                                "approved_by_user_id", "approved_at",
                                "updated_at"])

    primary = company.contacts.filter(is_primary=True).first()
    if primary:
        notifications.enqueue(
            topic="company.approved", dedupe_key=f"company.approved:{company.pk}",
            recipient_email=primary.email,
            subject=f"{company.name} is approved for campus recruitment",
            body="Your registration has been approved.",
            payload={"company_id": company.pk})
    return company


@transaction.atomic
def reject(*, company_id: int, actor, note: str) -> Company:
    if not (note or "").strip():
        raise ConflictError("A reason is required to reject a registration.",
                            code="reason_required")
    company = Company.objects.select_for_update().filter(pk=company_id).first()
    if company is None:
        raise NotFoundError("No such company.")

    company.approval_status = "rejected"
    company.approval_note = note
    company.save(update_fields=["approval_status", "approval_note", "updated_at"])
    _cut_off_sessions(company)
    return company


@transaction.atomic
def blacklist(*, company_id: int, actor, note: str) -> Company:
    """Stops a previously-approved company mid-season."""
    company = Company.objects.select_for_update().filter(pk=company_id).first()
    if company is None:
        raise NotFoundError("No such company.")
    company.status = "blacklisted"
    company.approval_note = note
    company.save(update_fields=["status", "approval_note", "updated_at"])
    _cut_off_sessions(company)
    return company


def _cut_off_sessions(company: Company) -> int:
    """Withdrawing authorization must take effect now, not when the recruiter's
    eight-hour session happens to end.

    Note the authentication class ALSO re-checks `can_operate` per request, so
    this is belt and braces — revoking here just avoids leaving live rows
    around that would otherwise be honoured if that check were ever relaxed.
    """
    return (RecruiterSession.objects
            .filter(account__company=company, revoked_at__isnull=True)
            .update(revoked_at=timezone.now()))
