"""Scheduled work.

Ids only in arguments, never ORM objects. Everything is idempotent, because
`acks_late` means a task can run twice if a worker dies mid-flight.
"""
from __future__ import annotations

import logging

from celery import shared_task

log = logging.getLogger("fusion.placement.tasks")


@shared_task(
    name="placement.deliver_notifications",
    acks_late=True, reject_on_worker_lost=True,
    soft_time_limit=270, time_limit=300,
)
def deliver_notifications(limit: int | None = None) -> str:
    """Drain the notification outbox (PC-BR-021).

    No autoretry — the rows carry their own attempts and backoff, so a failed
    pass is picked up by the next beat rather than re-sending the batch.
    """
    from modules.placement.services import notifications

    report = notifications.deliver_pending(limit=limit)
    log.info("placement.notify.run %s", report)
    return str(report)


@shared_task(
    name="placement.expire_overdue_offers",
    acks_late=True, reject_on_worker_lost=True,
    soft_time_limit=270, time_limit=300,
)
def expire_overdue_offers() -> int:
    """Close offers past their deadline (PC-BR-013), or a student who never
    answers stays blocked from the pool forever."""
    from modules.placement.services import offers

    n = offers.expire_overdue()
    if n:
        log.info("placement.offers.expired count=%d", n)
    return n


@shared_task(name="placement.rebuild_stats", acks_late=True)
def rebuild_stats(season: str) -> int:
    """Recompute the materialised statistics for one season."""
    from modules.placement.services import stats

    return stats.rebuild(season=season)


@shared_task(name="placement.rebuild_active_stats", acks_late=True)
def rebuild_active_stats() -> int:
    """Rebuild every active season. The beat entry point.

    A static schedule cannot name a season, and hard-coding one would silently
    stop refreshing the day the season rolls over.
    """
    from modules.placement.models import PlacementPolicy

    seasons = list(PlacementPolicy.objects
                   .filter(is_active=True)
                   .values_list("season", flat=True))
    rows = sum(rebuild_stats(season=s) for s in seasons)
    log.info("placement.stats.rebuilt seasons=%d rows=%d", len(seasons), rows)
    return rows


@shared_task(name="placement.expire_pending_offers", acks_late=True)
def expire_pending_offers() -> int:
    """Expire offers that are past their deadline (PR 445 / PBI 17)."""
    from modules.placement.services import offers

    count = offers.expire_overdue()
    log.info("placement.offers.expired count=%d", count)
    return count

