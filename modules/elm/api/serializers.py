from rest_framework import serializers

from modules.elm.models import LeaveBalance, LeaveRequest, LeaveType


class LeaveTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = LeaveType
        fields = ["id", "code", "name", "annual_quota", "carry_forward"]


class LeaveBalanceSerializer(serializers.ModelSerializer):
    leave_code = serializers.CharField(source="leave_type.code", read_only=True)
    leave_name = serializers.CharField(source="leave_type.name", read_only=True)
    available_days = serializers.DecimalField(
        max_digits=7, decimal_places=2, read_only=True
    )

    class Meta:
        model = LeaveBalance
        fields = [
            "id", "leave_code", "leave_name", "leave_year",
            "entitled_days", "carried_forward_days", "used_days",
            "available_days",
        ]


class LeaveRequestSerializer(serializers.ModelSerializer):
    leave_code = serializers.CharField(source="leave_type.code", read_only=True)

    class Meta:
        model = LeaveRequest
        fields = [
            "id", "leave_type", "leave_code", "start_date", "end_date",
            "half_day", "reason", "status", "created_at",
        ]
        read_only_fields = ["id", "leave_code", "status", "created_at"]

    def validate(self, attrs):
        from modules.elm.services.policy import calculate_leave_days

        start = attrs.get("start_date")
        end = attrs.get("end_date")
        leave_type = attrs.get("leave_type")
        half_day = attrs.get("half_day", "none")

        if start and end and leave_type:
            try:
                calculate_leave_days(
                    start, end, leave_code=leave_type.code, half_day=half_day
                )
            except ValueError as exc:
                raise serializers.ValidationError({"start_date": str(exc)}) from exc

        return attrs
