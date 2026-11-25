"""Tests for Student 1 FR implementations:
- PC-AFR-010: Student-scoped status view
- PC-AFR-014: Multiple-offer policy representation
- PC-AFR-022: Skills criteria recording and evaluation
- PC-AFR-029: TPO interview progress view
- PC-AFR-030: TPO placement outcomes view
- PC-AFR-033: TPO success-rate report
- PC-AFR-034: Company participation trends
- PC-AFR-035: Salary package distribution
- PC-AFR-036: Employment trends across seasons
"""
from decimal import Decimal

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from conftest import make_session
from fusion_auth.client import UserRef
from modules.placement.domain import eligibility as elig
from modules.placement.domain import offer_policy as pol
from modules.placement.models import (
    Application,
    ApplicationTransition,
    Company,
    InterviewRound,
    JobPosting,
    Offer,
    PlacementPolicy,
    PlacementRecord,
    PlacementRegistration,
    RoundParticipation,
)
from modules.placement.services import applications as app_service
from modules.placement.services import clearance as clearance_service
from modules.placement.services import interviews as interview_service
from modules.placement.services import stats as stats_service

pytestmark = pytest.mark.django_db

SEASON = "2026-27"


@pytest.fixture
def setup_env():
    policy = PlacementPolicy.objects.create(season=SEASON, is_active=True)
    company = Company.objects.create(
        name="Acme Corp", slug="acme-corp", status="active",
        approval_status="approved", approved_by_user_id=1)
    posting = JobPosting.objects.create(
        company=company, title="Software Engineer", placement_year=SEASON,
        description="Engineering role", closes_at=timezone.now() + timezone.timedelta(days=7),
        eligibility_rule_locked_at=timezone.now(),
        ctc_lpa=Decimal("12.00"), status="published", created_by_user_id=1)
    return policy, company, posting


def test_pc_afr_010_student_status_view(stub_iam, setup_env, user_ref):
    """PC-AFR-010: Student tracks lifecycle states and placement record status."""
    policy, company, posting = setup_env
    user_id = 1001

    PlacementRegistration.objects.create(
        policy=policy, user_id=user_id, status="registered",
        registered_at=timezone.now())

    app = Application.objects.create(
        posting=posting, user_id=user_id, status="interview_scheduled")
    ApplicationTransition.objects.create(
        application=app, from_status="draft", to_status="submitted",
        actor_user_id=user_id, actor_label="student", reason="")
    ApplicationTransition.objects.create(
        application=app, from_status="submitted", to_status="shortlisted",
        actor_user_id=9, actor_label="staff", reason="Shortlisted")
    ApplicationTransition.objects.create(
        application=app, from_status="shortlisted", to_status="interview_scheduled",
        actor_user_id=9, actor_label="staff", reason="Scheduled")

    rnd = InterviewRound.objects.create(
        posting=posting, seq=1, kind="tech", mode="online",
        starts_at=timezone.now(), meeting_url="https://meet.google.com/xyz")
    RoundParticipation.objects.create(
        round=rnd, application=app, outcome="passed", score=Decimal("85.00"),
        remarks="Strong problem solving")

    offer = Offer.objects.create(
        application=app, posting=posting, user_id=user_id,
        ctc_lpa=Decimal("12.00"), status="issued",
        respond_by=timezone.now() + timezone.timedelta(days=3))

    rec = PlacementRecord.objects.create(
        policy=policy, user_id=user_id, company=company, posting=posting,
        offer=offer, ctc_lpa=Decimal("12.00"), source="campus", is_active=True)

    student_actor = make_session(
        user_id=user_id, modules=("placement_cell",),
        permissions=("placement_cell.application.view_self",))
    stub_iam(student_actor, users={user_id: user_ref(user_id)})

    status_data = app_service.student_status_view(user_id=user_id, actor=student_actor)

    assert status_data["user_id"] == user_id
    assert status_data["is_placed"] is True
    assert status_data["active_placement"]["company_name"] == "Acme Corp"
    assert status_data["active_placement"]["record_id"] == rec.pk

    assert len(status_data["applications"]) == 1
    assert len(status_data["applications"][0]["transitions"]) == 3
    # Student reader gets redacted reasons from transition history
    assert status_data["applications"][0]["transitions"][1]["reason"] == ""

    assert len(status_data["interviews"]) == 1
    assert status_data["interviews"][0]["outcome"] == "passed"
    assert status_data["interviews"][0]["mode"] == "online"

    assert len(status_data["offers"]) == 1
    assert status_data["offers"][0]["status"] == "issued"

    assert len(status_data["placement_records"]) == 1
    assert status_data["placement_records"][0]["is_active"] is True

    # Also test via API endpoint
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION="Token abc")
    resp = client.get("/api/v1/placement/student/status")
    assert resp.status_code == 200
    assert resp.json()["is_placed"] is True


def test_pc_afr_014_multiple_offer_policy_representation():
    """PC-AFR-014: Apply multiple-offer handling only to extent explicitly configured."""
    unconfigured_policy = pol.PolicySpec(season=SEASON, categories=())

    placed_student = pol.StudentState(
        discipline="CSE", is_registered=True, accepted_offer_count=1,
        held_ctc_lpa=Decimal("10.00"), held_offer_id=101)

    new_offer = pol.OfferSpec(offer_id=202, ctc_lpa=Decimal("11.00"))

    # When no multiple-offer categories exist, no unsupported restriction is enforced
    accept_decision = pol.can_accept(unconfigured_policy, placed_student, new_offer)
    assert accept_decision.allowed is True
    assert accept_decision.rule == "no_policy_restriction"

    apply_decision = pol.can_apply(unconfigured_policy, placed_student, new_offer)
    assert apply_decision.allowed is True
    assert apply_decision.rule == "no_policy_restriction"

    # When categories are configured, explicit rules apply
    configured_policy = pol.PolicySpec(season=SEASON, categories=pol.default_categories())
    # Category 1 switch multiplier is 1.5x -> 10.00 needs 15.00 LPA
    restricted_decision = pol.can_accept(configured_policy, placed_student, new_offer)
    assert restricted_decision.allowed is False
    assert restricted_decision.rule == "below_switch_multiple"


def test_pc_afr_022_skills_criteria_recording_and_evaluation():
    """PC-AFR-022: Skills criteria recorded and evaluated from authorized source."""
    rule_sound = {"has_all": ["skills", ["Python", "Django"]]}
    assert elig.validate(rule_sound) == []

    rule_any = {"has_any": ["skills", ["Go", "Rust", "Python"]]}
    assert elig.validate(rule_any) == []

    rule_none = {"has_none": ["skills", ["Perl", "PHP"]]}
    assert elig.validate(rule_none) == []

    # Alias fields also valid
    assert elig.validate({"gte": ["cgpa", 7.5]}) == []
    assert elig.validate({"in": ["branch", ["CSE", "ECE"]]}) == []

    # Successful evaluation
    facts = {
        "skills": ["python", "django", "postgresql"],
        "cpi": Decimal("8.2"),
        "discipline": "CSE",
    }
    outcome = elig.evaluate(rule_sound, facts)
    assert outcome.is_eligible is True

    # Missing skill denies fail-closed
    facts_incomplete = {"skills": ["python"], "cpi": Decimal("8.2")}
    outcome_fail = elig.evaluate(rule_sound, facts_incomplete)
    assert outcome_fail.is_eligible is False
    reasons = elig.failure_reasons(outcome_fail)
    assert "django" in reasons[0]["message"].lower()

    # Evaluation with alias fields (cgpa -> cpi, branch -> discipline)
    alias_outcome = elig.evaluate({"gte": ["cgpa", 8.0]}, facts)
    assert alias_outcome.is_eligible is True

    # UserRef integration with facts gathering
    ref = UserRef(
        user_id=777, username="u777", display_name="Dev", kind="student",
        discipline="CSE", skills=("python", "docker"))
    assert ref.skills == ("python", "docker")


def test_pc_afr_029_tpo_interview_progress_view(stub_iam, setup_env, user_ref):
    """PC-AFR-029: TPO tracks interview progress and candidate status."""
    _, _company, posting = setup_env
    rnd = InterviewRound.objects.create(
        posting=posting, seq=1, kind="tech", mode="offline", venue="Hall A",
        starts_at=timezone.now())

    app1 = Application.objects.create(posting=posting, user_id=101, status="interview_scheduled")
    app2 = Application.objects.create(posting=posting, user_id=102, status="interview_scheduled")
    app3 = Application.objects.create(posting=posting, user_id=103, status="interview_scheduled")

    RoundParticipation.objects.create(round=rnd, application=app1, outcome="passed", score=90)
    RoundParticipation.objects.create(round=rnd, application=app2, outcome="failed", score=40)
    RoundParticipation.objects.create(round=rnd, application=app3, outcome="pending")

    tpo = make_session(
        user_id=1, kind="staff", modules=("placement_cell",),
        permissions=("placement_cell.report.view", "placement_cell.interview.schedule"))
    stub_iam(tpo)

    data = interview_service.interview_progress_view(actor=tpo, posting_id=posting.pk)
    assert len(data) == 1
    round_stat = data[0]["stats"]
    assert round_stat["total_candidates"] == 3
    assert round_stat["attended_candidates"] == 2
    assert round_stat["passed_candidates"] == 1
    assert round_stat["failed_candidates"] == 1
    assert round_stat["pending_candidates"] == 1

    # API check
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION="Token abc")
    resp = client.get("/api/v1/placement/interviews/progress")
    assert resp.status_code == 200
    assert len(resp.json()["results"]) >= 1


def test_pc_afr_030_tpo_placement_outcomes_view(stub_iam, setup_env, user_ref):
    """PC-AFR-030: TPO tracks placement outcomes and final placement status."""
    policy, company, posting = setup_env

    app1 = Application.objects.create(posting=posting, user_id=201, status="offer_accepted")
    offer1 = Offer.objects.create(
        application=app1, posting=posting, user_id=201, ctc_lpa=Decimal("15.00"),
        status="accepted", respond_by=timezone.now() + timezone.timedelta(days=3))

    PlacementRecord.objects.create(
        policy=policy, user_id=201, company=company, posting=posting, offer=offer1,
        ctc_lpa=Decimal("15.00"), source="campus", kind="fte", is_active=True)
    PlacementRecord.objects.create(
        policy=policy, user_id=202, company=company, offer=None, posting=None,
        ctc_lpa=Decimal("12.00"), source="off_campus", kind="fte", is_active=True,
        not_joining_declared_at=timezone.now(), not_joining_reason="Higher Studies")

    tpo = make_session(
        user_id=1, kind="staff", modules=("placement_cell",),
        permissions=("placement_cell.report.view", "placement_cell.record.manage",
                     "placement_cell.company.manage"))
    stub_iam(tpo, users={
        201: user_ref(201, "Alice"),
        202: user_ref(202, "Bob"),
    })

    outcomes = clearance_service.placement_outcomes_view(actor=tpo, season=SEASON)
    assert outcomes["total_records"] == 2
    assert outcomes["active_placements"] == 2
    assert outcomes["on_campus_count"] == 1
    assert outcomes["off_campus_count"] == 1
    assert outcomes["not_joining_count"] == 1

    rows = {r["user_id"]: r for r in outcomes["results"]}
    assert rows[201]["final_status"] == "placed"
    assert rows[202]["final_status"] == "not_joining"

    # API check
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION="Token abc")
    resp = client.get("/api/v1/placement/records/outcomes?season=2026-27")
    assert resp.status_code == 200
    assert resp.json()["total_records"] == 2


def test_pc_afr_033_036_tpo_reports(stub_iam, setup_env):
    """PC-AFR-033..036: Success rate, participation trend, salary distribution, employment."""
    policy, company, _posting = setup_env

    # 10 registered students, 5 placed with varying CTCs
    for i in range(10):
        uid = 7000 + i
        PlacementRegistration.objects.create(
            policy=policy, user_id=uid, status="registered",
            registered_at=timezone.now())

    ctcs = ["4.50", "8.00", "12.50", "18.00", "32.00"]
    for i, ctc in enumerate(ctcs):
        PlacementRecord.objects.create(
            policy=policy, user_id=7000 + i, company=company,
            ctc_lpa=Decimal(ctc), source="off_campus", is_active=True)

    tpo = make_session(
        user_id=1, kind="staff", modules=("placement_cell",),
        permissions=("placement_cell.report.view",))
    stub_iam(tpo)

    # AFR-033: Success rate
    staff_rep = stats_service.staff_view(season=SEASON)
    assert staff_rep["success_rate"] == 50.0
    rate_rep = stats_service.placement_success_rate(season=SEASON)
    assert rate_rep["success_rate"] == 50.0

    # AFR-034: Company participation trends
    trends = stats_service.company_participation_trends()
    assert len(trends) >= 1
    assert trends[-1]["companies_count"] >= 1
    assert "Acme Corp" in trends[-1]["company_names"]

    # AFR-035: Salary package distribution
    dist = stats_service.salary_distribution(season=SEASON)
    assert dist["total_placed"] == 5
    assert dist["distribution"]["< 6 LPA"] == 1
    assert dist["distribution"]["6-10 LPA"] == 1
    assert dist["distribution"]["10-15 LPA"] == 1
    assert dist["distribution"]["15-25 LPA"] == 1
    assert dist["distribution"]["> 25 LPA"] == 1

    # AFR-036: Employment trends across seasons
    emp_trends = stats_service.employment_trends()
    assert len(emp_trends) >= 1
    assert emp_trends[-1]["registered"] == 10
    assert emp_trends[-1]["placed"] == 5
    assert emp_trends[-1]["placement_rate"] == 50.0

    # API endpoints
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION="Token abc")

    resp1 = client.get("/api/v1/placement/reports/success-rate")
    assert resp1.status_code == 200
    assert resp1.json()["success_rate"] == 50.0

    resp2 = client.get("/api/v1/placement/reports/participation-trends")
    assert resp2.status_code == 200
    assert len(resp2.json()["results"]) >= 1

    resp3 = client.get("/api/v1/placement/reports/salary-distribution")
    assert resp3.status_code == 200
    assert resp3.json()["total_placed"] == 5

    resp4 = client.get("/api/v1/placement/reports/employment-trends")
    assert resp4.status_code == 200
    assert len(resp4.json()["results"]) >= 1
