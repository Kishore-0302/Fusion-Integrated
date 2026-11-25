"""FR strategy conformance cases from the frozen design."""

import pytest

pytestmark = pytest.mark.django_db


@pytest.fixture
def setup_env():
    from decimal import Decimal

    from django.utils import timezone

    from modules.placement.models import Company, JobPosting, PlacementPolicy

    season = "2026-27"
    policy = PlacementPolicy.objects.create(season=season, is_active=True)
    company = Company.objects.create(
        name="Acme Corp",
        slug="acme-corp",
        status="active",
        approval_status="approved",
        approved_by_user_id=1,
    )
    posting = JobPosting.objects.create(
        company=company,
        title="Software Engineer",
        placement_year=season,
        description="Engineering role",
        closes_at=timezone.now() + timezone.timedelta(days=7),
        eligibility_rule_locked_at=timezone.now(),
        ctc_lpa=Decimal("12.00"),
        status="published",
        created_by_user_id=1,
    )
    return policy, company, posting


CASES = [
    ('PCMS-AFR-004', 'PC-AFR-004 — configured profile completeness', 'Verify the configured profile-completeness condition gates application submission.'),
    ('PCMS-AFR-006', 'PC-AFR-006 — opportunity browsing', 'Verify Students can browse opportunities made available through PCMS.'),
    ('PCMS-AFR-007', 'PC-AFR-007 — application submission', 'Verify an eligible Student can apply for a job posting.'),
    ('PCMS-AFR-008', 'PC-AFR-008 — posting eligibility', 'Verify PCMS evaluates recorded posting eligibility criteria before accepting an application.'),
    ('PCMS-AFR-009', 'PC-AFR-009 — application history', 'Verify PCMS maintains application history.'),
    ('PCMS-AFR-010', 'PC-AFR-010 — placement status visibility', 'Verify Students can track supported placement states and related status information.'),
    ('PCMS-AFR-011', 'PC-AFR-011 — offer acceptance deadline', 'Verify a Student can accept a recorded offer while the applicable response deadline permits it.'),
    ('PCMS-AFR-012', 'PC-AFR-012 — offer rejection deadline', 'Verify a Student can reject a recorded offer while the applicable response deadline permits it.'),
    ('PCMS-AFR-013', 'PC-AFR-013 — placement update on acceptance', 'Verify accepting an offer updates the Student\'s placement record.'),
    ('PCMS-AFR-014', 'PC-AFR-014 — multiple-offer policy boundary', 'Verify multiple-offer handling respects only policy logic explicitly represented in PCMS.'),
    ('PCMS-AFR-015', 'PC-AFR-015 — anonymized statistics', 'Verify Students can view available anonymized placement statistics.'),
    ('PCMS-AFR-016', 'PC-AFR-016 — historical placement data', 'Verify Students can view historical placement data made available to their role.'),
    ('PCMS-AFR-017', 'PC-AFR-017 — TPO posting management', 'Verify the TPO can create and manage job postings.'),
    ('PCMS-AFR-018', 'PC-AFR-018 — Company job opportunity posting', 'Verify the supported Company/Recruiter job-opportunity posting paths.'),
    ('PCMS-AFR-019', 'PC-AFR-019 — Company internship opportunity posting', 'Verify an authorized Company/Recruiter can publish or submit an internship opportunity.'),
    ('PCMS-AFR-020', 'PC-AFR-020 — eligibility criteria recording', 'Verify permitted posting actors can record eligibility criteria within their posting scopes.'),
    ('PCMS-AFR-021', 'PC-AFR-021 — required job posting content', 'Verify job postings require a role description, eligibility criteria, and application deadline.'),
    ('PCMS-AFR-022', 'PC-AFR-022 — supported eligibility criteria', 'Verify the supported eligibility criteria vocabulary can be represented.'),
    ('PCMS-AFR-023', 'PC-AFR-023 — TPO application review', 'Verify the TPO can view and review applications within the TPO\'s authorized scope.'),
    ('PCMS-AFR-024', 'PC-AFR-024 — TPO application filtering', 'Verify the TPO can filter applications within the TPO\'s authorized scope.'),
    ('PCMS-AFR-025', 'PC-AFR-025 — TPO application administration', 'Verify the TPO can administratively manage applications without taking unsupported Company selection decisions.'),
    ('PCMS-AFR-026', 'PC-AFR-026 — TPO-coordinated interview scheduling', 'Verify the TPO can schedule interviews in coordination with Companies/Recruiters.'),
    ('PCMS-AFR-027', 'PC-AFR-027 — Company interview scheduling', 'Verify an authorized Company/Recruiter can schedule interviews for relevant shortlisted candidates.'),
    ('PCMS-AFR-028', 'PC-AFR-028 — required interview details', 'Verify interview schedules record the required date, time slot, and mode.'),
    ('PCMS-AFR-029', 'PC-AFR-029 — TPO interview progress tracking', 'Verify the TPO can track interview progress and status within the TPO\'s scope.'),
    ('PCMS-AFR-030', 'PC-AFR-030 — placement outcome tracking', 'Verify the TPO can track recorded placement outcomes and final status.'),
    ('PCMS-AFR-031', 'PC-AFR-031 — Student placement record maintenance', 'Verify the TPO can update supported Student placement records.'),
    ('PCMS-AFR-032', 'PC-AFR-032 — Alumni placement record maintenance', 'Verify the TPO can update supported Alumni placement records while Alumni access remains read-only.'),
    ('PCMS-AFR-033', 'PC-AFR-033 — placement success-rate report', 'Verify the TPO can generate a placement success-rate report.'),
    ('PCMS-AFR-034', 'PC-AFR-034 — company participation trend report', 'Verify the TPO can generate company participation trend reporting.'),
    ('PCMS-AFR-035', 'PC-AFR-035 — salary package distribution report', 'Verify the TPO can generate salary package distribution reporting.'),
    ('PCMS-AFR-036', 'PC-AFR-036 — employment trend report', 'Verify the TPO can generate employment trend reporting.'),
    ('PCMS-AFR-037', 'PC-AFR-037 — Chairman statistics oversight', 'Verify the Placement Chairman can view placement statistics available for oversight.'),
    ('PCMS-AFR-038', 'PC-AFR-038 — Chairman summarized reports', 'Verify the Placement Chairman can view summarized placement reports.'),
    ('PCMS-AFR-039', 'PC-AFR-039 — company participation oversight', 'Verify the Placement Chairman can monitor company participation and engagement using PCMS information.'),
    ('PCMS-AFR-040', 'PC-AFR-040 — TPO announcements', 'Verify an authorized TPO can publish a placement-related announcement.'),
    ('PCMS-AFR-041', 'PC-AFR-041 — Placement Chairman announcements', 'Verify the Placement Chairman can publish official placement-related announcements.'),
    ('PCMS-AFR-042', 'PC-AFR-042 — supported announcement content', 'Verify announcements can represent the supported placement topics.'),
    ('PCMS-AFR-043', 'PC-AFR-043 — announcement history', 'Verify PCMS maintains announcement history for authorized access.'),
    ('PCMS-AFR-044', 'PC-AFR-044 — Company registration submission', 'Verify a Company/Recruiter can submit registration information subject to institute approval.'),
    ('PCMS-AFR-045', 'PC-AFR-045 — Company authorization status', 'Verify Company/Recruiter placement functions depend on an available status that permits them.'),
    ('PCMS-AFR-046', 'PC-AFR-046 — Company application review', 'Verify an authorized Company/Recruiter can view and review applications for its own opportunities.'),
    ('PCMS-AFR-047', 'PC-AFR-047 — Company shortlist update', 'Verify an authorized Company/Recruiter can record a shortlist outcome for its opportunity.'),
    ('PCMS-AFR-048', 'PC-AFR-048 — Company rejection update', 'Verify an authorized Company/Recruiter can manage relevant application records and record supported rejection updates.'),
    ('PCMS-AFR-049', 'PC-AFR-049 — Company offer extension', 'Verify an authorized Company/Recruiter can extend an offer to a selected candidate for its opportunity.'),
    ('PCMS-AFR-050', 'PC-AFR-050 — new job posting notification', 'Verify a new job posting triggers an automated notification event where required by the accepted notification scope.'),
    ('PCMS-AFR-051', 'PC-AFR-051 — application submission notification', 'Verify application submission triggers an automated notification event.'),
    ('PCMS-AFR-052', 'PC-AFR-052 — shortlisting notification', 'Verify a shortlisting update triggers an automated notification event.'),
    ('PCMS-AFR-053', 'PC-AFR-053 — rejection notification', 'Verify a rejection update triggers an automated notification event.'),
    ('PCMS-AFR-054', 'PC-AFR-054 — interview schedule notification', 'Verify affected eligible or shortlisted Students are notified of recorded interview details.'),
    ('PCMS-AFR-055', 'PC-AFR-055 — job offer notification', 'Verify the Student is notified when a job offer is extended.'),
    ('PCMS-AFR-056', 'PC-AFR-056 — announcement notification', 'Verify Students are notified about a new supported placement announcement.'),
    ('PCMS-AFR-057', 'PC-AFR-057 — email notification handoff', 'Verify supported automated placement notifications are handed off as system-generated emails.'),
    ('PCMS-AFR-058', 'PC-AFR-058 — Alumni restricted data access', 'Verify Alumni receive only restricted placement-data access for supported mentorship and networking purposes.'),
    ('PCMS-AFR-059', 'PC-AFR-059 — Alumni read-only access', 'Verify Alumni placement-data access is read-only.'),
    ('PCMS-AFR-060', 'PC-AFR-060 — Alumni active workflow restriction', 'Verify Alumni cannot participate in active placement workflows.'),
    ('PCMS-AFR-061', 'PC-AFR-061 — role and access scope', 'Verify placement-data access and placement actions follow the user\'s role and defined access scope.'),
    ('PCMS-AFR-062', 'PC-AFR-062 — sensitive data view authorization', 'Verify only authorized stakeholders can view sensitive placement data.'),
    ('PCMS-AFR-063', 'PC-AFR-063 — sensitive data modification authorization', 'Verify only authorized stakeholders can modify sensitive placement data.'),
    ('PCMS-AFR-064', 'PC-AFR-064 — placement-data confidentiality', 'Verify role-based permissions protect placement-data confidentiality within the PCMS scope.'),
]

# The four cases omitted here are documented as jointly out of PCMS scope in
# docs/04-placement/spec-tests/triage.md; their frozen designs remain unchanged.
_CASES = {
    "PCMS-AFR-010": ("student1", None, "test_pc_afr_010_student_status_view"),
    "PCMS-AFR-014": ("student1", None, "test_pc_afr_014_multiple_offer_policy_representation"),
    "PCMS-AFR-022": ("student1", None, "test_pc_afr_022_skills_criteria_recording_and_evaluation"),
    "PCMS-AFR-029": ("student1", None, "test_pc_afr_029_tpo_interview_progress_view"),
    "PCMS-AFR-030": ("student1", None, "test_pc_afr_030_tpo_placement_outcomes_view"),
    "PCMS-AFR-031": ("placement_record", None, "student"),
    "PCMS-AFR-032": ("placement_record", None, "alumni"),
    "PCMS-AFR-033": ("student1", None, "test_pc_afr_033_036_tpo_reports"),
    "PCMS-AFR-034": ("student1", None, "test_pc_afr_033_036_tpo_reports"),
    "PCMS-AFR-035": ("student1", None, "test_pc_afr_033_036_tpo_reports"),
    "PCMS-AFR-036": ("student1", None, "test_pc_afr_033_036_tpo_reports"),
    "PCMS-AFR-004": ("application", None, "profile_gate"),
    "PCMS-AFR-006": ("api", None, "browse"),
    "PCMS-AFR-045": ("company", None, "authorization"),
    "PCMS-AFR-051": ("notification", None, "submitted"),
    "PCMS-AFR-052": ("notification", None, "shortlisted"),
    "PCMS-AFR-053": ("notification", None, "rejected"),
    "PCMS-AFR-054": ("notification", None, "interview"),
    "PCMS-AFR-026": ("interview", None, "tpo"),
    "PCMS-AFR-027": ("interview", None, "company"),
    "PCMS-AFR-028": ("api", None, "interview_fields"),
    "PCMS-AFR-047": ("application", None, "shortlist"),
    "PCMS-AFR-048": ("application", None, "reject"),
    "PCMS-AFR-049": ("offer", None, "issue"),
    "PCMS-AFR-058": ("roles", None, "alumni_read"),
    "PCMS-AFR-059": ("roles", None, "alumni_write"),
    "PCMS-AFR-060": ("roles", None, "alumni_workflow"),
    "PCMS-AFR-061": ("roles", None, "matrix"),
    "PCMS-AFR-062": ("roles", None, "sensitive_read"),
    "PCMS-AFR-063": ("roles", None, "sensitive_write"),
    "PCMS-AFR-064": ("roles", None, "confidentiality"),
    "PCMS-AFR-007": ("application", None, "eligible_apply"),
    "PCMS-AFR-008": ("application", None, "eligibility_gate"),
    "PCMS-AFR-023": ("application", None, "tpo_scope"),
    "PCMS-AFR-024": ("application", None, "filter"),
    "PCMS-AFR-025": ("application", None, "administration"),
    "PCMS-AFR-046": ("application", None, "company_scope"),
    "PCMS-AFR-017": ("posting", None, "tpo"),
    "PCMS-AFR-018": ("posting", None, "paths"),
    "PCMS-AFR-019": ("posting", None, "internship"),
    "PCMS-AFR-020": ("posting", None, "criteria"),
    "PCMS-AFR-021": ("posting", None, "required"),
    "PCMS-AFR-050": ("posting", None, "notification"),
    "PCMS-AFR-009": ("application", None, "history"),
    "PCMS-AFR-011": ("modules.placement.tests.test_offer_flow", "TestDeadlines", "test_responding_after_the_deadline_is_refused"),
    "PCMS-AFR-012": ("modules.placement.tests.test_offer_flow", "TestFirstAcceptance", "test_declining_records_the_decision"),
    "PCMS-AFR-013": ("modules.placement.tests.test_offer_flow", "TestFirstAcceptance", "test_accepting_creates_a_placement_record"),
    "PCMS-AFR-040": ("modules.placement.tests.test_announcements", "TestTPOAnnouncement", "test_tpo_can_publish_an_announcement"),
    "PCMS-AFR-041": ("modules.placement.tests.test_announcements", "TestChairmanAnnouncement", "test_chairman_can_publish_an_official_announcement"),
    "PCMS-AFR-042": ("modules.placement.tests.test_announcements", "TestChairmanAnnouncement", "test_announcement_content_topics_match_spec"),
    "PCMS-AFR-043": ("modules.placement.tests.test_announcements", "TestTPOAnnouncement", "test_announcement_is_persisted_in_history"),
    "PCMS-AFR-044": ("modules.placement.tests.test_company_registration", None, "test_pc_uc_014_registering_a_name_twice_gives_each_its_own_slug"),
    "PCMS-AFR-015": ("stats", None, "student"),
    "PCMS-AFR-016": ("stats", None, "historical"),
    "PCMS-AFR-037": ("stats", None, "staff"),
    "PCMS-AFR-038": ("stats", None, "staff"),
    "PCMS-AFR-039": ("stats", None, "company"),
    "PCMS-AFR-055": ("modules.placement.tests.test_offer_flow", "TestNotifications", "test_issuing_an_offer_queues_exactly_one_notification"),
    "PCMS-AFR-057": ("modules.placement.tests.test_notification_worker", "TestDelivery", "test_a_pending_row_is_sent_once"),
    "PCMS-AFR-056": ("modules.placement.tests.test_announcements", "TestTPOAnnouncement", "test_tpo_announcement_queues_a_broadcast_notification"),
}


@pytest.mark.parametrize(
    ("test_id", "source_id", "purpose"),
    CASES,
    ids=[f"{row[0]}::{row[1]}" for row in CASES],
)
def test_fr_case(test_id, source_id, purpose, request):
    """FR test ID and source ID are part of each collected test's node name."""
    target = _CASES.get(test_id)
    if target is None:
        raise AssertionError(f"No frozen FR test target is mapped for {test_id} ({source_id})")

    from importlib import import_module

    module_name, class_name, function_name = target
    if module_name == "student1":
        from importlib import import_module
        from inspect import signature

        module = import_module("modules.placement.tests.test_fr_student1")
        test = getattr(module, function_name)
        test(*(request.getfixturevalue(name) for name in signature(test).parameters))
        return
    if module_name == "placement_record":
        _assert_placement_record_maintenance(function_name)
        return
    if module_name == "modules.placement.tests.test_offer_flow":
        _install_offer_flow_directory(request)
    if module_name == "stats":
        _assert_statistics_view(function_name)
        return
    if module_name == "posting":
        _assert_posting_case(function_name)
        return
    if module_name == "application":
        if function_name == "profile_gate":
            _assert_profile_gate(request)
        else:
            _assert_application_case(function_name, request)
        return
    if module_name == "api":
        if function_name == "browse":
            _assert_student_browsing(request)
        else:
            _assert_interview_fields(request)
        return
    if module_name == "interview":
        _assert_interview_case(function_name)
        return
    if module_name == "offer":
        _install_offer_flow_directory(request)
        _assert_company_offer()
        return
    if module_name == "company":
        _assert_company_authorization(function_name)
        return
    if module_name == "notification":
        _assert_notification_case(function_name, request)
        return
    if module_name == "roles":
        _assert_role_case(function_name)
        return
    module = import_module(module_name)
    owner = getattr(module, class_name) if class_name else module
    test = getattr(owner, function_name)
    if class_name:
        test = test.__get__(object.__new__(owner), owner)
    test()






def _assert_placement_record_maintenance(case_kind):
    from decimal import Decimal

    import pytest

    from conftest import make_principal
    from core.api.exceptions import PermissionDeniedError
    from modules.placement.models import Company, PlacementPolicy
    from modules.placement.services import clearance

    policy = PlacementPolicy.objects.create(season="2026-27", is_active=True)
    company = Company.objects.create(
        name="FR Record Maintenance Co",
        slug=f"fr-record-maintenance-{case_kind}",
        status="active",
        approval_status="approved",
        approved_by_user_id=9,
    )
    tpo = make_principal(
        user_id=9,
        kind="staff",
        active_role="tpo",
        permissions=("placement_cell.record.manage",),
    )
    user_id = 9101 if case_kind == "student" else 9102
    record = clearance.record_off_campus(
        season=policy.season,
        user_id=user_id,
        company_id=company.pk,
        ctc_lpa=Decimal("12.00"),
        actor=tpo,
    )
    updated = clearance.update_record(
        record_id=record.pk,
        actor=tpo,
        ctc_lpa=Decimal("15.00"),
    )
    assert updated.ctc_lpa == Decimal("15.00")
    assert updated.user_id == user_id

    if case_kind == "alumni":
        alumni = make_principal(
            user_id=user_id,
            kind="alumni",
            active_role="alumni",
            permissions=(),
        )
        with pytest.raises(PermissionDeniedError):
            clearance.update_record(
                record_id=record.pk,
                actor=alumni,
                ctc_lpa=Decimal("20.00"),
            )
        record.refresh_from_db()
        assert record.ctc_lpa == Decimal("15.00")


def _assert_statistics_view(view_kind):
    from decimal import Decimal

    from django.utils import timezone

    from modules.placement.models import (
        Company,
        PlacementPolicy,
        PlacementRecord,
        PlacementRegistration,
    )
    from modules.placement.services import stats

    season = "2025-26" if view_kind == "historical" else "2026-27"
    policy = PlacementPolicy.objects.create(season=season)
    company = Company.objects.create(
        name="FR Statistics Co",
        slug=f"fr-statistics-{season[:4]}",
        status="active",
        approval_status="approved",
        approved_by_user_id=9,
    )
    for index in range(10):
        user_id = 7000 + index
        PlacementRegistration.objects.create(
            policy=policy,
            user_id=user_id,
            status="registered",
            registered_at=timezone.now(),
        )
        if index < 5:
            PlacementRecord.objects.create(
                policy=policy,
                user_id=user_id,
                company=company,
                ctc_lpa=Decimal("10.00"),
                source="off_campus",
            )

    stats.rebuild(season=season)
    if view_kind == "student":
        result = stats.student_view(season=season)
        assert result["available"] is True
        assert result["placed"] == 5
        assert "user_id" not in result
        assert "name" not in result
    elif view_kind == "historical":
        result = stats.student_view(season=season)
        assert result["season"] == season
        assert result["available"] is True
        assert result["placed"] == 5
    elif view_kind == "company":
        result = stats.staff_view(season=season)
        assert result["available"] is True
        assert result["by_company"] == [{
            "company__name": company.name,
            "placed": 5,
            "top": Decimal("10.00"),
        }]
    else:
        result = stats.staff_view(season=season)
        assert result["available"] is True
        assert result["placed"] == 5
        assert result["registered"] == 10


def _assert_posting_case(case_kind):
    from datetime import timedelta
    from types import SimpleNamespace

    from django.utils import timezone

    from conftest import make_principal
    from core.api.exceptions import ConflictError
    from modules.placement.models import Company, NotificationOutbox, RecruiterAccount
    from modules.placement.services import postings

    permission = "placement_cell.job_posting.manage"
    staff = make_principal(
        user_id=9, kind="staff", permissions=(permission,))
    company = Company.objects.create(
        name="FR Posting Co",
        slug="fr-posting-co",
        status="active",
        approval_status="approved",
        approved_by_user_id=9,
    )

    def create(actor, *, title="FR role", kind="fte", **fields):
        defaults = {
            "title": title,
            "kind": kind,
            "description": "Role description.",
            "closes_at": timezone.now() + timedelta(days=7),
            "eligibility_rule": {"gte": ["cpi", 7.0]},
        }
        defaults.update(fields)
        return postings.create(
            company_id=company.pk,
            placement_year="2026-27",
            actor=actor,
            **defaults,
        )

    def recruiter(label):
        account = RecruiterAccount.objects.create(
            company=company,
            email=f"{label}@example.test",
            full_name="FR Recruiter",
        )
        return SimpleNamespace(
            kind="recruiter",
            account_id=account.pk,
            company_id=company.pk,
            user_id=None,
            has_permission=lambda _permission: False,
        )

    if case_kind == "tpo":
        posting = create(staff)
        assert postings.publish(posting_id=posting.pk, actor=staff).status == "published"
    elif case_kind == "paths":
        company_actor = recruiter("fr-paths")
        direct = postings.publish(
            posting_id=create(company_actor, title="Direct posting").pk,
            actor=company_actor,
        )
        managed = create(company_actor, title="TPO managed posting")
        published = postings.publish(posting_id=managed.pk, actor=staff)
        assert direct.status == "published"
        assert published.status == "published"
    elif case_kind == "internship":
        posting = create(staff, kind="internship")
        assert postings.publish(posting_id=posting.pk, actor=staff).kind == "internship"
    elif case_kind == "criteria":
        rule = {"all": [
            {"gte": ["cpi", 7.0]},
            {"in": ["discipline", ["CSE", "ECE"]]},
            {"gte": ["batch_year", 2024]},
        ]}
        from types import SimpleNamespace

        staff_posting = create(staff, eligibility_rule=rule)
        company_actor = recruiter("fr-criteria")
        company_posting = create(
            company_actor, title="FR Recruiter Role", eligibility_rule=rule)
        assert staff_posting.eligibility_rule == rule
        assert company_posting.eligibility_rule == rule
    elif case_kind == "required":
        base = {
            "description": "Role description.",
            "closes_at": timezone.now() + timedelta(days=7),
            "eligibility_rule": {"gte": ["cpi", 7.0]},
        }
        for field in base:
            invalid = dict(base)
            invalid[field] = "" if field == "description" else ({} if field == "eligibility_rule" else None)
            posting = create(staff, **invalid)
            with pytest.raises(ConflictError) as exc:
                postings.publish(posting_id=posting.pk, actor=staff)
            assert exc.value.code == "incomplete_posting"
            posting.refresh_from_db()
            assert posting.status == "draft"
        ready = postings.publish(
            posting_id=create(staff, **base).pk, actor=staff)
        assert ready.status == "published"
    elif case_kind == "notification":
        posting = postings.publish(
            posting_id=create(staff).pk, actor=staff)
        event = NotificationOutbox.objects.get(topic="posting.published")
        assert event.payload["posting_id"] == posting.pk




def _assert_profile_gate(request):
    from dataclasses import replace
    from datetime import timedelta

    import pytest
    from django.utils import timezone

    from conftest import make_principal, make_session
    from core.api.exceptions import ConflictError
    from fusion_auth.client import UserRef
    from modules.placement.models import Application, Company, JobPosting
    from modules.placement.services.applications import transition

    user_id = 8101
    tpo = request.getfixturevalue("stub_iam")
    user = UserRef(
        user_id=user_id,
        username="fr-student",
        display_name="FR Student",
        kind="student",
        profile_completed=False,
    )
    tpo(make_session(
        user_id=user_id,
        kind="student",
        modules=("placement_cell",),
        permissions=("placement_cell.application.create",),
    ), users={user_id: user})
    company = Company.objects.create(
        name="FR Profile Co", slug="fr-profile-co", status="active",
        approval_status="approved", approved_by_user_id=9)
    posting = JobPosting.objects.create(
        company=company, title="FR Role", placement_year="2026-27",
        description="Role description.", status="published",
        eligibility_rule_locked_at=timezone.now(),
        closes_at=timezone.now() + timedelta(days=5),
        eligibility_rule={}, published_at=timezone.now())
    app = Application.objects.create(
        posting=posting, user_id=user_id, status="draft",
        eligibility_snapshot={"is_eligible": True,
                              "season_decision": {"allowed": True}})
    actor = make_principal(
        user_id=user_id, kind="student",
        permissions=("placement_cell.application.create",))
    with pytest.raises(ConflictError) as refusal:
        transition(application_id=app.pk, to_status="submitted", actor=actor)
    assert refusal.value.code == "profile_incomplete"
    app.refresh_from_db()
    assert app.status == "draft"

    complete_user = replace(user, profile_completed=True)
    tpo(make_session(
        user_id=user_id,
        kind="student",
        modules=("placement_cell",),
        permissions=("placement_cell.application.create",),
    ), users={user_id: complete_user})
    saved = transition(application_id=app.pk, to_status="submitted", actor=actor)
    assert saved.status == "submitted"


def _assert_student_browsing(request):
    from datetime import timedelta

    from django.utils import timezone
    from rest_framework.test import APIClient

    from conftest import make_session
    from modules.placement.models import Company, JobPosting

    stub_iam = request.getfixturevalue("stub_iam")
    user_id = 8201
    stub_iam(make_session(
        user_id=user_id,
        kind="student",
        modules=("placement_cell",),
        permissions=("placement_cell.job_posting.view",),
    ))
    company = Company.objects.create(
        name="FR Browsing Co", slug="fr-browsing-co", status="active",
        approval_status="approved", approved_by_user_id=9)
    expected = {"FR Job", "FR Internship"}
    for title, kind in (("FR Job", "fte"), ("FR Internship", "internship")):
        JobPosting.objects.create(
            company=company, title=title, kind=kind, placement_year="2026-27",
            description="Role description.", status="published",
            eligibility_rule_locked_at=timezone.now(),
            closes_at=timezone.now() + timedelta(days=5),
            eligibility_rule={}, published_at=timezone.now())
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION="Token abc")
    response = client.get("/api/v1/placement/postings")
    assert response.status_code == 200
    payload = response.json()
    rows = payload.get("results", payload)
    assert expected <= {row["title"] for row in rows}


def _assert_company_authorization(case_kind):
    from conftest import make_principal
    from core.api.exceptions import ConflictError
    from modules.placement.models import Company, JobPosting
    from modules.placement.services import postings

    company = Company.objects.create(
        name="FR Pending Co", slug="fr-pending-co", status="prospect",
        approval_status="pending")
    actor = make_principal(
        user_id=9, kind="staff",
        permissions=("placement_cell.job_posting.manage",))
    try:
        postings.create(
            company_id=company.pk,
            placement_year="2026-27",
            actor=actor,
            title="FR Job",
            description="Role description.",
            eligibility_rule={"gte": ["cpi", 7.0]},
        )
    except ConflictError as exc:
        assert exc.code == "company_not_approved"
        assert not JobPosting.objects.filter(company=company).exists()
    else:
        raise AssertionError("Unapproved companies must not create postings")

    company.status = "active"
    company.approval_status = "approved"
    company.approved_by_user_id = 9
    company.save(update_fields=[
        "status", "approval_status", "approved_by_user_id", "updated_at",
    ])
    posting = postings.create(
        company_id=company.pk,
        placement_year="2026-27",
        actor=actor,
        title="FR Job",
        description="Role description.",
        eligibility_rule={"gte": ["cpi", 7.0]},
    )
    assert posting.status == "draft"


def _assert_notification_case(case_kind, request):
    from datetime import timedelta

    from django.utils import timezone

    from conftest import make_principal, make_session
    from fusion_auth.client import UserRef
    from modules.placement.models import (
        Application,
        Company,
        JobPosting,
        NotificationOutbox,
    )
    from modules.placement.services import applications, interviews

    student_id = 8301
    if case_kind == "submitted":
        stub_iam = request.getfixturevalue("stub_iam")
        stub_iam(make_session(
            user_id=student_id,
            kind="student",
            modules=("placement_cell",),
            permissions=("placement_cell.application.create",),
        ), users={student_id: UserRef(
            user_id=student_id,
            username="fr-student",
            display_name="FR Student",
            kind="student",
            profile_completed=True,
        )})
        actor = make_principal(
            user_id=student_id, kind="student",
            permissions=("placement_cell.application.create",))
        initial_status = "draft"
        target_status = "submitted"
    else:
        actor = make_principal(
            user_id=9,
            kind="staff",
            permissions=("placement_cell.application.review",
                        "placement_cell.interview.schedule"),
        )
        initial_status = {
            "shortlisted": "under_review",
            "rejected": "submitted",
            "interview": "shortlisted",
        }[case_kind]

    company = Company.objects.create(
        name="FR Notification Co", slug="fr-notification-co",
        status="active", approval_status="approved", approved_by_user_id=9)
    posting = JobPosting.objects.create(
        company=company,
        title="FR Notification Role",
        placement_year="2026-27",
        description="Role description.",
        status="published",
        eligibility_rule_locked_at=timezone.now(),
        closes_at=timezone.now() + timedelta(days=5),
        eligibility_rule={},
        published_at=timezone.now(),
    )
    application = Application.objects.create(
        posting=posting, user_id=student_id, status=initial_status,
        eligibility_snapshot={"is_eligible": True,
                              "season_decision": {"allowed": True}})

    if case_kind == "submitted":
        applications.transition(
            application_id=application.pk,
            to_status=target_status,
            actor=actor,
        )
        event = NotificationOutbox.objects.get(topic="application.submitted")
        assert event.recipient_user_id == student_id
    elif case_kind == "shortlisted":
        applications.transition(
            application_id=application.pk,
            to_status="shortlisted",
            actor=actor,
        )
        assert NotificationOutbox.objects.filter(
            topic="application.shortlisted",
            recipient_user_id=student_id,
        ).exists()
    elif case_kind == "rejected":
        applications.transition(
            application_id=application.pk,
            to_status="rejected",
            actor=actor,
            reason="FR test decision",
        )
        assert NotificationOutbox.objects.filter(
            topic="application.rejected",
            recipient_user_id=student_id,
        ).exists()
    else:
        round_ = interviews.schedule_round(
            posting_id=posting.pk,
            actor=actor,
            mode="online",
            starts_at=timezone.now() + timedelta(hours=3),
            meeting_url="https://example.test/fr-interview",
        )
        interviews.add_candidates(
            round_id=round_.pk,
            application_ids=[application.pk],
            actor=actor,
        )
        event = NotificationOutbox.objects.get(topic="interview.scheduled")
        assert event.recipient_user_id == student_id
        assert event.payload["application_id"] == application.pk


def _assert_interview_case(case_kind):
    from datetime import timedelta
    from types import SimpleNamespace

    from django.utils import timezone

    from conftest import make_principal
    from modules.placement.models import Application, Company, JobPosting, RecruiterAccount
    from modules.placement.services import interviews

    company = Company.objects.create(
        name="FR Interview Co", slug="fr-interview-co", status="active",
        approval_status="approved", approved_by_user_id=9)
    posting = JobPosting.objects.create(
        company=company, title="FR Interview Role", placement_year="2026-27",
        description="Role description.", status="published",
        eligibility_rule_locked_at=timezone.now(),
        closes_at=timezone.now() + timedelta(days=5), eligibility_rule={},
        published_at=timezone.now())
    application = Application.objects.create(
        posting=posting, user_id=8401, status="shortlisted")

    if case_kind == "company":
        recruiter_account = RecruiterAccount.objects.create(
            company=company,
            email="fr-interview-recruiter@example.test",
            full_name="FR Interview Recruiter",
        )
        actor = SimpleNamespace(
            kind="recruiter",
            account_id=recruiter_account.pk,
            company_id=company.pk,
            user_id=None,
        )
        scope = JobPosting.objects.filter(company=company)
    else:
        actor = make_principal(
            user_id=9, kind="staff",
            permissions=("placement_cell.interview.schedule",
                         "placement_cell.application.review"))
        scope = None
    round_ = interviews.schedule_round(
        posting_id=posting.pk,
        actor=actor,
        scope=scope,
        mode="online",
        starts_at=timezone.now() + timedelta(hours=3),
        meeting_url="https://example.test/fr-schedule",
    )
    assert interviews.add_candidates(
        round_id=round_.pk,
        application_ids=[application.pk],
        actor=actor,
    ) == 1
    application.refresh_from_db()
    assert application.status == "interview_scheduled"


def _assert_application_update(case_kind):
    from datetime import timedelta

    from django.utils import timezone

    from modules.placement.models import Application, Company, JobPosting
    from modules.placement.services import applications

    company = Company.objects.create(
        name="FR Review Co", slug="fr-review-co", status="active",
        approval_status="approved", approved_by_user_id=9)
    posting = JobPosting.objects.create(
        company=company, title="FR Review Role", placement_year="2026-27",
        description="Role description.", status="published",
        eligibility_rule_locked_at=timezone.now(),
        closes_at=timezone.now() + timedelta(days=5), eligibility_rule={},
        published_at=timezone.now())
    application = Application.objects.create(
        posting=posting, user_id=8501, status="submitted")
    if case_kind == "shortlist":
        from types import SimpleNamespace

        company_actor = SimpleNamespace(
            kind="recruiter", account_id=905, company_id=company.pk, user_id=None)
        scope = Application.objects.filter(posting__company=company)
        applications.transition(
            application_id=application.pk, to_status="under_review",
            actor=company_actor, scope=scope)
        updated = applications.transition(
            application_id=application.pk, to_status="shortlisted",
            actor=company_actor, scope=scope)
        assert updated.status == "shortlisted"
    else:
        from types import SimpleNamespace

        company_actor = SimpleNamespace(
            kind="recruiter", account_id=906, company_id=company.pk, user_id=None)
        scope = Application.objects.filter(posting__company=company)
        updated = applications.transition(
            application_id=application.pk, to_status="rejected",
            actor=company_actor, reason="FR rejection update", scope=scope)
        assert updated.status == "rejected"
        assert updated.withdrawn_reason == ""

def _assert_interview_fields(request):
    from datetime import timedelta

    from django.utils import timezone
    from rest_framework.test import APIClient

    from conftest import make_session
    from modules.placement.models import Company, InterviewRound, JobPosting

    stub_iam = request.getfixturevalue("stub_iam")
    stub_iam(make_session(
        user_id=9,
        kind="staff",
        modules=("placement_cell",),
        roles=("tpo",),
        active_role="tpo",
        permissions=("placement_cell.interview.schedule",
                     "placement_cell.job_posting.view"),
    ))
    company = Company.objects.create(
        name="FR Interview Validation Co", slug="fr-interview-validation-co",
        status="active", approval_status="approved", approved_by_user_id=9)
    posting = JobPosting.objects.create(
        company=company, title="FR Schedule Role", placement_year="2026-27",
        description="Role description.", status="published",
        eligibility_rule_locked_at=timezone.now(),
        closes_at=timezone.now() + timedelta(days=5), eligibility_rule={},
        published_at=timezone.now())
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION="Token abc")
    base = {"posting_id": posting.pk,
            "starts_at": (timezone.now() + timedelta(hours=3)).isoformat()}
    missing_mode = client.post(
        "/api/v1/placement/interviews/rounds", base, format="json")
    missing_datetime = client.post(
        "/api/v1/placement/interviews/rounds",
        {"posting_id": posting.pk, "mode": "online"}, format="json")
    missing_time = client.post(
        "/api/v1/placement/interviews/rounds",
        {**base, "starts_at": "", "mode": "online"}, format="json")
    assert missing_mode.status_code == 400
    assert missing_datetime.status_code == 400
    assert missing_time.status_code == 400
    assert InterviewRound.objects.count() == 0

    online = client.post(
        "/api/v1/placement/interviews/rounds",
        {**base, "mode": "online", "meeting_url": "https://example.test/online"},
        format="json")
    offline = client.post(
        "/api/v1/placement/interviews/rounds",
        {**base, "mode": "offline", "venue": "Lab 2"}, format="json")
    assert online.status_code == 201
    assert offline.status_code == 201


def _assert_role_case(case_kind):
    from datetime import timedelta
    from types import SimpleNamespace

    from django.utils import timezone

    from conftest import make_principal
    from core.api.exceptions import PermissionDeniedError
    from modules.placement.models import Application, Company, JobPosting
    from modules.placement.selectors import scoping
    from modules.placement.services import applications

    company = Company.objects.create(
        name="FR Scope Co", slug="fr-scope-co", status="active",
        approval_status="approved", approved_by_user_id=9)
    other_company = Company.objects.create(
        name="FR Other Co", slug="fr-other-co", status="active",
        approval_status="approved", approved_by_user_id=9)
    posting = JobPosting.objects.create(
        company=company, title="FR In Scope", placement_year="2026-27",
        description="Role description.", status="published",
        eligibility_rule_locked_at=timezone.now(),
        closes_at=timezone.now() + timedelta(days=5), eligibility_rule={},
        published_at=timezone.now())
    other_posting = JobPosting.objects.create(
        company=other_company, title="FR Out of Scope", placement_year="2026-27",
        description="Role description.", status="published",
        eligibility_rule_locked_at=timezone.now(),
        closes_at=timezone.now() + timedelta(days=5), eligibility_rule={},
        published_at=timezone.now())
    own = Application.objects.create(
        posting=posting, user_id=8601, status="submitted")
    other = Application.objects.create(
        posting=other_posting, user_id=8602, status="submitted")
    tpo = make_principal(
        user_id=9, kind="staff",
        permissions=("placement_cell.application.view",
                     "placement_cell.application.review"))
    student = make_principal(user_id=8601, kind="student")
    company_actor = SimpleNamespace(
        kind="recruiter", account_id=902, company_id=company.pk,
        user_id=None)
    alumni = make_principal(
        user_id=8701, kind="alumni", active_role="alumni", roles=("alumni",))

    if case_kind in {"alumni_read", "matrix", "confidentiality"}:
        alumni_postings = scoping.postings_for(alumni)
        assert alumni_postings.filter(pk=posting.pk).exists()
        assert not alumni_postings.filter(status="draft").exists()
        assert not scoping.applications_for(alumni).exists()
    if case_kind in {"matrix", "confidentiality"}:
        assert set(scoping.applications_for(tpo).values_list("pk", flat=True)) == {
            own.pk, other.pk}
        assert list(scoping.applications_for(student).values_list("pk", flat=True)) == [own.pk]
        assert list(scoping.applications_for(company_actor).values_list("pk", flat=True)) == [own.pk]
    if case_kind == "sensitive_read":
        assert scoping.may_read_candidate(tpo, 8601)
        assert not scoping.may_read_candidate(student, 8602)
        assert scoping.may_read_candidate(company_actor, 8601)
        assert not scoping.may_read_candidate(alumni, 8601)
    if case_kind == "sensitive_write":
        applications.transition(
            application_id=own.pk, to_status="under_review", actor=tpo)
        with pytest.raises(PermissionDeniedError):
            applications.transition(
                application_id=other.pk, to_status="under_review", actor=student)
        other.refresh_from_db()
        assert other.status == "submitted"
    if case_kind == "alumni_write":
        alumni_owner = make_principal(user_id=8601, kind="alumni",
                                      active_role="alumni", roles=("alumni",))
        with pytest.raises(PermissionDeniedError):
            applications.transition(
                application_id=own.pk, to_status="under_review", actor=alumni_owner)
        own.refresh_from_db()
        assert own.status == "submitted"
    if case_kind == "alumni_workflow":
        from core.api.exceptions import ConflictError
        from modules.placement.models import Offer, PlacementPolicy
        from modules.placement.services import interviews, offers

        alumni_owner = make_principal(
            user_id=8601, kind="alumni", active_role="alumni",
            roles=("alumni",))
        with pytest.raises(ConflictError) as application_refusal:
            applications.apply_to(posting_id=posting.pk, actor=alumni_owner)
        assert application_refusal.value.code == "alumni_workflow_prohibited"

        own.status = "under_review"
        own.save(update_fields=["status", "updated_at"])
        with pytest.raises(PermissionDeniedError):
            applications.transition(
                application_id=own.pk, to_status="shortlisted",
                actor=alumni_owner)
        own.refresh_from_db()
        assert own.status == "under_review"

        with pytest.raises(PermissionDeniedError):
            interviews.schedule_round(
                posting_id=posting.pk, actor=alumni_owner, mode="online",
                starts_at=timezone.now() + timedelta(hours=2),
                meeting_url="https://example.test/alumni")
        with pytest.raises(PermissionDeniedError):
            offers.issue(application_id=own.pk, actor=alumni_owner)

        own.status = "offer_issued"
        own.save(update_fields=["status", "updated_at"])
        PlacementPolicy.objects.create(season="2026-27", is_active=True)
        offer = Offer.objects.create(
            application=own, posting=posting, user_id=own.user_id,
            ctc_lpa="10.00", respond_by=timezone.now() + timedelta(days=1))
        with pytest.raises(ConflictError):
            offers.respond(offer_id=offer.pk, accept=True, actor=alumni_owner)
        offer.refresh_from_db()
        own.refresh_from_db()
        assert offer.status == "issued"
        assert own.status == "offer_issued"


def _assert_application_case(case_kind, request):
    from datetime import timedelta
    from types import SimpleNamespace

    import pytest
    from django.utils import timezone

    from conftest import make_principal, make_session
    from core.api.exceptions import ConflictError, NotFoundError
    from fusion_auth.client import UserRef
    from modules.placement.models import (
        Application,
        Company,
        JobPosting,
        PlacementPolicy,
        PlacementRegistration,
    )
    from modules.placement.selectors import scoping
    from modules.placement.services import applications

    if case_kind == "history":
        from modules.placement.models import ApplicationTransition

        company = Company.objects.create(
            name="FR History Co", slug="fr-history-co", status="active",
            approval_status="approved", approved_by_user_id=9)
        posting = JobPosting.objects.create(
            company=company, title="FR History Role", placement_year="2026-27",
            description="Role description.", status="published",
            eligibility_rule_locked_at=timezone.now(),
            closes_at=timezone.now() + timedelta(days=5), eligibility_rule={},
            published_at=timezone.now())
        application = Application.objects.create(
            posting=posting, user_id=8803, status="submitted")
        actor = make_principal(
            user_id=9, kind="staff",
            permissions=("placement_cell.application.review",))
        applications.transition(
            application_id=application.pk, to_status="under_review", actor=actor)
        rows = ApplicationTransition.objects.filter(application=application)
        assert list(rows.values_list("to_status", flat=True)) == ["under_review"]
        application.refresh_from_db()
        assert application.status == "under_review"
        return

    if case_kind in {"eligible_apply", "eligibility_gate"}:
        stub_iam = request.getfixturevalue("stub_iam")
        user_ids = [8801, 8802] if case_kind == "eligibility_gate" else [8801]
        user_refs = {
            user_id: UserRef(
                user_id=user_id,
                username=f"fr-{user_id}",
                display_name=f"FR Student {user_id}",
                kind="student",
                profile_completed=True,
                discipline="CSE",
                programme="B.Tech",
                batch_year=2026,
            )
            for user_id in user_ids
        }
        iam = stub_iam(make_session(
            user_id=user_ids[0], kind="student",
            modules=("placement_cell",),
            permissions=("placement_cell.application.create",),
        ), users=user_refs)
        for user_id in user_ids:
            iam.standings[user_id] = {
                "cpi": "8.0" if user_id == 8801 else "6.0",
                "active_backlogs": 0,
                "earned_credits": "120",
                "semester": 6,
                "declared_seq": 1,
            }
        policy = PlacementPolicy.objects.create(
            season="2026-27", is_active=True)
        for user_id in user_ids:
            PlacementRegistration.objects.create(
                policy=policy, user_id=user_id, status="registered",
                registered_at=timezone.now())
        company = Company.objects.create(
            name="FR Apply Co", slug="fr-apply-co", status="active",
            approval_status="approved", approved_by_user_id=9)
        posting = JobPosting.objects.create(
            company=company, title="FR Eligible Role", placement_year="2026-27",
            description="Role description.", status="published",
            eligibility_rule_locked_at=timezone.now(),
            closes_at=timezone.now() + timedelta(days=5),
            eligibility_rule={"gte": ["cpi", 7.0]},
            published_at=timezone.now())
        student = make_principal(
            user_id=8801, kind="student",
            permissions=("placement_cell.application.create",))
        result = applications.apply_to(posting_id=posting.pk, actor=student)
        assert result.status == "submitted"
        if case_kind == "eligibility_gate":
            unqualified = make_principal(
                user_id=8802, kind="student",
                permissions=("placement_cell.application.create",))
            with pytest.raises(ConflictError) as refusal:
                applications.apply_to(posting_id=posting.pk, actor=unqualified)
            assert refusal.value.code == "not_eligible"
            assert not Application.objects.filter(
                posting=posting, user_id=8802).exists()
        return

    company = Company.objects.create(
        name="FR Application Scope Co", slug="fr-application-scope-co",
        status="active", approval_status="approved", approved_by_user_id=9)
    other_company = Company.objects.create(
        name="FR Other Scope Co", slug="fr-other-scope-co",
        status="active", approval_status="approved", approved_by_user_id=9)
    posting = JobPosting.objects.create(
        company=company, title="FR Scoped Role", placement_year="2026-27",
        description="Role description.", status="published",
        eligibility_rule_locked_at=timezone.now(),
        closes_at=timezone.now() + timedelta(days=5), eligibility_rule={},
        published_at=timezone.now())
    other_posting = JobPosting.objects.create(
        company=other_company, title="FR Foreign Role", placement_year="2026-27",
        description="Role description.", status="published",
        eligibility_rule_locked_at=timezone.now(),
        closes_at=timezone.now() + timedelta(days=5), eligibility_rule={},
        published_at=timezone.now())
    own = Application.objects.create(
        posting=posting, user_id=8901, status="submitted")
    foreign = Application.objects.create(
        posting=other_posting, user_id=8902, status="submitted")

    if case_kind == "tpo_scope":
        actor = make_principal(
            user_id=9, kind="staff",
            permissions=("placement_cell.application.review",))
        scope = Application.objects.filter(posting__company=company)
        updated = applications.transition(
            application_id=own.pk, to_status="under_review",
            actor=actor, scope=scope)
        assert updated.status == "under_review"
        with pytest.raises(NotFoundError):
            applications.transition(
                application_id=foreign.pk, to_status="under_review",
                actor=actor, scope=scope)
        foreign.refresh_from_db()
        assert foreign.status == "submitted"
    elif case_kind == "filter":
        stub_iam = request.getfixturevalue("stub_iam")
        stub_iam(make_session(
            user_id=9, kind="staff", modules=("placement_cell",),
            permissions=("placement_cell.application.view",)))
        Application.objects.filter(pk=foreign.pk).update(status="under_review")
        from rest_framework.test import APIClient

        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION="Token abc")
        response = client.get("/api/v1/placement/applications?status=submitted")
        assert response.status_code == 200
        rows = response.json().get("results", response.json())
        assert {row["id"] for row in rows} == {own.pk}
        own.refresh_from_db()
        foreign.refresh_from_db()
        assert (own.status, foreign.status) == ("submitted", "under_review")
    elif case_kind == "administration":
        actor = make_principal(
            user_id=9, kind="staff",
            permissions=("placement_cell.application.review",))
        updated = applications.transition(
            application_id=own.pk, to_status="under_review", actor=actor)
        assert updated.status == "under_review"
        with pytest.raises(ConflictError) as refusal:
            applications.transition(
                application_id=own.pk, to_status="selected", actor=actor)
        assert refusal.value.code == "invalid_transition"
        own.refresh_from_db()
        assert own.status == "under_review"
    else:
        actor = SimpleNamespace(
            kind="recruiter", company_id=company.pk, account_id=903,
            user_id=None)
        visible = scoping.applications_for(actor)
        assert list(visible.values_list("pk", flat=True)) == [own.pk]
        assert not visible.filter(pk=foreign.pk).exists()
        applications.transition(
            application_id=own.pk, to_status="under_review",
            actor=actor, scope=visible)
        with pytest.raises(NotFoundError):
            applications.transition(
                application_id=foreign.pk, to_status="under_review",
                actor=actor, scope=visible)
        foreign.refresh_from_db()
        assert foreign.status == "submitted"






def _install_offer_flow_directory(request):
    from importlib import import_module

    from conftest import make_session
    from fusion_auth.client import UserRef

    install_iam = request.getfixturevalue("stub_iam")
    offer_flow = import_module("modules.placement.tests.test_offer_flow")

    def install(discipline="CSE"):
        install_iam(make_session(
            user_id=1001,
            kind="student",
            permissions=("placement_cell.offer.respond",),
        ), users={1001: UserRef(
            user_id=1001,
            username="fr-student",
            display_name="FR Student",
            kind="student",
            discipline=discipline,
            profile_completed=True,
        )})

    offer_flow._SET_DISCIPLINE["fn"] = install
    install()







def _assert_company_offer():
    from datetime import timedelta
    from importlib import import_module
    from types import SimpleNamespace

    from django.utils import timezone

    from modules.placement.models import Application, Company, JobPosting, RecruiterAccount
    from modules.placement.services import offers

    offer_helpers = import_module("modules.placement.tests.test_offer_flow")
    offer_helpers.make_world()
    company = Company.objects.create(
        name="FR Recruiter Offer Co", slug="fr-recruiter-offer-co",
        status="active", approval_status="approved", approved_by_user_id=9)
    recruiter_account = RecruiterAccount.objects.create(
        company=company,
        email="fr-offer-recruiter@example.test",
        full_name="FR Offer Recruiter",
    )
    posting = JobPosting.objects.create(
        company=company, title="FR Recruiter Offer", placement_year="2026-27",
        description="Role description.", status="published",
        eligibility_rule_locked_at=timezone.now(),
        closes_at=timezone.now() + timedelta(days=5),
        eligibility_rule={}, ctc_lpa="11.00", published_at=timezone.now())
    application = Application.objects.create(
        posting=posting, user_id=1001, status="selected")
    recruiter = SimpleNamespace(
        kind="recruiter", account_id=recruiter_account.pk,
        company_id=company.pk, user_id=None)
    scope = Application.objects.filter(posting__company=company)
    offer = offers.issue(application_id=application.pk, actor=recruiter, scope=scope)
    assert offer.status == "issued"
    application.refresh_from_db()
    assert application.status == "offer_issued"


