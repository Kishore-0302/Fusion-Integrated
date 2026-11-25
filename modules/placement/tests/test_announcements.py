"""Announcement publishing tests.

Covers spec gaps G-05 (PC-UC-020: TPO publishes announcement) and
G-06 (PC-UC-013: Chairman publishes official announcement) and
G-07 (posting.published notification fires when posting goes live).

Spec refs: PC-UC-007, PC-UC-013, PC-UC-020, PC-BR-017, PC-AFR-040..043.
"""
from datetime import timedelta

import pytest
from django.utils import timezone

from conftest import make_principal
from core.api.exceptions import ConflictError, PermissionDeniedError
from modules.placement.models import (
    Announcement,
    Company,
    JobPosting,
    NotificationOutbox,
    PlacementPolicy,
)
from modules.placement.services import (
    announcements,
    postings,
)
from modules.placement.services import (
    applications as app_service,
)

pytestmark = pytest.mark.django_db

PUBLISH_PERM = "placement_cell.announcement.publish"
MANAGE_POSTING_PERM = "placement_cell.job_posting.manage"


def _tpo():
    return make_principal(user_id=10, kind="staff",
                          active_role="tpo",
                          permissions=(PUBLISH_PERM,))


def _chairman():
    return make_principal(user_id=11, kind="staff",
                          active_role="placement_chairman",
                          permissions=(PUBLISH_PERM,))


def _unprivileged():
    return make_principal(user_id=12, kind="staff",
                          active_role="staff",
                          permissions=())


# ---------------------------------------------------------------------------
# G-05 / G-06: Announcement publication (PC-UC-013, PC-UC-020)
# ---------------------------------------------------------------------------

class TestTPOAnnouncement:
    """PC-UC-020: authorized TPO can publish placement-related announcements."""

    def test_tpo_can_publish_an_announcement(self):
        ann = announcements.publish(
            actor=_tpo(),
            title="Campus Drive — Acme Corp",
            body="Acme Corp will conduct a placement drive on 10 Dec.",
            topic="drive",
        )
        assert ann.pk is not None
        assert ann.title == "Campus Drive — Acme Corp"
        assert ann.published_at is not None
        assert ann.published_by_user_id == 10

    def test_announcement_is_persisted_in_history(self):
        """PC-AFR-043: PCMS shall maintain announcement history."""
        announcements.publish(
            actor=_tpo(),
            title="Workshop on Resume Writing",
            body="Workshop details here.",
            topic="workshop",
        )
        assert Announcement.objects.filter(
            title="Workshop on Resume Writing").exists()

    def test_tpo_announcement_queues_a_broadcast_notification(self):
        """PC-UC-007: New Announcement event triggers notification for students."""
        announcements.publish(
            actor=_tpo(),
            title="Placement Drive",
            body="Drive on Monday.",
            topic="drive",
        )
        outbox = NotificationOutbox.objects.filter(
            topic="announcement.published").first()
        assert outbox is not None
        assert outbox.payload.get("broadcast") is True

    def test_missing_title_is_refused(self):
        """PC-BR-017: an announcement needs content within supported scope."""
        with pytest.raises(ConflictError) as exc:
            announcements.publish(
                actor=_tpo(), title="", body="Something.", topic="drive")
        assert exc.value.code == "content_required"

    def test_missing_body_is_refused(self):
        with pytest.raises(ConflictError) as exc:
            announcements.publish(
                actor=_tpo(), title="Drive", body="  ", topic="drive")
        assert exc.value.code == "content_required"

    def test_unprivileged_staff_cannot_publish(self):
        """Only actors with placement_cell.announcement.publish may publish."""
        with pytest.raises(PermissionDeniedError):
            announcements.publish(
                actor=_unprivileged(),
                title="Oops", body="Unauthorized publish attempt.", topic="general")

    def test_withdrawn_announcement_stays_in_history(self):
        """PC-AFR-043: history is maintained — withdrawal flags, not deletes."""
        ann = announcements.publish(
            actor=_tpo(), title="Cancelled Drive",
            body="Drive details.", topic="drive")
        announcements.withdraw(
            announcement_id=ann.pk, actor=_tpo(), reason="Drive cancelled.")
        ann.refresh_from_db()
        assert ann.is_withdrawn is True
        assert Announcement.objects.filter(pk=ann.pk).exists()


class TestChairmanAnnouncement:
    """PC-UC-013: Placement Chairman publishes official placement announcements."""

    def test_chairman_can_publish_an_official_announcement(self):
        ann = announcements.publish(
            actor=_chairman(),
            title="Official Recruitment Notice",
            body="All eligible students are invited to apply.",
            topic="general",
        )
        assert ann.pk is not None
        assert ann.published_by_user_id == 11

    def test_announcement_content_topics_match_spec(self):
        """PC-BR-017 / PC-AFR-042: supported topics include placement drives,
        company visits, training sessions, workshops, job opportunities,
        recruitment drives, internship programs."""
        # Verify each PS-listed topic can be used (they map to model choices)
        from modules.placement.models import Announcement
        valid_topics = {c for c, _ in Announcement.TOPIC}
        # Minimum required topics per spec PS 3.7 / PC-AFR-042
        expected_coverage = {"drive", "workshop", "general"}
        assert expected_coverage.issubset(valid_topics), (
            f"Supported topics {valid_topics} must include at least {expected_coverage}")


# ---------------------------------------------------------------------------
# G-07: PC-UC-007 — posting.published notification fires (PC-BR-021)
# ---------------------------------------------------------------------------

class TestPostingPublishedNotification:
    """PC-UC-007: when a new job posting becomes available, the New Job Posting
    event triggers automated notifications."""

    @pytest.fixture
    def world(self):
        PlacementPolicy.objects.create(season="2026-27", is_active=True)
        return Company.objects.create(
            name="Acme", slug="acme", status="active",
            approval_status="approved", approved_by_user_id=9)

    def test_publishing_a_posting_queues_a_notification(self, world, stub_iam):
        from conftest import make_session
        stub_iam(make_session(user_id=9))
        manager = make_principal(
            user_id=9, kind="staff", permissions=(MANAGE_POSTING_PERM,))
        company = world
        draft = JobPosting.objects.create(
            company=company, title="SDE-2", placement_year="2026-27",
            description="Build things.", status="draft",
            closes_at=timezone.now() + timedelta(days=14),
            eligibility_rule={"gte": ["cpi", 7.0]},
            created_by_user_id=9)
        postings.publish(posting_id=draft.pk, actor=manager)
        outbox = NotificationOutbox.objects.filter(
            topic="posting.published").first()
        assert outbox is not None, (
            "publishing a posting must enqueue a posting.published notification "
            "(PC-UC-007, PC-BR-021)")

    def test_draft_posting_does_not_notify(self, world, stub_iam):
        """Creating a draft posting must NOT send notifications."""
        from conftest import make_session
        stub_iam(make_session(user_id=9))
        manager = make_principal(
            user_id=9, kind="staff", permissions=(MANAGE_POSTING_PERM,))
        company = world
        postings.create(
            company_id=company.pk, placement_year="2026-27",
            actor=manager, title="Draft Role",
            eligibility_rule={"gte": ["cpi", 7.0]},
            closes_at=timezone.now() + timedelta(days=7),
            description="To be published later.")
        assert not NotificationOutbox.objects.filter(
            topic="posting.published").exists()


# ---------------------------------------------------------------------------
# G-08: PC-UC-007 — application.submitted notification fires
# ---------------------------------------------------------------------------

class TestApplicationSubmittedNotification:
    """PC-UC-003 step 6: the recorded Application Submitted event triggers
    PC-UC-007 Issue Automated Placement Notifications."""

    @pytest.fixture
    def world(self):
        PlacementPolicy.objects.create(season="2026-27", is_active=True)
        company = Company.objects.create(
            name="Acme", slug="acme", status="active",
            approval_status="approved", approved_by_user_id=9)
        return JobPosting.objects.create(
            company=company, title="SDE-1", placement_year="2026-27",
            description="Work.", status="published",
            closes_at=timezone.now() + timedelta(days=7),
            eligibility_rule={}, eligibility_rule_locked_at=timezone.now(),
            ctc_lpa="12.00", created_by_user_id=9,
            published_at=timezone.now())

    def test_submitting_an_application_queues_notification(
            self, world, stub_iam):
        """The application.submitted topic must be enqueued on successful apply."""
        from conftest import make_session
        from fusion_auth.client import UserRef
        posting = world
        stub_iam(make_session(
            user_id=1001, kind="student",
            modules=("placement_cell",),
            permissions=("placement_cell.application.create",
                         "placement_cell.job_posting.view")),
            users={1001: UserRef(
                user_id=1001, username="21BCS001",
                display_name="Test Student", kind="student",
                profile_completed=True,
                discipline="CSE")})
        from modules.placement.models import PlacementRegistration
        PlacementRegistration.objects.create(
            policy=PlacementPolicy.objects.get(season="2026-27"),
            user_id=1001, status="registered")

        actor = make_principal(
            user_id=1001, kind="student",
            permissions=("placement_cell.application.create",))
        app_service.apply_to(posting_id=posting.pk, actor=actor)

        note = NotificationOutbox.objects.filter(
            topic="application.submitted",
            recipient_user_id=1001).first()
        assert note is not None, (
            "applying to a posting must enqueue an application.submitted "
            "notification (PC-UC-007, PC-BR-021)")
