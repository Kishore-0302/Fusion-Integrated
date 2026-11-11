"""Role scope, decided in one place (PC-UC-018).

Every list and detail view starts from a queryset built here. Ownership is
enforced by narrowing the queryset, never by fetching a row and then checking
it — so a row you may not see is a 404, not a 403. A 403 would confirm it
exists, which for placement data is itself a disclosure.

    PC-BR-009  a company sees only applications to its own postings
    PC-BR-010  the TPO sees everything in the module
    PC-BR-016  students get anonymised aggregates, not raw records
    PC-BR-019  alumni get a narrow read-only slice
    PC-BR-020  alumni are excluded from active workflow objects
    PC-BR-023  sensitive data is restricted to authorised readers
"""
from __future__ import annotations

from django.db.models import QuerySet

from modules.placement.models import (
    Announcement,
    Application,
    Company,
    InterviewRound,
    JobPosting,
    Offer,
    PlacementRecord,
)

# Permission codes. Held by TPO / placement chairman via the IAM.
P_VIEW_ALL = "placement_cell.application.view"
P_MANAGE_POSTINGS = "placement_cell.job_posting.manage"
P_VIEW_REPORTS = "placement_cell.report.view"

# Any of these makes someone staff; view_self is the student grant and absent.
STAFF_SCOPE_PERMISSIONS = (
    P_VIEW_ALL,
    "placement_cell.application.review",
    "placement_cell.job_posting.manage",
    "placement_cell.interview.schedule",
    "placement_cell.offer.issue",
    "placement_cell.offer.revoke",
    "placement_cell.company.manage",
    "placement_cell.report.view",
    "placement_cell.announcement.publish",
    "placement_cell.academic_directory.view",
)

ALUMNI_ROLE = "alumni"


def _is_recruiter(actor) -> bool:
    return getattr(actor, "kind", None) == "recruiter"


def _own_id(actor) -> int | None:
    """None means no identity to scope by, which resolves to an empty
    queryset. Deny is the only safe reading of "who is asking?" being
    unanswerable."""
    return getattr(actor, "user_id", None)


def _is_alumni(actor) -> bool:
    """Alumni are an IAM role, not a separate pool."""
    return ALUMNI_ROLE in {r.lower() for r in getattr(actor, "roles", ())}


def _has(actor, *codes: str) -> bool:
    check = getattr(actor, "has_permission", None)
    return bool(check) and any(check(c) for c in codes)


def is_staff(actor) -> bool:
    """Sees the whole module. Never a recruiter or alumnus, whatever
    permissions they might somehow carry."""
    return (not _is_recruiter(actor)
            and not _is_alumni(actor)
            and _has(actor, *STAFF_SCOPE_PERMISSIONS))


_sees_everything = is_staff


# -- Postings ------------------------------------------------------------------
def postings_for(actor) -> QuerySet[JobPosting]:
    base = JobPosting.objects.select_related("company")

    if _is_recruiter(actor):
        # Their own company's postings in every state, including drafts.
        return base.filter(company_id=actor.company_id)

    if _sees_everything(actor):
        return base

    if _is_alumni(actor):
        return base.filter(status="published")

    # A draft's CTC and bar are commercially sensitive before publication.
    return base.filter(status__in=("published", "closed", "in_progress",
                                   "completed"))


# -- Applications — the most sensitive collection in the module ----------------
def applications_for(actor) -> QuerySet[Application]:
    base = Application.objects.select_related("posting", "posting__company")

    if _is_recruiter(actor):
        # PC-BR-009: filtered on the posting's company, drafts excluded.
        return (base.filter(posting__company_id=actor.company_id)
                .exclude(status="draft"))

    if _is_alumni(actor):
        return base.none()                        # PC-BR-020
    if _sees_everything(actor):
        return base
    own = _own_id(actor)
    return base.filter(user_id=own) if own is not None else base.none()


def offers_for(actor) -> QuerySet[Offer]:
    base = Offer.objects.select_related("posting", "posting__company",
                                        "application")
    if _is_recruiter(actor):
        return base.filter(posting__company_id=actor.company_id)
    if _is_alumni(actor):
        return base.none()
    if _sees_everything(actor):
        return base
    own = _own_id(actor)
    return base.filter(user_id=own) if own is not None else base.none()


def interview_rounds_for(actor) -> QuerySet[InterviewRound]:
    base = InterviewRound.objects.select_related("posting", "posting__company")
    if _is_recruiter(actor):
        return base.filter(posting__company_id=actor.company_id)
    if _is_alumni(actor):
        return base.none()
    if _sees_everything(actor):
        return base
    # Only rounds they are scheduled into; the full calendar leaks the shortlist.
    own = _own_id(actor)
    if own is None:
        return base.none()
    return base.filter(participants__application__user_id=own).distinct()


# -- Candidates ----------------------------------------------------------------
def may_read_candidate(actor, user_id: int) -> bool:
    """Whether this actor may open that person's candidate record.

    A predicate rather than a queryset: the record is assembled from the
    directory projection now, and placement holds no table to narrow.
    """
    if _is_alumni(actor):
        return False
    if _sees_everything(actor):
        return True
    if _is_recruiter(actor):
        # Only someone who has applied to them, and only while live.
        return (Application.objects
                .filter(posting__company_id=actor.company_id, user_id=user_id)
                .exclude(status__in=("draft", "withdrawn", "auto_withdrawn"))
                .exists())
    return _own_id(actor) == user_id


# -- Companies -----------------------------------------------------------------
def companies_for(actor) -> QuerySet[Company]:
    base = Company.objects.all()
    if _is_recruiter(actor):
        return base.filter(pk=actor.company_id)
    if _sees_everything(actor):
        return base
    # A pending or rejected registration is between the company and the office.
    return base.filter(approval_status="approved")


def placement_records_for(actor) -> QuerySet[PlacementRecord]:
    """PC-BR-016: students get aggregates from snapshots, never raw records."""
    base = PlacementRecord.objects.select_related("company", "posting", "policy")
    if _is_recruiter(actor):
        return base.filter(company_id=actor.company_id)
    if _is_alumni(actor):
        return base.none()
    if _sees_everything(actor):
        return base
    own = _own_id(actor)
    return base.filter(user_id=own) if own is not None else base.none()


# -- Announcements -------------------------------------------------------------
def announcements_for(actor) -> QuerySet[Announcement]:
    """History is kept (PC-BR-018), but a withdrawn notice is staff-only so
    nobody acts on a retracted one."""
    base = Announcement.objects.all()

    if _is_recruiter(actor):
        return base.none()                        # outsiders

    if _sees_everything(actor):
        return base

    visible = base.filter(is_withdrawn=False, published_at__isnull=False)
    if _is_alumni(actor):
        return visible.filter(audience__in=("alumni", "all"))
    return visible.filter(audience__in=("students", "registered", "all"))


# -- Scoped applications helper (PR 445 / PBI 17) ------------------------------

def scope_applications_queryset(
    qs: QuerySet[Application],
    user,
    user_roles: list[str] | set[str] | tuple[str, ...],
    company_id: int | None = None,
) -> QuerySet[Application]:
    """Scope applications queryset by user role and context."""
    roles = set(user_roles or [])
    if "tpo_admin" in roles or "placement_chairman" in roles or "staff" in roles:
        return qs.all()
    if "recruiter" in roles:
        if company_id is None:
            return qs.none()
        return qs.filter(posting__company_id=company_id)
    if "student" in roles:
        user_id = (
            getattr(user, "id", None)
            or getattr(user, "user_id", None)
            or (user if isinstance(user, int) else None)
        )
        if user_id is None:
            return qs.none()
        return qs.filter(user_id=user_id)
    if "alumni" in roles:
        return qs.none()
    return qs.none()

