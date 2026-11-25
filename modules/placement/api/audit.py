"""Reading the audit trail (PC-AFR-009, PC-UC-004).

Two records: every application state change, and every conduct incident.

What each caller sees differs, and the difference is deliberate.

  * **Staff** see everything, including who acted and the free-text reason.
  * **A student** sees their own timeline — what happened and when — but not the
    reason and not who acted. The reason field has never been shown to students
    (the notification says only that the status changed), so surfacing it now
    would expose notes written on the understanding they were internal. Naming
    the TPO who rejected someone also invites pressure on that person.
  * **A recruiter** sees the timeline for applications to their own postings,
    with institute actors unnamed for the same reason.

A student DOES see their own conduct record in full, reason included: rule 21
puts a sanction at the Chairperson's discretion and rule 19 allows a waiver, and
nobody can contest what they cannot read.
"""
from __future__ import annotations

from drf_spectacular.utils import extend_schema
from rest_framework.response import Response
from rest_framework.views import APIView

from core.api.exceptions import NotFoundError
from fusion_auth.permissions import HasModuleGrant, HasPermission
from modules.placement.api import serializers as s
from modules.placement.authentication import RecruiterAuthentication
from modules.placement.models import ApplicationTransition, ConductIncident
from modules.placement.selectors import scoping

MODULE = HasModuleGrant("placement_cell")
P_VIEW_SELF = "placement_cell.application.view_self"


def _actor(request):
    return getattr(request, "principal", None)


@extend_schema(responses=s.TransitionHistorySerializer)
class ApplicationHistoryView(APIView):
    """GET /placement/applications/<pk>/history"""

    authentication_classes = [RecruiterAuthentication,
                              *APIView.authentication_classes]
    permission_classes = [MODULE]

    def get(self, request, pk):
        actor = _actor(request)
        # Scoped like every other read, so a foreign history is absent, not forbidden.
        application = scoping.applications_for(actor).filter(pk=pk).first()
        if application is None:
            raise NotFoundError("No such application.")

        rows = (ApplicationTransition.objects
                .filter(application=application).order_by("at"))
        full = scoping.is_staff(actor)
        return Response({
            "application_id": application.pk,
            "redacted": not full,
            "results": [_entry(row, full=full) for row in rows],
        })


def _entry(row: ApplicationTransition, *, full: bool) -> dict:
    entry = {
        "from_status": row.from_status,
        "to_status": row.to_status,
        "at": row.at,
        # The lane — student, staff, recruiter, system — never the person.
        "actor_label": row.actor_label,
    }
    if full:
        entry["reason"] = row.reason
        entry["actor_user_id"] = row.actor_user_id
        entry["actor_recruiter_id"] = row.actor_recruiter_id
    return entry


@extend_schema(responses=s.ConductIncidentSerializer(many=True))
class MyConductRecordView(APIView):
    """A student's own conduct record, in full.

    Rule 19 allows a waiver and rule 21 leaves a sanction to the Chairperson's
    discretion. Both are contestable, and nobody can contest what they cannot
    see — so the note and any waiver reason are shown, unlike an application's
    internal review note.
    """

    permission_classes = [MODULE, HasPermission(P_VIEW_SELF)]

    def get(self, request):
        rows = (ConductIncident.objects
                .filter(user_id=_actor(request).user_id)
                .select_related("posting")
                .order_by("-created_at"))
        return Response({
            "results": s.StudentConductIncidentSerializer(rows, many=True).data})
