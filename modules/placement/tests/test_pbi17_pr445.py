"""Tests for PR 445 (PBI 17) integration and tweaks.

Validates the functions, models, serializers, and task integration introduced
from PR 445 with robust error-handling, defensive defaults, and domain alignment.
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from modules.placement.api.serializers import PlacementRecordUpdateSerializer
from modules.placement.domain import state_machine as sm
from modules.placement.domain.eligibility import evaluate_student_eligibility
from modules.placement.domain.state_machine import transition_application_state
from modules.placement.models.students import DebarmentRecord, StudentClearance
from modules.placement.selectors.scoping import scope_applications_queryset
from modules.placement.tasks import expire_pending_offers

# ---------------------------------------------------------------------------
# 1. Eligibility evaluation tests
# ---------------------------------------------------------------------------

def test_eligibility_debarred_student():
    facts = {"is_debarred": True, "cpi": 8.5, "discipline": "CSE", "active_backlogs": 0}
    criteria = {"min_cpi": 7.0, "eligible_branches": ["CSE"], "max_backlogs": 0}
    eligible, reasons = evaluate_student_eligibility(facts, criteria)
    assert not eligible
    assert "Student is debarred" in reasons


def test_eligibility_cpi_below_cutoff():
    facts = {"cpi": 6.5, "discipline": "CSE", "active_backlogs": 0}
    criteria = {"min_cpi": 7.0, "eligible_branches": ["CSE"], "max_backlogs": 0}
    eligible, reasons = evaluate_student_eligibility(facts, criteria)
    assert not eligible
    assert "CPI below cutoff" in reasons


def test_eligibility_cpi_meets_cutoff():
    facts = {"cpi": 7.0, "discipline": "CSE", "active_backlogs": 0}
    criteria = {"min_cpi": 7.0}
    eligible, reasons = evaluate_student_eligibility(facts, criteria)
    assert eligible
    assert reasons == []


def test_eligibility_branch_not_eligible():
    facts = {"cpi": 8.0, "discipline": "ME", "active_backlogs": 0}
    criteria = {"min_cpi": 7.0, "eligible_branches": ["CSE", "ECE"]}
    eligible, reasons = evaluate_student_eligibility(facts, criteria)
    assert not eligible
    assert "Branch not eligible" in reasons


def test_eligibility_branch_case_insensitive():
    facts = {"cpi": 8.0, "discipline": "cse", "active_backlogs": 0}
    criteria = {"eligible_branches": ["CSE"]}
    eligible, reasons = evaluate_student_eligibility(facts, criteria)
    assert eligible
    assert reasons == []


def test_eligibility_no_branch_restriction():
    # If criteria does not restrict branches, student should not be rejected on branch
    facts = {"cpi": 8.0, "discipline": "ME", "active_backlogs": 0}
    criteria = {"min_cpi": 7.0}
    eligible, reasons = evaluate_student_eligibility(facts, criteria)
    assert eligible
    assert reasons == []


def test_eligibility_active_backlogs_exceeded():
    facts = {"cpi": 8.0, "discipline": "CSE", "active_backlogs": 2}
    criteria = {"max_backlogs": 1}
    eligible, reasons = evaluate_student_eligibility(facts, criteria)
    assert not eligible
    assert "Active backlogs present" in reasons


def test_eligibility_active_backlogs_allowed():
    facts = {"cpi": 8.0, "discipline": "CSE", "active_backlogs": 1}
    criteria = {"max_backlogs": 1}
    eligible, reasons = evaluate_student_eligibility(facts, criteria)
    assert eligible
    assert reasons == []


def test_eligibility_graceful_missing_data():
    # No facts or empty criteria should not raise exceptions
    eligible, reasons = evaluate_student_eligibility({}, {})
    assert eligible
    assert reasons == []

    # Missing CPI when min_cpi is specified
    eligible, reasons = evaluate_student_eligibility({}, {"min_cpi": 6.5})
    assert not eligible
    assert "CPI below cutoff" in reasons


def test_eligibility_ast_rule_support():
    criteria = {"gte": ["cpi", 7.5]}
    facts_pass = {"cpi": 8.0}
    facts_fail = {"cpi": 7.0}

    ok_pass, reasons_pass = evaluate_student_eligibility(facts_pass, criteria)
    assert ok_pass
    assert reasons_pass == []

    ok_fail, reasons_fail = evaluate_student_eligibility(facts_fail, criteria)
    assert not ok_fail
    assert len(reasons_fail) > 0


# ---------------------------------------------------------------------------
# 2. State machine transition helper tests
# ---------------------------------------------------------------------------

def test_transition_application_state_valid():
    # Student DRAFT -> SUBMITTED
    next_state = transition_application_state(sm.DRAFT, sm.SUBMITTED, sm.STUDENT)
    assert next_state == sm.SUBMITTED

    # Recruiter SUBMITTED -> UNDER_REVIEW
    next_state = transition_application_state(sm.SUBMITTED, sm.UNDER_REVIEW, sm.RECRUITER)
    assert next_state == sm.UNDER_REVIEW


def test_transition_application_state_invalid_edge():
    with pytest.raises(ValueError, match="Invalid transition"):
        transition_application_state(sm.DRAFT, sm.OFFER_ACCEPTED, sm.STUDENT)


def test_transition_application_state_disallowed_actor():
    # Student cannot transition SUBMITTED -> UNDER_REVIEW
    with pytest.raises(ValueError, match="Invalid transition"):
        transition_application_state(sm.SUBMITTED, sm.UNDER_REVIEW, sm.STUDENT)


# ---------------------------------------------------------------------------
# 3. PlacementRecordUpdateSerializer tests
# ---------------------------------------------------------------------------

def test_serializer_pr445_fields():
    data = {
        "ctc_lpa": "12.50",
        "verified_by_user_id": 42,
        "is_accepted": True,
    }
    ser = PlacementRecordUpdateSerializer(data=data, partial=True)
    assert ser.is_valid(), ser.errors
    assert ser.validated_data["ctc_lpa"] == pytest.approx(12.50)
    assert ser.validated_data["verified_by_user_id"] == 42
    assert ser.validated_data["is_accepted"] is True


def test_serializer_administrative_correction_fields():
    data = {
        "company_id": 5,
        "kind": "fte",
        "is_active": True,
        "reason": "Correcting recruiter recording typo",
    }
    ser = PlacementRecordUpdateSerializer(data=data)
    assert ser.is_valid(), ser.errors
    assert ser.validated_data["company_id"] == 5
    assert ser.validated_data["kind"] == "fte"
    assert ser.validated_data["reason"] == "Correcting recruiter recording typo"


def test_serializer_empty_payload_fails():
    ser = PlacementRecordUpdateSerializer(data={})
    assert not ser.is_valid()
    assert "non_field_errors" in ser.errors


# ---------------------------------------------------------------------------
# 4. Scoping helper tests
# ---------------------------------------------------------------------------

def test_scope_applications_queryset_roles():
    qs = MagicMock()
    user = MagicMock(id=101)

    # TPO admin gets all
    scope_applications_queryset(qs, user, ["tpo_admin"])
    qs.all.assert_called_once()

    # Recruiter with company_id gets filtered
    qs.reset_mock()
    scope_applications_queryset(qs, user, ["recruiter"], company_id=25)
    qs.filter.assert_called_once_with(posting__company_id=25)

    # Recruiter without company_id gets none
    qs.reset_mock()
    scope_applications_queryset(qs, user, ["recruiter"], company_id=None)
    qs.none.assert_called_once()

    # Student gets filtered by user id
    qs.reset_mock()
    scope_applications_queryset(qs, user, ["student"])
    qs.filter.assert_called_once_with(user_id=101)

    # Student passed as int
    qs.reset_mock()
    scope_applications_queryset(qs, 202, ["student"])
    qs.filter.assert_called_once_with(user_id=202)

    # Alumni gets none
    qs.reset_mock()
    scope_applications_queryset(qs, user, ["alumni"])
    qs.none.assert_called_once()

    # Unknown role gets none
    qs.reset_mock()
    scope_applications_queryset(qs, user, ["guest"])
    qs.none.assert_called_once()


# ---------------------------------------------------------------------------
# 5. Model metadata tests
# ---------------------------------------------------------------------------

def test_models_metadata():
    assert StudentClearance._meta.db_table == "placement_student_clearance"
    assert DebarmentRecord._meta.db_table == "placement_debarment_record"

    clr = StudentClearance(user_id=12, academic_year="2026-27")
    assert str(clr) == "clr u12 2026-27"

    deb = DebarmentRecord(user_id=12, season="2026-27")
    assert str(deb) == "deb u12 2026-27"


# ---------------------------------------------------------------------------
# 6. Task registration test
# ---------------------------------------------------------------------------

def test_expire_pending_offers_task():
    assert expire_pending_offers.name == "placement.expire_pending_offers"
    with patch("modules.placement.services.offers.expire_overdue", return_value=3) as mock_expire:
        count = expire_pending_offers()
        assert count == 3
        mock_expire.assert_called_once()
