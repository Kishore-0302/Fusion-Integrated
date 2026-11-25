"""Interview scheduling and tracking tests.

Covers spec gaps G-01 (PC-BR-011: required fields) and G-02 (PC-UC-021: recruiter
scheduling, BW-PC-06).
"""
from datetime import timedelta
from types import SimpleNamespace

import pytest
from django.utils import timezone

from conftest import make_principal, make_session
from core.api.exceptions import ConflictError, NotFoundError
from modules.placement.models import (
    Application,
    Company,
    InterviewRound,
    JobPosting,
    NotificationOutbox,
    PlacementPolicy,
    RecruiterAccount,
    RoundParticipation,
)
from modules.placement.services import interviews

pytestmark = pytest.mark.django_db

SCHEDULE_PERM = "placement_cell.interview.schedule"
REVIEW_PERM = "placement_cell.application.review"


def _make_recruiter_principal(company_pk, permissions=(SCHEDULE_PERM,)):
    """Build a recruiter-flavoured principal with account_id.

    Principal is a frozen dataclass and does not carry account_id; services
    access it via getattr(actor, 'account_id', None), so a SimpleNamespace
    with the right attributes is sufficient.
    """
    return SimpleNamespace(
        user_id=None,
        username="recruiter",
        display_name="Recruiter",
        kind="recruiter",
        active_role=None,
        roles=(),
        permissions=frozenset(permissions),
        modules=(),
        is_authenticated=True,
        is_anonymous=False,
        account_id=company_pk,
    )


@pytest.fixture
def world():
    """One company, one posting, one shortlisted applicant."""
    policy = PlacementPolicy.objects.create(season="2026-27", is_active=True)
    company = Company.objects.create(
        name="Acme", slug="acme", status="active",
        approval_status="approved", approved_by_user_id=9)
    posting = JobPosting.objects.create(
        company=company, title="SDE-1", placement_year="2026-27",
        description="Build things.", status="published",
        closes_at=timezone.now() + timedelta(days=7),
        eligibility_rule={}, eligibility_rule_locked_at=timezone.now(),
        ctc_lpa="12.00", created_by_user_id=9)
    app = Application.objects.create(
        posting=posting, user_id=1001, status="shortlisted")
    return policy, company, posting, app


def _staff():
    return make_principal(user_id=9, kind="staff",
                          permissions=(SCHEDULE_PERM, REVIEW_PERM))


# ---------------------------------------------------------------------------
# G-01: PC-BR-011 — interview schedule requires date + time slot + mode
# ---------------------------------------------------------------------------

class TestInterviewRequiredFields:
    """PC-BR-011: a recorded interview schedule must include date/time, and
    mode as online or offline. Missing any field must be refused."""

    def test_online_round_requires_a_meeting_url(self, world, stub_iam):
        _, _, posting, _ = world
        stub_iam(make_session(user_id=9))
        with pytest.raises(ConflictError) as exc:
            interviews.schedule_round(
                posting_id=posting.pk, actor=_staff(),
                mode="online",
                starts_at=timezone.now() + timedelta(hours=2),
                # meeting_url intentionally omitted
            )
        assert exc.value.code == "meeting_url_required"

    def test_offline_round_requires_a_venue(self, world, stub_iam):
        _, _, posting, _ = world
        stub_iam(make_session(user_id=9))
        with pytest.raises(ConflictError) as exc:
            interviews.schedule_round(
                posting_id=posting.pk, actor=_staff(),
                mode="offline",
                starts_at=timezone.now() + timedelta(hours=2),
                # venue intentionally omitted
            )
        assert exc.value.code == "venue_required"

    def test_mode_must_be_online_or_offline(self, world, stub_iam):
        _, _, posting, _ = world
        stub_iam(make_session(user_id=9))
        with pytest.raises(ConflictError) as exc:
            interviews.schedule_round(
                posting_id=posting.pk, actor=_staff(),
                mode="hybrid",    # not in spec
                starts_at=timezone.now() + timedelta(hours=2),
            )
        assert exc.value.code == "bad_mode"

    def test_online_round_with_url_is_accepted(self, world, stub_iam):
        _, _, posting, _ = world
        stub_iam(make_session(user_id=9))
        round_ = interviews.schedule_round(
            posting_id=posting.pk, actor=_staff(),
            mode="online",
            starts_at=timezone.now() + timedelta(hours=2),
            meeting_url="https://meet.example.com/abc",
        )
        assert round_.pk is not None
        assert round_.mode == "online"

    def test_offline_round_with_venue_is_accepted(self, world, stub_iam):
        _, _, posting, _ = world
        stub_iam(make_session(user_id=9))
        round_ = interviews.schedule_round(
            posting_id=posting.pk, actor=_staff(),
            mode="offline",
            starts_at=timezone.now() + timedelta(hours=2),
            venue="Room 101, Admin Block",
        )
        assert round_.mode == "offline"
        assert round_.venue == "Room 101, Admin Block"

    def test_round_records_the_start_datetime(self, world, stub_iam):
        """The 'time slot' part of PC-BR-011."""
        _, _, posting, _ = world
        stub_iam(make_session(user_id=9))
        starts = timezone.now() + timedelta(hours=3)
        round_ = interviews.schedule_round(
            posting_id=posting.pk, actor=_staff(),
            mode="online",
            starts_at=starts,
            meeting_url="https://meet.example.com/x",
        )
        # starts_at is preserved to the second
        assert abs((round_.starts_at - starts).total_seconds()) < 2

    def test_a_nonexistent_posting_raises_404(self, world, stub_iam):
        stub_iam(make_session(user_id=9))
        with pytest.raises(NotFoundError):
            interviews.schedule_round(
                posting_id=99999, actor=_staff(),
                mode="online",
                starts_at=timezone.now() + timedelta(hours=1),
                meeting_url="https://meet.example.com/x",
            )


# ---------------------------------------------------------------------------
# G-02: PC-UC-021 / BW-PC-06 — Company/Recruiter schedules interview
# ---------------------------------------------------------------------------

class TestRecruiterSchedulesInterview:
    """PC-UC-021: authorized Company/Recruiter can schedule an interview for
    a relevant shortlisted candidate (BW-PC-06). The notification must fire."""

    @pytest.fixture
    def recruiter(self, world):
        """A minimal recruiter-like principal that has schedule permission."""
        _, company, _, _ = world
        acct = RecruiterAccount.objects.create(
            company=company,
            email="recruiter@acme.example.com",
            full_name="Jane Recruiter",
        )
        return _make_recruiter_principal(acct.pk)

    def test_recruiter_can_schedule_an_interview(self, world, stub_iam, recruiter):
        _, _company, posting, _ = world
        stub_iam(make_session(user_id=9))
        round_ = interviews.schedule_round(
            posting_id=posting.pk,
            actor=recruiter,
            mode="online",
            starts_at=timezone.now() + timedelta(hours=2),
            meeting_url="https://meet.example.com/r",
        )
        assert InterviewRound.objects.filter(pk=round_.pk).exists()

    def test_recruiter_round_is_scoped_to_their_posting(self, world, stub_iam):
        """A recruiter for company B cannot schedule on company A's posting."""
        _, _company, posting, _ = world
        other_company = Company.objects.create(
            name="OtherCo", slug="otherco", status="active",
            approval_status="approved", approved_by_user_id=9)
        other_acct = RecruiterAccount.objects.create(
            company=other_company,
            email="recruiter@otherco.example.com",
            full_name="Other Recruiter",
        )
        other_recruiter = _make_recruiter_principal(other_acct.pk)
        stub_iam(make_session(user_id=9))
        # Provide a scope that excludes company A's postings
        from modules.placement.models import JobPosting as JP
        scope = JP.objects.filter(company=other_company)
        with pytest.raises(NotFoundError):
            interviews.schedule_round(
                posting_id=posting.pk,
                actor=other_recruiter,
                mode="online",
                starts_at=timezone.now() + timedelta(hours=2),
                meeting_url="https://meet.example.com/r",
                scope=scope,
            )


# ---------------------------------------------------------------------------
# PC-BR-012 — interview.scheduled notification fires when candidates added
# ---------------------------------------------------------------------------

class TestInterviewNotification:
    """PC-BR-012: eligible/shortlisted students receive notification when
    an interview is scheduled for them."""

    def test_adding_a_candidate_queues_interview_notification(
            self, world, stub_iam):
        _, _, posting, app = world
        stub_iam(make_session(user_id=9))
        round_ = interviews.schedule_round(
            posting_id=posting.pk, actor=_staff(),
            mode="offline",
            starts_at=timezone.now() + timedelta(hours=4),
            venue="Lab 203",
        )
        interviews.add_candidates(
            round_id=round_.pk,
            application_ids=[app.pk],
            actor=_staff(),
        )
        note = NotificationOutbox.objects.filter(
            topic="interview.scheduled",
            recipient_user_id=app.user_id,
        ).first()
        assert note is not None
        assert note.payload["round_id"] == round_.pk
        assert note.payload["mode"] == "offline"

    def test_adding_the_same_candidate_twice_is_idempotent(
            self, world, stub_iam):
        """Deduplication: the same student should not get two notifications."""
        _, _, posting, app = world
        stub_iam(make_session(user_id=9))
        round_ = interviews.schedule_round(
            posting_id=posting.pk, actor=_staff(),
            mode="online",
            starts_at=timezone.now() + timedelta(hours=4),
            meeting_url="https://meet.example.com/d",
        )
        interviews.add_candidates(
            round_id=round_.pk, application_ids=[app.pk], actor=_staff())
        interviews.add_candidates(
            round_id=round_.pk, application_ids=[app.pk], actor=_staff())
        # Only one participation row
        assert RoundParticipation.objects.filter(round=round_).count() == 1
        # Only one notification (dedupe_key prevents duplicates)
        assert NotificationOutbox.objects.filter(
            topic="interview.scheduled",
            recipient_user_id=app.user_id).count() == 1

    def test_shortlisted_application_moves_to_interview_scheduled(
            self, world, stub_iam):
        """BW-PC-05/06: adding to a round transitions the application state."""
        _, _, posting, app = world
        stub_iam(make_session(user_id=9))
        round_ = interviews.schedule_round(
            posting_id=posting.pk, actor=_staff(),
            mode="online",
            starts_at=timezone.now() + timedelta(hours=4),
            meeting_url="https://meet.example.com/t",
        )
        interviews.add_candidates(
            round_id=round_.pk, application_ids=[app.pk], actor=_staff())
        app.refresh_from_db()
        assert app.status == "interview_scheduled"
