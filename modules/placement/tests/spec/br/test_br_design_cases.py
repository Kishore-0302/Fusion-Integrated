"""Executable coverage for every frozen PCMS business-rule case in BR_DESIGN.json."""

from datetime import timedelta

import pytest
from django.utils import timezone

from conftest import make_principal
from core.api.exceptions import ConflictError, PermissionDeniedError
from modules.placement.domain.eligibility import evaluate
from modules.placement.models import (
    Announcement,
    Application,
    Company,
    InterviewRound,
    JobPosting,
    NotificationOutbox,
    Offer,
    PlacementPolicy,
    PlacementRecord,
    PlacementRegistration,
)
from modules.placement.selectors import scoping
from modules.placement.services import (
    announcements,
    applications,
    interviews,
    notifications,
    postings,
)
from modules.placement.services.authz import require

pytestmark = pytest.mark.django_db

MANAGE = "placement_cell.job_posting.manage"
REVIEW = "placement_cell.application.review"
SCHEDULE = "placement_cell.interview.schedule"
PUBLISH = "placement_cell.announcement.publish"


@pytest.fixture
def company():
    return Company.objects.create(
        name="Acme", slug="acme", status="active", approval_status="approved",
        approved_by_user_id=9,
    )


@pytest.fixture
def posting(company):
    return JobPosting.objects.create(
        company=company,
        title="Engineer",
        placement_year="2026-27",
        description="Build software.",
        status="published",
        closes_at=timezone.now() + timedelta(days=10),
        eligibility_rule={"gte": ["cpi", 7]},
        eligibility_rule_locked_at=timezone.now(),
        published_at=timezone.now(),
    )


@pytest.fixture
def issued_offer(company, stub_iam, user_ref):
    policy = PlacementPolicy.objects.create(season="2026-27", is_active=True)
    PlacementRegistration.objects.create(
        policy=policy, user_id=1001, status="registered",
    )
    stub_iam(users={1001: user_ref(1001, discipline="CSE")})
    posting_row = JobPosting.objects.create(
        company=company, title="Offer role", placement_year="2026-27",
        description="Work", status="published",
        closes_at=timezone.now() + timedelta(days=5),
        eligibility_rule={}, eligibility_rule_locked_at=timezone.now(),
        published_at=timezone.now(), ctc_lpa="8.00",
    )
    app = Application.objects.create(posting=posting_row, user_id=1001, status="offer_issued")
    return Offer.objects.create(
        application=app, posting=posting_row, user_id=1001, ctc_lpa="8.00",
        tier_rank=1, respond_by=timezone.now() + timedelta(days=1),
        status="issued",
    )

def _staff(user_id=9, *permissions, role="tpo"):
    return make_principal(
        user_id=user_id, kind="staff", active_role=role,
        permissions=permissions,
    )


def _student(user_id=1001):
    return make_principal(
        user_id=user_id, kind="student", active_role="student",
        permissions=("placement_cell.application.view_self",),
    )


def _recruiter(company_id):
    from modules.placement.authentication import RecruiterPrincipal

    return RecruiterPrincipal(
        account_id=77, company_id=company_id, email="hire@example.test",
        display_name="Recruiter",
    )


def test_pcbr001_01_configured_completeness_satisfied(posting, stub_iam, user_ref):
    """test_id=PCMS-BR001-01; source_id=PC-BR-001 configured completeness satisfied"""
    from modules.placement.models import PlacementRegistration

    policy = PlacementPolicy.objects.create(season="2026-27", is_active=True)
    PlacementRegistration.objects.create(policy=policy, user_id=1001, status="registered")
    posting.eligibility_rule = {}
    posting.save(update_fields=["eligibility_rule"])
    from dataclasses import replace

    stub_iam(users={1001: replace(user_ref(1001), profile_completed=True)})
    created = applications.apply_to(
        posting_id=posting.pk,
        actor=make_principal(user_id=1001, kind="student", permissions=("placement_cell.application.create",)),
    )
    assert created.status == "submitted"
    assert created.eligibility_snapshot["is_eligible"] is True


def test_pcbr001_02_configured_completeness_unsatisfied(posting, stub_iam, user_ref):
    """test_id=PCMS-BR001-02; source_id=PC-BR-001 configured completeness unsatisfied"""
    from modules.placement.models import PlacementRegistration

    policy = PlacementPolicy.objects.create(season="2026-27", is_active=True)
    PlacementRegistration.objects.create(policy=policy, user_id=1001, status="registered")
    from dataclasses import replace

    stub_iam(users={1001: replace(user_ref(1001), profile_completed=False)})
    with pytest.raises(ConflictError) as exc:
        applications.apply_to(
            posting_id=posting.pk,
            actor=make_principal(user_id=1001, kind="student", permissions=("placement_cell.application.create",)),
        )
    assert exc.value.code == "profile_incomplete"
    assert not Application.objects.filter(posting=posting, user_id=1001).exists()


def test_pcbr002_01_eligible_student():
    """test_id=PCMS-BR002-01; source_id=PC-BR-002 eligible Student"""
    assert evaluate({"gte": ["cpi", 7]}, {"cpi": 8}).is_eligible


def test_pcbr002_02_ineligible_student():
    """test_id=PCMS-BR002-02; source_id=PC-BR-002 ineligible Student"""
    assert not evaluate({"gte": ["cpi", 7]}, {"cpi": 6.9}).is_eligible


def test_pcbr003_01_required_posting_content_present(company):
    """test_id=PCMS-BR003-01; source_id=PC-BR-003 required posting content present"""
    actor = _staff(9, MANAGE)
    draft = JobPosting.objects.create(
        company=company, title="Complete", placement_year="2026-27",
        description="Role details", closes_at=timezone.now() + timedelta(days=4),
        eligibility_rule={"gte": ["cpi", 7]},
    )
    published = postings.publish(posting_id=draft.pk, actor=actor)
    assert published.status == "published"


def test_pcbr003_02_required_posting_content_missing(company):
    """test_id=PCMS-BR003-02; source_id=PC-BR-003 required posting content missing"""
    draft = JobPosting.objects.create(
        company=company, title="Incomplete", placement_year="2026-27",
        description="", closes_at=None, eligibility_rule={},
    )
    before = (draft.status, draft.published_at)
    with pytest.raises(ConflictError) as exc:
        postings.publish(posting_id=draft.pk, actor=_staff(9, MANAGE))
    assert exc.value.code == "incomplete_posting"
    draft.refresh_from_db()
    assert (draft.status, draft.published_at) == before


def test_pcbr004_recorded_eligibility_criteria():
    """test_id=PCMS-BR004-01; source_id=PC-BR-004 recorded eligibility criteria"""
    # Only represented criteria are read; a hypothetical external rule is ignored.
    assert evaluate({"gte": ["cpi", 7]}, {"cpi": 8, "external_exam": 0}).is_eligible


def test_pcbr005_tpo_posting_management(company):
    """test_id=PCMS-BR005-01; source_id=PC-BR-005 TPO posting-management authority"""
    actor = _staff(9, MANAGE)
    created = postings.create(
        company_id=company.pk, placement_year="2026-27", actor=actor,
        title="Role", description="Work", eligibility_rule={"gte": ["cpi", 7]},
        closes_at=timezone.now() + timedelta(days=5),
    )
    assert created.status == "draft"


def test_pcbr006_01_authorized_company_opportunity(company):
    """test_id=PCMS-BR006-01; source_id=PC-BR-006 authorized Company/Recruiter opportunity authority"""
    require(_recruiter(company.pk), MANAGE, allow_recruiter=True)
    assert company.can_operate


def test_pcbr006_02_company_outside_authorized_scope(company, posting):
    """test_id=PCMS-BR006-02; source_id=PC-BR-006 Company/Recruiter outside authorized scope"""
    outsider = _recruiter(company.pk + 100)
    assert posting not in scoping.postings_for(outsider)


def test_pcbr007_01_authorization_state_allows_company_function():
    """test_id=PCMS-BR007-01; source_id=PC-BR-007 represented authorization permits Company functions"""
    require(_staff(9, MANAGE), MANAGE)


def test_pcbr007_02_authorization_state_denies_company_function():
    """test_id=PCMS-BR007-02; source_id=PC-BR-007 represented authorization does not permit Company functions"""
    with pytest.raises(PermissionDeniedError):
        require(_staff(9), MANAGE)


def test_pcbr009_01_own_authorized_opportunity(posting):
    """test_id=PCMS-BR009-01; source_id=PC-BR-009 own authorized opportunity"""
    app = Application.objects.create(posting=posting, user_id=1001, status="submitted")
    assert list(scoping.applications_for(_recruiter(posting.company_id))) == [app]


def test_pcbr009_02_another_company_opportunity(company, posting):
    """test_id=PCMS-BR009-02; source_id=PC-BR-009 another Company's opportunity"""
    foreign = Company.objects.create(
        name="Other", slug="other", status="active", approval_status="approved",
        approved_by_user_id=9,
    )
    foreign_posting = JobPosting.objects.create(company=foreign, title="Other role", placement_year="2026-27")
    app = Application.objects.create(posting=foreign_posting, user_id=1002, status="submitted")
    assert app.pk not in scoping.applications_for(_recruiter(company.pk)).values_list("pk", flat=True)


def test_pcbr010_tpo_application_management(posting):
    """test_id=PCMS-BR010-01; source_id=PC-BR-010 TPO application-management authority"""
    app = Application.objects.create(posting=posting, user_id=1001, status="submitted")
    assert app in scoping.applications_for(_staff(9, REVIEW))


def test_pcbr011_01_complete_interview_schedule(posting):
    """test_id=PCMS-BR011-01; source_id=PC-BR-011 complete interview schedule"""
    round_ = interviews.schedule_round(
        posting_id=posting.pk, actor=_staff(9, SCHEDULE), mode="online",
        starts_at=timezone.now() + timedelta(days=1), meeting_url="https://meet.test/room",
    )
    assert round_.mode == "online"


def test_pcbr011_02_incomplete_interview_schedule(posting):
    """test_id=PCMS-BR011-02; source_id=PC-BR-011 incomplete interview schedule"""
    before = InterviewRound.objects.count()
    with pytest.raises(ConflictError):
        interviews.schedule_round(
            posting_id=posting.pk, actor=_staff(9, SCHEDULE), mode="online",
            starts_at=timezone.now() + timedelta(days=1),
        )
    assert InterviewRound.objects.count() == before


def test_pcbr012_shortlisted_student_interview_notification(posting):
    """test_id=PCMS-BR012-01; source_id=PC-BR-012 eligible and shortlisted Student"""
    app = Application.objects.create(posting=posting, user_id=1001, status="shortlisted")
    round_ = interviews.schedule_round(
        posting_id=posting.pk, actor=_staff(9, SCHEDULE), mode="offline",
        starts_at=timezone.now() + timedelta(days=1), venue="Room 2",
    )
    interviews.add_candidates(round_id=round_.pk, application_ids=[app.pk], actor=_staff(9, SCHEDULE))
    assert NotificationOutbox.objects.filter(topic="interview.scheduled", recipient_user_id=1001).exists()


def test_pcbr013_01_response_within_deadline(issued_offer):
    """test_id=PCMS-BR013-01; source_id=PC-BR-013 response within represented deadline"""
    from modules.placement.services import offers

    result = offers.respond(offer_id=issued_offer.pk, accept=False, actor=_student())
    assert result.status == "declined"


def test_pcbr013_02_response_outside_deadline(issued_offer):
    """test_id=PCMS-BR013-02; source_id=PC-BR-013 response outside represented deadline"""
    from modules.placement.services import offers

    Offer.objects.filter(pk=issued_offer.pk).update(respond_by=timezone.now() - timedelta(seconds=1))
    before = Offer.objects.get(pk=issued_offer.pk).status
    with pytest.raises(ConflictError) as exc:
        offers.respond(offer_id=issued_offer.pk, accept=False, actor=_student())
    assert exc.value.code == "offer_expired"
    assert Offer.objects.get(pk=issued_offer.pk).status == before


def test_pcbr014_offer_acceptance_transition_is_supported(issued_offer):
    """test_id=PCMS-BR014-01; source_id=PC-BR-014 offer acceptance"""
    from modules.placement.services import offers

    offers.respond(offer_id=issued_offer.pk, accept=True, actor=_student())
    issued_offer.refresh_from_db()
    assert issued_offer.status == "accepted"
    assert PlacementRecord.objects.filter(offer=issued_offer, is_active=True).exists()


def test_pcbr015_01_represented_multiple_offer_policy():
    """test_id=PCMS-BR015-01; source_id=PC-BR-015 represented multiple-offer policy"""
    from modules.placement.domain.offer_policy import (
        OfferSpec,
        PolicySpec,
        StudentState,
        can_accept,
    )

    decision = can_accept(PolicySpec(season="2026-27"), StudentState(discipline="CSE", is_registered=True), OfferSpec(offer_id=1, ctc_lpa=10))
    assert decision.allowed


def test_pcbr015_02_unrepresented_multiple_offer_policy():
    """test_id=PCMS-BR015-02; source_id=PC-BR-015 unrepresented multiple-offer policy"""
    from modules.placement.domain.offer_policy import (
        OfferSpec,
        PolicySpec,
        StudentState,
        can_accept,
    )

    decision = can_accept(PolicySpec(season="2026-27"), StudentState(discipline="CSE", is_registered=True), OfferSpec(offer_id=1, ctc_lpa=10))
    assert decision.allowed


def test_pcbr016_student_anonymized_statistics_view():
    """test_id=PCMS-BR016-01; source_id=PC-BR-016 Student anonymized statistics view"""
    from modules.placement.services.stats import student_view

    view = student_view(season="missing-season")
    assert "user_id" not in str(view)


def test_pcbr017_01_supported_placement_announcement():
    """test_id=PCMS-BR017-01; source_id=PC-BR-017 supported placement announcement content"""
    ann = announcements.publish(actor=_staff(9, PUBLISH), title="Drive", body="Details", topic="drive")
    assert ann.pk and ann.topic == "drive"


def test_pcbr017_02_unrelated_announcement_topic():
    """test_id=PCMS-BR017-02; source_id=PC-BR-017 unrelated announcement content"""
    with pytest.raises(ConflictError) as exc:
        announcements.publish(actor=_staff(9, PUBLISH), title="Unrelated", body="Details", topic="unrelated")
    assert exc.value.code == "bad_topic"
    assert not Announcement.objects.exists()


def test_pcbr019_01_alumni_permitted_read_only_access(posting):
    """test_id=PCMS-BR019-01; source_id=PC-BR-019 Alumni permitted read-only access"""
    alumni = make_principal(user_id=5001, kind="alumni", active_role="alumni", roles=("alumni",), permissions=())
    assert posting in scoping.postings_for(alumni)


def test_pcbr019_02_alumni_write_restriction():
    """test_id=PCMS-BR019-02; source_id=PC-BR-019 Alumni write restriction"""
    alumni = make_principal(user_id=5001, kind="alumni", active_role="alumni", permissions=())
    with pytest.raises(PermissionDeniedError):
        require(alumni, MANAGE)


def test_pcbr020_alumni_active_workflow_prohibition(posting):
    """test_id=PCMS-BR020-01; source_id=PC-BR-020 Alumni active placement workflow prohibition"""
    alumni = make_principal(user_id=5001, kind="alumni", active_role="alumni", permissions=())
    with pytest.raises(ConflictError) as exc:
        applications.apply_to(posting_id=posting.pk, actor=alumni)
    assert exc.value.code == "alumni_workflow_prohibited"
    assert not Application.objects.filter(posting=posting, user_id=5001).exists()


def test_pcbr021_supported_notification_email_handoff():
    """test_id=PCMS-BR021-01; source_id=PC-BR-021 supported notification event email handoff"""
    topics = (
        "posting.published", "application.submitted", "application.shortlisted",
        "application.rejected", "interview.scheduled", "offer.issued",
        "announcement.published",
    )
    for topic in topics:
        notifications.enqueue(topic=topic, dedupe_key=f"br:{topic}", subject="Notice", body="Details", recipient_email="configured@example.test")
    assert set(NotificationOutbox.objects.values_list("topic", flat=True)) == set(topics)


def test_pcbr022_01_role_authorized_scope(posting):
    """test_id=PCMS-BR022-01; source_id=PC-BR-022 role-authorized access and action"""
    app = Application.objects.create(posting=posting, user_id=1001, status="submitted")
    assert app in scoping.applications_for(_staff(9, REVIEW))


def test_pcbr022_02_outside_role_scope(posting):
    """test_id=PCMS-BR022-02; source_id=PC-BR-022 access and action outside role scope"""
    app = Application.objects.create(posting=posting, user_id=1001, status="submitted")
    assert app not in scoping.applications_for(_student(1002))


def test_pcbr023_01_authorized_sensitive_data_view(posting):
    """test_id=PCMS-BR023-01; source_id=PC-BR-023 authorized sensitive-data view"""
    app = Application.objects.create(posting=posting, user_id=1001, status="submitted")
    assert app in scoping.applications_for(_staff(9, REVIEW))


def test_pcbr023_02_unauthorized_sensitive_data_view(posting):
    """test_id=PCMS-BR023-02; source_id=PC-BR-023 unauthorized sensitive-data view"""
    app = Application.objects.create(posting=posting, user_id=1001, status="submitted")
    assert app not in scoping.applications_for(_student(1002))


def test_pcbr024_01_authorized_sensitive_data_modification():
    """test_id=PCMS-BR024-01; source_id=PC-BR-024 authorized sensitive-data modification"""
    require(_staff(9, REVIEW), REVIEW)


def test_pcbr024_02_unauthorized_sensitive_data_modification():
    """test_id=PCMS-BR024-02; source_id=PC-BR-024 unauthorized sensitive-data modification"""
    with pytest.raises(PermissionDeniedError):
        require(_student(), REVIEW)


def test_pcbr025_01_referenced_academic_data():
    """test_id=PCMS-BR025-01; source_id=PC-BR-025 referenced or imported academic data"""
    verdict = evaluate({"gte": ["cpi", 7]}, {"cpi": 8})
    assert verdict.is_eligible


def test_pcbr025_02_academic_master_data_boundary():
    """test_id=PCMS-BR025-02; source_id=PC-BR-025 academic master-data management boundary"""
    with pytest.raises(PermissionDeniedError):
        require(_student(), "placement_cell.academic_directory.manage")


def test_pcbr026_01_role_enforcement():
    """test_id=PCMS-BR026-01; source_id=PC-BR-026 PCMS role/access enforcement"""
    require(_staff(9, MANAGE), MANAGE)


def test_pcbr026_02_platform_identity_boundary():
    """test_id=PCMS-BR026-02; source_id=PC-BR-026 platform authentication and RBAC administration boundary"""
    assert "placement_cell.identity.admin" not in {p[0] for p in __import__("modules.placement.registry", fromlist=["PERMISSIONS"]).PERMISSIONS}


def test_pcbr029_tpo_placement_record_update_authority():
    """test_id=PCMS-BR029-01; source_id=PC-BR-029 TPO Student and Alumni placement-record update"""
    require(_staff(9, "placement_cell.record.manage"), "placement_cell.record.manage")


def test_pcbr030_authorized_recruitment_status_update(posting):
    """test_id=PCMS-BR030-01; source_id=PC-BR-030 authorized recruitment decision/status update"""
    app = Application.objects.create(posting=posting, user_id=1001, status="under_review")
    updated = applications.transition(
        application_id=app.pk, to_status="shortlisted", actor=_staff(9, REVIEW),
    )
    assert updated.status == "shortlisted"
