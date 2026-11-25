"""End-to-End Placement Application Lifecycle test (CW-PC-04).

Covers the complete six-step composite workflow CW-PC-04:
Step 1: Opportunity Published (PC-UC-006 / PC-UC-015, PC-BR-003, PC-BR-004)
Step 2: Student Application (PC-UC-003, PC-BR-001, PC-BR-002)
Step 3: Application Shortlisted (PC-UC-016, PC-BR-009, PC-BR-030)
Step 4: Interview Scheduled (PC-UC-009 / PC-UC-021, PC-BR-011, PC-BR-012)
Step 5: Job Offer Extended (PC-UC-022, PC-BR-009, PC-BR-030)
Step 6: Job Offer Accepted & Placement Record Created (PC-UC-005, PC-BR-013, PC-BR-014, PC-BR-015)
"""
from datetime import timedelta
from decimal import Decimal

import pytest
from django.utils import timezone

from conftest import make_principal, make_session
from core.api.exceptions import ConflictError
from fusion_auth.client import UserRef
from modules.placement.domain import offer_policy as pol
from modules.placement.models import (
    Application,
    Company,
    NotificationOutbox,
    PlacementPolicy,
    PlacementRecord,
    PlacementRegistration,
    PolicyCategory,
)
from modules.placement.services import (
    applications as app_service,
)
from modules.placement.services import (
    interviews as interview_service,
)
from modules.placement.services import (
    offers as offer_service,
)
from modules.placement.services import (
    postings as posting_service,
)

pytestmark = pytest.mark.django_db

SEASON = "2026-27"
STUDENT_ID = 1001
STAFF_ID = 9

MANAGE_POSTING_PERM = "placement_cell.job_posting.manage"
APPLY_PERM = "placement_cell.application.create"
VIEW_POSTING_PERM = "placement_cell.job_posting.view"
REVIEW_PERM = "placement_cell.application.review"
SCHEDULE_PERM = "placement_cell.interview.schedule"
ISSUE_OFFER_PERM = "placement_cell.offer.issue"
RESPOND_OFFER_PERM = "placement_cell.offer.respond"


@pytest.fixture
def env(stub_iam):
    """Set up the placement environment: policy, company, and IAM user stub."""
    iam = stub_iam(
        make_session(
            user_id=STUDENT_ID,
            kind="student",
            modules=("placement_cell",),
            permissions=(APPLY_PERM, VIEW_POSTING_PERM, RESPOND_OFFER_PERM),
        ),
        users={
            STUDENT_ID: UserRef(
                user_id=STUDENT_ID,
                username="21BCS001",
                display_name="Life Cycle Student",
                kind="student",
                profile_completed=True,
                discipline="CSE",
            )
        },
    )
    iam.standings[STUDENT_ID] = {
        "cpi": "8.50",
        "earned_credits": "120",
        "active_backlogs": 0,
        "semester": 7,
        "semester_type": "autumn",
        "declared_seq": 1,
    }

    policy = PlacementPolicy.objects.create(
        season=SEASON,
        is_active=True,
        discipline_groups=dict(pol.DEFAULT_GROUP_MAP),
    )
    for c in pol.default_categories():
        PolicyCategory.objects.create(
            policy=policy,
            group=c.group,
            number=c.number,
            ctc_min=c.ctc_min,
            ctc_max=c.ctc_max,
            switch_multiplier=c.switch_multiplier,
            switch_floor=c.switch_floor,
            exit_above=c.exit_above,
            max_switches=c.max_switches,
        )

    company = Company.objects.create(
        name="TechCorp",
        slug="techcorp",
        status="active",
        approval_status="approved",
        approved_by_user_id=STAFF_ID,
    )

    PlacementRegistration.objects.create(
        policy=policy,
        user_id=STUDENT_ID,
        status="registered",
        registered_at=timezone.now(),
    )

    tpo_principal = make_principal(
        user_id=STAFF_ID,
        kind="staff",
        active_role="tpo",
        permissions=(
            MANAGE_POSTING_PERM,
            REVIEW_PERM,
            SCHEDULE_PERM,
            ISSUE_OFFER_PERM,
        ),
    )

    student_principal = make_principal(
        user_id=STUDENT_ID,
        kind="student",
        active_role="student",
        permissions=(APPLY_PERM, VIEW_POSTING_PERM, RESPOND_OFFER_PERM),
    )

    return policy, company, tpo_principal, student_principal


def test_cw_pc_04_end_to_end_application_lifecycle(env):
    """CW-PC-04: Full lifecycle from opportunity publication through acceptance."""
    policy, company, tpo, student = env

    # -------------------------------------------------------------------------
    # Step 1: Opportunity Published (PC-UC-006 / PC-UC-015, PC-BR-003)
    # -------------------------------------------------------------------------
    draft = posting_service.create(
        company_id=company.pk,
        placement_year=SEASON,
        actor=tpo,
        title="Full Stack Engineer",
        description="Develop scalable cloud services.",
        ctc_lpa=Decimal("14.50"),
        eligibility_rule={"gte": ["cpi", 6.5]},
        closes_at=timezone.now() + timedelta(days=14),
    )
    assert draft.status == "draft"

    posting = posting_service.publish(posting_id=draft.pk, actor=tpo)
    assert posting.status == "published"
    assert posting.eligibility_rule_locked_at is not None
    # Notification for published posting is queued
    assert NotificationOutbox.objects.filter(
        topic="posting.published", payload__posting_id=posting.pk
    ).exists()

    # -------------------------------------------------------------------------
    # Step 2: Student Application (PC-UC-003, PC-BR-001, PC-BR-002)
    # -------------------------------------------------------------------------
    app = app_service.apply_to(
        posting_id=posting.pk,
        actor=student,
        cover_note="Excited to apply!",
    )
    assert app.status == "submitted"
    assert app.user_id == STUDENT_ID
    assert app.posting_id == posting.pk
    # Application submitted notification is queued
    assert NotificationOutbox.objects.filter(
        topic="application.submitted", recipient_user_id=STUDENT_ID
    ).exists()

    # -------------------------------------------------------------------------
    # Step 3: Application Under Review -> Shortlisted (PC-UC-016, PC-BR-009, PC-BR-030)
    # -------------------------------------------------------------------------
    app = app_service.transition(
        application_id=app.pk,
        to_status="under_review",
        actor=tpo,
        reason="Under initial screening.",
    )
    assert app.status == "under_review"

    app = app_service.transition(
        application_id=app.pk,
        to_status="shortlisted",
        actor=tpo,
        reason="Candidate profile meets initial screening criteria.",
    )
    assert app.status == "shortlisted"

    # -------------------------------------------------------------------------
    # Step 4: Interview Scheduled (PC-UC-009 / PC-UC-021, PC-BR-011, PC-BR-012)
    # -------------------------------------------------------------------------
    round_ = interview_service.schedule_round(
        posting_id=posting.pk,
        actor=tpo,
        kind="tech",
        mode="online",
        starts_at=timezone.now() + timedelta(days=2),
        meeting_url="https://meet.google.com/xyz-tech-round",
        instructions="Prepare code editor.",
    )
    interview_service.add_candidates(
        round_id=round_.pk,
        application_ids=[app.pk],
        actor=tpo,
    )
    app.refresh_from_db()
    assert app.status == "interview_scheduled"
    # Interview notification is queued
    assert NotificationOutbox.objects.filter(
        topic="interview.scheduled", recipient_user_id=STUDENT_ID
    ).exists()

    # Candidate cleared the interview round and is selected
    app = app_service.transition(
        application_id=app.pk,
        to_status="selected",
        actor=tpo,
        reason="Candidate cleared technical interview round.",
    )
    assert app.status == "selected"

    # -------------------------------------------------------------------------
    # Step 5: Job Offer Extended (PC-UC-022, PC-BR-009, PC-BR-030)
    # -------------------------------------------------------------------------
    offer = offer_service.issue(
        application_id=app.pk,
        actor=tpo,
    )
    app.refresh_from_db()
    assert app.status == "offer_issued"
    assert offer.status == "issued"
    # Offer issued notification is queued
    assert NotificationOutbox.objects.filter(
        topic="offer.issued", recipient_user_id=STUDENT_ID
    ).exists()

    # -------------------------------------------------------------------------
    # Step 6: Offer Accepted & Placement Record Updated (PC-UC-005, PC-BR-013..015)
    # -------------------------------------------------------------------------
    offer_service.respond(
        offer_id=offer.pk,
        accept=True,
        actor=student,
    )
    app.refresh_from_db()
    assert app.status == "offer_accepted"
    offer.refresh_from_db()
    assert offer.status == "accepted"

    # Placement record is created and active
    record = PlacementRecord.objects.filter(
        user_id=STUDENT_ID, is_active=True
    ).first()
    assert record is not None
    assert record.company_id == company.pk
    assert record.posting_id == posting.pk
    assert record.ctc_lpa == Decimal("14.50")
    assert record.source == "campus"

    # Student's registration is updated with offer counts
    reg = PlacementRegistration.objects.get(policy=policy, user_id=STUDENT_ID)
    assert reg.offer_count == 1
    assert reg.best_accepted_ctc_lpa == Decimal("14.50")


def test_apply_to_ineligible_with_decimal_cpi_snapshot_regression(env):
    """Regression test for PCMS-TC-010 / PCMS-AFR-008:
    When an ineligible student applies, the eligibility snapshot containing
    Decimal values (such as required threshold or actual CPI) must serialize cleanly
    to JSONField without raising TypeError: Object of type Decimal is not JSON serializable,
    and must raise ConflictError('not_eligible') leaving no Application created.
    """
    _policy, company, tpo, student = env

    posting = posting_service.create(
        actor=tpo,
        company_id=company.pk,
        title="High Bar Engineer",
        placement_year=SEASON,
        description="High requirement",
        ctc_lpa=Decimal("20.00"),
        closes_at=timezone.now() + timedelta(days=7),
        eligibility_rule={"gte": ["cpi", 9.0]},
    )
    posting_service.publish(posting_id=posting.pk, actor=tpo)

    # Student has CPI 8.50, which is below required 9.00.
    # Attempting to apply should report not eligible and create no application.
    with pytest.raises(ConflictError) as exc_info:
        app_service.apply_to(posting_id=posting.pk, actor=student)

    assert exc_info.value.code == "not_eligible"
    assert "not eligible" in str(exc_info.value)
    # Ensure no application row was persisted
    assert not Application.objects.filter(posting=posting, user_id=STUDENT_ID).exists()


def test_eligibility_snapshot_serialization_with_decimals(env):
    """Ensure Application row with nested Decimal values in eligibility_snapshot
    converts and saves cleanly to JSONField."""
    _policy, company, tpo, _student = env
    posting = posting_service.create(
        actor=tpo,
        company_id=company.pk,
        title="Sample Engineer",
        placement_year=SEASON,
        description="Engineering role",
        ctc_lpa=Decimal("15.00"),
        closes_at=timezone.now() + timedelta(days=7),
        eligibility_rule={"gte": ["cpi", 7.0]},
    )
    raw_snapshot = {
        "is_eligible": False,
        "failed": [
            {
                "field": "cpi",
                "reason": "less_than",
                "required": Decimal("8.50"),
                "actual": Decimal("7.25"),
                "message": "CPI below required minimum.",
            }
        ],
        "standing": {
            "cpi": Decimal("7.25"),
            "earned_credits": Decimal("120.00"),
        },
    }
    safe_snapshot = app_service._json_safe(raw_snapshot)
    app = Application.objects.create(
        posting=posting,
        user_id=STUDENT_ID,
        status="draft",
        eligibility_snapshot=safe_snapshot,
    )
    app.refresh_from_db()
    assert app.eligibility_snapshot["failed"][0]["actual"] == 7.25
    assert app.eligibility_snapshot["failed"][0]["required"] == 8.5
    assert app.eligibility_snapshot["standing"]["cpi"] == 7.25
    assert app.eligibility_snapshot["standing"]["earned_credits"] == 120

