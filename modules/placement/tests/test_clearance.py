"""Post-offer obligations (policy rules 22 and 24).

Rule 24 lets placement hold up a no-dues certificate, which is the only place
this module can block a student's graduation paperwork. So the tests care about
two things: that it blocks exactly the right people, and that a refusal says
which company still owes a letter — an unexplained hold at the end of a degree
is what ends up in the Dean's office.
"""
from datetime import date, timedelta

import pytest
from django.db import IntegrityError, transaction
from django.utils import timezone
from rest_framework.test import APIClient

from conftest import make_session
from core.api.exceptions import ConflictError, NotFoundError, PermissionDeniedError
from modules.placement import contracts
from modules.placement.domain import clearance as rules
from modules.placement.models import (
    Application,
    Company,
    JobPosting,
    Offer,
    PlacementPolicy,
    PlacementRecord,
)
from modules.placement.services import clearance as service
from modules.placement.services import documents as document_service

pytestmark = pytest.mark.django_db

SEASON = "2026-27"
STUDENT = 1001
OTHER = 2002
LINK = "https://drive.google.com/file/d/1A2b3C4d5E6f7G8h9I0jKlMnOpQrStUv/view"


def _actor(uid=9, perms=("placement_cell.record.manage",)):
    from fusion_auth.principal import Principal
    return Principal.from_session(
        make_session(user_id=uid, kind="staff", permissions=perms,
                     modules=("placement_cell",)))


def _client(stub_iam, perms=("placement_cell.application.view_self",),
            uid=STUDENT):
    stub_iam(make_session(user_id=uid, modules=("placement_cell",),
                          permissions=perms))
    c = APIClient()
    c.credentials(HTTP_AUTHORIZATION="Token abc")
    return c


@pytest.fixture
def policy():
    return PlacementPolicy.objects.create(
        season=SEASON, is_active=True,
        notify_non_joining_by=timezone.localdate() + timedelta(days=30))


def make_company(name="Acme", slug="acme"):
    return Company.objects.create(
        name=name, slug=slug, status="active",
        approval_status="approved", approved_by_user_id=9)


def campus_record(policy, company, user_id=STUDENT):
    """A placement that came through the portal — offer and posting present."""
    posting = JobPosting.objects.create(
        company=company, title="SDE", placement_year=SEASON, description="d",
        status="published", published_at=timezone.now(),
        closes_at=timezone.now() + timedelta(days=7),
        eligibility_rule={}, eligibility_rule_locked_at=timezone.now())
    app = Application.objects.create(posting=posting, user_id=user_id,
                                     status="offer_accepted")
    offer = Offer.objects.create(
        application=app, posting=posting, user_id=user_id, ctc_lpa="18.00",
        respond_by=timezone.now() + timedelta(days=1), status="accepted")
    return PlacementRecord.objects.create(
        policy=policy, offer=offer, posting=posting, company=company,
        user_id=user_id, ctc_lpa="18.00", kind="fte", source="campus",
        is_active=True, recorded_by_user_id=user_id)


def offer_letter(user_id=STUDENT):
    return document_service.attach_link(
        user_id=user_id, kind="offer_letter", url=LINK, title="Signed offer")


# -- Rule 24, as pure rules ------------------------------------------------------
class TestClearanceRules:

    def test_a_student_with_no_placement_is_cleared(self):
        """The rule bites on the placed. Everyone else walks through."""
        assert rules.no_dues_clearance(()).cleared is True

    def test_a_placement_without_a_letter_blocks(self):
        verdict = rules.no_dues_clearance(
            (rules.RecordState("Acme", has_signed_offer_letter=False),))
        assert verdict.cleared is False
        assert verdict.blocking == ("Acme",)

    def test_the_refusal_names_the_company(self):
        """"Blocked" alone sends the student to the wrong office."""
        verdict = rules.no_dues_clearance(
            (rules.RecordState("Acme", has_signed_offer_letter=False),))
        assert "Acme" in verdict.message
        assert "rule 24" in verdict.message.lower()

    def test_declaring_not_joining_does_not_release_the_letter(self):
        """The acceptance happened and the record stands, so rule 24 still
        wants the signed copy."""
        verdict = rules.no_dues_clearance((
            rules.RecordState("Acme", has_signed_offer_letter=False,
                              declared_not_joining=True),))
        assert verdict.cleared is False


# -- Rule 22, as pure rules ------------------------------------------------------
class TestNonJoiningRules:

    def test_on_or_before_the_cut_off_is_not_late(self):
        v = rules.assess_non_joining(declared_on=date(2027, 4, 15),
                                     deadline=date(2027, 4, 15))
        assert v.accepted and not v.is_late

    def test_after_the_cut_off_is_late_but_still_accepted(self):
        """Refusing it would leave the Placement Cell less informed, which is
        the opposite of what rule 22 wants."""
        v = rules.assess_non_joining(declared_on=date(2027, 4, 16),
                                     deadline=date(2027, 4, 15))
        assert v.accepted and v.is_late
        assert "may refer" in v.message

    def test_with_no_cut_off_configured_nothing_is_late(self):
        v = rules.assess_non_joining(declared_on=date(2027, 12, 1), deadline=None)
        assert v.accepted and not v.is_late


# -- The service -----------------------------------------------------------------
class TestOfferLetter:

    def test_submitting_the_letter_clears_the_hold(self, stub_iam, policy):
        stub_iam()
        record = campus_record(policy, make_company())
        assert service.no_dues_clearance(user_id=STUDENT).cleared is False

        service.submit_offer_letter(record_id=record.pk, user_id=STUDENT,
                                    document_id=offer_letter().pk)
        assert service.no_dues_clearance(user_id=STUDENT).cleared is True

    def test_only_a_document_of_the_right_kind_counts(self, stub_iam, policy):
        """A certificate is not an offer letter, however it is named."""
        stub_iam()
        record = campus_record(policy, make_company())
        other = document_service.attach_link(user_id=STUDENT, kind="certificate",
                                             url=LINK, title="Offer letter")
        with pytest.raises(ConflictError) as exc:
            service.submit_offer_letter(record_id=record.pk, user_id=STUDENT,
                                        document_id=other.pk)
        assert exc.value.code == "wrong_document_kind"

    def test_someone_elses_record_is_a_404(self, stub_iam, policy):
        stub_iam()
        record = campus_record(policy, make_company(), user_id=OTHER)
        with pytest.raises(NotFoundError):
            service.submit_offer_letter(record_id=record.pk, user_id=STUDENT,
                                        document_id=offer_letter().pk)

    def test_someone_elses_document_is_a_404(self, stub_iam, policy):
        """Both ids are scoped to the caller, so neither reaches a peer."""
        stub_iam()
        record = campus_record(policy, make_company())
        theirs = offer_letter(user_id=OTHER)
        with pytest.raises(NotFoundError):
            service.submit_offer_letter(record_id=record.pk, user_id=STUDENT,
                                        document_id=theirs.pk)


class TestNotJoining:

    def test_declaring_on_time(self, stub_iam, policy):
        stub_iam()
        record = campus_record(policy, make_company())
        record, verdict = service.declare_not_joining(
            record_id=record.pk, user_id=STUDENT, reason="Higher studies")
        assert verdict.is_late is False
        assert record.not_joining_reason == "Higher studies"

    def test_declaring_after_the_cut_off_is_recorded_as_late(self, stub_iam,
                                                             policy):
        stub_iam()
        policy.notify_non_joining_by = timezone.localdate() - timedelta(days=1)
        policy.save()
        record = campus_record(policy, make_company())
        record, verdict = service.declare_not_joining(
            record_id=record.pk, user_id=STUDENT, reason="Higher studies")
        assert verdict.is_late is True
        assert record.not_joining_was_late is True

    def test_a_reason_is_required(self, stub_iam, policy):
        """Rule 22 asks for the ground — higher studies or another genuine one."""
        stub_iam()
        record = campus_record(policy, make_company())
        with pytest.raises(ConflictError):
            service.declare_not_joining(record_id=record.pk, user_id=STUDENT,
                                        reason="   ")

    def test_declaring_twice_is_refused(self, stub_iam, policy):
        stub_iam()
        record = campus_record(policy, make_company())
        service.declare_not_joining(record_id=record.pk, user_id=STUDENT,
                                    reason="Higher studies")
        with pytest.raises(ConflictError) as exc:
            service.declare_not_joining(record_id=record.pk, user_id=STUDENT,
                                        reason="again")
        assert exc.value.code == "already_declared"

    def test_the_placement_cell_is_told(self, stub_iam, policy):
        from modules.placement.models import NotificationOutbox
        stub_iam()
        record = campus_record(policy, make_company())
        service.declare_not_joining(record_id=record.pk, user_id=STUDENT,
                                    reason="Higher studies")
        assert NotificationOutbox.objects.filter(
            topic="record.not_joining").exists()


class TestOffCampus:

    def test_an_off_campus_placement_also_blocks_no_dues(self, stub_iam, policy):
        """Rule 24 says "placed (on/off campus)". Without a record for these,
        the gate would miss the students least likely to have submitted
        anything."""
        stub_iam()
        service.record_off_campus(season=SEASON, user_id=STUDENT,
                                  company_id=make_company("Globex", "globex").pk,
                                  ctc_lpa="22.00", actor=_actor())
        verdict = service.no_dues_clearance(user_id=STUDENT)
        assert verdict.cleared is False
        assert verdict.blocking == ("Globex",)

    def test_recording_one_needs_the_manage_permission(self, stub_iam, policy):
        stub_iam()
        with pytest.raises(PermissionDeniedError):
            service.record_off_campus(
                season=SEASON, user_id=STUDENT, company_id=make_company().pk,
                actor=_actor(perms=("placement_cell.report.view",)))

    def test_a_second_active_placement_is_refused(self, stub_iam, policy):
        stub_iam()
        campus_record(policy, make_company())
        with pytest.raises(ConflictError) as exc:
            service.record_off_campus(
                season=SEASON, user_id=STUDENT,
                company_id=make_company("Globex", "globex").pk, actor=_actor())
        assert exc.value.code == "already_placed"

    def test_the_database_refuses_a_campus_record_with_no_offer(self, policy):
        """The source field would otherwise be able to lie about where a
        placement came from."""
        company = make_company()
        with pytest.raises(IntegrityError), transaction.atomic():
            PlacementRecord.objects.create(
                policy=policy, user_id=STUDENT, company=company,
                source="campus", offer=None, posting=None, is_active=True)


class TestOutstandingWorklist:

    def test_it_lists_only_records_still_owing_a_letter(self, stub_iam, policy):
        stub_iam()
        record = campus_record(policy, make_company())
        assert len(service.outstanding(season=SEASON)) == 1
        service.submit_offer_letter(record_id=record.pk, user_id=STUDENT,
                                    document_id=offer_letter().pk)
        assert service.outstanding(season=SEASON) == []


# -- The contract other modules use ----------------------------------------------
class TestContract:

    def test_clearances_are_batched_and_keyed_by_user(self, stub_iam, policy):
        """The academic office checks a graduating batch, not a person."""
        stub_iam()
        campus_record(policy, make_company(), user_id=STUDENT)
        result = contracts.get_no_dues_clearances([STUDENT, OTHER, None])

        assert set(result) == {STUDENT, OTHER}
        assert result[STUDENT].cleared is False
        assert result[STUDENT].blocking == ("Acme",)
        # No placement at all, so nothing for rule 24 to hold.
        assert result[OTHER].cleared is True

    def test_an_empty_request_costs_nothing(self):
        assert contracts.get_no_dues_clearances([]) == {}


# -- HTTP --------------------------------------------------------------------------
class TestClearanceApi:

    def test_a_student_sees_their_own_clearance(self, stub_iam, policy):
        campus_record(policy, make_company())
        client = _client(stub_iam)
        body = client.get("/api/v1/placement/records/clearance").json()
        assert body["cleared"] is False
        assert body["blocking"] == ["Acme"]

    def test_the_clearance_endpoint_takes_no_user_parameter(self, stub_iam,
                                                           policy):
        """Scoped by the credential, so it cannot be pointed at a peer."""
        campus_record(policy, make_company(), user_id=OTHER)
        client = _client(stub_iam)
        body = client.get(
            "/api/v1/placement/records/clearance?user_id=2002").json()
        assert body["user_id"] == STUDENT
        assert body["cleared"] is True

    def test_a_student_cannot_read_the_office_worklist(self, stub_iam, policy):
        campus_record(policy, make_company())
        client = _client(stub_iam)
        assert client.get(
            "/api/v1/placement/records/outstanding").status_code == 403

    def test_a_reports_reader_can_read_the_office_worklist(self, stub_iam,
                                                           policy):
        """The worklist is a report; gating it on record.manage locked out every
        coordinator and rendered as "every student has filed one"."""
        campus_record(policy, make_company())
        client = _client(stub_iam, perms=("placement_cell.report.view",), uid=9)
        assert client.get(
            "/api/v1/placement/records/outstanding").status_code == 200

    def test_a_student_cannot_record_an_off_campus_placement(self, stub_iam,
                                                            policy):
        client = _client(stub_iam)
        assert client.post("/api/v1/placement/records/off-campus", {
            "season": SEASON, "user_id": STUDENT,
            "company_id": make_company().pk,
        }, format="json").status_code == 403


def test_a_student_can_release_the_hold_over_http(stub_iam, policy):
    """The whole point of the UI work: rule 24 blocks, and the student has a
    reachable way to clear it. A hold with no remedy is worse than no hold."""
    record = campus_record(policy, make_company())
    client = _client(stub_iam)

    before = client.get("/api/v1/placement/records/clearance").json()
    assert before["cleared"] is False

    letter = client.post("/api/v1/placement/documents", {
        "kind": "offer_letter", "url": LINK, "title": "Signed offer",
    }, format="json").json()

    submitted = client.post(
        f"/api/v1/placement/records/{record.pk}/offer-letter",
        {"document_id": letter["id"]}, format="json")
    assert submitted.status_code == 200
    assert submitted.json()["offer_letter_submitted"] is True

    after = client.get("/api/v1/placement/records/clearance").json()
    assert after["cleared"] is True
    assert after["blocking"] == []


def test_declaring_not_joining_over_http_does_not_clear_the_hold(stub_iam, policy):
    record = campus_record(policy, make_company())
    client = _client(stub_iam)

    declared = client.post(
        f"/api/v1/placement/records/{record.pk}/not-joining",
        {"reason": "Higher studies"}, format="json")
    assert declared.status_code == 200
    assert declared.json()["is_late"] is False

    assert client.get(
        "/api/v1/placement/records/clearance").json()["cleared"] is False


def test_tpo_can_update_student_and_alumni_placement_record(stub_iam, policy):
    """PC-BR-029: TPO may update placement records for Students and Alumni."""
    from decimal import Decimal

    company = make_company()
    # Student record
    student_rec = service.record_off_campus(
        season=policy.season, user_id=1001, company_id=company.pk,
        ctc_lpa=Decimal("15.00"), kind="fte", actor=_actor())
    # Alumni record (e.g. user_id 5001 who is alumni)
    alumni_rec = service.record_off_campus(
        season=policy.season, user_id=5001, company_id=company.pk,
        ctc_lpa=Decimal("20.00"), kind="fte", actor=_actor())

    # TPO updates student record
    updated_st = service.update_record(
        record_id=student_rec.pk, actor=_actor(),
        ctc_lpa=Decimal("18.00"), kind="ppo")
    assert updated_st.ctc_lpa == Decimal("18.00")
    assert updated_st.kind == "ppo"

    # TPO updates alumni record
    updated_al = service.update_record(
        record_id=alumni_rec.pk, actor=_actor(),
        ctc_lpa=Decimal("25.00"))
    assert updated_al.ctc_lpa == Decimal("25.00")

    # Unprivileged cannot update
    from conftest import make_principal
    student_principal = make_principal(
        user_id=1001, kind="student", permissions=())
    with pytest.raises(PermissionDeniedError):
        service.update_record(
            record_id=alumni_rec.pk, actor=student_principal,
            ctc_lpa=Decimal("30.00"))

