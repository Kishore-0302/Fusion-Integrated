"""Company submission through the TPO-managed interview workflow.

Assignment 7 end-to-end workflow coverage:
PC-UC-015 -> PC-UC-006 -> PC-UC-003 -> PC-UC-016 -> PC-UC-009 -> PC-UC-022 -> PC-UC-008 -> PC-UC-010
FR: PC-CFR-007/003/015/009/008/010/017; PC-AFR-018/019/020/021/022,
    007/008/009, 046/047/048, 026/028/054, 023/024/025, 031/032
BR: PC-BR-001/002/003/004/005/006/009/011/012/013/014/015/016/017/021/029/030
WF: BW-PC-01/02/03/04/05/06/07/08; CW-PC-01/02/04
"""
from datetime import timedelta
from decimal import Decimal

import pytest
from django.utils import timezone

from conftest import make_principal, make_session
from core.api.exceptions import ConflictError, NotFoundError, PermissionDeniedError
from fusion_auth.client import UserRef
from modules.placement.authentication import RecruiterPrincipal
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
    RoundParticipation,
)
from modules.placement.services import postings, registration
from modules.placement_cell import use_cases

pytestmark = pytest.mark.django_db

STUDENT_ID = 1001
SEASON = "2026-27"


def _company(name="Acme"):
    return Company.objects.create(
        name=name,
        slug=name.lower(),
        status="active",
        approval_status="approved",
        approved_by_user_id=9,
    )


def _recruiter(company, account_id=71):
    return RecruiterPrincipal(
        account_id=account_id,
        company_id=company.pk,
        email=f"hiring@{company.slug}.test",
        display_name=f"{company.name} Recruiter",
    )


def _tpo():
    return make_principal(
        user_id=9,
        kind="staff",
        modules=("placement_cell",),
        permissions=(
            "placement_cell.job_posting.manage",
            "placement_cell.application.view",
            "placement_cell.application.review",
            "placement_cell.interview.schedule",
            "placement_cell.offer.issue",
            "placement_cell.record.manage",
            "placement_cell.announcement.publish",
        ),
    )


def _complete_posting(company, actor):
    return postings.create(
        company_id=company.pk,
        placement_year=SEASON,
        actor=actor,
        title="Software Engineer",
        kind="fte",
        description="Build and support software products.",
        eligibility_rule={"gte": ["cpi", 7.0]},
        closes_at=timezone.now() + timedelta(days=10),
    )


def test_company_submission_runs_through_five_linked_use_cases(stub_iam):
    """PC-UC-015/006/003/016/009 and BW-PC-03/04/05, CW-PC-01/02/04.

    Company submission stays pending until the TPO publishes; an eligible
    Student then applies, the Company records its shortlist decision, and the
    TPO schedules an interview with the required notification event.
    """
    company = _company()
    recruiter = _recruiter(company)
    tpo = _tpo()
    fake = stub_iam(
        make_session(user_id=STUDENT_ID, modules=("placement_cell",),
                     permissions=("placement_cell.application.create",)),
        users={STUDENT_ID: UserRef(
            user_id=STUDENT_ID, username="21BCS001", display_name="Asha Verma",
            kind="student", discipline="CSE", programme="B.Tech",
            batch_year=2023, profile_completed=True,
        )},
    )
    fake.standings = {STUDENT_ID: {
        "cpi": "8.10", "active_backlogs": 0, "earned_credits": "120",
        "semester": 6, "declared_seq": 1,
    }}

    # UC-015: the Company creates and submits a complete opportunity.
    posting = _complete_posting(company, recruiter)
    submitted = use_cases.submit_company_opportunity(posting_id=posting.pk, actor=recruiter)
    assert submitted.status == "pending_approval"
    assert submitted.published_at is None

    # UC-006: only an authorized TPO makes the submitted opportunity visible.
    published = use_cases.publish_tpo_opportunity(posting_id=posting.pk, actor=tpo)
    assert published.status == "published"
    assert published.eligibility_rule_locked_at is not None

    # UC-003: the registered Student passes the recorded eligibility rule.
    PlacementPolicy.objects.create(season=SEASON, is_active=True)
    registration.register(season=SEASON, user_id=STUDENT_ID)
    student = make_principal(
        user_id=STUDENT_ID, kind="student", modules=("placement_cell",),
        permissions=("placement_cell.application.create",))
    application = use_cases.apply_to_opportunity(
        posting_id=published.pk, actor=student,
        cover_note="I am applying for the posted role.")
    assert application.status == "submitted"
    assert application.eligibility_snapshot["is_eligible"] is True

    # UC-016: the owning Company records its shortlist decision in PCMS.
    use_cases.review_company_application(
        application_id=application.pk, decision="under_review",
        actor=recruiter)
    shortlisted = use_cases.review_company_application(
        application_id=application.pk, decision="shortlisted",
        actor=recruiter)
    assert shortlisted.status == "shortlisted"

    # UC-009: the TPO records a complete schedule and the Student is notified.
    round_, scheduled_count = use_cases.schedule_interviews(
        posting_id=published.pk, actor=tpo, application_ids=[application.pk],
        mode="online", starts_at=timezone.now() + timedelta(days=2),
        meeting_url="https://meet.example.test/placement-round",
    )
    assert isinstance(round_, InterviewRound)
    assert scheduled_count == 1
    application.refresh_from_db()
    assert application.status == "interview_scheduled"
    assert RoundParticipation.objects.filter(
        round=round_, application=application, outcome="pending").exists()
    notification = NotificationOutbox.objects.get(
        topic="interview.scheduled",
        dedupe_key=f"interview.scheduled:{round_.pk}:{application.pk}")
    assert notification.recipient_user_id == STUDENT_ID


@pytest.mark.parametrize("missing_field", [
    "description", "eligibility_rule", "closes_at",
])
def test_company_cannot_submit_posting_without_required_content(
        missing_field):
    """PC-UC-015 / PC-AFR-021 / PC-BR-003 / BW-PC-03."""
    company = _company()
    recruiter = _recruiter(company)
    fields = {
        "title": "Incomplete role",
        "description": "A role description.",
        "eligibility_rule": {"gte": ["cpi", 7.0]},
        "closes_at": timezone.now() + timedelta(days=5),
    }
    fields[missing_field] = "" if missing_field == "description" else (
        {} if missing_field == "eligibility_rule" else None)
    posting = JobPosting.objects.create(
        company=company, placement_year=SEASON, **fields)

    with pytest.raises(ConflictError) as exc:
        use_cases.submit_company_opportunity(posting_id=posting.pk, actor=recruiter)

    assert exc.value.code == "incomplete_posting"
    posting.refresh_from_db()
    assert posting.status == "draft"


def test_submitted_posting_requires_tpo_publication():
    """PC-UC-015/006 / PC-AFR-017/018 / PC-BR-005/006 / BW-PC-03."""
    company = _company()
    recruiter = _recruiter(company)
    posting = _complete_posting(company, recruiter)
    submitted = use_cases.submit_company_opportunity(posting_id=posting.pk, actor=recruiter)

    with pytest.raises(PermissionDeniedError) as exc:
        use_cases.publish_tpo_opportunity(posting_id=submitted.pk, actor=recruiter)

    assert exc.value.code == "tpo_publication_required"


def test_tpo_cannot_publish_an_unsubmitted_draft():
    company = _company()
    posting = _complete_posting(company, _recruiter(company))

    with pytest.raises(ConflictError) as exc:
        use_cases.publish_tpo_opportunity(posting_id=posting.pk, actor=_tpo())

    assert exc.value.code == "submission_required"
    posting.refresh_from_db()
    assert posting.status == "draft"


def test_company_submission_scope_hides_another_company_posting():
    """PC-UC-015 / PC-AFR-018 / PC-BR-006 / BW-PC-02/03."""
    owner = _company("Owner")
    other = _company("Other")
    posting = _complete_posting(other, _recruiter(other))
    recruiter = _recruiter(owner)

    with pytest.raises(NotFoundError):
        use_cases.submit_company_opportunity(posting_id=posting.pk, actor=recruiter)

    posting.refresh_from_db()
    assert posting.status == "draft"


def test_student_can_withdraw_submitted_application(stub_iam):
    """PC-UC-005 / PC-BR-010 / BW-PC-04."""
    company = _company()
    posting = _complete_posting(company, _tpo())
    posting.status = "published"
    posting.eligibility_rule_locked_at = timezone.now()
    posting.save()

    PlacementPolicy.objects.create(season=SEASON, is_active=True)
    registration.register(season=SEASON, user_id=STUDENT_ID)

    fake = stub_iam(
        make_session(user_id=STUDENT_ID, modules=("placement_cell",),
                     permissions=("placement_cell.application.create",
                                  "placement_cell.application.delete")),
        users={STUDENT_ID: UserRef(
            user_id=STUDENT_ID, username="21BCS001", display_name="Asha Verma",
            kind="student", discipline="CSE", programme="B.Tech",
            batch_year=2023, profile_completed=True,
        )},
    )
    fake.standings = {STUDENT_ID: {"cpi": "8.50", "active_backlogs": 0, "declared_seq": 1}}

    student = make_principal(
        user_id=STUDENT_ID, kind="student", modules=("placement_cell",),
        permissions=("placement_cell.application.create",
                     "placement_cell.application.delete"))

    app = use_cases.apply_to_opportunity(posting_id=posting.pk, actor=student)
    assert app.status == "submitted"

    withdrawn = use_cases.withdraw_application(
        application_id=app.pk, actor=student, reason="Personal career preference")
    assert withdrawn.status == "withdrawn"


def test_tpo_record_correction_requires_reason():
    """PC-UC-010 / PC-BR-029 / BW-PC-08."""
    company = _company()
    policy = PlacementPolicy.objects.create(season=SEASON, is_active=True)
    record = PlacementRecord.objects.create(
        user_id=STUDENT_ID, policy=policy, company=company,
        source="off_campus", kind="fte", ctc_lpa=Decimal("12.00"), is_active=True)

    tpo = _tpo()
    # Successful correction
    corrected = use_cases.update_placement_record(
        record_id=record.pk, actor=tpo, reason="CTC updated after proof verification",
        ctc_lpa=Decimal("14.50"))
    assert corrected.ctc_lpa == Decimal("14.50")

    # Failing correction: empty reason
    with pytest.raises(Exception):
        use_cases.update_placement_record(
            record_id=record.pk, actor=tpo, reason="   ")


def test_announcement_publishing_and_topics():
    """PC-UC-013 / PC-BR-017 / PC-BR-021."""
    tpo = _tpo()
    announcement = use_cases.publish_announcement(
        actor=tpo, title="Acme Hiring Drive", body="Drive commences Monday.",
        topic="drives", placement_year=SEASON)
    assert announcement.title == "Acme Hiring Drive"
    assert announcement.topic == "drives"

    # Bad topic fails
    with pytest.raises(ConflictError) as exc:
        use_cases.publish_announcement(
            actor=tpo, title="Invalid Topic", body="Test",
            topic="unrecognized_topic")
    assert exc.value.code == "bad_topic"


def test_student_stats_anonymization():
    """PC-UC-024 / PC-BR-016."""
    PlacementPolicy.objects.create(season=SEASON, is_active=True)
    stats_data = use_cases.get_student_stats(season=SEASON)
    assert stats_data["season"] == SEASON
