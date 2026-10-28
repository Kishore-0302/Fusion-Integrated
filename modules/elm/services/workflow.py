"""Basic leave-request transitions; hierarchy-specific sanctioning remains separate."""
from django.db import transaction
from django.utils import timezone

from modules.elm.models import LeaveRequest


class WorkflowError(ValueError):
    pass


@transaction.atomic
def submit_request(*, request_id: int, actor):
    item = LeaveRequest.objects.select_for_update().filter(
        pk=request_id, user_id=actor.user_id
    ).first()
    if item is None:
        raise WorkflowError("Leave request not found.")
    if item.status != "draft":
        raise WorkflowError("Only draft requests can be submitted.")
    item.status = "submitted"
    item.submitted_at = timezone.now()
    item.save(update_fields=["status", "submitted_at", "updated_at"])
    return item


@transaction.atomic
def withdraw_request(*, request_id: int, actor):
    item = LeaveRequest.objects.select_for_update().filter(
        pk=request_id, user_id=actor.user_id
    ).first()
    if item is None:
        raise WorkflowError("Leave request not found.")
    if item.status not in {"submitted", "pending"}:
        raise WorkflowError("Only requests awaiting final approval can be withdrawn.")
    item.status = "withdrawn"
    item.save(update_fields=["status", "updated_at"])
    return item


@transaction.atomic
def decide_request(*, request_id: int, actor, decision: str, reason: str = ""):
    item = LeaveRequest.objects.select_for_update().filter(pk=request_id).first()
    if item is None:
        raise WorkflowError("Leave request not found.")
    if item.user_id == actor.user_id:
        raise WorkflowError("You cannot approve or reject your own request.")
    if item.status not in {"submitted", "pending"}:
        raise WorkflowError("This request is not awaiting a decision.")
    if decision not in {"approved", "rejected"}:
        raise WorkflowError("Decision must be approved or rejected.")
    if decision == "rejected" and not reason.strip():
        raise WorkflowError("A reason is required when rejecting a request.")

    item.status = decision
    item.final_approver_user_id = actor.user_id
    item.decision_at = timezone.now()
    item.decision_reason = reason.strip()
    item.save(update_fields=[
        "status", "final_approver_user_id", "decision_at",
        "decision_reason", "updated_at",
    ])
    return item
