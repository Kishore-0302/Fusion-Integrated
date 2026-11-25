"""Alumni access tests.

Covers spec gaps G-03 (PC-BR-019: alumni CAN view job postings) and
G-04 (PC-BR-020: alumni CANNOT participate in active placement workflows).

Spec refs: PC-UC-017, PC-BR-019, PC-BR-020.
"""
from datetime import timedelta

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from conftest import make_session
from core.api.exceptions import ConflictError
from modules.placement.models import Company, JobPosting, PlacementPolicy
from modules.placement.services import applications as app_service

pytestmark = pytest.mark.django_db

VIEW_POSTING_PERM = "placement_cell.job_posting.view"


@pytest.fixture
def published_posting():
    company = Company.objects.create(
        name="Acme", slug="acme", status="active",
        approval_status="approved", approved_by_user_id=9)
    PlacementPolicy.objects.create(season="2026-27", is_active=True)
    return JobPosting.objects.create(
        company=company, title="SDE-1", placement_year="2026-27",
        description="Build great software.", status="published",
        closes_at=timezone.now() + timedelta(days=7),
        eligibility_rule={}, eligibility_rule_locked_at=timezone.now(),
        ctc_lpa="12.00", created_by_user_id=9,
        published_at=timezone.now())


# ---------------------------------------------------------------------------
# G-03: PC-BR-019 — Alumni CAN view job postings (read-only)
# ---------------------------------------------------------------------------

class TestAlumniReadOnlyAccess:
    """PC-BR-019: Alumni access is restricted to mentorship/networking
    purposes and is read-only. PC-AFR-058..060: they may view job postings."""

    def test_alumni_can_list_job_postings_over_http(
            self, stub_iam, published_posting):
        """An alumni token with job_posting.view permission can browse."""
        stub_iam(make_session(
            user_id=5001, kind="alumni", active_role="alumni",
            modules=("placement_cell",),
            permissions=(VIEW_POSTING_PERM,)))
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION="Token abc")
        resp = client.get("/api/v1/placement/postings")
        # Alumni may view published postings
        assert resp.status_code == 200

    def test_alumni_can_see_a_specific_posting(
            self, stub_iam, published_posting):
        """PC-UC-017: alumni opens the permitted placement-data view."""
        stub_iam(make_session(
            user_id=5001, kind="alumni", active_role="alumni",
            modules=("placement_cell",),
            permissions=(VIEW_POSTING_PERM,)))
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION="Token abc")
        resp = client.get(f"/api/v1/placement/postings/{published_posting.pk}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["title"] == "SDE-1"

    def test_alumni_registry_role_has_view_posting_permission(self):
        """registry.py ROLE_GRANTS must include job_posting.view for alumni."""
        from modules.placement.registry import ROLE_GRANTS
        grants = ROLE_GRANTS.get("alumni", [])
        assert "placement_cell.job_posting.view" in grants, (
            "Alumni registry entry must include job_posting.view — "
            "see PC-BR-019, PC-AFR-058")


# ---------------------------------------------------------------------------
# G-04: PC-BR-020 — Alumni CANNOT participate in active placement workflows
# ---------------------------------------------------------------------------

class TestAlumniWorkflowProhibition:
    """PC-BR-020: PCMS shall prevent Alumni from participating in active
    placement workflows: applying, shortlisting, scheduling, offer issuance,
    or offer acceptance."""

    def test_alumni_cannot_apply_to_a_posting(
            self, stub_iam, published_posting):
        """PC-BR-020 primary path: apply_to raises ConflictError for alumni."""
        stub_iam(make_session(user_id=5001, kind="alumni",
                              active_role="alumni",
                              modules=("placement_cell",),
                              permissions=(
                                  "placement_cell.application.create",
                                  VIEW_POSTING_PERM,)))
        from conftest import make_principal
        alumni_principal = make_principal(
            user_id=5001, kind="alumni", active_role="alumni",
            permissions=("placement_cell.application.create",))
        with pytest.raises(ConflictError) as exc:
            app_service.apply_to(
                posting_id=published_posting.pk,
                actor=alumni_principal)
        assert exc.value.code == "alumni_workflow_prohibited"

    def test_alumni_applying_via_http_is_refused(
            self, stub_iam, published_posting):
        """The HTTP layer must also refuse alumni from applying."""
        stub_iam(make_session(
            user_id=5001, kind="alumni", active_role="alumni",
            modules=("placement_cell",),
            permissions=(
                "placement_cell.application.create",
                VIEW_POSTING_PERM,)))
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION="Token abc")
        resp = client.post(
            "/api/v1/placement/applications/apply",
            {"posting_id": published_posting.pk}, format="json")
        # Must be refused — 409 Conflict from the alumni workflow guard
        assert resp.status_code == 409
        assert resp.json()["error"]["code"] == "alumni_workflow_prohibited"

    def test_alumni_cannot_write_placement_data(self, stub_iam, published_posting):
        """PC-BR-024: only authorized stakeholders may modify placement data.
        Alumni have no modify permissions in their registry role."""
        from modules.placement.registry import ROLE_GRANTS
        alumni_permissions = set(ROLE_GRANTS.get("alumni", []))
        # Alumni should have NO write/manage/review permissions
        write_perms = {p for p in alumni_permissions
                       if any(x in p for x in
                              ("manage", "create", "review", "schedule",
                               "issue", "respond", "publish"))}
        assert not write_perms, (
            f"Alumni registry must not include write permissions, "
            f"but found: {write_perms}")
