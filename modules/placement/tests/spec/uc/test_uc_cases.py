"""Backend conformance tests for the frozen UC design cases."""

from datetime import timedelta

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from conftest import make_principal, make_session
from core.api.exceptions import ConflictError, PermissionDeniedError
from modules.placement.models import (
    Announcement,
    Application,
    Company,
    JobPosting,
    PlacementPolicy,
    PlacementRecord,
)
from modules.placement.services import announcements, stats
from modules.placement.services import applications as application_service

pytestmark = pytest.mark.django_db


PUBLISH = "placement_cell.announcement.publish"
VIEW_POSTING = "placement_cell.job_posting.view"


def _principal(user_id, role, permissions):
    return make_principal(
        user_id=user_id,
        kind="staff",
        active_role=role,
        permissions=permissions,
    )


def _published_posting():
    company = Company.objects.create(
        name="UC Acme",
        slug="uc-acme",
        status="active",
        approval_status="approved",
        approved_by_user_id=9,
    )
    return JobPosting.objects.create(
        company=company,
        title="UC Engineer",
        placement_year="2026-27",
        description="Build software.",
        status="published",
        closes_at=timezone.now() + timedelta(days=7),
        published_at=timezone.now(),
        eligibility_rule={},
        eligibility_rule_locked_at=timezone.now(),
    )


def test_pcms_tc_044_official_placement_announcement():
    """test_id=PCMS-TC-044; source_id=PC-UC-013 Main Success Scenario"""
    from modules.placement.models import NotificationOutbox

    actor = _principal(11, "placement_chairman", (PUBLISH,))

    notice = announcements.publish(
        actor=actor,
        title="Placement notice",
        body="A placement drive is scheduled.",
        topic="drive",
    )

    assert Announcement.objects.filter(pk=notice.pk).exists()
    assert notice.published_by_user_id == actor.user_id
    assert notice.published_at is not None
    assert NotificationOutbox.objects.filter(
        topic="announcement.published").exists()


def test_pcms_tc_045_announcement_refusal_has_no_state_change():
    """test_id=PCMS-TC-045; source_id=PC-UC-013 Exception E1"""
    authorized = _principal(11, "placement_chairman", (PUBLISH,))
    before = Announcement.objects.count()

    with pytest.raises(ConflictError):
        announcements.publish(
            actor=authorized, title="", body="Notice body.", topic="drive")
    with pytest.raises(PermissionDeniedError):
        announcements.publish(
            actor=_principal(12, "staff", ()),
            title="Unauthorized notice",
            body="Notice body.",
            topic="drive",
        )

    assert Announcement.objects.count() == before


def test_pcms_tc_057_alumni_reads_permitted_published_postings(stub_iam):
    """test_id=PCMS-TC-057; source_id=PC-UC-017 Main Success Scenario"""
    posting = _published_posting()
    stub_iam(make_session(
        user_id=5001,
        kind="alumni",
        active_role="alumni",
        modules=("placement_cell",),
        permissions=(VIEW_POSTING,),
    ))
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION="Token abc")

    response = client.get(f"/api/v1/placement/postings/{posting.pk}")

    assert response.status_code == 200
    assert response.json()["title"] == posting.title


def test_pcms_tc_058_alumni_cannot_read_unpublished_postings(stub_iam):
    """test_id=PCMS-TC-058; source_id=PC-UC-017 Exception E1"""
    posting = _published_posting()
    JobPosting.objects.filter(pk=posting.pk).update(status="draft")
    stub_iam(make_session(
        user_id=5001,
        kind="alumni",
        active_role="alumni",
        modules=("placement_cell",),
        permissions=(VIEW_POSTING,),
    ))
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION="Token abc")

    response = client.get(f"/api/v1/placement/postings/{posting.pk}")

    assert response.status_code == 404
    posting.refresh_from_db()
    assert posting.status == "draft"


def test_pcms_tc_059_alumni_cannot_apply_or_change_placement_state(stub_iam):
    """test_id=PCMS-TC-059; source_id=PC-UC-017 Exception E2"""
    posting = _published_posting()
    stub_iam(make_session(
        user_id=5001,
        kind="alumni",
        active_role="alumni",
        modules=("placement_cell",),
        permissions=("placement_cell.application.create",),
    ))
    actor = make_principal(
        user_id=5001,
        kind="alumni",
        active_role="alumni",
        permissions=("placement_cell.application.create",),
    )
    before = posting.applications.count()

    with pytest.raises(ConflictError) as refusal:
        application_service.apply_to(posting_id=posting.pk, actor=actor)

    assert refusal.value.code == "alumni_workflow_prohibited"
    assert posting.applications.count() == before


def test_pcms_tc_060_tpo_publishes_placement_announcement():
    """test_id=PCMS-TC-060; source_id=PC-UC-020 Main Success Scenario"""
    from modules.placement.models import NotificationOutbox

    actor = _principal(9, "tpo", (PUBLISH,))

    notice = announcements.publish(
        actor=actor,
        title="Placement drive",
        body="Company visit on Monday.",
        topic="drive",
    )

    assert Announcement.objects.filter(pk=notice.pk).exists()
    assert notice.published_by_user_id == actor.user_id
    assert notice.published_at is not None
    assert NotificationOutbox.objects.filter(
        topic="announcement.published").exists()


def test_pcms_tc_061_tpo_announcement_refusal_has_no_state_change():
    """test_id=PCMS-TC-061; source_id=PC-UC-020 Exception E1"""
    actor = _principal(9, "tpo", (PUBLISH,))
    before = Announcement.objects.count()

    with pytest.raises(ConflictError):
        announcements.publish(actor=actor, title="", body="Body", topic="drive")
    with pytest.raises(PermissionDeniedError):
        announcements.publish(
            actor=_principal(10, "tpo", ()),
            title="Unauthorized",
            body="Body",
            topic="drive",
        )

    assert Announcement.objects.count() == before


def test_pcms_tc_070_student_sees_anonymized_placement_statistics():
    """test_id=PCMS-TC-070; source_id=PC-UC-024 Main Success Scenario"""
    policy = PlacementPolicy.objects.create(season="2026-27", is_active=True)
    result = stats.student_view(season=policy.season)

    assert result["season"] == policy.season
    assert "user_id" not in result
    assert "name" not in result


def test_pcms_tc_071_student_statistics_expose_no_sensitive_data():
    """test_id=PCMS-TC-071; source_id=PC-UC-024 Exception E1"""
    policy = PlacementPolicy.objects.create(season="2026-27", is_active=True)
    result = stats.student_view(season=policy.season)

    assert "user_id" not in result
    assert "name" not in result
    assert "email" not in result

@pytest.fixture
def uc_world(stub_iam):
    """Isolated policy, approved posting, Student, and authorized TPO."""
    from datetime import timedelta
    from decimal import Decimal

    from conftest import make_principal
    from fusion_auth.client import UserRef
    from modules.placement.domain import offer_policy
    from modules.placement.models import (
        Application,
        PlacementRegistration,
        PolicyCategory,
        RecruiterAccount,
    )

    student_id = 1001
    identity = UserRef(
        user_id=student_id,
        username="uc-student",
        display_name="UC Student",
        kind="student",
        discipline="CSE",
        profile_completed=True,
    )
    iam = stub_iam(
        make_session(
            user_id=student_id,
            kind="student",
            modules=("placement_cell",),
            permissions=(
                "placement_cell.application.create",
                "placement_cell.application.view_self",
                "placement_cell.job_posting.view",
                "placement_cell.offer.respond",
            ),
        ),
        users={student_id: identity},
    )
    iam.standings[student_id] = {
        "cpi": "8.50",
        "earned_credits": "120",
        "active_backlogs": 0,
        "semester": 7,
        "semester_type": "autumn",
        "declared_seq": 1,
    }
    policy = PlacementPolicy.objects.create(
        season="2026-27",
        is_active=True,
        discipline_groups=dict(offer_policy.DEFAULT_GROUP_MAP),
    )
    for category in offer_policy.default_categories():
        PolicyCategory.objects.create(
            policy=policy,
            group=category.group,
            number=category.number,
            ctc_min=category.ctc_min,
            ctc_max=category.ctc_max,
            switch_multiplier=category.switch_multiplier,
            switch_floor=category.switch_floor,
            exit_above=category.exit_above,
            max_switches=category.max_switches,
        )
    PlacementRegistration.objects.create(
        policy=policy,
        user_id=student_id,
        status="registered",
        registered_at=timezone.now(),
    )
    company = Company.objects.create(
        name="UC World Co",
        slug="uc-world-co",
        status="active",
        approval_status="approved",
        approved_by_user_id=9,
    )
    # Keep the explicit recruiter identifiers used by the case scenarios
    # backed by real rows so Django's database teardown checks pass.
    RecruiterAccount.objects.create(
        id=601, company=company, email="tc021@uc.example.test",
        full_name="UC Recruiter 601",
    )
    RecruiterAccount.objects.create(
        id=701, company=company, email="tc015@uc.example.test",
        full_name="UC Recruiter 701",
    )
    posting = JobPosting.objects.create(
        company=company,
        title="UC Role",
        placement_year=policy.season,
        description="Role description.",
        status="published",
        closes_at=timezone.now() + timedelta(days=7),
        published_at=timezone.now(),
        eligibility_rule={"gte": ["cpi", 7.0]},
        eligibility_rule_locked_at=timezone.now(),
        ctc_lpa=Decimal("12.00"),
        created_by_user_id=9,
    )
    student = make_principal(
        user_id=student_id,
        kind="student",
        permissions=(
            "placement_cell.application.create",
            "placement_cell.application.view_self",
            "placement_cell.job_posting.view",
            "placement_cell.offer.respond",
        ),
    )
    tpo = make_principal(
        user_id=9,
        kind="staff",
        active_role="tpo",
        permissions=(
            "placement_cell.job_posting.manage",
            "placement_cell.application.view",
            "placement_cell.application.review",
            "placement_cell.interview.schedule",
            "placement_cell.offer.issue",
            "placement_cell.announcement.publish",
            "placement_cell.report.view",
            "placement_cell.company.manage",
            "placement_cell.record.manage",
        ),
    )
    app = Application.objects.create(
        posting=posting,
        user_id=student_id,
        status="submitted",
        eligibility_snapshot={"is_eligible": True,
                              "season_decision": {"allowed": True}},
    )
    return {
        "policy": policy,
        "company": company,
        "posting": posting,
        "application": app,
        "student": student,
        "tpo": tpo,
        "identity": identity,
    }


def test_pcms_tc_008_student_application_is_recorded(uc_world):
    """test_id=PCMS-TC-008; source_id=PC-UC-003 Main Success Scenario"""
    from modules.placement.models import Application, NotificationOutbox
    from modules.placement.services import applications

    world = uc_world
    world["application"].delete()
    applied = applications.apply_to(
        posting_id=world["posting"].pk, actor=world["student"])

    assert applied.status == "submitted"
    assert applied.user_id == world["student"].user_id
    assert Application.objects.filter(pk=applied.pk).exists()
    assert NotificationOutbox.objects.filter(
        topic="application.submitted",
        recipient_user_id=applied.user_id,
    ).exists()


def test_pcms_tc_009_incomplete_profile_cannot_apply(uc_world, stub_iam):
    """test_id=PCMS-TC-009; source_id=PC-UC-003 Exception E1"""
    from conftest import make_session
    from core.api.exceptions import ConflictError
    from modules.placement.services import applications

    world = uc_world
    from dataclasses import replace

    world["identity"] = replace(world["identity"], profile_completed=False)
    stub_iam(make_session(
        user_id=world["student"].user_id,
        kind="student",
        modules=("placement_cell",),
        permissions=("placement_cell.application.create",),
    ), users={world["student"].user_id: world["identity"]})
    world["application"].delete()

    with pytest.raises(ConflictError) as refusal:
        applications.apply_to(posting_id=world["posting"].pk,
                              actor=world["student"])

    assert refusal.value.code == "profile_incomplete"
    assert not world["posting"].applications.exists()


def test_pcms_tc_010_ineligible_student_cannot_apply(uc_world, stub_iam):
    """test_id=PCMS-TC-010; source_id=PC-UC-003 Exception E2"""
    from conftest import make_session
    from core.api.exceptions import ConflictError
    from fusion_auth.client import UserRef
    from modules.placement.services import applications

    world = uc_world
    user_id = world["student"].user_id
    stub_iam(make_session(
        user_id=user_id,
        kind="student",
        modules=("placement_cell",),
        permissions=("placement_cell.application.create",),
    ), users={user_id: UserRef(
        user_id=user_id,
        username="uc-student",
        display_name="UC Student",
        kind="student",
        discipline="CSE",
        profile_completed=True,
    )})
    world["application"].delete()
    world["posting"].eligibility_rule = {"gte": ["cpi", 9.9]}
    world["posting"].save(update_fields=["eligibility_rule"])

    with pytest.raises(ConflictError) as refusal:
        applications.apply_to(posting_id=world["posting"].pk,
                              actor=world["student"])

    assert refusal.value.code == "not_eligible"
    assert not world["posting"].applications.exists()


def test_pcms_tc_011_application_requires_authorized_access(uc_world):
    """test_id=PCMS-TC-011; source_id=PC-UC-003 Exception E3"""
    from modules.placement.services import applications

    world = uc_world
    world["application"].delete()
    unauthorized = make_principal(user_id=1001, kind="student", permissions=())

    with pytest.raises(PermissionDeniedError):
        applications.apply_to(posting_id=world["posting"].pk,
                              actor=unauthorized)

    assert not world["posting"].applications.exists()


def test_pcms_tc_012_student_reads_application_history(stub_iam, uc_world):
    """test_id=PCMS-TC-012; source_id=PC-UC-004 Main Success Scenario"""
    from modules.placement.services import applications

    applications.transition(
        application_id=uc_world["application"].pk,
        to_status="under_review",
        actor=make_principal(
            user_id=9,
            kind="staff",
            permissions=("placement_cell.application.review",),
        ),
    )
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION="Token abc")
    stub_iam(make_session(
        user_id=1001,
        kind="student",
        modules=("placement_cell",),
        permissions=("placement_cell.application.view_self",),
    ))

    result = client.get("/api/v1/placement/applications")
    history = client.get(
        f"/api/v1/placement/applications/{uc_world['application'].pk}/history")

    assert result.status_code == 200
    assert result.json()["results"][0]["status"] == "under_review"
    assert history.status_code == 200
    assert history.json()["results"]


def test_pcms_tc_013_empty_student_application_history(stub_iam, uc_world):
    """test_id=PCMS-TC-013; source_id=PC-UC-004 Alternative A1"""
    uc_world["application"].delete()
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION="Token abc")
    stub_iam(make_session(
        user_id=1001,
        kind="student",
        modules=("placement_cell",),
        permissions=("placement_cell.application.view_self",),
    ))

    result = client.get("/api/v1/placement/applications")

    assert result.status_code == 200
    assert result.json()["results"] == []


def test_pcms_tc_014_student_cannot_read_another_students_history(
        stub_iam, uc_world):
    """test_id=PCMS-TC-014; source_id=PC-UC-004 Exception E1"""
    from modules.placement.models import Application

    foreign = Application.objects.create(
        posting=uc_world["posting"], user_id=2002, status="submitted")
    stub_iam(make_session(
        user_id=1001,
        kind="student",
        modules=("placement_cell",),
        permissions=("placement_cell.application.view_self",),
    ))
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION="Token abc")

    result = client.get(f"/api/v1/placement/applications/{foreign.pk}/history")

    assert result.status_code == 404
    foreign.refresh_from_db()
    assert foreign.status == "submitted"


def _issue_uc_offer(world, *, ctc="12.00", respond_by=None):
    from datetime import timedelta

    from django.utils import timezone

    from modules.placement.models import Application
    from modules.placement.services import offers

    app = world["application"]
    Application.objects.filter(pk=app.pk).update(status="selected")
    app.refresh_from_db()
    staff = world["tpo"]
    return offers.issue(
        application_id=app.pk,
        actor=staff,
        ctc_lpa=ctc,
        respond_by=respond_by or timezone.now() + timedelta(days=1),
    )


def test_pcms_tc_015_student_accepts_offer_before_deadline(uc_world):
    """test_id=PCMS-TC-015; source_id=PC-UC-005 Main Success Scenario; PC-UC-005 Alternative A1"""
    from modules.placement.services import offers

    world = uc_world
    offer = _issue_uc_offer(world)

    accepted = offers.respond(offer_id=offer.pk, accept=True,
                              actor=world["student"])

    assert accepted.status == "accepted"
    assert PlacementRecord.objects.filter(
        user_id=world["student"].user_id, is_active=True).exists()


def test_pcms_tc_016_student_rejects_offer_before_deadline(uc_world):
    """test_id=PCMS-TC-016; source_id=PC-UC-005 Alternative A2"""
    from modules.placement.models import PlacementRecord
    from modules.placement.services import offers

    world = uc_world
    offer = _issue_uc_offer(world)

    rejected = offers.respond(offer_id=offer.pk, accept=False,
                              actor=world["student"])

    assert rejected.status == "declined"
    assert not PlacementRecord.objects.filter(
        user_id=world["student"].user_id, is_active=True).exists()


def test_pcms_tc_017_offer_response_after_deadline_is_refused(uc_world):
    """test_id=PCMS-TC-017; source_id=PC-UC-005 Exception E1"""
    from datetime import timedelta

    from core.api.exceptions import ConflictError
    from modules.placement.models import Offer, PlacementRecord
    from modules.placement.services import offers

    world = uc_world
    offer = _issue_uc_offer(world)
    Offer.objects.filter(pk=offer.pk).update(
        respond_by=timezone.now() - timedelta(seconds=1))

    with pytest.raises(ConflictError) as refusal:
        offers.respond(offer_id=offer.pk, accept=True,
                       actor=world["student"])

    assert refusal.value.code == "offer_expired"
    offer.refresh_from_db()
    assert offer.status == "issued"
    assert not PlacementRecord.objects.filter(
        user_id=world["student"].user_id, is_active=True).exists()


def test_pcms_tc_018_offer_policy_uses_represented_rules_only():
    """test_id=PCMS-TC-018; source_id=PC-UC-005 Exception E2"""
    from modules.placement.domain import offer_policy

    policy = offer_policy.PolicySpec(season="2026-27")
    student = offer_policy.StudentState(
        discipline="CSE",
        is_registered=True,
        category_number=1,
        accepted_offer_count=1,
        held_ctc_lpa=8,
        held_offer_id=99,
    )
    offer = offer_policy.OfferSpec(offer_id=1, ctc_lpa=10)

    decision = offer_policy.can_accept(policy, student, offer)

    assert decision.allowed is False
    assert decision.rule == "below_switch_multiple"


def test_pcms_tc_019_actor_without_offer_access_cannot_respond(
        stub_iam, uc_world):
    """test_id=PCMS-TC-019; source_id=PC-UC-005 Exception E3"""
    from modules.placement.models import PlacementRecord

    world = uc_world
    offer = _issue_uc_offer(world)
    stub_iam(make_session(
        user_id=world["student"].user_id,
        kind="student",
        modules=("placement_cell",),
        permissions=(),
    ))
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION="Token abc")

    response = client.post(
        f"/api/v1/placement/offers/{offer.pk}/respond",
        {"accept": True},
        format="json",
    )

    assert response.status_code == 403
    offer.refresh_from_db()
    assert offer.status == "issued"
    assert not PlacementRecord.objects.filter(
        user_id=world["student"].user_id, is_active=True).exists()


def test_pcms_tc_020_tpo_publishes_valid_posting(uc_world):
    """test_id=PCMS-TC-020; source_id=PC-UC-006 Main Success Scenario"""
    from modules.placement.services import postings

    world = uc_world
    draft = postings.create(
        company_id=world["company"].pk,
        placement_year=world["policy"].season,
        actor=world["tpo"],
        title="New UC Role",
        description="Role description.",
        eligibility_rule={"gte": ["cpi", 7.0]},
        closes_at=timezone.now() + timedelta(days=5),
    )

    published = postings.publish(posting_id=draft.pk, actor=world["tpo"])

    assert published.status == "published"
    assert published.eligibility_rule_locked_at is not None


def test_pcms_tc_021_recruiter_submission_requires_tpo_publication(uc_world):
    """test_id=PCMS-TC-021; source_id=PC-UC-006 Alternative A1"""
    from types import SimpleNamespace

    from modules.placement.services import postings

    world = uc_world
    recruiter = SimpleNamespace(
        kind="recruiter", account_id=601, company_id=world["company"].pk,
        user_id=None, has_permission=lambda _permission: False)
    draft = postings.create(
        company_id=world["company"].pk,
        placement_year=world["policy"].season,
        actor=recruiter,
        title="Submitted UC Role",
        description="Role description.",
        eligibility_rule={"gte": ["cpi", 7.0]},
        closes_at=timezone.now() + timedelta(days=5),
    )

    assert draft.status == "draft"
    assert postings.publish(posting_id=draft.pk, actor=world["tpo"]).status == "published"


def test_pcms_tc_022_posting_without_required_content_is_not_published(
        uc_world):
    """test_id=PCMS-TC-022; source_id=PC-UC-006 Exception E1"""
    from core.api.exceptions import ConflictError
    from modules.placement.models import JobPosting
    from modules.placement.services import postings

    world = uc_world
    draft = JobPosting.objects.create(
        company=world["company"],
        title="Incomplete UC Role",
        placement_year=world["policy"].season,
        description="",
        status="draft",
        closes_at=timezone.now() + timedelta(days=5),
        eligibility_rule={},
        created_by_user_id=world["tpo"].user_id,
    )

    with pytest.raises(ConflictError):
        postings.publish(posting_id=draft.pk, actor=world["tpo"])

    draft.refresh_from_db()
    assert draft.status == "draft"


def test_pcms_tc_023_tpo_without_posting_access_is_refused(uc_world):
    """test_id=PCMS-TC-023; source_id=PC-UC-006 Exception E2"""
    from core.api.exceptions import PermissionDeniedError
    from modules.placement.services import postings

    world = uc_world
    unauthorized = make_principal(user_id=10, kind="staff", permissions=())

    with pytest.raises(PermissionDeniedError):
        postings.publish(posting_id=world["posting"].pk, actor=unauthorized)

    world["posting"].refresh_from_db()
    assert world["posting"].status == "published"


def test_pcms_tc_024_posting_publish_queues_supported_notification(uc_world):
    """test_id=PCMS-TC-024; source_id=PC-UC-007 Main Success Scenario"""
    from modules.placement.models import NotificationOutbox
    from modules.placement.services import postings

    world = uc_world
    draft = postings.create(
        company_id=world["company"].pk,
        placement_year=world["policy"].season,
        actor=world["tpo"],
        title="Notified Role",
        description="Role details.",
        eligibility_rule={"gte": ["cpi", 7.0]},
        closes_at=timezone.now() + timedelta(days=3),
    )
    postings.publish(posting_id=draft.pk, actor=world["tpo"])

    event = NotificationOutbox.objects.get(topic="posting.published")

    assert event.payload["posting_id"] == draft.pk
    assert event.payload.get("broadcast") is True


def test_pcms_tc_025_event_recipients_follow_recorded_student_semantics(
        uc_world):
    """test_id=PCMS-TC-025; source_id=PC-UC-007 Alternative A1"""
    from modules.placement.models import NotificationOutbox
    from modules.placement.services import interviews, offers

    world = uc_world
    application = world["application"]
    application.status = "shortlisted"
    application.save(update_fields=["status"])
    round_ = interviews.schedule_round(
        posting_id=world["posting"].pk,
        actor=world["tpo"],
        mode="offline",
        starts_at=timezone.now() + timedelta(hours=2),
        venue="UC Interview Room",
    )
    interviews.add_candidates(
        round_id=round_.pk,
        application_ids=[application.pk],
        actor=world["tpo"],
    )
    interview_notice = NotificationOutbox.objects.get(
        topic="interview.scheduled")
    assert interview_notice.recipient_user_id == application.user_id

    application.refresh_from_db()
    application.status = "selected"
    application.save(update_fields=["status"])
    offer = offers.issue(application_id=application.pk, actor=world["tpo"])
    offer_notice = NotificationOutbox.objects.get(topic="offer.issued")
    assert offer_notice.recipient_user_id == application.user_id
    assert offer_notice.payload["offer_id"] == offer.pk


def test_pcms_tc_026_placement_drive_uses_announcement_notification(
        uc_world):
    """test_id=PCMS-TC-026; source_id=PC-UC-007 Alternative A2"""
    from modules.placement.models import NotificationOutbox

    actor = uc_world["tpo"]
    announcements.publish(
        actor=actor, title="Placement drive", body="Drive details.",
        topic="drive")

    event = NotificationOutbox.objects.get(topic="announcement.published")

    assert event.payload["broadcast"] is True


def test_pcms_tc_027_unresolved_recipient_policy_does_not_send_to_guessed_address():
    """test_id=PCMS-TC-027; source_id=PC-UC-007 Exception E1"""
    from modules.placement.models import NotificationOutbox
    from modules.placement.services import notifications

    before = NotificationOutbox.objects.count()
    with pytest.raises(ValueError, match="needs a recipient"):
        notifications.enqueue(
            topic="application.submitted",
            dedupe_key="uc-unresolved-recipient",
            subject="Application update",
            body="An application event occurred.",
        )

    assert NotificationOutbox.objects.count() == before


def test_pcms_tc_028_missing_notification_recipient_is_not_fabricated():
    """test_id=PCMS-TC-028; source_id=PC-UC-007 Exception E2"""
    from modules.placement.models import NotificationOutbox
    from modules.placement.services import notifications

    before = NotificationOutbox.objects.count()
    with pytest.raises(ValueError, match="needs a recipient"):
        notifications.enqueue(
            topic="interview.scheduled",
            dedupe_key="uc-missing-event-data",
            subject="",
            body="",
        )

    assert NotificationOutbox.objects.count() == before


def test_pcms_tc_029_tpo_updates_administrative_application_status(uc_world):
    """test_id=PCMS-TC-029; source_id=PC-UC-008 Main Success Scenario"""
    from modules.placement.models import ApplicationTransition
    from modules.placement.services import applications

    world = uc_world
    updated = applications.transition(
        application_id=world["application"].pk,
        to_status="under_review",
        actor=world["tpo"],
    )

    assert updated.status == "under_review"
    assert ApplicationTransition.objects.filter(
        application=updated, to_status="under_review").exists()


def test_pcms_tc_030_tpo_filters_applications_without_mutation(
        stub_iam, uc_world):
    """test_id=PCMS-TC-030; source_id=PC-UC-008 Alternative A1"""
    application = uc_world["application"]
    before_status = application.status
    stub_iam(make_session(
        user_id=9,
        kind="staff",
        roles=("tpo",),
        active_role="tpo",
        modules=("placement_cell",),
        permissions=("placement_cell.application.view",),
    ))
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION="Token abc")

    response = client.get(
        f"/api/v1/placement/applications?posting={uc_world['posting'].pk}"
        "&status=submitted")

    assert response.status_code == 200
    assert [row["id"] for row in response.json()["results"]] == [application.pk]
    application.refresh_from_db()
    assert application.status == before_status


def test_pcms_tc_031_tpo_application_scope_hides_unrelated_record(uc_world):
    """test_id=PCMS-TC-031; source_id=PC-UC-008 Exception E1"""
    from core.api.exceptions import NotFoundError
    from modules.placement.models import Application
    from modules.placement.services import applications

    world = uc_world
    foreign = Application.objects.create(
        posting=world["posting"], user_id=2002, status="submitted")
    scope = Application.objects.filter(pk=world["application"].pk)

    with pytest.raises(NotFoundError):
        applications.transition(
            application_id=foreign.pk,
            to_status="under_review",
            actor=world["tpo"],
            scope=scope,
        )

    foreign.refresh_from_db()
    assert foreign.status == "submitted"


def test_pcms_tc_032_tpo_cannot_make_unsupported_company_selection(
        uc_world):
    """test_id=PCMS-TC-032; source_id=PC-UC-008 Exception E2"""
    from core.api.exceptions import ConflictError
    from modules.placement.services import applications

    world = uc_world

    with pytest.raises(ConflictError):
        applications.transition(
            application_id=world["application"].pk,
            to_status="selected",
            actor=world["tpo"],
        )

    world["application"].refresh_from_db()
    assert world["application"].status == "submitted"


def test_pcms_tc_033_tpo_schedules_and_tracks_interview_progress(uc_world):
    """test_id=PCMS-TC-033; source_id=PC-UC-009 Main Success Scenario"""
    from modules.placement.models import RoundParticipation
    from modules.placement.services import applications, interviews

    world = uc_world
    shortlisted = applications.transition(
        application_id=world["application"].pk,
        to_status="under_review",
        actor=world["tpo"],
    )
    shortlisted = applications.transition(
        application_id=shortlisted.pk,
        to_status="shortlisted",
        actor=world["tpo"],
    )
    round_ = interviews.schedule_round(
        posting_id=world["posting"].pk,
        actor=world["tpo"],
        mode="online",
        starts_at=timezone.now() + timedelta(hours=4),
        meeting_url="https://meet.example.test/uc",
    )
    interviews.add_candidates(
        round_id=round_.pk,
        application_ids=[shortlisted.pk],
        actor=world["tpo"],
    )

    participation = RoundParticipation.objects.get(round=round_)
    assert participation.application_id == shortlisted.pk


def test_pcms_tc_034_interview_without_required_details_is_refused(
        uc_world):
    """test_id=PCMS-TC-034; source_id=PC-UC-009 Exception E1"""
    from core.api.exceptions import ConflictError
    from modules.placement.services import interviews

    world = uc_world
    with pytest.raises(ConflictError):
        interviews.schedule_round(
            posting_id=world["posting"].pk,
            actor=world["tpo"],
            mode="offline",
            starts_at=timezone.now() + timedelta(hours=2),
        )

    from modules.placement.models import InterviewRound

    assert not InterviewRound.objects.filter(posting=world["posting"]).exists()


def test_pcms_tc_035_interview_scope_excludes_unrelated_posting(uc_world):
    """test_id=PCMS-TC-035; source_id=PC-UC-009 Exception E2"""
    from core.api.exceptions import NotFoundError
    from modules.placement.models import JobPosting
    from modules.placement.services import interviews

    world = uc_world
    with pytest.raises(NotFoundError):
        interviews.schedule_round(
            posting_id=world["posting"].pk,
            actor=world["tpo"],
            mode="online",
            starts_at=timezone.now() + timedelta(hours=2),
            meeting_url="https://meet.example.test/uc",
            scope=JobPosting.objects.none(),
        )

    from modules.placement.models import InterviewRound

    assert not InterviewRound.objects.filter(posting=world["posting"]).exists()


def test_pcms_tc_036_offer_acceptance_records_placement_outcome(uc_world):
    """test_id=PCMS-TC-036; source_id=PC-UC-010 Main Success Scenario"""
    from modules.placement.models import PlacementRecord
    from modules.placement.services import offers

    world = uc_world
    offer = _issue_uc_offer(world)
    offers.respond(offer_id=offer.pk, accept=True, actor=world["student"])

    record = PlacementRecord.objects.get(user_id=world["student"].user_id)
    assert record.is_active
    assert record.offer_id == offer.pk


def test_pcms_tc_037_tpo_updates_alumni_placement_record(uc_world):
    """test_id=PCMS-TC-037; source_id=PC-UC-010 Alternative A1"""
    from decimal import Decimal

    from modules.placement.services import clearance

    world = uc_world
    record = clearance.record_off_campus(
        season=world["policy"].season,
        user_id=5001,
        company_id=world["company"].pk,
        ctc_lpa=Decimal("20.00"),
        actor=world["tpo"],
    )

    updated = clearance.update_record(
        record_id=record.pk, actor=world["tpo"], ctc_lpa=Decimal("25.00"))

    assert updated.user_id == 5001
    assert updated.ctc_lpa == Decimal("25.00")


def test_pcms_tc_038_unauthorized_placement_record_update_is_refused(
        uc_world):
    """test_id=PCMS-TC-038; source_id=PC-UC-010 Exception E1"""
    from core.api.exceptions import PermissionDeniedError
    from modules.placement.services import clearance

    world = uc_world
    record = clearance.record_off_campus(
        season=world["policy"].season,
        user_id=5001,
        company_id=world["company"].pk,
        ctc_lpa="20.00",
        actor=world["tpo"],
    )
    unauthorized = make_principal(user_id=10, kind="staff", permissions=())

    with pytest.raises(PermissionDeniedError):
        clearance.update_record(
            record_id=record.pk, actor=unauthorized, ctc_lpa="30.00")

    record.refresh_from_db()
    assert record.ctc_lpa == 20
    assert record.is_active


def test_pcms_tc_039_staff_generates_placement_analytics():
    """test_id=PCMS-TC-039; source_id=PC-UC-011 Main Success Scenario"""
    policy = PlacementPolicy.objects.create(season="2026-27")
    result = stats.staff_view(season=policy.season)

    assert result["season"] == policy.season
    assert result["available"] is True


def test_pcms_tc_040_alternate_supported_report_preserves_placement_data():
    """test_id=PCMS-TC-040; source_id=PC-UC-011 Alternative A1"""
    policy = PlacementPolicy.objects.create(season="2026-27")
    before = Company.objects.count()

    report = stats.staff_view(season=policy.season)

    assert report["season"] == policy.season
    assert Company.objects.count() == before


def test_pcms_tc_041_report_without_tpo_permission_exposes_no_staff_data(
        stub_iam, uc_world):
    """test_id=PCMS-TC-041; source_id=PC-UC-011 Exception E1"""
    stub_iam(make_session(
        user_id=20,
        kind="staff",
        active_role="staff",
        modules=("placement_cell",),
        permissions=(),
    ))
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION="Token abc")

    response = client.get("/api/v1/placement/stats")

    assert response.status_code == 200
    assert "by_company" not in response.json()
    assert "user_id" not in response.json()


def test_pcms_tc_042_chairman_can_view_summarized_placement_data(
        stub_iam, uc_world):
    """test_id=PCMS-TC-042; source_id=PC-UC-012 Main Success Scenario"""
    stub_iam(make_session(
        user_id=11,
        kind="staff",
        roles=("placement_chairman",),
        active_role="placement_chairman",
        modules=("placement_cell",),
        permissions=("placement_cell.report.view",),
    ))
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION="Token abc")

    response = client.get("/api/v1/placement/stats?season=2026-27")

    assert response.status_code == 200
    assert "season" in response.json()


def test_pcms_tc_043_non_oversight_role_gets_no_staff_company_report(
        stub_iam, uc_world):
    """test_id=PCMS-TC-043; source_id=PC-UC-012 Exception E1"""
    stub_iam(make_session(
        user_id=20,
        kind="staff",
        active_role="staff",
        modules=("placement_cell",),
        permissions=(),
    ))
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION="Token abc")

    response = client.get("/api/v1/placement/stats?season=2026-27")

    assert response.status_code == 200
    assert "by_company" not in response.json()


def _recruiter_actor(company_id, account_id=701):
    from types import SimpleNamespace

    return SimpleNamespace(
        kind="recruiter", account_id=account_id, company_id=company_id,
        user_id=None, permissions=frozenset(),
        has_permission=lambda _permission: False)


def test_pcms_tc_046_company_registration_records_external_approval():
    """test_id=PCMS-TC-046; source_id=PC-UC-014 Main Success Scenario"""
    from modules.placement.services import companies

    company = companies.register(
        name="UC Registration Co", sector="software",
        website="https://uc.example.test", hq_city="Bhopal")
    actor = make_principal(
        user_id=9, kind="staff", permissions=("placement_cell.company.manage",))
    approved = companies.approve(
        company_id=company.pk, actor=actor, note="External approval recorded.")

    assert Company.objects.filter(pk=approved.pk).exists()
    assert approved.approval_status == "approved"
    assert approved.can_operate


def test_pcms_tc_047_registration_without_approval_keeps_functions_unavailable():
    """test_id=PCMS-TC-047; source_id=PC-UC-014 Alternative A1"""
    from modules.placement.services import companies

    company = companies.register(name="UC Pending Co")

    assert Company.objects.filter(pk=company.pk).exists()
    assert not company.can_operate


def test_pcms_tc_048_incomplete_company_registration_is_rejected(
        stub_iam):
    """test_id=PCMS-TC-048; source_id=PC-UC-014 Exception E1"""
    before = Company.objects.count()
    stub_iam(make_session(
        user_id=700,
        kind="staff",
        modules=("placement_cell",),
        permissions=(),
    ))
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION="Token abc")

    response = client.post("/api/v1/placement/companies", {}, format="json")

    assert response.status_code in (400, 422)
    assert Company.objects.count() == before


def test_pcms_tc_049_recruiter_can_publish_authorized_opportunity(uc_world):
    """test_id=PCMS-TC-049; source_id=PC-UC-015 Main Success Scenario; PC-UC-015 Alternative A1"""
    from modules.placement.services import postings

    world = uc_world
    recruiter = _recruiter_actor(world["company"].pk)
    posting = postings.create(
        company_id=world["company"].pk,
        placement_year=world["policy"].season,
        actor=recruiter,
        title="Direct UC Posting",
        description="Role details.",
        eligibility_rule={"gte": ["cpi", 7.0]},
        closes_at=timezone.now() + timedelta(days=3),
    )

    published = postings.publish(posting_id=posting.pk, actor=recruiter)

    assert published.status == "published"
    assert published.kind == "fte"


def test_pcms_tc_050_recruiter_can_submit_posting_for_tpo_management(
        uc_world):
    """test_id=PCMS-TC-050; source_id=PC-UC-015 Alternative A2"""
    from modules.placement.services import postings

    world = uc_world
    recruiter = _recruiter_actor(world["company"].pk)
    posting = postings.create(
        company_id=world["company"].pk,
        placement_year=world["policy"].season,
        actor=recruiter,
        title="Managed UC Posting",
        description="Role details.",
        eligibility_rule={"gte": ["cpi", 7.0]},
        closes_at=timezone.now() + timedelta(days=3),
    )

    assert posting.status == "draft"
    assert not posting.applications.exists()


def test_pcms_tc_051_incomplete_recruiter_posting_cannot_publish(uc_world):
    """test_id=PCMS-TC-051; source_id=PC-UC-015 Exception E1"""
    from core.api.exceptions import ConflictError
    from modules.placement.services import postings

    world = uc_world
    recruiter = _recruiter_actor(world["company"].pk)
    draft = postings.create(
        company_id=world["company"].pk,
        placement_year=world["policy"].season,
        actor=recruiter,
        title="Incomplete Recruiter Posting",
        description="",
        eligibility_rule={},
        closes_at=timezone.now() + timedelta(days=3),
    )

    with pytest.raises(ConflictError):
        postings.publish(posting_id=draft.pk, actor=recruiter)

    draft.refresh_from_db()
    assert draft.status == "draft"


def test_pcms_tc_052_unauthorized_recruiter_cannot_publish_or_create(
        uc_world):
    """test_id=PCMS-TC-052; source_id=PC-UC-015 Exception E2"""
    from core.api.exceptions import PermissionDeniedError
    from modules.placement.models import JobPosting
    from modules.placement.services import postings

    world = uc_world
    actor = make_principal(user_id=800, kind="staff", permissions=())
    before = JobPosting.objects.count()

    with pytest.raises(PermissionDeniedError):
        postings.create(
            company_id=world["company"].pk,
            placement_year=world["policy"].season,
            actor=actor,
            title="Unauthorized Posting",
            description="Role.",
            eligibility_rule={},
            closes_at=timezone.now() + timedelta(days=3),
        )

    assert JobPosting.objects.count() == before


def test_pcms_tc_053_recruiter_records_shortlist_for_own_opportunity(
        uc_world):
    """test_id=PCMS-TC-053; source_id=PC-UC-016 Main Success Scenario"""
    from modules.placement.models import ApplicationTransition
    from modules.placement.services import applications

    world = uc_world
    recruiter = _recruiter_actor(world["company"].pk)
    scope = Application.objects.filter(posting__company=world["company"])
    applications.transition(
        application_id=world["application"].pk,
        to_status="under_review", actor=recruiter, scope=scope)
    updated = applications.transition(
        application_id=world["application"].pk,
        to_status="shortlisted", actor=recruiter, scope=scope)

    assert updated.status == "shortlisted"
    assert ApplicationTransition.objects.filter(
        application=updated, to_status="shortlisted").exists()


def test_pcms_tc_054_recruiter_records_external_rejection_update(
        uc_world):
    """test_id=PCMS-TC-054; source_id=PC-UC-016 Alternative A1"""
    from modules.placement.services import applications

    world = uc_world
    recruiter = _recruiter_actor(world["company"].pk)
    scope = Application.objects.filter(posting__company=world["company"])
    updated = applications.transition(
        application_id=world["application"].pk,
        to_status="rejected", actor=recruiter, scope=scope,
        reason="External decision recorded.")

    assert updated.status == "rejected"


def test_pcms_tc_055_recruiter_cannot_access_unrelated_applications(
        uc_world):
    """test_id=PCMS-TC-055; source_id=PC-UC-016 Exception E1"""
    from core.api.exceptions import NotFoundError
    from modules.placement.models import Application
    from modules.placement.services import applications

    world = uc_world
    foreign = Application.objects.create(
        posting=world["posting"], user_id=2002, status="submitted")
    scope = Application.objects.filter(user_id=1001)

    with pytest.raises(NotFoundError):
        applications.transition(
            application_id=foreign.pk, to_status="under_review",
            actor=_recruiter_actor(world["company"].pk), scope=scope)

    foreign.refresh_from_db()
    assert foreign.status == "submitted"


def test_pcms_tc_056_recruiter_read_does_not_record_hiring_decision(
        stub_iam, uc_world):
    """test_id=PCMS-TC-056; source_id=PC-UC-016 Exception E2"""
    from modules.placement.models import Offer

    world = uc_world
    before = world["application"].status
    stub_iam(make_session(
        user_id=9,
        kind="staff",
        roles=("tpo",),
        active_role="tpo",
        modules=("placement_cell",),
        permissions=("placement_cell.application.view",),
    ))
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION="Token abc")

    response = client.get(
        f"/api/v1/placement/applications?posting={world['posting'].pk}")

    assert response.status_code == 200
    world["application"].refresh_from_db()
    assert world["application"].status == before
    assert not Offer.objects.filter(application=world["application"]).exists()


def test_pcms_tc_062_recruiter_schedules_shortlisted_candidate_interview(
        uc_world):
    """test_id=PCMS-TC-062; source_id=PC-UC-021 Main Success Scenario"""
    from modules.placement.models import InterviewRound, RoundParticipation
    from modules.placement.services import interviews

    world = uc_world
    app = world["application"]
    app.status = "shortlisted"
    app.save(update_fields=["status"])
    recruiter = _recruiter_actor(world["company"].pk)
    round_ = interviews.schedule_round(
        posting_id=world["posting"].pk,
        actor=recruiter,
        mode="online",
        starts_at=timezone.now() + timedelta(hours=3),
        meeting_url="https://meet.example.test/recruiter",
        scope=JobPosting.objects.filter(company=world["company"]),
    )
    interviews.add_candidates(
        round_id=round_.pk,
        application_ids=[app.pk],
        actor=recruiter,
        scope=Application.objects.filter(posting__company=world["company"]),
    )

    assert InterviewRound.objects.filter(pk=round_.pk).exists()
    assert RoundParticipation.objects.filter(
        round=round_, application=app).exists()


def test_pcms_tc_063_company_interview_missing_details_is_refused(uc_world):
    """test_id=PCMS-TC-063; source_id=PC-UC-021 Exception E1"""
    from core.api.exceptions import ConflictError
    from modules.placement.models import InterviewRound
    from modules.placement.services import interviews

    world = uc_world
    before = InterviewRound.objects.count()
    with pytest.raises(ConflictError):
        interviews.schedule_round(
            posting_id=world["posting"].pk,
            actor=_recruiter_actor(world["company"].pk),
            mode="online",
            starts_at=timezone.now() + timedelta(hours=2),
            meeting_url="",
            scope=JobPosting.objects.filter(company=world["company"]),
        )

    assert InterviewRound.objects.count() == before


def test_pcms_tc_064_recruiter_cannot_schedule_outside_company_scope(
        uc_world):
    """test_id=PCMS-TC-064; source_id=PC-UC-021 Exception E2"""
    from core.api.exceptions import NotFoundError
    from modules.placement.models import InterviewRound, JobPosting
    from modules.placement.services import interviews

    world = uc_world
    before = InterviewRound.objects.count()
    with pytest.raises(NotFoundError):
        interviews.schedule_round(
            posting_id=world["posting"].pk,
            actor=_recruiter_actor(world["company"].pk),
            mode="online",
            starts_at=timezone.now() + timedelta(hours=2),
            meeting_url="https://meet.example.test/out-of-scope",
            scope=JobPosting.objects.none(),
        )

    assert InterviewRound.objects.count() == before


def test_pcms_tc_065_recruiter_extends_offer_for_own_opportunity(uc_world):
    """test_id=PCMS-TC-065; source_id=PC-UC-022 Main Success Scenario"""
    from modules.placement.models import Application, NotificationOutbox
    from modules.placement.services import offers

    world = uc_world
    app = world["application"]
    app.status = "selected"
    app.save(update_fields=["status"])
    scope = Application.objects.filter(posting__company=world["company"])
    offer = offers.issue(
        application_id=app.pk,
        actor=_recruiter_actor(world["company"].pk),
        scope=scope,
    )

    assert offer.status == "issued"
    assert offer.respond_by > timezone.now()
    assert NotificationOutbox.objects.filter(
        topic="offer.issued", recipient_user_id=app.user_id).exists()


def test_pcms_tc_066_recruiter_cannot_extend_offer_outside_scope(uc_world):
    """test_id=PCMS-TC-066; source_id=PC-UC-022 Exception E1"""
    from core.api.exceptions import NotFoundError
    from modules.placement.models import Application, Offer
    from modules.placement.services import offers

    world = uc_world
    foreign = Application.objects.create(
        posting=world["posting"], user_id=2002, status="selected")
    scope = Application.objects.filter(user_id=1001)

    with pytest.raises(NotFoundError):
        offers.issue(
            application_id=foreign.pk,
            actor=_recruiter_actor(world["company"].pk),
            scope=scope,
        )

    assert not Offer.objects.filter(application=foreign).exists()


def test_pcms_tc_067_reading_candidate_does_not_make_hiring_decision(
        stub_iam, uc_world):
    """test_id=PCMS-TC-067; source_id=PC-UC-022 Exception E2"""
    from modules.placement.models import Offer

    world = uc_world
    stub_iam(make_session(
        user_id=9,
        kind="staff",
        roles=("tpo",),
        active_role="tpo",
        modules=("placement_cell",),
        permissions=("placement_cell.application.view",),
    ), users={1001: world["identity"]})
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION="Token abc")

    response = client.get(
        f"/api/v1/placement/applications?posting={world['posting'].pk}")

    assert response.status_code == 200
    assert not Offer.objects.filter(application=world["application"]).exists()
    world["application"].refresh_from_db()
    assert world["application"].status == "submitted"


def test_pcms_tc_004_student_cannot_access_another_students_profile(stub_iam):
    """test_id=PCMS-TC-004; source_id=PC-UC-001 Exception E2"""
    stub_iam(make_session(
        user_id=1001,
        kind="student",
        modules=("placement_cell",),
        permissions=("placement_cell.application.view_self",),
    ))
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION="Token abc")

    response = client.get("/api/v1/placement/profiles/2002")

    assert response.status_code == 404


def test_pcms_tc_005_student_browses_posting_details_without_mutation(
        stub_iam):
    """test_id=PCMS-TC-005; source_id=PC-UC-002 Main Success Scenario"""
    posting = _published_posting()
    stub_iam(make_session(
        user_id=1001,
        kind="student",
        modules=("placement_cell",),
        permissions=(VIEW_POSTING,),
    ))
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION="Token abc")
    before = posting.applications.count()

    response = client.get(f"/api/v1/placement/postings/{posting.pk}")

    assert response.status_code == 200
    details = response.json()
    assert details["title"] == posting.title
    assert details["description"] == posting.description
    assert details["eligibility_rule"] == posting.eligibility_rule
    assert details["closes_at"]
    assert posting.applications.count() == before


def test_pcms_tc_006_student_sees_empty_opportunity_list(stub_iam):
    """test_id=PCMS-TC-006; source_id=PC-UC-002 Alternative A1"""
    stub_iam(make_session(
        user_id=1001,
        kind="student",
        modules=("placement_cell",),
        permissions=(VIEW_POSTING,),
    ))
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION="Token abc")

    response = client.get("/api/v1/placement/postings")

    assert response.status_code == 200
    assert response.json()["results"] == []


def test_pcms_tc_007_student_cannot_read_out_of_scope_draft_posting(
        stub_iam):
    """test_id=PCMS-TC-007; source_id=PC-UC-002 Exception E1"""
    posting = _published_posting()
    JobPosting.objects.filter(pk=posting.pk).update(status="draft")
    stub_iam(make_session(
        user_id=1001,
        kind="student",
        modules=("placement_cell",),
        permissions=(VIEW_POSTING,),
    ))
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION="Token abc")

    response = client.get(f"/api/v1/placement/postings/{posting.pk}")

    assert response.status_code == 404
    posting.refresh_from_db()
    assert posting.status == "draft"


def test_pcms_tc_001_student_profile_data_and_document_are_available(
        stub_iam):
    """test_id=PCMS-TC-001; source_id=PC-UC-001 Main Success Scenario"""
    from fusion_auth.client import UserRef
    from modules.placement.models import ProfileDocument

    identity = UserRef(
        user_id=1001,
        username="21UC001",
        display_name="UC Profile Student",
        kind="student",
        email="student@example.test",
        programme="B.Tech",
        discipline="CSE",
        batch_year=2023,
        resume_link="https://erp.example.test/resume/1001",
        profile_completed=True,
        extra={"skills": ["Python"], "achievements": ["Hackathon"]},
    )
    stub_iam(make_session(
        user_id=1001,
        kind="student",
        modules=("placement_cell",),
        permissions=("placement_cell.application.view_self",),
    ), users={1001: identity})
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION="Token abc")
    doc = client.post("/api/v1/placement/documents", {
        "kind": "certificate",
        "url": "https://drive.google.com/file/d/1A2b3C4d5E6f7G8h9I0jKlMnOpQrStUv/view",
        "title": "Academic certificate",
    }, format="json")
    profile = client.get("/api/v1/placement/profile/resume")

    assert doc.status_code == 201
    assert ProfileDocument.objects.filter(user_id=1001, is_active=True).exists()
    assert profile.status_code == 200
    assert profile.json()["profile_completed"] is True
    assert profile.json()["resume_link"] == identity.resume_link


def test_pcms_tc_002_student_updates_only_document_section(stub_iam):
    """test_id=PCMS-TC-002; source_id=PC-UC-001 Alternative A1"""
    from fusion_auth.client import UserRef
    from modules.placement.models import ProfileDocument

    identity = UserRef(
        user_id=1001,
        username="21UC001",
        display_name="UC Profile Student",
        kind="student",
        profile_completed=True,
        extra={"skills": ["Python"]},
    )
    stub_iam(make_session(
        user_id=1001,
        kind="student",
        modules=("placement_cell",),
        permissions=("placement_cell.application.view_self",),
    ), users={1001: identity})
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION="Token abc")
    client.post("/api/v1/placement/documents", {
        "kind": "certificate",
        "url": "https://drive.google.com/file/d/1A2b3C4d5E6f7G8h9I0jKlMnOpQrStUv/view",
        "title": "Certificate",
    }, format="json")
    before = ProfileDocument.objects.filter(user_id=1001).count()

    response = client.post("/api/v1/placement/documents", {
        "kind": "other",
        "url": "https://drive.google.com/file/d/2B3c4D5e6F7g8H9i0J1kLmNoPqRsTuVw/view",
        "title": "Achievement record",
    }, format="json")

    assert response.status_code == 201
    assert ProfileDocument.objects.filter(user_id=1001).count() == before + 1
    assert identity.extra["skills"] == ["Python"]


def test_pcms_tc_003_invalid_profile_document_is_rejected_without_replacing_valid_data(
        stub_iam):
    """test_id=PCMS-TC-003; source_id=PC-UC-001 Exception E1"""
    from modules.placement.models import ProfileDocument

    stub_iam(make_session(
        user_id=1001,
        kind="student",
        modules=("placement_cell",),
        permissions=("placement_cell.application.view_self",),
    ))
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION="Token abc")
    valid = client.post("/api/v1/placement/documents", {
        "kind": "certificate",
        "url": "https://drive.google.com/file/d/1A2b3C4d5E6f7G8h9I0jKlMnOpQrStUv/view",
        "title": "Valid certificate",
    }, format="json")
    assert valid.status_code == 201
    previous_id = valid.json()["id"]

    invalid = client.post("/api/v1/placement/documents", {
        "kind": "unknown",
        "url": "not-a-drive-link",
    }, format="json")

    assert invalid.status_code in (400, 422)
    assert ProfileDocument.objects.filter(
        pk=previous_id, user_id=1001, is_active=True).exists()
    assert ProfileDocument.objects.filter(user_id=1001, is_active=True).count() == 1


def test_pcms_tc_068_student_resume_view_returns_structured_saved_profile(
        stub_iam):
    """test_id=PCMS-TC-068; source_id=PC-UC-023 Main Success Scenario"""
    from fusion_auth.client import UserRef

    identity = UserRef(
        user_id=1001,
        username="21UC001",
        display_name="UC Resume Student",
        kind="student",
        email="student@example.test",
        programme="B.Tech",
        discipline="CSE",
        batch_year=2023,
        resume_link="https://erp.example.test/resume/1001",
        profile_completed=True,
    )
    stub_iam(make_session(
        user_id=1001,
        kind="student",
        modules=("placement_cell",),
        permissions=("placement_cell.application.view_self",),
    ), users={1001: identity})
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION="Token abc")

    response = client.get("/api/v1/placement/profile/resume")

    assert response.status_code == 200
    resume = response.json()
    assert resume["name"] == identity.display_name
    assert resume["programme"] == identity.programme
    assert resume["discipline"] == identity.discipline
    assert resume["resume_link"] == identity.resume_link


def test_pcms_tc_069_incomplete_profile_is_reported_without_mutation(stub_iam):
    """test_id=PCMS-TC-069; source_id=PC-UC-023 Exception E1"""
    from fusion_auth.client import UserRef

    identity = UserRef(
        user_id=1001,
        username="21UC001",
        display_name="UC Resume Student",
        kind="student",
        profile_completed=False,
        resume_link="",
    )
    stub_iam(make_session(
        user_id=1001,
        kind="student",
        modules=("placement_cell",),
        permissions=("placement_cell.application.view_self",),
    ), users={1001: identity})
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION="Token abc")

    response = client.get("/api/v1/placement/profile/resume")

    assert response.status_code == 200
    assert response.json()["profile_completed"] is False
    assert response.json()["resume_link"] == ""
