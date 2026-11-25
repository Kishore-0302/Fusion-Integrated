"""Notification decisions and delivery (PC-UC-007, PC-BR-021, PC-AFR-050..056).

Every notification is written to the outbox in the same transaction as the
event that caused it, so an offer and its email commit together and a broken
mail server can never fail a student's application. `dedupe_key` makes
redelivery idempotent.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import timedelta

from django.conf import settings
from django.core.mail import send_mail
from django.db import IntegrityError, transaction
from django.utils import timezone

from modules.directory import contracts as directory
from modules.placement.models import NotificationOutbox

log = logging.getLogger("fusion.placement.notify")

# Anything not listed is a programming error (PC-BR-021).
TOPICS = {
    "posting.published", "application.submitted", "application.shortlisted",
    "application.rejected", "interview.scheduled", "interview.rescheduled",
    "offer.issued", "offer.expiring", "offer.expired",
    "announcement.published", "recruiter.invited", "company.approved",
    "company.rejected", "conduct.sanctioned", "registration.confirmed",
    "record.not_joining",
}


def enqueue(*, topic: str, dedupe_key: str, subject: str, body: str,
            recipient_user_id: int | None = None, recipient_email: str = "",
            payload: dict | None = None) -> NotificationOutbox | None:
    """Queue one notification, inside the caller's transaction. None if it was
    already queued."""
    if topic not in TOPICS:
        raise ValueError(f"Unknown notification topic {topic!r}.")
    if recipient_user_id is None and not recipient_email:
        raise ValueError("A notification needs a recipient.")

    try:
        # Nested, so a duplicate key cannot poison the caller's transaction.
        with transaction.atomic():
            return NotificationOutbox.objects.create(
                topic=topic, dedupe_key=dedupe_key, subject=subject, body=body,
                recipient_user_id=recipient_user_id,
                recipient_email=recipient_email, payload=payload or {},
            )
    except IntegrityError:
        log.debug("placement.notify.duplicate key=%s", dedupe_key)
        return None


def enqueue_many(rows: list[dict]) -> int:
    """Fan-out, one at a time so a single duplicate does not drop the batch."""
    return sum(1 for r in rows if enqueue(**r) is not None)


# -- Delivery: outside the request cycle, audiences expanded at send time -------
BROADCAST_SENTINEL = "placement-broadcast@invalid"


@dataclass
class DeliveryReport:
    expanded: int = 0
    sent: int = 0
    failed: int = 0
    skipped_capped: int = 0
    deferred: int = 0

    def __str__(self) -> str:
        return (f"expanded={self.expanded} sent={self.sent} failed={self.failed} "
                f"capped={self.skipped_capped} deferred={self.deferred}")


def _backoff_ready(row: NotificationOutbox, now) -> bool:
    """1, 2, 4, 8… minutes, so a dead address stops drowning the log."""
    if row.attempts == 0:
        return True
    wait = timedelta(minutes=2 ** (row.attempts - 1))
    return (now - row.updated_at) >= wait


def _sent_today(recipient_user_id: int | None, now) -> int:
    if recipient_user_id is None:
        return 0
    since = now - timedelta(hours=24)
    return NotificationOutbox.objects.filter(
        recipient_user_id=recipient_user_id, status="sent",
        sent_at__gte=since).count()


#: A row unresolved this long is assumed orphaned and returned to the queue.
CLAIM_TIMEOUT = timedelta(minutes=10)


def _reclaim_stranded(now) -> int:
    """Return rows whose worker died mid-send back to pending."""
    return (NotificationOutbox.objects
            .filter(status="sending", claimed_at__lt=now - CLAIM_TIMEOUT)
            .update(status="pending", claimed_at=None))


def _claim(row) -> bool:
    """Take exclusive ownership of a row, or report that someone else has it.

    A single conditional UPDATE: the database decides the winner, so of two
    workers holding the same `pending` row exactly one proceeds to send. Doing
    this after send_mail — which is where the mark used to be — meant both
    would deliver and the recipient got the notification twice.
    """
    return NotificationOutbox.objects.filter(
        pk=row.pk, status="pending",
    ).update(status="sending", claimed_at=timezone.now()) == 1


def deliver_pending(*, limit: int | None = None, now=None) -> DeliveryReport:
    """Drain the outbox. Safe to run concurrently and safe to re-run."""
    now = now or timezone.now()
    _reclaim_stranded(now)
    limit = limit or getattr(settings, "NOTIFY_MAX_PER_RUN", 500)
    max_attempts = getattr(settings, "NOTIFY_MAX_ATTEMPTS", 5)
    daily_cap = getattr(settings, "NOTIFY_DAILY_CAP_PER_RECIPIENT", 20)
    report = DeliveryReport()

    pending = list(NotificationOutbox.objects
                   .filter(status="pending")
                   .order_by("created_at")[:limit])

    # Broadcasts first, so the same pass can send what they expand into.
    for row in [r for r in pending if r.recipient_email == BROADCAST_SENTINEL]:
        report.expanded += _expand_broadcast(row)

    queue = list(NotificationOutbox.objects
                 .filter(status="pending")
                 .exclude(recipient_email=BROADCAST_SENTINEL)
                 .order_by("created_at")[:limit])

    addresses = _resolve_addresses(queue)

    for row in queue:
        if not _backoff_ready(row, now):
            report.deferred += 1
            continue

        to = row.recipient_email or addresses.get(row.recipient_user_id or -1, "")
        if not to:
            _fail(row, "No email address on record for this recipient.",
                  max_attempts)
            report.failed += 1
            continue

        if _sent_today(row.recipient_user_id, now) >= daily_cap:
            # Suppressed, not failed: the decision was right, the volume is not.
            row.status = "suppressed"
            row.last_error = f"Daily cap of {daily_cap} reached."
            row.save(update_fields=["status", "last_error", "updated_at"])
            report.skipped_capped += 1
            continue

        # Claim before sending, never after.
        if not _claim(row):
            report.deferred += 1
            continue

        try:
            send_mail(
                subject=row.subject, message=row.body,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[to], fail_silently=False,
            )
        except Exception as exc:                               # noqa: BLE001
            _fail(row, f"{exc.__class__.__name__}: {exc}"[:300], max_attempts)
            report.failed += 1
            continue

        row.status = "sent"
        row.sent_at = timezone.now()
        row.attempts += 1
        row.last_error = ""
        row.claimed_at = None
        row.save(update_fields=["status", "sent_at", "attempts", "last_error",
                                "claimed_at", "updated_at"])
        report.sent += 1

    left = NotificationOutbox.objects.filter(status="pending").count()
    if left:
        # Never let "sent 500" read as "drained the queue".
        log.info("placement.notify.backlog remaining=%d", left)
    return report


def _fail(row: NotificationOutbox, error: str, max_attempts: int) -> None:
    row.attempts += 1
    row.last_error = error
    if row.attempts >= max_attempts:
        row.status = "failed"
        log.warning("placement.notify.giving_up id=%s topic=%s err=%s",
                    row.pk, row.topic, error)
    else:
        # Back to the queue explicitly, or it sits in "sending" until the sweep.
        row.status = "pending"
    row.claimed_at = None
    row.save(update_fields=["attempts", "last_error", "status", "claimed_at",
                            "updated_at"])


def _resolve_addresses(rows: list[NotificationOutbox]) -> dict[int, str]:
    """One batched directory call for the whole run."""
    ids = {r.recipient_user_id for r in rows
           if r.recipient_user_id and not r.recipient_email}
    if not ids:
        return {}
    try:
        people = directory.get_users(sorted(ids))
    except Exception as exc:                                   # noqa: BLE001
        log.warning("placement.notify.directory_unavailable err=%s", exc)
        return {}
    return {uid: p.email for uid, p in people.items() if p.email}


def _expand_broadcast(row: NotificationOutbox) -> int:
    """One broadcast decision into per-recipient rows.

    Resolved at send time so a student who registers after the announcement
    still receives it, and publishing stays one fast transaction.
    """
    audience = (row.payload or {}).get("audience", "students")
    season = (row.payload or {}).get("placement_year", "")

    user_ids = _audience_ids(audience, season)
    made = 0
    for uid in user_ids:
        if enqueue(
            topic=row.topic,
            dedupe_key=f"{row.dedupe_key}:u{uid}",
            recipient_user_id=uid,
            subject=row.subject, body=row.body,
            payload={**(row.payload or {}), "broadcast": False},
        ) is not None:
            made += 1

    row.status = "sent"
    row.sent_at = timezone.now()
    row.last_error = f"Expanded to {made} recipient(s)."
    row.save(update_fields=["status", "sent_at", "last_error", "updated_at"])
    log.info("placement.notify.expanded topic=%s recipients=%d", row.topic, made)
    return made


def _audience_ids(audience: str, season: str) -> list[int]:
    """Who a broadcast reaches — only people already known to this module.

    There is deliberately no "email every student in the institute" path.
    """
    from modules.placement.models import PlacementRegistration

    if audience in ("registered", "students", "all"):
        # Registering for the season is the opt-in; there is no weaker one now.
        qs = PlacementRegistration.objects.filter(status="registered")
        if season:
            qs = qs.filter(policy__season=season)
        return sorted(qs.values_list("user_id", flat=True))
    return []
