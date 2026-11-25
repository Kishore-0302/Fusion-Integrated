"""Announcements (PC-UC-013, PC-UC-020, PC-UC-007, PC-AFR-040..043, PC-BR-017)."""
from __future__ import annotations

from django.db import transaction
from django.utils import timezone

from core.api.exceptions import ConflictError, NotFoundError
from modules.placement.models import Announcement
from modules.placement.services import notifications

P_PUBLISH = "placement_cell.announcement.publish"

VALID_TOPICS = {c for c, _ in Announcement.TOPIC}
VALID_AUDIENCES = {c for c, _ in Announcement.AUDIENCE}


@transaction.atomic
def publish(*, actor, title: str, body: str, topic: str = "general",
            audience: str = "students", placement_year: str = "") -> Announcement:
    """PC-UC-013 / PC-UC-020: validate publication authority and scope, then
    publish and notify via PC-UC-007."""
    if not actor.has_permission(P_PUBLISH):
        from core.api.exceptions import PermissionDeniedError
        raise PermissionDeniedError(f"This action needs {P_PUBLISH}.",
                                    code="permission_denied")
    if topic not in VALID_TOPICS:
        raise ConflictError(f"Topic must be one of {sorted(VALID_TOPICS)}.",
                            code="bad_topic")
    if audience not in VALID_AUDIENCES:
        raise ConflictError(f"Audience must be one of {sorted(VALID_AUDIENCES)}.",
                            code="bad_audience")
    if not (title or "").strip() or not (body or "").strip():
        raise ConflictError("An announcement needs a title and a body.",
                            code="content_required")

    announcement = Announcement.objects.create(
        title=title.strip(), body=body, topic=topic, audience=audience,
        placement_year=placement_year, published_at=timezone.now(),
        published_by_user_id=actor.user_id,
        published_by_role=actor.active_role or "",
    )
    notifications.enqueue(
        topic="announcement.published",
        dedupe_key=f"announcement.published:{announcement.pk}",
        recipient_email="placement-broadcast@invalid",
        subject=announcement.title,
        body=announcement.body[:500],
        payload={"announcement_id": announcement.pk, "audience": audience,
                 "broadcast": True})
    return announcement


@transaction.atomic
def withdraw(*, announcement_id: int, actor, reason: str) -> Announcement:
    """PC-AFR-043: history is maintained, so this flags rather than deletes."""
    if not (reason or "").strip():
        raise ConflictError("A reason is required to withdraw an announcement.",
                            code="reason_required")
    announcement = (Announcement.objects.select_for_update()
                    .filter(pk=announcement_id).first())
    if announcement is None:
        raise NotFoundError("No such announcement.")

    announcement.is_withdrawn = True
    announcement.withdrawn_at = timezone.now()
    announcement.withdrawn_reason = reason
    announcement.save(update_fields=["is_withdrawn", "withdrawn_at",
                                     "withdrawn_reason", "updated_at"])
    return announcement
