"""Automated coverage for the frozen WF_DESIGN.json cases."""

from datetime import timedelta
from decimal import Decimal
from types import SimpleNamespace

import pytest
from django.utils import timezone

from conftest import make_principal, make_session
from fusion_auth.client import UserRef
from modules.placement.models import (
    Company,
    JobPosting,
    PlacementPolicy,
    PlacementRecord,
    PlacementRegistration,
    RecruiterAccount,
)
from modules.placement.services import applications, interviews, offers, postings

pytestmark = pytest.mark.django_db

SEASON = "2026-27"
STUDENT_ID = 1001
TPO_ID = 9


@pytest.fixture
def wf_world(stub_iam):
    """Create the isolated policy, eligible student, company and authorized actors."""
    fake = stub_iam(
        make_session(
            user_id=STUDENT_ID,
            kind="student",
            modules=("placement_cell",),
            permissions=(
                "placement_cell.application.create",
                "placement_cell.application.view_self",
                "placement_cell.offer.respond",
            ),
        ),
        users={
            STUDENT_ID: UserRef(
                user_id=STUDENT_ID,
                username="21BCS001",
                display_name="WF Student",
                kind="student",
                profile_completed=True,
                discipline="CSE",
            )
        },
    )
    fake.standings[STUDENT_ID] = {
        "cpi": "8.50",
        "earned_credits": "120",
        "active_backlogs": 0,
        "semester": 7,
        "semester_type": "autumn",
        "declared_seq": 1,
    }

    policy = PlacementPolicy.objects.create(season=SEASON, is_active=True)
    PlacementRegistration.objects.create(
        policy=policy,
        user_id=STUDENT_ID,
        status="registered",
        registered_at=timezone.now(),
    )
    company = Company.objects.create(
        name="WF Company",
        slug="wf-company",
        status="active",
        approval_status="approved",
        approved_by_user_id=TPO_ID,
    )
    recruiter_account = RecruiterAccount.objects.create(
        company=company,
        email="recruiter@wf-company.example",
        full_name="WF Recruiter",
    )
    recruiter = SimpleNamespace(
        user_id=None,
        username="wf-recruiter",
        display_name="WF Recruiter",
        kind="recruiter",
        active_role=None,
        roles=(),
        permissions=frozenset(),
        modules=(),
        is_authenticated=True,
        is_anonymous=False,
        account_id=recruiter_account.pk,
        company_id=company.pk,
    )
    tpo = make_principal(
        user_id=TPO_ID,
        kind="staff",
        active_role="tpo",
        permissions=(
            "placement_cell.job_posting.manage",
            "placement_cell.application.review",
            "placement_cell.interview.schedule",
            "placement_cell.offer.issue",
        ),
    )
    student = make_principal(
        user_id=STUDENT_ID,
        kind="student",
        active_role="student",
        permissions=(
            "placement_cell.application.create",
            "placement_cell.application.view_self",
            "placement_cell.offer.respond",
        ),
    )
    return {
        "company": company,
        "policy": policy,
        "recruiter": recruiter,
        "student": student,
        "tpo": tpo,
    }


def _posting(world, actor):
    return postings.create(
        company_id=world["company"].pk,
        placement_year=SEASON,
        actor=actor,
        title="Software Engineer",
        description="Build and maintain software systems.",
        ctc_lpa=Decimal("14.50"),
        eligibility_rule={"gte": ["cpi", 6.5]},
        closes_at=timezone.now() + timedelta(days=14),
    )


def _submitted_application(world, posting):
    return applications.apply_to(posting_id=posting.pk, actor=world["student"])


def _shortlist(world, application):
    application = applications.transition(
        application_id=application.pk,
        to_status="under_review",
        actor=world["recruiter"],
    )
    assert application.status == "under_review"
    return applications.transition(
        application_id=application.pk,
        to_status="shortlisted",
        actor=world["recruiter"],
    )


def _schedule(world, posting, application, actor):
    round_ = interviews.schedule_round(
        posting_id=posting.pk,
        actor=actor,
        kind="tech",
        mode="online",
        starts_at=timezone.now() + timedelta(days=2),
        meeting_url="https://meet.example.com/wf-interview",
    )
    interviews.add_candidates(
        round_id=round_.pk,
        application_ids=[application.pk],
        actor=actor,
    )
    application.refresh_from_db()
    return application


def test_pcms_wf_001_tpo_publication_and_student_application(wf_world):
    """PCMS-WF-001; source_id: BW-PC-01 — TPO publication and eligible Student application; PC-BR-001, PC-BR-002, PC-BR-003, PC-BR-004, PC-BR-005."""
    posting = postings.publish(
        posting_id=_posting(wf_world, wf_world["tpo"]).pk,
        actor=wf_world["tpo"],
    )
    application = _submitted_application(wf_world, posting)

    assert posting.status == "published"
    # The persisted `submitted` state represents the design's Applied outcome.
    assert application.status == "submitted"


def test_pcms_wf_002_company_direct_publication_and_student_application(wf_world):
    """PCMS-WF-002; source_id: BW-PC-02 — direct Company publication and eligible Student application; PC-BR-001, PC-BR-002, PC-BR-003, PC-BR-004, PC-BR-006."""
    posting = postings.publish(
        posting_id=_posting(wf_world, wf_world["recruiter"]).pk,
        actor=wf_world["recruiter"],
    )
    application = _submitted_application(wf_world, posting)

    assert posting.status == "published"
    assert application.status == "submitted"


def test_pcms_wf_003_company_submission_tpo_publication_and_application(wf_world):
    """PCMS-WF-003; source_id: BW-PC-03 — Company submission via TPO and eligible Student application; PC-BR-001, PC-BR-002, PC-BR-003, PC-BR-004, PC-BR-005, PC-BR-006."""
    # There is no submit-for-TPO service/API in this checkout; seed the persisted
    # workflow state so the TPO publication and Student application are exercised.
    posting = JobPosting.objects.create(
        company=wf_world["company"], placement_year=SEASON,
        status="pending_approval", title="Software Engineer",
        description="Build and maintain software systems.",
        ctc_lpa=Decimal("14.50"), eligibility_rule={"gte": ["cpi", 6.5]},
        closes_at=timezone.now() + timedelta(days=14),
        created_by_recruiter_id=wf_world["recruiter"].account_id,
    )
    assert JobPosting.objects.get(pk=posting.pk).status == "pending_approval"

    posting = postings.publish(posting_id=posting.pk, actor=wf_world["tpo"])
    application = _submitted_application(wf_world, posting)

    assert posting.status == "published"
    assert application.status == "submitted"


def test_pcms_wf_004_applied_application_to_company_shortlist(wf_world):
    """PCMS-WF-004; source_id: BW-PC-04 — Applied application to Company/Recruiter shortlist; PC-BR-001, PC-BR-002, PC-BR-009, PC-BR-030."""
    posting = postings.publish(
        posting_id=_posting(wf_world, wf_world["tpo"]).pk,
        actor=wf_world["tpo"],
    )
    application = _submitted_application(wf_world, posting)
    assert application.status == "submitted"

    application = _shortlist(wf_world, application)

    assert application.status == "shortlisted"


def test_pcms_wf_005_company_shortlist_to_tpo_interview(wf_world):
    """PCMS-WF-005; source_id: BW-PC-05 — Company shortlist to TPO-coordinated interview; PC-BR-009, PC-BR-011, PC-BR-012, PC-BR-030."""
    posting = postings.publish(
        posting_id=_posting(wf_world, wf_world["tpo"]).pk,
        actor=wf_world["tpo"],
    )
    application = _submitted_application(wf_world, posting)
    application = _shortlist(wf_world, application)
    assert application.status == "shortlisted"

    application = _schedule(wf_world, posting, application, wf_world["tpo"])

    assert application.status == "interview_scheduled"


def test_pcms_wf_006_student_application_to_company_interview(wf_world):
    """PCMS-WF-006; source_id: BW-PC-06 — Student application to Company-scheduled interview; PC-BR-001, PC-BR-002, PC-BR-009, PC-BR-011, PC-BR-012, PC-BR-030."""
    posting = postings.publish(
        posting_id=_posting(wf_world, wf_world["tpo"]).pk,
        actor=wf_world["tpo"],
    )
    application = _submitted_application(wf_world, posting)
    assert application.status == "submitted"
    application = _shortlist(wf_world, application)
    assert application.status == "shortlisted"

    application = _schedule(wf_world, posting, application, wf_world["recruiter"])

    assert application.status == "interview_scheduled"


def test_pcms_wf_007_interview_offer_acceptance_and_placement_update(wf_world):
    """PCMS-WF-007; source_id: BW-PC-07 — offer extension from Interview Scheduled and Student acceptance with placement update; PC-BR-009, PC-BR-013, PC-BR-014, PC-BR-015, PC-BR-030."""
    posting = postings.publish(
        posting_id=_posting(wf_world, wf_world["tpo"]).pk,
        actor=wf_world["tpo"],
    )
    application = _submitted_application(wf_world, posting)
    application = _shortlist(wf_world, application)
    assert application.status == "shortlisted"
    application = _schedule(wf_world, posting, application, wf_world["recruiter"])
    assert application.status == "interview_scheduled"
    application = applications.transition(
        application_id=application.pk,
        to_status="selected",
        actor=wf_world["tpo"],
        reason="Interview successful.",
    )
    offer = offers.issue(
        application_id=application.pk, actor=wf_world["recruiter"],
        respond_by=timezone.now() + timedelta(days=3),
    )
    assert offer.status == "issued"
    assert offer.respond_by > timezone.now()

    offer = offers.respond(offer_id=offer.pk, accept=True, actor=wf_world["student"])

    application.refresh_from_db()
    assert offer.status == "accepted"
    assert application.status == "offer_accepted"
    assert PlacementRecord.objects.filter(
        user_id=STUDENT_ID, posting=posting, offer=offer, is_active=True
    ).exists()


def test_pcms_wf_008_shortlisted_offer_and_student_rejection(wf_world):
    """PCMS-WF-008; source_id: BW-PC-08 — offer extension from Shortlisted and Student rejection; PC-BR-009, PC-BR-013, PC-BR-015, PC-BR-030."""
    posting = postings.publish(
        posting_id=_posting(wf_world, wf_world["tpo"]).pk,
        actor=wf_world["tpo"],
    )
    application = _submitted_application(wf_world, posting)
    application = _shortlist(wf_world, application)
    assert application.status == "shortlisted"
    offer = offers.issue(
        application_id=application.pk, actor=wf_world["recruiter"],
        respond_by=timezone.now() + timedelta(days=3),
    )
    assert offer.status == "issued"
    assert offer.respond_by > timezone.now()

    offer = offers.respond(offer_id=offer.pk, accept=False, actor=wf_world["student"])

    application.refresh_from_db()
    assert offer.status == "declined"
    assert application.status == "offer_declined"
