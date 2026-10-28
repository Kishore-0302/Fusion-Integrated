from datetime import date
from decimal import Decimal

from django.db.models import Q

from modules.elm.models import LeaveRequest


ACTIVE_STATUSES = ("submitted", "pending", "approved")


def calculate_leave_days(
    start_date: date,
    end_date: date,
    *,
    leave_code: str,
    half_day: str = "none",
) -> Decimal:
    """Calculate requested leave days using the current ELM rules."""
    if end_date < start_date:
        raise ValueError("End date cannot be before start date.")

    if half_day not in {"none", "first", "second"}:
        raise ValueError("Invalid half-day selection.")

    if half_day != "none":
        if leave_code != "CL":
            raise ValueError("Half-day leave is supported only for CL.")
        if start_date != end_date:
            raise ValueError("Half-day leave must cover one date.")
        return Decimal("0.5")

    # EL, COL and VL count calendar days, including weekends/holidays.
    return Decimal((end_date - start_date).days + 1)


def find_overlapping_requests(
    *,
    user_id: int,
    start_date: date,
    end_date: date,
    exclude_request_id: int | None = None,
):
    """Return active requests whose date ranges overlap the requested range."""
    if end_date < start_date:
        raise ValueError("End date cannot be before start date.")

    requests = LeaveRequest.objects.filter(
        user_id=user_id,
        status__in=ACTIVE_STATUSES,
        start_date__lte=end_date,
        end_date__gte=start_date,
    ).select_related("leave_type")

    if exclude_request_id is not None:
        requests = requests.exclude(pk=exclude_request_id)

    return requests



def validate_no_overlap(
    *,
    user_id: int,
    leave_code: str,
    start_date: date,
    end_date: date,
    half_day: str = "none",
    exclude_request_id: int | None = None,
) -> None:
    """Reject overlapping active leave, except opposite-half CL on one date."""
    calculate_leave_days(
        start_date,
        end_date,
        leave_code=leave_code,
        half_day=half_day,
    )

    overlaps = find_overlapping_requests(
        user_id=user_id,
        start_date=start_date,
        end_date=end_date,
        exclude_request_id=exclude_request_id,
    )

    for existing in overlaps:
        same_single_date = (
            start_date == end_date == existing.start_date == existing.end_date
        )
        opposite_cl_halves = (
            leave_code == "CL"
            and existing.leave_type.code == "CL"
            and same_single_date
            and half_day in {"first", "second"}
            and existing.half_day in {"first", "second"}
            and half_day != existing.half_day
        )

        if not opposite_cl_halves:
            raise ValueError(
                f"Requested dates overlap active leave request #{existing.pk}."
            )
