from datetime import date
from decimal import Decimal

from django.test import SimpleTestCase

from modules.elm.services.policy import calculate_leave_days


class CalculateLeaveDaysTests(SimpleTestCase):
    def test_single_full_day(self):
        self.assertEqual(
            calculate_leave_days(
                date(2026, 10, 26), date(2026, 10, 26), leave_code="CL"
            ),
            Decimal("1"),
        )

    def test_cl_half_day(self):
        self.assertEqual(
            calculate_leave_days(
                date(2026, 10, 26), date(2026, 10, 26),
                leave_code="CL", half_day="first",
            ),
            Decimal("0.5"),
        )

    def test_calendar_days_include_weekends(self):
        self.assertEqual(
            calculate_leave_days(
                date(2026, 10, 23), date(2026, 10, 26), leave_code="EL"
            ),
            Decimal("4"),
        )

    def test_rejects_half_day_for_non_cl(self):
        with self.assertRaises(ValueError):
            calculate_leave_days(
                date(2026, 10, 26), date(2026, 10, 26),
                leave_code="EL", half_day="first",
            )

    def test_rejects_reversed_dates(self):
        with self.assertRaises(ValueError):
            calculate_leave_days(
                date(2026, 10, 27), date(2026, 10, 26), leave_code="CL"
            )
    def test_rejects_invalid_half_day_value(self):
        with self.assertRaises(ValueError):
            calculate_leave_days(
                date(2026, 10, 26), date(2026, 10, 26),
                leave_code="CL", half_day="third",
            )

    def test_rejects_half_day_across_multiple_dates(self):
        with self.assertRaises(ValueError):
            calculate_leave_days(
                date(2026, 10, 26), date(2026, 10, 27),
                leave_code="CL", half_day="first",
            )

    def test_second_half_day(self):
        self.assertEqual(
            calculate_leave_days(
                date(2026, 10, 26), date(2026, 10, 26),
                leave_code="CL", half_day="second",
            ),
            Decimal("0.5"),
        )
