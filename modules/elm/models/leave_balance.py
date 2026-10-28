from django.db import models

from core.db.mixins import TimeStampedModel


class LeaveBalance(TimeStampedModel):
    """An employee's leave entitlement for one category and leave year."""

    user_id = models.IntegerField(db_index=True)
    leave_type = models.ForeignKey(
        "elm.LeaveType",
        on_delete=models.PROTECT,
        related_name="balances",
    )
    leave_year = models.PositiveSmallIntegerField()
    entitled_days = models.DecimalField(max_digits=6, decimal_places=2, default=0)
    used_days = models.DecimalField(max_digits=6, decimal_places=2, default=0)
    carried_forward_days = models.DecimalField(
        max_digits=6, decimal_places=2, default=0
    )

    class Meta:
        db_table = "elm_leave_balance"
        constraints = [
            models.UniqueConstraint(
                fields=["user_id", "leave_type", "leave_year"],
                name="elm_balance_user_type_year_uniq",
            ),
            models.CheckConstraint(
                condition=models.Q(entitled_days__gte=0),
                name="elm_balance_entitled_nonnegative",
            ),
            models.CheckConstraint(
                condition=models.Q(used_days__gte=0),
                name="elm_balance_used_nonnegative",
            ),
            models.CheckConstraint(
                condition=models.Q(carried_forward_days__gte=0),
                name="elm_balance_carry_nonnegative",
            ),
        ]

    @property
    def available_days(self):
        return self.entitled_days + self.carried_forward_days - self.used_days

    def __str__(self):
        return f"user#{self.user_id} {self.leave_type.code} {self.leave_year}"
