"""Placement domain tables.

Institute people are referenced by plain `user_id` integers, never foreign
keys — there is no user table in this database. Recruiters are the exception:
they are local rows, scoped to one company.
"""

from django.db import models

from core.db.mixins import TimeStampedModel, UserScopedModel


# -- Applications --------------------------------------------------------------
class Application(TimeStampedModel, UserScopedModel):
    STATUS = [
        ("draft", "Draft"), ("submitted", "Submitted"),
        ("under_review", "Under review"), ("shortlisted", "Shortlisted"),
        ("interview_scheduled", "Interview scheduled"),
        ("selected", "Selected"),
        ("rejected", "Rejected"), ("withdrawn", "Withdrawn"),
        ("auto_withdrawn", "Withdrawn automatically"),
        ("offer_issued", "Offer issued"), ("offer_accepted", "Offer accepted"),
        ("offer_declined", "Offer declined"), ("offer_expired", "Offer expired"),
    ]

    posting = models.ForeignKey("JobPosting", on_delete=models.PROTECT,
                                related_name="applications")
    status = models.CharField(max_length=24, choices=STATUS, default="draft")

    # Frozen at submission, so a later CPI change never rewrites history.
    cpi_at_apply = models.DecimalField(max_digits=4, decimal_places=2,
                                       null=True, blank=True)
    semester_at_apply = models.PositiveSmallIntegerField(null=True, blank=True)
    standing_declared_seq_at_apply = models.IntegerField(null=True, blank=True)
    eligibility_snapshot = models.JSONField(default=dict, blank=True)
    cover_note = models.TextField(blank=True)
    applied_at = models.DateTimeField(null=True, blank=True)
    withdrawn_reason = models.CharField(max_length=300, blank=True)

    class Meta:
        db_table = "placement_application"
        constraints = [
            models.UniqueConstraint(fields=["posting", "user_id"],
                                    name="application_unique_per_posting"),
        ]
        indexes = [
            models.Index(fields=["posting", "status"], name="application_posting_idx"),
            models.Index(fields=["user_id", "status"], name="application_user_idx"),
        ]

    def __str__(self) -> str:
        return f"app#{self.pk} u{self.user_id} {self.status}"


class ApplicationTransition(models.Model):
    """Append-only audit of every status change (PC-AFR-009)."""

    application = models.ForeignKey(Application, on_delete=models.CASCADE,
                                    related_name="transitions")
    from_status = models.CharField(max_length=24)
    to_status = models.CharField(max_length=24)
    actor_user_id = models.IntegerField(null=True, blank=True)       # institute person
    actor_recruiter_id = models.IntegerField(null=True, blank=True)  # or a recruiter
    actor_label = models.CharField(max_length=80, blank=True)
    reason = models.CharField(max_length=300, blank=True)
    at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "placement_application_transition"
        indexes = [models.Index(fields=["application", "at"],
                                name="transition_app_idx")]

    def __str__(self) -> str:
        return f"app#{self.application_id} {self.from_status}->{self.to_status}"
