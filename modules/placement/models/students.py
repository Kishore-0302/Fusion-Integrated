"""Placement domain tables.

Institute people are referenced by plain `user_id` integers, never foreign
keys — there is no user table in this database. Recruiters are the exception:
they are local rows, scoped to one company.
"""

from django.db import models

from core.db.mixins import TimeStampedModel, UserScopedModel

# -- Student placement profile (PC-UC-001, PC-BR-001) --------------------------

class ProfileDocument(TimeStampedModel, UserScopedModel):
    """A document a student has submitted to the placement office.

    Offer letters and clearance paperwork. Not resumes: those are maintained
    once on the ERP portal and reach here through the directory projection.

    New rows are Drive links; rows written before the switch hold uploaded
    bytes. The CHECK constraint allows exactly one, so the download view
    always knows which it is holding.
    """

    KIND = [("certificate", "Certificate"),
            ("offer_letter", "Offer letter"), ("other", "Other")]
    kind = models.CharField(max_length=20, choices=KIND, default="other")
    title = models.CharField(max_length=160, blank=True)
    #: Display only, sanitised on the way in.
    original_filename = models.CharField(max_length=255, blank=True)

    #: Rebuilt from the file id, never a copy of what was submitted.
    drive_url = models.URLField(max_length=500, blank=True)
    drive_file_id = models.CharField(max_length=200, blank=True, db_index=True)

    #: Legacy upload path. Blank on every row written since the switch.
    storage_key = models.CharField(max_length=255, blank=True, null=True,
                                   unique=True)
    content_type = models.CharField(max_length=100, blank=True)
    size_bytes = models.PositiveIntegerField(null=True, blank=True)
    sha256 = models.CharField(max_length=64, blank=True)

    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "placement_profile_document"
        indexes = [models.Index(fields=["user_id", "kind", "is_active"],
                                name="document_user_idx")]
        constraints = [
            models.CheckConstraint(
                condition=(
                    models.Q(drive_file_id="", storage_key__isnull=False)
                    | (~models.Q(drive_file_id="")
                       & models.Q(storage_key__isnull=True))
                ),
                name="document_is_link_or_file_not_both",
            ),
        ]

    @property
    def is_link(self) -> bool:
        return bool(self.drive_file_id)

    def __str__(self) -> str:
        return f"{self.kind}:{self.title or self.original_filename}"


class PlacementRegistration(TimeStampedModel, UserScopedModel):
    """A student opting into a season. Carries the counters the offer policy
    reads."""

    STATUS = [("registered", "Registered"), ("debarred", "Debarred"),
              ("opted_out", "Opted out")]

    policy = models.ForeignKey("PlacementPolicy", on_delete=models.PROTECT,
                               related_name="registrations")
    status = models.CharField(max_length=12, choices=STATUS, default="registered")
    offer_count = models.PositiveSmallIntegerField(default=0)
    best_accepted_tier_rank = models.PositiveSmallIntegerField(null=True, blank=True)
    best_accepted_ctc_lpa = models.DecimalField(max_digits=8, decimal_places=2,
                                                null=True, blank=True)

    # Rule 2.A, one time only: locked on the first accepted offer in its band.
    category_number = models.PositiveSmallIntegerField(null=True, blank=True)
    category_locked_at = models.DateTimeField(null=True, blank=True)

    # Rule 2: each category caps this.
    switches_used = models.PositiveSmallIntegerField(default=0)

    # Denormalised from the held offer so the policy check is one row read.
    held_is_marquee = models.BooleanField(default=False)
    held_sector_kind = models.CharField(max_length=8, blank=True)

    # Rules 19 and 21. Recorded only — debarment is a human decision.
    consent_failures = models.PositiveSmallIntegerField(default=0)
    reregistration_count = models.PositiveSmallIntegerField(default=0)
    registered_late = models.BooleanField(default=False)

    debarred_reason = models.CharField(max_length=300, blank=True)
    registered_at = models.DateTimeField(null=True, blank=True)

    # Rules 20 and 21: no payment is taken, only the reference the office saw.
    late_fee_reference = models.CharField(max_length=80, blank=True)
    reregistration_reference = models.CharField(max_length=80, blank=True)
    approved_by_user_id = models.IntegerField(null=True, blank=True)

    # Rule 19's first tier bars the next two drives, so the bar needs a start point.
    sanction = models.CharField(max_length=16, blank=True)
    sanction_rule = models.CharField(max_length=4, blank=True)
    sanctioned_at = models.DateTimeField(null=True, blank=True)
    sanctioned_by_user_id = models.IntegerField(null=True, blank=True)

    class Meta:
        db_table = "placement_registration"
        constraints = [
            models.UniqueConstraint(fields=["policy", "user_id"],
                                    name="registration_unique_per_season"),
        ]
        indexes = [models.Index(fields=["policy", "status"],
                                name="registration_season_idx")]

    def __str__(self) -> str:
        return f"reg u{self.user_id} {self.policy_id} {self.status}"


# -- Student clearance and debarment records (PR 445 / PBI 17) -----------------

class StudentClearance(TimeStampedModel, UserScopedModel):
    """A record of a student's clearance status."""

    academic_year = models.CharField(max_length=10)
    is_cleared = models.BooleanField(default=False)
    clearance_reason = models.TextField(blank=True, default="")
    verified_by_user_id = models.IntegerField(null=True, blank=True)

    class Meta:
        db_table = "placement_student_clearance"
        indexes = [models.Index(fields=["user_id", "academic_year"],
                                name="clearance_user_year_idx")]

    def __str__(self) -> str:
        return f"clr u{self.user_id} {self.academic_year}"


class DebarmentRecord(TimeStampedModel, UserScopedModel):
    """A record of a student's debarment status."""

    season = models.CharField(max_length=20)
    is_debarred = models.BooleanField(default=True)
    reason = models.TextField(blank=True, default="")
    debarred_until = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "placement_debarment_record"
        indexes = [models.Index(fields=["user_id", "season"],
                                name="debarment_user_season_idx")]

    def __str__(self) -> str:
        return f"deb u{self.user_id} {self.season}"

