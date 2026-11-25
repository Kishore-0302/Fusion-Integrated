"""Placement domain tables.

Institute people are referenced by plain `user_id` integers, never foreign
keys — there is no user table in this database. Recruiters are the exception:
they are local rows, scoped to one company.
"""

from django.db import models
from django.db.models import Q

from core.db.mixins import TimeStampedModel, UserScopedModel


# -- Announcements and notifications (PC-UC-013/020, PC-BR-017/018/021) --------
class Announcement(TimeStampedModel):
    """PC-BR-017 bounds the topics. PC-AFR-043 keeps history, so withdrawal
    sets a flag rather than deleting."""

    TOPIC = [("drive", "Placement drive"), ("company_visit", "Company visit"),
             ("training", "Training session"), ("workshop", "Workshop"),
             ("internship", "Internship programme"), ("general", "General")]
    AUDIENCE = [("students", "All students"),
                ("registered", "Registered students"),
                ("alumni", "Alumni"), ("all", "Everyone")]

    title = models.CharField(max_length=200)
    body = models.TextField()
    topic = models.CharField(max_length=20, choices=TOPIC, default="general")
    audience = models.CharField(max_length=12, choices=AUDIENCE, default="students")
    placement_year = models.CharField(max_length=12, blank=True, db_index=True)

    published_at = models.DateTimeField(null=True, blank=True)
    published_by_user_id = models.IntegerField(null=True, blank=True)
    published_by_role = models.CharField(max_length=60, blank=True)
    is_withdrawn = models.BooleanField(default=False)
    withdrawn_at = models.DateTimeField(null=True, blank=True)
    withdrawn_reason = models.CharField(max_length=300, blank=True)

    class Meta:
        db_table = "placement_announcement"
        indexes = [
            models.Index(fields=["-published_at"], name="announcement_recent_idx"),
            models.Index(fields=["audience", "is_withdrawn"],
                         name="announcement_audience_idx"),
        ]

    def __str__(self) -> str:
        return self.title


class NotificationOutbox(TimeStampedModel):
    """A notification PCMS decided to send (PC-BR-021).

    Written in the same transaction as the event that caused it and drained by
    a separate worker, so an offer and its email commit together or not at all.
    `dedupe_key` makes redelivery idempotent.
    """

    STATUS = [("pending", "Pending"), ("sending", "Sending"), ("sent", "Sent"),
              ("failed", "Failed"), ("suppressed", "Suppressed")]

    topic = models.CharField(max_length=60, db_index=True)
    dedupe_key = models.CharField(max_length=200, unique=True)

    recipient_user_id = models.IntegerField(null=True, blank=True)
    recipient_email = models.EmailField(blank=True)

    subject = models.CharField(max_length=200)
    body = models.TextField()
    payload = models.JSONField(default=dict, blank=True)

    status = models.CharField(max_length=12, choices=STATUS, default="pending")
    attempts = models.PositiveSmallIntegerField(default=0)
    last_error = models.CharField(max_length=300, blank=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    #: When a worker claimed it, so a crash cannot strand it in "sending".
    claimed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "placement_notification_outbox"
        indexes = [
            models.Index(fields=["status", "created_at"], name="outbox_pending_idx"),
            models.Index(fields=["recipient_user_id", "-created_at"],
                         name="outbox_recipient_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.topic} -> {self.recipient_user_id or self.recipient_email}"


class PlacementStatsSnapshot(TimeStampedModel):
    """Materialised aggregate for the statistics screens (PC-UC-011/012).

    Reports read snapshots, never transactional tables, so a busy stats page
    cannot slow down an application deadline.
    """

    policy = models.ForeignKey("PlacementPolicy", on_delete=models.CASCADE,
                               related_name="snapshots")
    dimension = models.CharField(max_length=32)      # overall | discipline | company
    dimension_value = models.CharField(max_length=120, blank=True)

    registered = models.IntegerField(default=0)
    placed = models.IntegerField(default=0)
    offers = models.IntegerField(default=0)
    companies_participated = models.IntegerField(default=0)
    median_ctc = models.DecimalField(max_digits=8, decimal_places=2,
                                     null=True, blank=True)
    mean_ctc = models.DecimalField(max_digits=8, decimal_places=2,
                                   null=True, blank=True)
    max_ctc = models.DecimalField(max_digits=8, decimal_places=2,
                                  null=True, blank=True)
    computed_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "placement_stats_snapshot"
        constraints = [
            models.UniqueConstraint(fields=["policy", "dimension", "dimension_value"],
                                    name="snapshot_unique_dimension"),
        ]

    def __str__(self) -> str:
        return f"{self.policy_id} {self.dimension}={self.dimension_value}"


class ConductIncident(TimeStampedModel, UserScopedModel):
    """One recorded breach of the code of conduct (rules 18, 19, 21).

    The ladder is derived by counting these, never by a stored tally that could
    drift. A waived incident stays on the record and stops counting, because
    rule 19's escape hatch — "the student may inform the placement cell in
    writing" — is a decision someone made and should remain visible.
    """

    KIND = [("consent_failure", "Did not appear after consenting (r19)"),
            ("code_of_conduct", "Code of conduct (r21)"),
            ("misrepresentation", "False resume or unfair means (r18)")]

    registration = models.ForeignKey("PlacementRegistration",
                                     on_delete=models.CASCADE,
                                     related_name="incidents")
    kind = models.CharField(max_length=20, choices=KIND)
    #: Which company's process, where the incident had one.
    posting = models.ForeignKey("JobPosting", on_delete=models.SET_NULL,
                                null=True, blank=True, related_name="incidents")
    note = models.CharField(max_length=300)

    recorded_by_user_id = models.IntegerField()

    waived = models.BooleanField(default=False)
    waived_reason = models.CharField(max_length=300, blank=True)
    waived_by_user_id = models.IntegerField(null=True, blank=True)
    waived_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "placement_conduct_incident"
        indexes = [
            models.Index(fields=["registration", "kind", "waived"],
                         name="incident_ladder_idx"),
        ]
        constraints = [
            # A waiver is a decision; it must say who made it and why.
            models.CheckConstraint(
                condition=Q(waived=False)
                | (Q(waived=True) & ~Q(waived_reason="")
                   & Q(waived_by_user_id__isnull=False)),
                name="incident_waiver_is_attributed",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.kind} u{self.user_id}{' (waived)' if self.waived else ''}"
