"""Placement statistics (PC-UC-011, PC-UC-012, PC-BR-016): who counts as placed."""
from decimal import Decimal

import pytest
from django.utils import timezone

from modules.placement.models import (
    Company,
    PlacementPolicy,
    PlacementRecord,
    PlacementRegistration,
    PlacementStatsSnapshot,
)
from modules.placement.services import stats

pytestmark = pytest.mark.django_db

SEASON = "2026-27"


@pytest.fixture
def season():
    policy = PlacementPolicy.objects.create(season=SEASON)
    company = Company.objects.create(name="Acme", slug="acme", status="active",
                                     approval_status="approved", approved_by_user_id=9)
    return policy, company


def _student(policy, user_id, status="registered"):
    PlacementRegistration.objects.create(policy=policy, user_id=user_id, status=status,
                                         registered_at=timezone.now())


def _place(policy, company, user_id, ctc="10.00"):
    PlacementRecord.objects.create(policy=policy, user_id=user_id, company=company,
                                   ctc_lpa=Decimal(ctc), source="off_campus")


def _season_of_ten(policy, company, placed=5):
    for i in range(10):
        _student(policy, 5000 + i)
        if i < placed:
            _place(policy, company, 5000 + i)


def _overall(policy):
    return PlacementStatsSnapshot.objects.get(policy=policy, dimension="overall")


def test_registered_placed_students_are_counted(season):
    policy, company = season
    _season_of_ten(policy, company)
    stats.rebuild(season=SEASON)
    overall = _overall(policy)
    assert (overall.registered, overall.placed) == (10, 5)
    assert stats.student_view(season=SEASON)["placement_rate"] == 50.0


def test_a_student_debarred_after_placement_leaves_both_counts(season):
    policy, company = season
    _season_of_ten(policy, company)
    _student(policy, 6001, status="debarred")
    _place(policy, company, 6001, ctc="40.00")

    stats.rebuild(season=SEASON)

    overall = _overall(policy)
    assert (overall.registered, overall.placed) == (10, 5)
    assert overall.max_ctc == Decimal("10.00")
    assert stats.student_view(season=SEASON)["placement_rate"] == 50.0


def test_a_student_who_opted_out_after_placement_leaves_both_counts(season):
    policy, company = season
    _season_of_ten(policy, company)
    _student(policy, 6002, status="opted_out")
    _place(policy, company, 6002)

    stats.rebuild(season=SEASON)

    assert _overall(policy).placed == 5
    company_row = PlacementStatsSnapshot.objects.get(policy=policy, dimension="company")
    assert company_row.placed == 5


def test_the_staff_view_counts_the_same_students(season):
    policy, company = season
    _season_of_ten(policy, company)
    _student(policy, 6001, status="debarred")
    _place(policy, company, 6001, ctc="40.00")

    view = stats.staff_view(season=SEASON)

    assert (view["registered"], view["placed"], view["debarred"]) == (10, 5, 1)
    assert view["max_ctc"] == "10.00"
    assert [row["placed"] for row in view["by_company"]] == [5]
