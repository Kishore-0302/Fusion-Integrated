"""Serializers. Thin, and every write serializer is an explicit allow-list.

`fields = "__all__"` is never used here — it is exactly how `user_id`,
`status` or `cpi_at_apply` ends up writable by whoever posts the right JSON.
"""
from rest_framework import serializers

from modules.placement.models import (
    Announcement,
    Application,
    Company,
    CompanyContact,
    ConductIncident,
    InterviewRound,
    JobPosting,
    Offer,
    PlacementPolicy,
    PlacementRecord,
    PlacementRegistration,
    ProfileDocument,
    RoundParticipation,
)


# -- Companies -----------------------------------------------------------------
class CompanyContactSerializer(serializers.ModelSerializer):
    class Meta:
        model = CompanyContact
        fields = ("id", "name", "designation", "email", "phone", "is_primary")


class CompanySerializer(serializers.ModelSerializer):
    contacts = CompanyContactSerializer(many=True, read_only=True)
    can_operate = serializers.BooleanField(read_only=True)

    class Meta:
        model = Company
        fields = ("id", "name", "slug", "sector", "sector_kind", "website",
                  "hq_city", "tier_rank", "is_marquee", "status",
                  "approval_status", "approval_note", "approved_at",
                  "can_operate", "contacts", "created_at")
        read_only_fields = fields


class CompanyBriefSerializer(serializers.ModelSerializer):
    """What a student sees. No approval trail, no internal notes."""

    class Meta:
        model = Company
        fields = ("id", "name", "slug", "sector", "sector_kind", "website",
                  "hq_city", "tier_rank", "is_marquee")
        read_only_fields = fields


class CompanyRegisterSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=160)
    sector = serializers.CharField(max_length=60, required=False, allow_blank=True)
    website = serializers.URLField(required=False, allow_blank=True)
    hq_city = serializers.CharField(max_length=80, required=False, allow_blank=True)
    contact_name = serializers.CharField(max_length=120, required=False,
                                         allow_blank=True)
    contact_email = serializers.EmailField(required=False, allow_blank=True)
    contact_phone = serializers.CharField(max_length=32, required=False,
                                          allow_blank=True)


class ApprovalSerializer(serializers.Serializer):
    note = serializers.CharField(max_length=300, required=False, allow_blank=True,
                                 default="")


# -- Postings ------------------------------------------------------------------
class JobPostingSerializer(serializers.ModelSerializer):
    company = CompanyBriefSerializer(read_only=True)
    is_open = serializers.SerializerMethodField()

    class Meta:
        model = JobPosting
        fields = ("id", "title", "kind", "company", "placement_year",
                  "description", "location", "ctc_lpa", "stipend_pm",
                  "bond_months", "seats", "eligibility_rule", "status",
                  "is_dream_slot", "dream_slot_note",
                  "opens_at", "closes_at", "published_at", "is_open",
                  "created_at")
        read_only_fields = fields

    def get_is_open(self, obj) -> bool:
        from django.utils import timezone
        return bool(obj.status == "published" and obj.closes_at
                    and obj.closes_at > timezone.now())


class JobPostingWriteSerializer(serializers.Serializer):
    company_id = serializers.IntegerField(required=False)
    placement_year = serializers.CharField(max_length=12)
    title = serializers.CharField(max_length=160)
    kind = serializers.ChoiceField(choices=("fte", "internship", "ppo"),
                                   default="fte")
    description = serializers.CharField(required=False, allow_blank=True,
                                        default="")
    location = serializers.CharField(max_length=120, required=False,
                                     allow_blank=True, default="")
    ctc_lpa = serializers.DecimalField(max_digits=8, decimal_places=2,
                                       required=False, allow_null=True)
    stipend_pm = serializers.DecimalField(max_digits=10, decimal_places=2,
                                          required=False, allow_null=True)
    bond_months = serializers.IntegerField(required=False, allow_null=True)
    seats = serializers.IntegerField(required=False, allow_null=True)
    eligibility_rule = serializers.JSONField(required=False, default=dict)
    opens_at = serializers.DateTimeField(required=False, allow_null=True)
    closes_at = serializers.DateTimeField(required=False, allow_null=True)
    # Policy rule 7. Declared by the Placement Cell per company.
    is_dream_slot = serializers.BooleanField(required=False, default=False)
    dream_slot_note = serializers.CharField(max_length=300, required=False,
                                            allow_blank=True, default="")


# -- Profiles ------------------------------------------------------------------
class DocumentLinkSerializer(serializers.Serializer):
    """A Drive link. Validated in core.files.drive."""

    kind = serializers.ChoiceField(
        choices=["resume", "certificate", "offer_letter", "other"])
    url = serializers.CharField(max_length=500)
    title = serializers.CharField(max_length=160, required=False,
                                  allow_blank=True, default="")


class ProfileDocumentSerializer(serializers.ModelSerializer):
    """Deliberately no `drive_url` — whoever holds it opens the file, with no
    further check. `download_url` re-authorises on every use."""

    is_link = serializers.BooleanField(read_only=True)
    download_url = serializers.SerializerMethodField()

    class Meta:
        model = ProfileDocument
        fields = ("id", "kind", "title", "original_filename", "content_type",
                  "size_bytes", "is_link", "download_url", "created_at")
        read_only_fields = fields

    def get_download_url(self, obj) -> str:
        return f"/api/v1/placement/documents/{obj.pk}/download"


# -- Applications --------------------------------------------------------------
class ApplicationSerializer(serializers.ModelSerializer):
    posting = JobPostingSerializer(read_only=True)
    allowed_transitions = serializers.SerializerMethodField()
    candidate = serializers.SerializerMethodField()

    class Meta:
        model = Application
        fields = ("id", "posting", "user_id", "status", "cpi_at_apply",
                  "semester_at_apply", "eligibility_snapshot", "cover_note",
                  "applied_at", "withdrawn_reason", "allowed_transitions",
                  "candidate", "created_at")
        read_only_fields = fields

    def get_allowed_transitions(self, obj) -> list[str]:
        from modules.placement.domain import state_machine as sm
        from modules.placement.services.applications import actor_kind
        actor = self.context.get("actor")
        return sm.allowed_targets(obj.status, actor_kind(actor) if actor else None)

    def get_candidate(self, obj) -> dict | None:
        """Populated only when the view batch-loaded the directory, i.e. when
        the reader is staff. A student's own list needs no directory call."""
        person = (self.context.get("people") or {}).get(obj.user_id)
        if person is None:
            return None
        return {"user_id": obj.user_id,
                "name": getattr(person, "display_name", "") or "",
                "roll_no": getattr(person, "username", "") or "",
                "discipline": getattr(person, "discipline", "") or "",
                "programme": getattr(person, "programme", "") or "",
                "batch_year": getattr(person, "batch_year", None),
                "resume_link": getattr(person, "resume_link", "") or ""}


class ApplicantSerializer(serializers.ModelSerializer):
    """The recruiter-facing view of an application.

    Narrower than ApplicationSerializer on purpose: enough to make a hiring
    decision and nothing more. No eligibility snapshot (it records why other
    people failed), no withdrawal reasons, no audit trail.
    """

    candidate = serializers.SerializerMethodField()

    class Meta:
        model = Application
        fields = ("id", "status", "cpi_at_apply", "semester_at_apply",
                  "cover_note", "applied_at", "candidate")
        read_only_fields = fields

    def get_candidate(self, obj) -> dict:
        person = (self.context.get("people") or {}).get(obj.user_id)
        return {
            "user_id": obj.user_id,
            "name": getattr(person, "display_name", "") or "",
            "roll_no": getattr(person, "username", "") or "",
            "discipline": getattr(person, "discipline", "") or "",
            "programme": getattr(person, "programme", "") or "",
            "batch_year": getattr(person, "batch_year", None),
            # The one the student maintains on the ERP portal, not a second copy.
            "resume_link": getattr(person, "resume_link", "") or "",
        }


class TransitionSerializer(serializers.Serializer):
    to_status = serializers.CharField(max_length=24)
    reason = serializers.CharField(max_length=300, required=False,
                                   allow_blank=True, default="")


class ApplySerializer(serializers.Serializer):
    posting_id = serializers.IntegerField()
    cover_note = serializers.CharField(max_length=4000, required=False,
                                       allow_blank=True, default="")
    resume_id = serializers.IntegerField(required=False, allow_null=True)


# -- Interviews ----------------------------------------------------------------
class InterviewRoundSerializer(serializers.ModelSerializer):
    class Meta:
        model = InterviewRound
        fields = ("id", "posting", "seq", "kind", "mode", "starts_at",
                  "ends_at", "venue", "meeting_url", "capacity", "instructions",
                  "created_at")
        read_only_fields = fields


class InterviewRoundWriteSerializer(serializers.Serializer):
    posting_id = serializers.IntegerField()
    kind = serializers.CharField(max_length=12, default="tech")
    mode = serializers.ChoiceField(choices=("online", "offline"))
    starts_at = serializers.DateTimeField()
    ends_at = serializers.DateTimeField(required=False, allow_null=True)
    venue = serializers.CharField(max_length=200, required=False,
                                  allow_blank=True, default="")
    meeting_url = serializers.URLField(required=False, allow_blank=True,
                                       default="")
    capacity = serializers.IntegerField(required=False, allow_null=True)
    instructions = serializers.CharField(required=False, allow_blank=True,
                                         default="")


class AddCandidatesSerializer(serializers.Serializer):
    application_ids = serializers.ListField(
        child=serializers.IntegerField(), min_length=1, max_length=500)


class RoundOutcomeSerializer(serializers.Serializer):
    application_id = serializers.IntegerField()
    outcome = serializers.ChoiceField(
        choices=("pending", "attended", "absent", "passed", "failed"))
    score = serializers.DecimalField(max_digits=6, decimal_places=2,
                                     required=False, allow_null=True)
    remarks = serializers.CharField(max_length=300, required=False,
                                    allow_blank=True, default="")


class RoundParticipationSerializer(serializers.ModelSerializer):
    class Meta:
        model = RoundParticipation
        fields = ("id", "round", "application", "outcome", "score", "remarks")
        read_only_fields = ("id", "round", "application")


# -- Offers --------------------------------------------------------------------
class OfferSerializer(serializers.ModelSerializer):
    posting = JobPostingSerializer(read_only=True)

    class Meta:
        model = Offer
        fields = ("id", "posting", "user_id", "ctc_lpa", "tier_rank",
                  "is_dream", "status", "respond_by", "responded_at",
                  "policy_decision", "created_at")
        read_only_fields = fields


class OfferIssueSerializer(serializers.Serializer):
    application_id = serializers.IntegerField()
    ctc_lpa = serializers.DecimalField(max_digits=8, decimal_places=2,
                                       required=False, allow_null=True)
    tier_rank = serializers.IntegerField(required=False, allow_null=True)
    respond_by = serializers.DateTimeField(required=False, allow_null=True)


class OfferRespondSerializer(serializers.Serializer):
    accept = serializers.BooleanField()


# -- Records, policy, registration, announcements ------------------------------
class PlacementRecordSerializer(serializers.ModelSerializer):
    company = CompanyBriefSerializer(read_only=True)

    class Meta:
        model = PlacementRecord
        fields = ("id", "user_id", "company", "posting", "ctc_lpa", "kind",
                  "is_active", "created_at")
        read_only_fields = fields


class PlacementPolicySerializer(serializers.ModelSerializer):
    class Meta:
        model = PlacementPolicy
        fields = ("id", "season", "label", "starts_on", "ends_on", "is_active",
                  "mandatory_from", "discipline_groups",
                  "min_cpi_to_register", "allow_backlog_registration",
                  "late_registration_fee", "reregistration_fee",
                  "default_offer_response_hours")


class SeasonSerializer(serializers.ModelSerializer):
    """Just enough to populate a season picker."""

    class Meta:
        model = PlacementPolicy
        fields = ("season", "label", "is_active")
        read_only_fields = fields


class RegistrationSerializer(serializers.ModelSerializer):
    #: The season code, so a client need not resolve the policy id.
    season = serializers.CharField(source="policy.season", read_only=True)

    class Meta:
        model = PlacementRegistration
        fields = ("id", "policy", "season", "user_id", "status",
                  "category_number", "switches_used", "offer_count",
                  "best_accepted_ctc_lpa", "held_is_marquee",
                  "held_sector_kind", "registered_late", "debarred_reason",
                  "registered_at")
        read_only_fields = fields


class AnnouncementSerializer(serializers.ModelSerializer):
    class Meta:
        model = Announcement
        fields = ("id", "title", "body", "topic", "audience", "placement_year",
                  "published_at", "published_by_role", "is_withdrawn",
                  "withdrawn_reason", "created_at")
        read_only_fields = fields


class AnnouncementWriteSerializer(serializers.Serializer):
    title = serializers.CharField(max_length=200)
    body = serializers.CharField()
    topic = serializers.CharField(max_length=20, default="general")
    audience = serializers.CharField(max_length=12, default="students")
    placement_year = serializers.CharField(max_length=12, required=False,
                                           allow_blank=True, default="")


class WithdrawSerializer(serializers.Serializer):
    reason = serializers.CharField(max_length=300)


# -- Recruiter portal ----------------------------------------------------------
class RecruiterInviteSerializer(serializers.Serializer):
    company_id = serializers.IntegerField()
    email = serializers.EmailField()
    full_name = serializers.CharField(max_length=120, required=False,
                                      allow_blank=True, default="")


class RecruiterAcceptSerializer(serializers.Serializer):
    token = serializers.CharField(max_length=200)
    password = serializers.CharField(max_length=128, write_only=True)


class RecruiterLoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(max_length=128, write_only=True)


# -- Response shapes: endpoints that answer with a dict, not a model ----------
class DetailSerializer(serializers.Serializer):
    detail = serializers.CharField()


class EligibilityFailureSerializer(serializers.Serializer):
    field = serializers.CharField()
    reason = serializers.CharField()
    message = serializers.CharField()
    required = serializers.JSONField(allow_null=True)
    actual = serializers.JSONField(allow_null=True)


class SeasonDecisionSerializer(serializers.Serializer):
    allowed = serializers.BooleanField()
    rule = serializers.CharField()
    message = serializers.CharField()


class EligibilityVerdictSerializer(serializers.Serializer):
    """Why a student may or may not apply (PC-UC-003)."""

    is_eligible = serializers.BooleanField()
    failed = EligibilityFailureSerializer(many=True)
    error = serializers.CharField(allow_null=True)
    season_decision = SeasonDecisionSerializer()
    #: A string, not a number — see the note on Decimal in the wire types.
    cpi = serializers.CharField(allow_null=True)
    semester = serializers.IntegerField(allow_null=True)
    declared_seq = serializers.IntegerField(allow_null=True)
    standing = serializers.JSONField()
    evaluated_at = serializers.DateTimeField()


class CandidateSerializer(serializers.Serializer):
    """A person as the ERP portal and the IAM describe them. Read-only here."""

    user_id = serializers.IntegerField()
    name = serializers.CharField(allow_blank=True)
    roll_no = serializers.CharField(allow_blank=True)
    email = serializers.CharField(allow_blank=True)
    programme = serializers.CharField(allow_blank=True)
    discipline = serializers.CharField(allow_blank=True)
    batch_year = serializers.IntegerField(allow_null=True)
    resume_link = serializers.CharField(allow_blank=True)
    profile_completed = serializers.BooleanField()
    academic = serializers.JSONField(allow_null=True)


class ScheduledCountSerializer(serializers.Serializer):
    scheduled = serializers.IntegerField()


class CompanyPlacedSerializer(serializers.Serializer):
    company = serializers.CharField()
    placed = serializers.IntegerField()


class StudentStatsSerializer(serializers.Serializer):
    """PC-BR-016. Anonymised, and absent entirely below the small-cell floor."""

    season = serializers.CharField()
    available = serializers.BooleanField()
    reason = serializers.CharField(required=False)
    registered = serializers.IntegerField(required=False)
    placed = serializers.IntegerField(required=False)
    placement_rate = serializers.FloatField(required=False, allow_null=True)
    companies_participated = serializers.IntegerField(required=False)
    median_ctc = serializers.CharField(required=False, allow_null=True)
    max_ctc = serializers.CharField(required=False, allow_null=True)
    companies = CompanyPlacedSerializer(many=True, required=False)
    computed_at = serializers.DateTimeField(required=False)


class StaffStatsSerializer(serializers.Serializer):
    """PC-UC-011/012. Operational figures, staff only."""

    season = serializers.CharField()
    available = serializers.BooleanField()
    registered = serializers.IntegerField(required=False)
    debarred = serializers.IntegerField(required=False)
    placed = serializers.IntegerField(required=False)
    median_ctc = serializers.CharField(required=False, allow_null=True)
    mean_ctc = serializers.CharField(required=False, allow_null=True)
    max_ctc = serializers.CharField(required=False, allow_null=True)
    by_company = serializers.JSONField(required=False)
    applications_by_status = serializers.JSONField(required=False)


class RecruiterInviteResultSerializer(serializers.Serializer):
    """`invite_token` is returned once and is not stored in readable form."""

    account_id = serializers.IntegerField()
    email = serializers.EmailField()
    invite_token = serializers.CharField()
    expires_at = serializers.DateTimeField()


class RecruiterLoginResultSerializer(serializers.Serializer):
    expires_at = serializers.DateTimeField()
    company_id = serializers.IntegerField()
    csrf_token = serializers.CharField()


class RecruiterCompanySerializer(serializers.Serializer):
    id = serializers.IntegerField()
    name = serializers.CharField()
    approval_status = serializers.CharField()


class RecruiterMeSerializer(serializers.Serializer):
    csrf_token = serializers.CharField()
    email = serializers.EmailField()
    full_name = serializers.CharField(allow_blank=True)
    company = RecruiterCompanySerializer()
    modules = serializers.ListField(child=serializers.CharField())


class AcademicStandingRowSerializer(serializers.Serializer):
    """One row of the CPI directory. `cpi` is null when nothing is declared —
    never zero."""

    user_id = serializers.IntegerField()
    roll_no = serializers.CharField()
    name = serializers.CharField(allow_blank=True)
    programme = serializers.CharField(allow_blank=True)
    discipline = serializers.CharField(allow_blank=True)
    batch_year = serializers.IntegerField(allow_null=True)
    cpi = serializers.CharField(allow_null=True)
    semester = serializers.IntegerField(allow_null=True)
    semester_type = serializers.CharField(allow_null=True)
    declared_seq = serializers.IntegerField(allow_null=True)
    earned_credits = serializers.CharField(allow_null=True)
    active_backlogs = serializers.IntegerField(allow_null=True)


class AcademicDirectorySerializer(serializers.Serializer):
    count = serializers.IntegerField()
    limit = serializers.IntegerField()
    offset = serializers.IntegerField()
    results = AcademicStandingRowSerializer(many=True)


class AcademicFiltersSerializer(serializers.Serializer):
    disciplines = serializers.ListField(child=serializers.CharField())
    batch_years = serializers.ListField(child=serializers.IntegerField())
    programmes = serializers.ListField(child=serializers.CharField())


# -- Conduct and sanctions (rules 18, 19, 21) ----------------------------------
class ConductIncidentSerializer(serializers.ModelSerializer):
    class Meta:
        model = ConductIncident
        fields = ("id", "user_id", "kind", "posting", "note", "waived",
                  "waived_reason", "recorded_by_user_id", "created_at")
        read_only_fields = fields


class RecordIncidentSerializer(serializers.Serializer):
    season = serializers.CharField(max_length=12)
    user_id = serializers.IntegerField()
    kind = serializers.ChoiceField(
        choices=["consent_failure", "code_of_conduct", "misrepresentation"])
    note = serializers.CharField(max_length=300)
    posting_id = serializers.IntegerField(required=False, allow_null=True)


class RecommendationSerializer(serializers.Serializer):
    """What the policy points to. `automatic` is always false — rules 19 and 21
    leave the decision to a human."""

    sanction = serializers.CharField()
    rule = serializers.CharField()
    message = serializers.CharField()
    automatic = serializers.BooleanField()


class IncidentRecordedSerializer(serializers.Serializer):
    incident = ConductIncidentSerializer()
    recommendation = RecommendationSerializer()


class ApplySanctionSerializer(serializers.Serializer):
    season = serializers.CharField(max_length=12)
    user_id = serializers.IntegerField()
    sanction = serializers.ChoiceField(
        choices=["bar_next_two", "deregister", "bar_season", "bar_permanent"])
    rule = serializers.CharField(max_length=4)
    reason = serializers.CharField(max_length=300)


class LiftSanctionSerializer(serializers.Serializer):
    season = serializers.CharField(max_length=12)
    user_id = serializers.IntegerField()
    reason = serializers.CharField(max_length=300)


class WaiveIncidentSerializer(serializers.Serializer):
    reason = serializers.CharField(max_length=300)


# -- Registration (rules 1, 20, 21) --------------------------------------------
class RegistrationTermsSerializer(serializers.Serializer):
    """What route is open to this student, and what it costs."""

    route = serializers.CharField()
    reason = serializers.CharField()
    message = serializers.CharField()
    fee = serializers.IntegerField()
    allowed = serializers.BooleanField()


class RegisterSerializer(serializers.Serializer):
    season = serializers.CharField(max_length=12)


class OptOutSerializer(serializers.Serializer):
    season = serializers.CharField(max_length=12)
    reason = serializers.CharField(max_length=300, required=False,
                                   allow_blank=True, default="")


class FeeApprovalSerializer(serializers.Serializer):
    """Rules 20 and 21 both require the challan or receipt to be produced."""

    season = serializers.CharField(max_length=12)
    user_id = serializers.IntegerField()
    fee_reference = serializers.CharField(max_length=80)


# -- Post-offer obligations (rules 22, 24) -------------------------------------
class PlacementRecordDetailSerializer(serializers.ModelSerializer):
    """A student's own record, with what rules 22 and 24 still want from it."""

    company = CompanyBriefSerializer(read_only=True)
    offer_letter_submitted = serializers.SerializerMethodField()

    class Meta:
        model = PlacementRecord
        fields = ("id", "company", "source", "kind", "ctc_lpa",
                  "offer_letter_submitted", "offer_letter_submitted_at",
                  "not_joining_declared_at", "not_joining_reason",
                  "not_joining_was_late", "created_at")
        read_only_fields = fields

    def get_offer_letter_submitted(self, obj) -> bool:
        return obj.offer_letter_id is not None


class PlacementRecordUpdateSerializer(serializers.Serializer):
    """Fields the placement office may correct on an existing record (PC-AFR-031, PR 445)."""

    id = serializers.IntegerField(required=False)
    company_id = serializers.IntegerField(required=False, min_value=1)
    ctc_lpa = serializers.DecimalField(max_digits=8, decimal_places=2,
                                       required=False, allow_null=True,
                                       min_value=0)
    kind = serializers.CharField(required=False, max_length=12, allow_blank=False)
    is_active = serializers.BooleanField(required=False)
    verified_by_user_id = serializers.IntegerField(required=False, allow_null=True)
    is_accepted = serializers.BooleanField(required=False)
    reason = serializers.CharField(max_length=300, required=False, allow_blank=True, default="")

    def validate_reason(self, value):
        return (value or "").strip()

    def validate(self, attrs):
        updatable = ("company_id", "ctc_lpa", "kind", "is_active",
                     "verified_by_user_id", "is_accepted")
        if not any(field in attrs for field in updatable):
            raise serializers.ValidationError(
                "Provide at least one placement field to update.")
        return attrs



class PlacementRecordAdminSerializer(serializers.ModelSerializer):
    """Placement office view of a corrected record."""

    company = CompanyBriefSerializer(read_only=True)

    class Meta:
        model = PlacementRecord
        fields = ("id", "user_id", "company", "source", "kind", "ctc_lpa",
                  "is_active", "created_at", "updated_at")
        read_only_fields = fields


class ClearanceSerializer(serializers.Serializer):
    """Rule 24. `blocking` names each company, so a refusal is actionable."""

    user_id = serializers.IntegerField()
    cleared = serializers.BooleanField()
    blocking = serializers.ListField(child=serializers.CharField())
    message = serializers.CharField()


class SubmitOfferLetterSerializer(serializers.Serializer):
    document_id = serializers.IntegerField()


class NotJoiningSerializer(serializers.Serializer):
    reason = serializers.CharField(max_length=300)


class NotJoiningResultSerializer(serializers.Serializer):
    record = PlacementRecordDetailSerializer()
    accepted = serializers.BooleanField()
    is_late = serializers.BooleanField()
    message = serializers.CharField()


class OffCampusRecordSerializer(serializers.Serializer):
    season = serializers.CharField(max_length=12)
    user_id = serializers.IntegerField()
    company_id = serializers.IntegerField()
    ctc_lpa = serializers.DecimalField(max_digits=8, decimal_places=2,
                                       required=False, allow_null=True)
    kind = serializers.ChoiceField(choices=["fte", "internship", "ppo"],
                                   default="fte")


# -- Bulk actions --------------------------------------------------------------
class BulkTransitionSerializer(serializers.Serializer):
    application_ids = serializers.ListField(
        child=serializers.IntegerField(), allow_empty=False, max_length=200)
    to_status = serializers.CharField(max_length=24)
    reason = serializers.CharField(max_length=300, required=False,
                                   allow_blank=True, default="")


class BulkOutcomeSerializer(serializers.Serializer):
    application_id = serializers.IntegerField()
    moved = serializers.BooleanField()
    error = serializers.CharField(allow_blank=True)
    code = serializers.CharField(allow_blank=True)


class BulkResultSerializer(serializers.Serializer):
    """Counts first, then the per-item detail — a partial run must never read
    as a complete one."""

    moved = serializers.IntegerField()
    refused = serializers.IntegerField()
    results = BulkOutcomeSerializer(many=True)


# -- Audit trail (PC-BR-008) ---------------------------------------------------
class TransitionEntrySerializer(serializers.Serializer):
    """`reason` and the actor ids are absent for a non-staff reader — see
    api/audit.py for why."""

    from_status = serializers.CharField()
    to_status = serializers.CharField()
    at = serializers.DateTimeField()
    actor_label = serializers.CharField(allow_blank=True)
    reason = serializers.CharField(required=False, allow_blank=True)
    actor_user_id = serializers.IntegerField(required=False, allow_null=True)
    actor_recruiter_id = serializers.IntegerField(required=False, allow_null=True)


class TransitionHistorySerializer(serializers.Serializer):
    application_id = serializers.IntegerField()
    #: True when reasons and actors were withheld, so the UI can say so.
    redacted = serializers.BooleanField()
    results = TransitionEntrySerializer(many=True)


class StudentConductIncidentSerializer(serializers.ModelSerializer):
    """A student's own record. Shows the note and waiver — both contestable —
    but not who recorded it."""

    class Meta:
        model = ConductIncident
        fields = ("id", "kind", "note", "waived", "waived_reason", "created_at")
        read_only_fields = fields
