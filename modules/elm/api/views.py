from rest_framework import generics
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import BasePermission
from fusion_auth.permissions import HasModuleGrant, HasPermission

from modules.elm.models import LeaveBalance, LeaveRequest, LeaveType
from modules.elm.services.policy import validate_no_overlap
MODULE = HasModuleGrant("elm")
P_VIEW_TYPES = "elm.leave_type.view"
P_VIEW_SELF = "elm.leave_request.view_self"
P_CREATE = "elm.leave_request.create"

class RequestPermission(BasePermission):
    def has_permission(self, request, view):
        principal = getattr(request, 'principal', None)
        if principal is None or not principal.has_module('elm'):
            return False
        code = P_CREATE if request.method == 'POST' else P_VIEW_SELF
        return principal.has_permission(code)

from modules.elm.api.serializers import (
    LeaveBalanceSerializer, LeaveRequestSerializer, LeaveTypeSerializer,
)


class LeaveTypeListView(generics.ListAPIView):
    serializer_class = LeaveTypeSerializer
    permission_classes = [MODULE, HasPermission(P_VIEW_TYPES)]
    queryset = LeaveType.objects.filter(is_active=True)


class MyLeaveBalanceListView(generics.ListAPIView):
    serializer_class = LeaveBalanceSerializer
    permission_classes = [MODULE, HasPermission(P_VIEW_SELF)]

    def get_queryset(self):
        principal = getattr(self.request, "principal", None)
        user_id = getattr(principal, "user_id", None)
        if user_id is None:
            return LeaveBalance.objects.none()
        return LeaveBalance.objects.filter(user_id=user_id).select_related("leave_type")


class MyLeaveRequestListCreateView(generics.ListCreateAPIView):
    serializer_class = LeaveRequestSerializer
    permission_classes = [RequestPermission]

    def get_queryset(self):
        principal = getattr(self.request, "principal", None)
        user_id = getattr(principal, "user_id", None)
        if user_id is None:
            return LeaveRequest.objects.none()
        return LeaveRequest.objects.filter(user_id=user_id).select_related("leave_type")

    def perform_create(self, serializer):
        principal = getattr(self.request, "principal", None)
        user_id = getattr(principal, "user_id", None)
        if user_id is None:
            raise ValidationError("Authenticated user identity is unavailable.")

        leave_type = serializer.validated_data["leave_type"]
        start_date = serializer.validated_data["start_date"]
        end_date = serializer.validated_data["end_date"]
        half_day = serializer.validated_data.get("half_day", "none")

        try:
            validate_no_overlap(
                user_id=user_id,
                leave_code=leave_type.code,
                start_date=start_date,
                end_date=end_date,
                half_day=half_day,
            )
        except ValueError as exc:
            raise ValidationError({"non_field_errors": [str(exc)]}) from exc

        serializer.save(user_id=user_id, status="draft")
