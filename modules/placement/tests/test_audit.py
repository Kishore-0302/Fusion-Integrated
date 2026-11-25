"""Reading the audit trail (PC-AFR-009, PC-UC-004).

The interesting property is not that the trail exists — services already write
it — but that each reader sees the right slice of it. A student is owed their own
timeline; they are not owed the TPO's internal note or the name of the person who
rejected them. Their own conduct record is the opposite: shown in full, because
rule 19's waiver and rule 21's sanction are both contestable.
"""
from datetime import timedelta

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from conftest import make_session
from modules.placement.models import (
    Application,
    Company,
    ConductIncident,
    JobPosting,
    PlacementPolicy,
    PlacementRegistration,
    RecruiterAccount,
)
from modules.placement.services import applications as application_service
from modules.placement.services import recruiters

pytestmark = pytest.mark.django_db

SEASON = "2026-27"
STUDENT = 1001
OTHER = 2002
PASSWORD = "a-long-enough-password"
REASON = "Weak on data structures — do not shortlist again"


def _client(stub_iam, perms, uid=STUDENT, kind="student"):
    stub_iam(make_session(user_id=uid, kind=kind, modules=("placement_cell",),
                          permissions=perms))
    c = APIClient()
    c.credentials(HTTP_AUTHORIZATION="Token abc")
    return c


def _staff_actor(uid=9):
    from fusion_auth.principal import Principal
    return Principal.from_session(make_session(
        user_id=uid, kind="staff", modules=("placement_cell",),
        permissions=("placement_cell.application.view",
                     "placement_cell.application.review")))


@pytest.fixture
def rejected_application(stub_iam):
    """An application a TPO has rejected, with an internal note on the record."""
    stub_iam()
    PlacementPolicy.objects.create(season=SEASON, is_active=True)
    company = Company.objects.create(
        name="Acme", slug="acme", status="active",
        approval_status="approved", approved_by_user_id=9)
    posting = JobPosting.objects.create(
        company=company, title="SDE", placement_year=SEASON, description="d",
        status="published", published_at=timezone.now(),
        closes_at=timezone.now() + timedelta(days=7),
        eligibility_rule={}, eligibility_rule_locked_at=timezone.now())
    app = Application.objects.create(posting=posting, user_id=STUDENT,
                                     status="submitted")
    application_service.transition(
        application_id=app.pk, to_status="rejected", actor=_staff_actor(),
        reason=REASON, scope=Application.objects.all())
    return app


# -- Who sees the reason -----------------------------------------------------------
class TestApplicationHistory:

    def test_staff_see_the_reason_and_the_actor(self, stub_iam,
                                                rejected_application):
        client = _client(stub_iam, ("placement_cell.application.view",),
                         uid=9, kind="staff")
        body = client.get(
            f"/api/v1/placement/applications/{rejected_application.pk}/history"
        ).json()

        assert body["redacted"] is False
        entry = body["results"][-1]
        assert entry["reason"] == REASON
        assert entry["actor_user_id"] == 9

    def test_a_student_sees_the_timeline_without_the_internal_note(
            self, stub_iam, rejected_application):
        """The note was written on the understanding it was internal — the
        notification only ever told the student the status changed."""
        client = _client(stub_iam, ("placement_cell.application.view_self",))
        body = client.get(
            f"/api/v1/placement/applications/{rejected_application.pk}/history"
        ).json()

        assert body["redacted"] is True
        entry = body["results"][-1]
        assert entry["to_status"] == "rejected"
        assert "reason" not in entry
        assert REASON not in str(body)

    def test_a_student_is_not_told_who_acted(self, stub_iam,
                                             rejected_application):
        """Naming the TPO who rejected someone invites pressure on them. The
        lane — staff, student, system — is still shown."""
        client = _client(stub_iam, ("placement_cell.application.view_self",))
        entry = client.get(
            f"/api/v1/placement/applications/{rejected_application.pk}/history"
        ).json()["results"][-1]

        assert "actor_user_id" not in entry
        assert entry["actor_label"] == "staff"

    def test_the_timeline_is_ordered_oldest_first(self, stub_iam,
                                                  rejected_application):
        client = _client(stub_iam, ("placement_cell.application.view_self",))
        rows = client.get(
            f"/api/v1/placement/applications/{rejected_application.pk}/history"
        ).json()["results"]
        assert [r["to_status"] for r in rows][-1] == "rejected"
        assert rows == sorted(rows, key=lambda r: r["at"])


# -- Scope ---------------------------------------------------------------------------
class TestHistoryScope:

    def test_another_students_history_is_a_404(self, stub_iam,
                                               rejected_application):
        """Scoped like every other read, so it is absent rather than forbidden."""
        client = _client(stub_iam, ("placement_cell.application.view_self",),
                         uid=OTHER)
        assert client.get(
            f"/api/v1/placement/applications/{rejected_application.pk}/history"
        ).status_code == 404

    def test_an_unauthenticated_read_is_refused(self, rejected_application):
        assert APIClient().get(
            f"/api/v1/placement/applications/{rejected_application.pk}/history"
        ).status_code == 401

    def test_a_recruiter_reads_their_own_applicants_redacted(
            self, stub_iam, rejected_application):
        """PC-BR-009 gets them the timeline; the institute's note is not theirs
        to read."""
        stub_iam()
        company = rejected_application.posting.company
        _, raw = recruiters.invite(company_id=company.pk, email="r@acme.test",
                                   invited_by_user_id=9)
        recruiters.accept_invite(token=raw, password=PASSWORD)
        RecruiterAccount.objects.get(email="r@acme.test")
        session = recruiters.sign_in(email="r@acme.test", password=PASSWORD)
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f"Recruiter {session.raw_key}")

        body = client.get(
            f"/api/v1/placement/applications/{rejected_application.pk}/history"
        ).json()

        assert body["redacted"] is True
        assert REASON not in str(body)

    def test_another_companys_recruiter_gets_a_404(self, stub_iam,
                                                  rejected_application):
        stub_iam()
        borg = Company.objects.create(
            name="Borg", slug="borg", status="active",
            approval_status="approved", approved_by_user_id=9)
        _, raw = recruiters.invite(company_id=borg.pk, email="r@borg.test",
                                   invited_by_user_id=9)
        recruiters.accept_invite(token=raw, password=PASSWORD)
        session = recruiters.sign_in(email="r@borg.test", password=PASSWORD)
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f"Recruiter {session.raw_key}")

        assert client.get(
            f"/api/v1/placement/applications/{rejected_application.pk}/history"
        ).status_code == 404


# -- A student's own conduct record ----------------------------------------------------
class TestMyConductRecord:

    @pytest.fixture
    def incident(self):
        policy = PlacementPolicy.objects.create(season=SEASON, is_active=True)
        registration = PlacementRegistration.objects.create(
            policy=policy, user_id=STUDENT, status="registered")
        return ConductIncident.objects.create(
            registration=registration, user_id=STUDENT,
            kind="consent_failure", note="Did not appear at the Acme test",
            recorded_by_user_id=9)

    def test_a_student_sees_their_own_incident_in_full(self, stub_iam, incident):
        """Rule 21 leaves a sanction to the Chairperson and rule 19 allows a
        waiver. Neither is contestable if the student cannot read the record."""
        client = _client(stub_iam, ("placement_cell.application.view_self",))
        rows = client.get("/api/v1/placement/conduct/mine").json()["results"]

        assert len(rows) == 1
        assert rows[0]["note"] == "Did not appear at the Acme test"
        assert rows[0]["kind"] == "consent_failure"

    def test_the_waiver_reason_is_shown_too(self, stub_iam, incident):
        # Waiving needs registration.debar, which the actor above does not hold.
        from fusion_auth.principal import Principal
        from modules.placement.services import conduct
        officer = Principal.from_session(make_session(
            user_id=9, kind="staff", modules=("placement_cell",),
            permissions=("placement_cell.registration.debar",)))
        conduct.waive(incident_id=incident.pk, reason="Wrote in advance; ill",
                      actor=officer)
        client = _client(stub_iam, ("placement_cell.application.view_self",))
        row = client.get("/api/v1/placement/conduct/mine").json()["results"][0]

        assert row["waived"] is True
        assert row["waived_reason"] == "Wrote in advance; ill"

    def test_who_recorded_it_is_not_shown(self, stub_iam, incident):
        client = _client(stub_iam, ("placement_cell.application.view_self",))
        row = client.get("/api/v1/placement/conduct/mine").json()["results"][0]
        assert "recorded_by_user_id" not in row

    def test_a_student_sees_only_their_own(self, stub_iam, incident):
        """Scoped by the credential — there is no user parameter to point
        elsewhere."""
        client = _client(stub_iam, ("placement_cell.application.view_self",),
                         uid=OTHER)
        assert client.get(
            "/api/v1/placement/conduct/mine").json()["results"] == []
