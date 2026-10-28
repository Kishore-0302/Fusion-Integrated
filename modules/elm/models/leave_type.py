from django.db import models

from core.db.mixins import TimeStampedModel


class LeaveType(TimeStampedModel):
    """A configured category of employee leave."""

    code = models.CharField(max_length=8, unique=True)
    name = models.CharField(max_length=80)
    annual_quota = models.DecimalField(
        max_digits=6, decimal_places=2, default=0
    )
    carry_forward = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "elm_leave_type"
        ordering = ["code"]

    def __str__(self):
        return f"{self.code} - {self.name}"
