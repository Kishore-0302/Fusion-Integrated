"""Reports and statistics (PC-UC-011, PC-UC-012, PC-BR-016).

Staff get operational figures from the live tables; students get anonymised
aggregates from materialised snapshots, so a viral share of the stats page
cannot slow an application deadline. An aggregate over a group of one is not
anonymous, hence the small-cell suppression below.
"""
from __future__ import annotations

from decimal import Decimal

from django.db import transaction
from django.db.models import Avg, Count, Max

from modules.placement.models import (
    Application,
    JobPosting,
    PlacementPolicy,
    PlacementRecord,
    PlacementRegistration,
    PlacementStatsSnapshot,
)

#: Below this many placements, a "median CTC" identifies individuals.
MIN_CELL = 5


def _median(values: list[Decimal]) -> Decimal | None:
    if not values:
        return None
    ordered = sorted(values)
    mid = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[mid]
    return (ordered[mid - 1] + ordered[mid]) / 2


def _counted_records(policy: PlacementPolicy):
    """Active placements of registered students: a debarred or opted-out student
    leaves the numerator as well as the denominator."""
    registered = PlacementRegistration.objects.filter(
        policy=policy, status="registered").values("user_id")
    return PlacementRecord.objects.filter(policy=policy, is_active=True,
                                          user_id__in=registered)


@transaction.atomic
def rebuild(*, season: str) -> int:
    """Recompute every snapshot for a season. Idempotent."""
    policy = PlacementPolicy.objects.filter(season=season).first()
    if policy is None:
        return 0

    records = list(_counted_records(policy).select_related("company"))
    registered = PlacementRegistration.objects.filter(
        policy=policy, status="registered").count()
    offers = Application.objects.filter(
        posting__placement_year=season,
        status__in=("offer_issued", "offer_accepted")).count()

    rows = [_overall(policy, records, registered, offers)]
    rows += _by_company(policy, records)

    PlacementStatsSnapshot.objects.filter(policy=policy).delete()
    PlacementStatsSnapshot.objects.bulk_create(rows)
    return len(rows)


def _overall(policy, records, registered, offers) -> PlacementStatsSnapshot:
    ctcs = [r.ctc_lpa for r in records if r.ctc_lpa is not None]
    return PlacementStatsSnapshot(
        policy=policy, dimension="overall", dimension_value="",
        registered=registered, placed=len(records), offers=offers,
        companies_participated=len({r.company_id for r in records}),
        median_ctc=_median(ctcs),
        mean_ctc=(sum(ctcs) / len(ctcs)) if ctcs else None,
        max_ctc=max(ctcs) if ctcs else None,
    )


def _by_company(policy, records) -> list[PlacementStatsSnapshot]:
    by: dict[int, list] = {}
    names: dict[int, str] = {}
    for r in records:
        by.setdefault(r.company_id, []).append(r)
        names[r.company_id] = r.company.name

    out = []
    for company_id, rs in by.items():
        ctcs = [r.ctc_lpa for r in rs if r.ctc_lpa is not None]
        out.append(PlacementStatsSnapshot(
            policy=policy, dimension="company",
            dimension_value=names[company_id][:120],
            registered=0, placed=len(rs), offers=len(rs),
            companies_participated=1,
            median_ctc=_median(ctcs),
            mean_ctc=(sum(ctcs) / len(ctcs)) if ctcs else None,
            max_ctc=max(ctcs) if ctcs else None))
    return out


def student_view(*, season: str) -> dict:
    """The anonymised figures a student may see (PC-BR-016).

    No names, no per-student rows, and any cell below MIN_CELL suppressed.
    """
    policy = PlacementPolicy.objects.filter(season=season).first()
    if policy is None:
        return {"season": season, "available": False}

    overall = PlacementStatsSnapshot.objects.filter(
        policy=policy, dimension="overall").first()
    if overall is None or overall.placed < MIN_CELL:
        # Early in a season the totals themselves identify people.
        return {"season": season, "available": False,
                "reason": "Not enough placements yet to publish statistics."}

    companies = [
        {"company": s.dimension_value, "placed": s.placed}
        for s in PlacementStatsSnapshot.objects.filter(
            policy=policy, dimension="company", placed__gte=MIN_CELL)
        .order_by("-placed")[:25]
    ]
    return {
        "season": season,
        "available": True,
        "registered": overall.registered,
        "placed": overall.placed,
        "placement_rate": (round(overall.placed * 100 / overall.registered, 1)
                           if overall.registered else None),
        "companies_participated": overall.companies_participated,
        "median_ctc": str(overall.median_ctc) if overall.median_ctc else None,
        "max_ctc": str(overall.max_ctc) if overall.max_ctc else None,
        # Mean CTC and per-discipline splits are absent: they identify outliers.
        "companies": companies,
        "computed_at": overall.computed_at.isoformat(),
    }


def staff_view(*, season: str) -> dict:
    """Operational figures for the TPO and chairman (PC-UC-011, PC-UC-012, PC-AFR-033)."""
    policy = PlacementPolicy.objects.filter(season=season).first()
    if policy is None:
        return {"season": season, "available": False}

    records = _counted_records(policy)
    agg = records.aggregate(n=Count("id"), mean=Avg("ctc_lpa"), top=Max("ctc_lpa"))
    ctcs = [r for r in records.values_list("ctc_lpa", flat=True) if r is not None]

    by_company = list(
        records.values("company__name")
        .annotate(placed=Count("id"), top=Max("ctc_lpa"))
        .order_by("-placed"))
    by_status = dict(
        Application.objects.filter(posting__placement_year=season)
        .values_list("status").annotate(n=Count("id")))

    registered_count = PlacementRegistration.objects.filter(
        policy=policy, status="registered").count()
    placed_count = agg["n"] or 0
    success_rate = (
        round(placed_count * 100 / registered_count, 2)
        if registered_count else 0.0
    )

    return {
        "season": season,
        "available": True,
        "registered": registered_count,
        "debarred": PlacementRegistration.objects.filter(
            policy=policy, status="debarred").count(),
        "placed": placed_count,
        "success_rate": success_rate,
        "placement_rate": success_rate,
        "median_ctc": str(_median(ctcs)) if ctcs else None,
        "mean_ctc": (
            f"{Decimal(str(round(agg['mean'], 2))):.2f}" if agg["mean"] is not None else None
        ),
        "max_ctc": f"{Decimal(str(agg['top'])):.2f}" if agg["top"] is not None else None,
        "by_company": by_company,
        "applications_by_status": by_status,
    }


def placement_success_rate(*, season: str) -> dict:
    """PC-AFR-033: Dedicated placement success-rate report for TPO."""
    policy = PlacementPolicy.objects.filter(season=season).first()
    if policy is None:
        return {"season": season, "available": False, "reason": "No policy for season."}
    records = _counted_records(policy)
    registered = PlacementRegistration.objects.filter(policy=policy, status="registered").count()
    placed = records.count()
    rate = round(placed * 100 / registered, 2) if registered else 0.0
    debarred = PlacementRegistration.objects.filter(policy=policy, status="debarred").count()
    return {
        "season": season,
        "available": True,
        "registered": registered,
        "placed": placed,
        "success_rate": rate,
        "placement_rate": rate,
        "debarred": debarred,
    }


def company_participation_trends() -> list[dict]:
    """PC-AFR-034: Company participation trend across seasons."""
    policies = list(PlacementPolicy.objects.order_by("season"))
    seen_companies: set[int] = set()
    trends = []
    for pol in policies:
        records = _counted_records(pol).select_related("company")
        co_in_season = {r.company_id: r.company.name for r in records}
        co_ids = set(co_in_season.keys())
        new_ids = co_ids - seen_companies
        repeat_ids = co_ids & seen_companies
        seen_companies.update(co_ids)

        trends.append({
            "season": pol.season,
            "companies_count": len(co_ids),
            "company_names": sorted(co_in_season.values()),
            "new_companies_count": len(new_ids),
            "new_companies": sorted(co_in_season[i] for i in new_ids),
            "repeat_companies_count": len(repeat_ids),
            "repeat_companies": sorted(co_in_season[i] for i in repeat_ids),
            "postings_count": JobPosting.objects.filter(placement_year=pol.season).count(),
        })
    return trends


def salary_distribution(*, season: str) -> dict:
    """PC-AFR-035: Salary package distribution report."""
    policy = PlacementPolicy.objects.filter(season=season).first()
    if policy is None:
        return {"season": season, "available": False, "reason": "No policy for season."}

    records = _counted_records(policy)
    ctcs = [r for r in records.values_list("ctc_lpa", flat=True) if r is not None]
    total = len(ctcs)
    if not total:
        return {
            "season": season,
            "available": True,
            "total_placed": 0,
            "min_ctc": None,
            "max_ctc": None,
            "mean_ctc": None,
            "median_ctc": None,
            "brackets": [],
            "distribution": {},
        }

    b_under_6 = sum(1 for c in ctcs if c < Decimal("6.0"))
    b_6_10 = sum(1 for c in ctcs if Decimal("6.0") <= c < Decimal("10.0"))
    b_10_15 = sum(1 for c in ctcs if Decimal("10.0") <= c < Decimal("15.0"))
    b_15_25 = sum(1 for c in ctcs if Decimal("15.0") <= c < Decimal("25.0"))
    b_above_25 = sum(1 for c in ctcs if c >= Decimal("25.0"))

    def pct(count: int) -> float:
        return round(count * 100 / total, 2) if total else 0.0

    brackets = [
        {"bracket": "< 6 LPA", "count": b_under_6, "percentage": pct(b_under_6)},
        {"bracket": "6-10 LPA", "count": b_6_10, "percentage": pct(b_6_10)},
        {"bracket": "10-15 LPA", "count": b_10_15, "percentage": pct(b_10_15)},
        {"bracket": "15-25 LPA", "count": b_15_25, "percentage": pct(b_15_25)},
        {"bracket": "> 25 LPA", "count": b_above_25, "percentage": pct(b_above_25)},
    ]
    distribution = {b["bracket"]: b["count"] for b in brackets}

    agg = records.aggregate(mean=Avg("ctc_lpa"), top=Max("ctc_lpa"))
    return {
        "season": season,
        "available": True,
        "total_placed": total,
        "min_ctc": str(min(ctcs)) if ctcs else None,
        "max_ctc": str(agg["top"]) if agg["top"] is not None else None,
        "mean_ctc": str(round(agg["mean"], 2)) if agg["mean"] is not None else None,
        "median_ctc": str(_median(ctcs)) if ctcs else None,
        "brackets": brackets,
        "distribution": distribution,
    }


def employment_trends() -> list[dict]:
    """PC-AFR-036: Employment trends across seasons."""
    policies = list(PlacementPolicy.objects.order_by("season"))
    trends = []
    for pol in policies:
        records = _counted_records(pol)
        agg = records.aggregate(n=Count("id"), mean=Avg("ctc_lpa"), top=Max("ctc_lpa"))
        ctcs = [r for r in records.values_list("ctc_lpa", flat=True) if r is not None]
        registered = PlacementRegistration.objects.filter(policy=pol, status="registered").count()
        placed = agg["n"] or 0
        rate = round(placed * 100 / registered, 2) if registered else 0.0
        offers = Application.objects.filter(
            posting__placement_year=pol.season,
            status__in=("offer_issued", "offer_accepted")).count()

        trends.append({
            "season": pol.season,
            "registered": registered,
            "placed": placed,
            "placement_rate": rate,
            "success_rate": rate,
            "total_offers": offers,
            "companies_participated": len({r.company_id for r in records}),
            "median_ctc": str(_median(ctcs)) if ctcs else None,
            "mean_ctc": str(round(agg["mean"], 2)) if agg["mean"] is not None else None,
            "max_ctc": str(agg["top"]) if agg["top"] is not None else None,
        })
    return trends
