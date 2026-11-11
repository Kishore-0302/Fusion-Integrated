"""HTTP adapters and request serializers for Placement Cell use cases."""
from rest_framework import serializers, status
from rest_framework.response import Response
from rest_framework.views import APIView

from fusion_auth.permissions import HasModuleGrant
from modules.placement.api import serializers as placement_serializers
from modules.placement.authentication import RecruiterAuthentication
from modules.placement_cell import use_cases

MODULE = HasModuleGrant("placement_cell")


class _WorkflowView(APIView):
    authentication_classes = [RecruiterAuthentication, *APIView.authentication_classes]
    permission_classes = [MODULE]


def _actor(request):
    return getattr(request, "principal", None)


# ---------------------------------------------------------------------------
# Serializers
# ---------------------------------------------------------------------------
class ApplyInput(serializers.Serializer):
    cover_note = serializers.CharField(required=False, allow_blank=True, default="")
    resume_id = serializers.IntegerField(required=False, allow_null=True)


class WithdrawInput(serializers.Serializer):
    reason = serializers.CharField(required=False, allow_blank=True, default="")


class ReviewInput(serializers.Serializer):
    decision = serializers.ChoiceField(choices=("under_review", "shortlisted", "rejected"))
    reason = serializers.CharField(required=False, allow_blank=True, default="")


class ScheduleInput(serializers.Serializer):
    application_ids = serializers.ListField(
        child=serializers.IntegerField(min_value=1), allow_empty=False
    )
    mode = serializers.ChoiceField(choices=("online", "offline"))
    starts_at = serializers.DateTimeField()
    kind = serializers.ChoiceField(
        choices=("screening", "tech", "hr", "presentation"), default="tech"
    )
    seq = serializers.IntegerField(min_value=1, required=False)
    ends_at = serializers.DateTimeField(required=False, allow_null=True)
    venue = serializers.CharField(required=False, allow_blank=True, default="")
    meeting_url = serializers.URLField(required=False, allow_blank=True, default="")
    capacity = serializers.IntegerField(min_value=1, required=False, allow_null=True)
    instructions = serializers.CharField(required=False, allow_blank=True, default="")


class OfferIssueInput(serializers.Serializer):
    ctc_lpa = serializers.DecimalField(max_digits=8, decimal_places=2, required=False, min_value=0)
    tier_rank = serializers.IntegerField(required=False, min_value=1)
    respond_by = serializers.DateTimeField(required=False)
    letter_id = serializers.IntegerField(required=False, allow_null=True)


class OfferRespondInput(serializers.Serializer):
    accept = serializers.BooleanField()


class RecordManageInput(serializers.Serializer):
    company_id = serializers.IntegerField(required=False, min_value=1)
    ctc_lpa = serializers.DecimalField(max_digits=8, decimal_places=2, required=False, min_value=0)
    kind = serializers.CharField(required=False, max_length=12)
    is_active = serializers.BooleanField(required=False)
    reason = serializers.CharField(max_length=300, allow_blank=False)

    def validate_reason(self, value):
        val = value.strip()
        if not val:
            raise serializers.ValidationError("A correction reason is required.")
        return val


class AnnouncementPublishInput(serializers.Serializer):
    title = serializers.CharField(max_length=120)
    body = serializers.CharField()
    topic = serializers.ChoiceField(choices=("drives", "shortlists", "results", "general"), default="general")
    audience = serializers.ChoiceField(choices=("students", "recruiters", "all"), default="students")
    placement_year = serializers.CharField(max_length=10, required=False, default="")


# ---------------------------------------------------------------------------
# Views
# ---------------------------------------------------------------------------
class CompanySubmitView(_WorkflowView):
    """PC-UC-015: Recruiter submits draft opportunity for TPO review."""
    def post(self, request, pk):
        posting = use_cases.submit_company_opportunity(
            posting_id=pk, actor=_actor(request))
        return Response(placement_serializers.JobPostingSerializer(posting).data)


class TpoPublishView(_WorkflowView):
    """PC-UC-006: TPO publishes pending opportunity with frozen criteria."""
    def post(self, request, pk):
        posting = use_cases.publish_tpo_opportunity(
            posting_id=pk, actor=_actor(request))
        return Response(placement_serializers.JobPostingSerializer(posting).data)


class StudentApplyView(_WorkflowView):
    """PC-UC-003: Student applies to published posting."""
    def post(self, request, pk):
        payload = ApplyInput(data=request.data)
        payload.is_valid(raise_exception=True)
        application = use_cases.apply_to_opportunity(
            posting_id=pk, actor=_actor(request), **payload.validated_data)
        data = placement_serializers.ApplicationSerializer(
            application, context={"actor": _actor(request)}).data
        return Response(data, status=status.HTTP_201_CREATED)


class StudentWithdrawView(_WorkflowView):
    """PC-UC-005: Student withdraws submitted application."""
    def post(self, request, pk):
        payload = WithdrawInput(data=request.data)
        payload.is_valid(raise_exception=True)
        application = use_cases.withdraw_application(
            application_id=pk, actor=_actor(request), **payload.validated_data)
        data = placement_serializers.ApplicationSerializer(
            application, context={"actor": _actor(request)}).data
        return Response(data)


class CompanyReviewView(_WorkflowView):
    """PC-UC-016: Recruiter records shortlisting or rejection."""
    def post(self, request, pk):
        payload = ReviewInput(data=request.data)
        payload.is_valid(raise_exception=True)
        application = use_cases.review_company_application(
            application_id=pk, actor=_actor(request), **payload.validated_data)
        data = placement_serializers.ApplicationSerializer(
            application, context={"actor": _actor(request)}).data
        return Response(data)


class TpoScheduleView(_WorkflowView):
    """PC-UC-009: TPO schedules interview round with shortlisted candidates."""
    def post(self, request, pk):
        payload = ScheduleInput(data=request.data)
        payload.is_valid(raise_exception=True)
        data = dict(payload.validated_data)
        application_ids = data.pop("application_ids")
        round_, count = use_cases.schedule_interviews(
            posting_id=pk, actor=_actor(request),
            application_ids=application_ids, **data)
        return Response({
            "id": round_.pk,
            "posting_id": round_.posting_id,
            "seq": round_.seq,
            "kind": round_.kind,
            "mode": round_.mode,
            "starts_at": round_.starts_at,
            "scheduled_applications": count,
        }, status=status.HTTP_201_CREATED)


class OfferIssueView(_WorkflowView):
    """PC-UC-022: Recruiter or TPO extends formal job offer."""
    def post(self, request, pk):
        payload = OfferIssueInput(data=request.data)
        payload.is_valid(raise_exception=True)
        offer = use_cases.issue_job_offer(
            application_id=pk, actor=_actor(request), **payload.validated_data)
        return Response(placement_serializers.OfferSerializer(offer).data,
                        status=status.HTTP_201_CREATED)


class OfferRespondView(_WorkflowView):
    """PC-UC-008: Student accepts or declines formal job offer."""
    def post(self, request, pk):
        payload = OfferRespondInput(data=request.data)
        payload.is_valid(raise_exception=True)
        offer = use_cases.respond_to_offer(
            offer_id=pk, accept=payload.validated_data["accept"], actor=_actor(request))
        return Response(placement_serializers.OfferSerializer(offer).data)


class PlacementRecordManageView(_WorkflowView):
    """PC-UC-010: TPO corrects or manages recorded placement."""
    def patch(self, request, pk):
        payload = RecordManageInput(data=request.data)
        payload.is_valid(raise_exception=True)
        record = use_cases.update_placement_record(
            record_id=pk, actor=_actor(request), **payload.validated_data)
        return Response(placement_serializers.PlacementRecordAdminSerializer(record).data)


class AnnouncementPublishView(_WorkflowView):
    """PC-UC-013: TPO publishes recruitment announcement."""
    def post(self, request):
        payload = AnnouncementPublishInput(data=request.data)
        payload.is_valid(raise_exception=True)
        announcement = use_cases.publish_announcement(
            actor=_actor(request), **payload.validated_data)
        return Response(placement_serializers.AnnouncementSerializer(announcement).data,
                        status=status.HTTP_201_CREATED)


class StudentStatsView(_WorkflowView):
    """PC-UC-024: Student accesses anonymized placement metrics."""
    def get(self, request):
        season = request.query_params.get("season", "2026-27")
        data = use_cases.get_student_stats(season=season)
        return Response(data)
