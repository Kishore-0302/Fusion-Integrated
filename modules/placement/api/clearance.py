"""Post-offer obligations (rules 22 and 24).

Rule 24 lets this module hold up a no-dues certificate, so the clearance read is
deliberately narrow: a student sees their own, and a peer service asks about a
batch through `contracts.get_no_dues_clearances`. There is no endpoint that
hands one student another's clearance.
"""
from __future__ import annotations

from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from fusion_auth.permissions import HasModuleGrant, HasPermission
from modules.placement.api import serializers as s
from modules.placement.models import PlacementRecord
from modules.placement.services import clearance as service

MODULE = HasModuleGrant("placement_cell")
P_VIEW_SELF = "placement_cell.application.view_self"
P_MANAGE = "placement_cell.record.manage"
#: Reading the worklist is a report; recording a placement is not.
P_VIEW_REPORTS = "placement_cell.report.view"


def _actor(request):
    return getattr(request, "principal", None)


def _own_records(user_id: int):
    return (PlacementRecord.objects
            .filter(user_id=user_id, is_active=True)
            .select_related("company").order_by("-created_at"))


@extend_schema(responses=s.PlacementRecordDetailSerializer(many=True))
class MyRecordsView(APIView):
    """The caller's own placements and what each still owes."""

    permission_classes = [MODULE, HasPermission(P_VIEW_SELF)]

    def get(self, request):
        rows = _own_records(_actor(request).user_id)
        return Response({
            "results": s.PlacementRecordDetailSerializer(rows, many=True).data})


@extend_schema(responses=s.ClearanceSerializer)
class MyClearanceView(APIView):
    """Rule 24, for the caller. Scoped by the credential, never by a parameter."""

    permission_classes = [MODULE, HasPermission(P_VIEW_SELF)]

    def get(self, request):
        user_id = _actor(request).user_id
        verdict = service.no_dues_clearance(user_id=user_id)
        return Response({"user_id": user_id, "cleared": verdict.cleared,
                         "blocking": list(verdict.blocking),
                         "message": verdict.message})


@extend_schema(request=s.SubmitOfferLetterSerializer,
               responses=s.PlacementRecordDetailSerializer)
class SubmitOfferLetterView(APIView):
    """Rule 24 — attach the signed copy to release the no-dues hold."""

    permission_classes = [MODULE, HasPermission(P_VIEW_SELF)]

    def post(self, request, pk):
        payload = s.SubmitOfferLetterSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        record = service.submit_offer_letter(
            record_id=pk, user_id=_actor(request).user_id,
            document_id=payload.validated_data["document_id"])
        return Response(s.PlacementRecordDetailSerializer(record).data)


@extend_schema(request=s.NotJoiningSerializer,
               responses=s.NotJoiningResultSerializer)
class NotJoiningView(APIView):
    """Rule 22 — telling the Placement Cell you will not join."""

    permission_classes = [MODULE, HasPermission(P_VIEW_SELF)]

    def post(self, request, pk):
        payload = s.NotJoiningSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        record, verdict = service.declare_not_joining(
            record_id=pk, user_id=_actor(request).user_id,
            reason=payload.validated_data["reason"])
        return Response({
            "record": s.PlacementRecordDetailSerializer(record).data,
            "accepted": verdict.accepted, "is_late": verdict.is_late,
            "message": verdict.message,
        })


@extend_schema(responses=s.PlacementRecordDetailSerializer(many=True))
class OutstandingLettersView(APIView):
    """The office's worklist: placed students who still owe a letter."""

    permission_classes = [MODULE, HasPermission(P_VIEW_REPORTS, P_MANAGE)]

    def get(self, request):
        rows = service.outstanding(season=request.query_params.get("season"))
        return Response({
            "results": s.PlacementRecordDetailSerializer(rows, many=True).data})


@extend_schema(request=s.OffCampusRecordSerializer,
               responses={201: s.PlacementRecordDetailSerializer})
class OffCampusRecordView(APIView):
    """Rules 5 and 24 — an off-campus placement the Cell was told about.

    Without this the no-dues gate would miss off-campus students entirely,
    which is the group rule 24 names explicitly.
    """

    permission_classes = [MODULE, HasPermission(P_MANAGE)]

    def post(self, request):
        payload = s.OffCampusRecordSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        record = service.record_off_campus(actor=_actor(request),
                                           **payload.validated_data)
        return Response(s.PlacementRecordDetailSerializer(record).data,
                        status=status.HTTP_201_CREATED)


@extend_schema(request=s.PlacementRecordUpdateSerializer,
               responses=s.PlacementRecordAdminSerializer)
class PlacementRecordManageView(APIView):
    """Correct or deactivate an existing placement record (PC-AFR-031)."""

    permission_classes = [MODULE, HasPermission(P_MANAGE)]

    def patch(self, request, pk):
        payload = s.PlacementRecordUpdateSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        values = dict(payload.validated_data)
        reason = values.pop("reason")
        record = service.update_placement_record(
            record_id=pk, actor=_actor(request), reason=reason, **values)
        return Response(s.PlacementRecordAdminSerializer(record).data)
