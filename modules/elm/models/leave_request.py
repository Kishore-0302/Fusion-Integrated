from django.db import models

from core.db.mixins import TimeStampedModel


class LeaveRequest(TimeStampedModel):
    STATUS_CHOICES = [
        ("draft", "Draft"),
        ("submitted", "Submitted"),
        ("pending", "Pending Approval"),
        ("approved", "Approved"),
        ("rejected", "Rejected"),
        ("withdrawn", "Withdrawn"),
        ("cancelled", "Cancelled"),
    ]

    HALF_DAY_CHOICES = [
        ("none", "Full Day"),
        ("first", "First Half"),
        ("second", "Second Half"),
    ]

    user_id = models.IntegerField(db_index=True)
    leave_type = models.ForeignKey(
        "elm.LeaveType",
        on_delete=models.PROTECT,
        related_name="requests",
    )
    start_date = models.DateField()
    end_date = models.DateField()
    half_day = models.CharField(
        max_length=8,
        choices=HALF_DAY_CHOICES,
        default="none",
    )
    reason = models.TextField()
    status = models.CharField(
        max_length=16,
        choices=STATUS_CHOICES,
        default="draft",
        db_index=True,
    )
    submitted_at = models.DateTimeField(null=True, blank=True)
    final_approver_user_id = models.IntegerField(null=True, blank=True)
    decision_at = models.DateTimeField(null=True, blank=True)
    decision_reason = models.CharField(max_length=500, blank=True)

    class Meta:
        db_table = "elm_leave_request"
        ordering = ["-created_at"]
        indexes = [
            models.Index(
                fields=["user_id", "status"],
                name="elm_request_user_status_idx",
            ),
            models.Index(
                fields=["start_date", "end_date"],
                name="elm_request_dates_idx",
            ),
        ]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(end_date__gte=models.F("start_date")),
                name="elm_request_valid_dates",
            ),
        ]

    def __str__(self):
        return (
            f"Leave request #{self.pk}: user#{self.user_id} "
            f"{self.start_date} to {self.end_date} ({self.status})"
        )
