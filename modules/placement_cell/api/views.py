"""HTTP adapters for the Assignment 7 use cases."""
from rest_framework import serializers, status
from rest_framework.response import Response
from rest_framework.views import APIView

from fusion_auth.permissions import HasModuleGrant
from modules.placement.authentication import RecruiterAuthentication
from modules.placement.api import serializers as placement_serializers
from modules.placement_cell import use_cases

MODULE = HasModuleGrant("placement_cell")


class _WorkflowView(APIView):
    authentication_classes = [RecruiterAuthentication, *APIView.authentication_classes]
    permission_classes = [MODULE]


class ApplyInput(serializers.Serializer):
    cover_note = serializers.CharField(required=False, allow_blank=True, default="")
    resume_id = serializers.IntegerField(required=False, allow_null=True)


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


def _actor(request):
    return getattr(request, "principal", None)


class CompanySubmitView(_WorkflowView):
    def post(self, request, pk):
        posting = use_cases.submit_company_opportunity(
            posting_id=pk, actor=_actor(request))
        return Response(placement_serializers.JobPostingSerializer(posting).data)


class TpoPublishView(_WorkflowView):
    def post(self, request, pk):
        posting = use_cases.publish_tpo_opportunity(
            posting_id=pk, actor=_actor(request))
        return Response(placement_serializers.JobPostingSerializer(posting).data)


class StudentApplyView(_WorkflowView):
    def post(self, request, pk):
        payload = ApplyInput(data=request.data)
        payload.is_valid(raise_exception=True)
        application = use_cases.apply_to_opportunity(
            posting_id=pk, actor=_actor(request), **payload.validated_data)
        data = placement_serializers.ApplicationSerializer(
            application, context={"actor": _actor(request)}).data
        return Response(data, status=status.HTTP_201_CREATED)


class CompanyReviewView(_WorkflowView):
    def post(self, request, pk):
        payload = ReviewInput(data=request.data)
        payload.is_valid(raise_exception=True)
        application = use_cases.review_company_application(
            application_id=pk, actor=_actor(request), **payload.validated_data)
        data = placement_serializers.ApplicationSerializer(
            application, context={"actor": _actor(request)}).data
        return Response(data)


class TpoScheduleView(_WorkflowView):
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
