"""HTTP layer: parse, scope, delegate, serialise.

Every view takes its queryset from `selectors.scoping`, so authorisation is
never re-derived per endpoint. Anything out of scope is simply absent, which
is why detail views 404 rather than 403.
"""
from __future__ import annotations

from django.conf import settings
from django.utils import timezone
from drf_spectacular.utils import extend_schema
from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.views import APIView

from core.api import csrf
from core.api.exceptions import BadRequestError, ConflictError, NotFoundError
from fusion_auth.client import IamUnavailable
from fusion_auth.permissions import HasModuleGrant, HasPermission
from modules.directory import contracts as directory
from modules.placement.api import serializers as s
from modules.placement.api.permissions import ScopedCollection
from modules.placement.authentication import (
    COOKIE_NAME as RECRUITER_COOKIE,
)
from modules.placement.authentication import (
    COOKIE_PATH as RECRUITER_COOKIE_PATH,
)
from modules.placement.authentication import (
    RecruiterAuthentication,
)
from modules.placement.models import (
    PlacementPolicy,
    RecruiterAccount,
)
from modules.placement.selectors import scoping
from modules.placement.services import announcements as announcement_service
from modules.placement.services import applications as application_service
from modules.placement.services import candidates
from modules.placement.services import companies as company_service
from modules.placement.services import interviews as interview_service
from modules.placement.services import offers as offer_service
from modules.placement.services import postings as posting_service
from modules.placement.services import recruiters as recruiter_service
from modules.placement.services import stats as stats_service

MODULE = HasModuleGrant("placement_cell")

P_VIEW_POSTINGS = "placement_cell.job_posting.view"
P_MANAGE_POSTINGS = "placement_cell.job_posting.manage"
P_VIEW_APPS = "placement_cell.application.view"
P_VIEW_SELF = "placement_cell.application.view_self"
P_MANAGE_COMPANIES = "placement_cell.company.manage"
P_VIEW_REPORTS = "placement_cell.report.view"


def _actor(request):
    return getattr(request, "principal", None)


def _int_param(params, name):
    """A non-integer filter is a 400, not a ValueError deep in the ORM."""
    raw = params.get(name)
    if raw in (None, ""):
        return None
    try:
        return int(raw)
    except (TypeError, ValueError) as exc:
        raise BadRequestError(f"{name} must be a number.",
                              code="invalid_filter") from exc


def _client_ip(request):
    """The hop our proxy added, not the first one the client claimed."""
    from rest_framework.settings import api_settings

    forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
    hops = api_settings.NUM_PROXIES or 0
    if forwarded and hops:
        addrs = [a.strip() for a in forwarded.split(",") if a.strip()]
        if addrs:
            return addrs[-min(hops, len(addrs))]
    return request.META.get("REMOTE_ADDR")


class _Scoped(generics.GenericAPIView):
    """Recruiters authenticate on a separate scheme; both pools land on
    `request.principal`."""

    authentication_classes = [RecruiterAuthentication,
                              *generics.GenericAPIView.authentication_classes]

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        ctx["actor"] = _actor(self.request)
        return ctx


# -- Postings ------------------------------------------------------------------
class PostingListView(_Scoped, generics.ListCreateAPIView):
    serializer_class = s.JobPostingSerializer
    permission_classes = [MODULE]

    def get_queryset(self):
        qs = scoping.postings_for(_actor(self.request))
        year = self.request.query_params.get("placement_year")
        kind = self.request.query_params.get("kind")
        if year:
            qs = qs.filter(placement_year=year)
        if kind:
            qs = qs.filter(kind=kind)
        return qs.order_by("-created_at")

    def create(self, request, *args, **kwargs):
        actor = _actor(request)
        payload = s.JobPostingWriteSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        data = dict(payload.validated_data)

        if getattr(actor, "kind", None) == "recruiter":
            # From the credential, never the body: a one-field escalation.
            data.pop("company_id", None)
            company_id = actor.company_id
        else:
            company_id = data.pop("company_id", None)
            if company_id is None:
                raise ConflictError("company_id is required.",
                                    code="company_required")

        posting = posting_service.create(
            company_id=company_id, actor=actor,
            placement_year=data.pop("placement_year"), **data)
        return Response(s.JobPostingSerializer(posting).data,
                        status=status.HTTP_201_CREATED)


class PostingDetailView(_Scoped, generics.RetrieveUpdateAPIView):
    serializer_class = s.JobPostingSerializer
    permission_classes = [MODULE]

    def get_queryset(self):
        return scoping.postings_for(_actor(self.request))

    def update(self, request, *args, **kwargs):
        actor = _actor(request)
        payload = s.JobPostingWriteSerializer(data=request.data, partial=True)
        payload.is_valid(raise_exception=True)
        data = dict(payload.validated_data)
        data.pop("company_id", None)          # never reassignable
        data.pop("placement_year", None)      # never reassignable
        posting = posting_service.update(
            posting_id=kwargs["pk"], actor=actor, scope=self.get_queryset(),
            **data)
        return Response(s.JobPostingSerializer(posting).data)


@extend_schema(request=None, responses=s.JobPostingSerializer)
class PostingSubmitView(_Scoped, APIView):
    """Company recruiter submits draft opportunity for TPO review (PC-UC-015)."""
    permission_classes = [MODULE]

    def post(self, request, pk):
        posting = posting_service.submit(
            posting_id=pk, actor=_actor(request),
            scope=scoping.postings_for(_actor(request)))
        return Response(s.JobPostingSerializer(posting).data)


@extend_schema(request=None, responses=s.JobPostingSerializer)
class PostingPublishView(_Scoped, APIView):
    permission_classes = [MODULE]

    def post(self, request, pk):
        posting = posting_service.publish(
            posting_id=pk, actor=_actor(request),
            scope=scoping.postings_for(_actor(request)))
        return Response(s.JobPostingSerializer(posting).data)


@extend_schema(responses=s.EligibilityVerdictSerializer)
class PostingEligibilityView(_Scoped, APIView):
    """PC-UC-003's precondition, made visible to the student."""

    permission_classes = [MODULE, HasPermission(P_VIEW_POSTINGS, P_VIEW_SELF)]

    def get(self, request, pk):
        actor = _actor(request)
        posting = scoping.postings_for(actor).filter(pk=pk).first()
        if posting is None:
            raise NotFoundError("No such posting.")
        policy = PlacementPolicy.objects.filter(
            season=posting.placement_year).first()
        if policy is None:
            raise ConflictError("No placement policy for this season.",
                                code="policy_missing")
        try:
            verdict = application_service.evaluate_for(
                posting=posting, user_id=actor.user_id, policy=policy)
        except IamUnavailable as exc:
            # A 503 is truthful; "ineligible" would be a lie acted on.
            return Response(
                {"error": {"code": "identity_service_unavailable",
                           "message": f"Academic records are unavailable: {exc}",
                           "details": [], "request_id": ""}},
                status=status.HTTP_503_SERVICE_UNAVAILABLE)
        return Response(verdict)


# -- Applications --------------------------------------------------------------
class ApplicationListView(_Scoped, generics.ListAPIView):
    # A recruiter is authorised by the company-scoped queryset, not by a code.
    permission_classes = [MODULE, ScopedCollection(P_VIEW_APPS, P_VIEW_SELF)]

    def get_serializer_class(self):
        if getattr(_actor(self.request), "kind", None) == "recruiter":
            return s.ApplicantSerializer
        return s.ApplicationSerializer

    serializer_class = s.ApplicationSerializer     # the documented default

    def get_queryset(self):
        qs = scoping.applications_for(_actor(self.request))
        posting_id = _int_param(self.request.query_params, "posting")
        state = self.request.query_params.get("status")
        if posting_id:
            qs = qs.filter(posting_id=posting_id)
        if state:
            qs = qs.filter(status=state)
        return qs.order_by("-created_at")

    def list(self, request, *args, **kwargs):
        actor = _actor(request)
        queryset = self.get_queryset()
        page = self.paginate_queryset(queryset)
        rows = page if page is not None else list(queryset)

        # One batched directory call per page, and none for a student's own list.
        context = {"actor": actor, "view": self, "request": request}
        if scoping.is_staff(actor) or getattr(actor, "kind", None) == "recruiter":
            context["people"] = directory.get_users([a.user_id for a in rows])

        data = self.get_serializer_class()(rows, many=True, context=context).data
        return (self.get_paginated_response(data) if page is not None
                else Response(data))


@extend_schema(request=s.BulkTransitionSerializer,
               responses=s.BulkResultSerializer)
class ApplicationBulkTransitionView(_Scoped, APIView):
    """Move several applications at once (PC-UC-008).

    Every item goes through the same service as a single transition, so the
    scope, permission, state machine and guards are identical. Partial success
    is reported rather than hidden.
    """

    permission_classes = [MODULE]
    throttle_scope = "apply"

    def post(self, request):
        payload = s.BulkTransitionSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        actor = _actor(request)
        outcomes = application_service.bulk_transition(
            actor=actor, scope=scoping.applications_for(actor),
            **payload.validated_data)
        moved = sum(1 for o in outcomes if o.moved)
        return Response({
            "moved": moved,
            "refused": len(outcomes) - moved,
            "results": [
                {"application_id": o.application_id, "moved": o.moved,
                 "error": o.error, "code": o.code} for o in outcomes
            ],
        })


@extend_schema(request=s.TransitionSerializer, responses=s.ApplicationSerializer)
class ApplicationTransitionView(_Scoped, APIView):
    permission_classes = [MODULE]

    def post(self, request, pk):
        payload = s.TransitionSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        actor = _actor(request)
        app = application_service.transition(
            application_id=pk, to_status=payload.validated_data["to_status"],
            actor=actor, reason=payload.validated_data["reason"],
            scope=scoping.applications_for(actor))
        return Response(s.ApplicationSerializer(
            app, context={"actor": actor}).data)


@extend_schema(request=s.ApplySerializer, responses=s.ApplicationSerializer)
class ApplyView(_Scoped, APIView):
    permission_classes = [MODULE, HasPermission("placement_cell.application.create")]
    throttle_scope = "apply"

    def post(self, request):
        payload = s.ApplySerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        actor = _actor(request)
        try:
            app = application_service.apply_to(actor=actor,
                                               **payload.validated_data)
        except IamUnavailable as exc:
            return Response(
                {"error": {"code": "identity_service_unavailable",
                           "message": f"Academic records are unavailable: {exc}",
                           "details": [], "request_id": ""}},
                status=status.HTTP_503_SERVICE_UNAVAILABLE)
        return Response(s.ApplicationSerializer(app, context={"actor": actor}).data,
                        status=status.HTTP_201_CREATED)


# -- Profile -------------------------------------------------------------------
@extend_schema(responses=s.CandidateSerializer)
class MyResumeView(_Scoped, APIView):
    """The student's own candidate record, including the resume they maintain
    on the ERP portal."""

    permission_classes = [MODULE, HasPermission(P_VIEW_SELF)]

    def get(self, request):
        actor = _actor(request)
        return Response(_candidate(actor.user_id))


@extend_schema(responses=s.CandidateSerializer)
class ProfileDetailView(_Scoped, APIView):
    """A recruiter or the TPO reading a candidate.

    A recruiter reaches only their own live applicants — anyone else is a 404,
    not a 403, because a 403 confirms the person exists.
    """

    permission_classes = [MODULE]

    def get(self, request, user_id: int):
        actor = _actor(request)
        if not scoping.may_read_candidate(actor, user_id):
            raise NotFoundError("No such candidate.")
        return Response(_candidate(user_id))


def _candidate(user_id: int) -> dict:
    """Assembled from the directory, with the CPI when the IAM answers."""
    standing = None
    try:
        from modules.placement.services import facts
        standing = (facts.academic_facts([user_id])
                    .get(user_id, {}).get("_standing"))
    except IamUnavailable:
        standing = None              # the record still renders, minus the CPI
    return candidates.candidate_record(user_id=user_id, standing=standing)


# -- Companies -----------------------------------------------------------------
class CompanyListView(_Scoped, generics.ListCreateAPIView):
    serializer_class = s.CompanySerializer
    permission_classes = [MODULE]

    def get_queryset(self):
        return scoping.companies_for(_actor(self.request)).order_by("name")

    def create(self, request, *args, **kwargs):
        payload = s.CompanyRegisterSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        d = payload.validated_data
        company = company_service.register(
            name=d["name"], sector=d.get("sector", ""),
            website=d.get("website", ""), hq_city=d.get("hq_city", ""),
            contact={"name": d.get("contact_name", ""),
                     "email": d.get("contact_email", ""),
                     "phone": d.get("contact_phone", "")}
            if d.get("contact_email") else None,
            actor=_actor(request),
            registered_by_user_id=getattr(_actor(request), "user_id", None))
        return Response(s.CompanySerializer(company).data,
                        status=status.HTTP_201_CREATED)


class CompanyApprovalView(_Scoped, APIView):
    permission_classes = [MODULE, HasPermission(P_MANAGE_COMPANIES)]

    @extend_schema(
        # Distinct from the company-create POST, which collides on operationId.
        operation_id="placement_company_decide",
        request=s.ApprovalSerializer, responses=s.CompanySerializer)
    def post(self, request, pk, action):
        payload = s.ApprovalSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        note = payload.validated_data["note"]
        actor = _actor(request)
        if action == "approve":
            company = company_service.approve(company_id=pk, actor=actor,
                                              note=note)
        elif action == "reject":
            company = company_service.reject(company_id=pk, actor=actor,
                                             note=note)
        elif action == "blacklist":
            company = company_service.blacklist(company_id=pk, actor=actor,
                                                note=note)
        else:
            raise NotFoundError("Unknown action.")
        return Response(s.CompanySerializer(company).data)


# -- Interviews ----------------------------------------------------------------
class InterviewRoundListView(_Scoped, generics.ListCreateAPIView):
    serializer_class = s.InterviewRoundSerializer
    permission_classes = [MODULE]

    def get_queryset(self):
        qs = scoping.interview_rounds_for(_actor(self.request))
        posting_id = _int_param(self.request.query_params, "posting")
        if posting_id:
            qs = qs.filter(posting_id=posting_id)
        return qs.order_by("posting_id", "seq")

    def create(self, request, *args, **kwargs):
        payload = s.InterviewRoundWriteSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        actor = _actor(request)
        round_ = interview_service.schedule_round(
            actor=actor, scope=scoping.postings_for(actor),
            **payload.validated_data)
        return Response(s.InterviewRoundSerializer(round_).data,
                        status=status.HTTP_201_CREATED)


@extend_schema(request=s.AddCandidatesSerializer,
               responses=s.ScheduledCountSerializer)
class RoundCandidatesView(_Scoped, APIView):
    permission_classes = [MODULE]

    def post(self, request, pk):
        payload = s.AddCandidatesSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        actor = _actor(request)
        n = interview_service.add_candidates(
            round_id=pk, application_ids=payload.validated_data["application_ids"],
            actor=actor, scope=scoping.applications_for(actor))
        return Response({"scheduled": n}, status=status.HTTP_201_CREATED)


@extend_schema(request=s.RoundOutcomeSerializer,
               responses=s.RoundParticipationSerializer)
class RoundOutcomeView(_Scoped, APIView):
    permission_classes = [MODULE]

    def post(self, request, pk):
        payload = s.RoundOutcomeSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        actor = _actor(request)
        participation = interview_service.record_outcome(
            round_id=pk, actor=actor, scope=scoping.applications_for(actor),
            **payload.validated_data)
        return Response(s.RoundParticipationSerializer(participation).data)


# -- Offers --------------------------------------------------------------------
class OfferListView(_Scoped, generics.ListAPIView):
    serializer_class = s.OfferSerializer
    permission_classes = [MODULE]

    def get_queryset(self):
        return scoping.offers_for(_actor(self.request)).order_by("-created_at")


@extend_schema(request=s.OfferIssueSerializer, responses=s.OfferSerializer)
class OfferIssueView(_Scoped, APIView):
    permission_classes = [MODULE]

    def post(self, request):
        payload = s.OfferIssueSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        actor = _actor(request)
        offer = offer_service.issue(actor=actor,
                                    scope=scoping.applications_for(actor),
                                    **payload.validated_data)
        return Response(s.OfferSerializer(offer).data,
                        status=status.HTTP_201_CREATED)


@extend_schema(request=s.OfferRespondSerializer, responses=s.OfferSerializer)
class OfferRespondView(_Scoped, APIView):
    permission_classes = [MODULE, HasPermission("placement_cell.offer.respond")]

    def post(self, request, pk):
        payload = s.OfferRespondSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        offer = offer_service.respond(
            offer_id=pk, accept=payload.validated_data["accept"],
            actor=_actor(request))
        return Response(s.OfferSerializer(offer).data)


# -- Announcements -------------------------------------------------------------
class AnnouncementListView(_Scoped, generics.ListCreateAPIView):
    serializer_class = s.AnnouncementSerializer
    permission_classes = [MODULE]

    def get_queryset(self):
        return scoping.announcements_for(_actor(self.request)).order_by(
            "-published_at", "-created_at")

    def create(self, request, *args, **kwargs):
        payload = s.AnnouncementWriteSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        announcement = announcement_service.publish(actor=_actor(request),
                                                    **payload.validated_data)
        return Response(s.AnnouncementSerializer(announcement).data,
                        status=status.HTTP_201_CREATED)


@extend_schema(request=s.WithdrawSerializer, responses=s.AnnouncementSerializer)
class AnnouncementWithdrawView(_Scoped, APIView):
    permission_classes = [MODULE,
                          HasPermission("placement_cell.announcement.publish")]

    def post(self, request, pk):
        payload = s.WithdrawSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        announcement = announcement_service.withdraw(
            announcement_id=pk, actor=_actor(request),
            reason=payload.validated_data["reason"])
        return Response(s.AnnouncementSerializer(announcement).data)


class SeasonListView(_Scoped, generics.ListAPIView):
    """The seasons a posting may belong to.

    Free text here was a trap: a typo produced a posting whose season has no
    PlacementPolicy, so it looked fine until a student applied and hit an
    opaque `policy_missing`. A closed list moves that failure to authoring time.
    """

    serializer_class = s.SeasonSerializer
    permission_classes = [MODULE]
    pagination_class = None          # a handful of rows; never paginated

    def get_queryset(self):
        return PlacementPolicy.objects.order_by("-is_active", "-season")


# -- Statistics ----------------------------------------------------------------
@extend_schema(responses=s.StaffStatsSerializer,
               description="Staff receive StaffStats; everyone else receives "
                           "the anonymised StudentStats shape (PC-BR-016).")
class StatsView(_Scoped, APIView):
    """Anonymised aggregates for a student (PC-BR-016), operational figures
    for staff (PC-UC-011/012)."""

    permission_classes = [MODULE]

    def get(self, request):
        actor = _actor(request)
        season = request.query_params.get("season") or _current_season()
        if getattr(actor, "kind", None) != "recruiter" and \
                actor.has_permission(P_VIEW_REPORTS):
            return Response(stats_service.staff_view(season=season))
        return Response(stats_service.student_view(season=season))


def _current_season() -> str:
    policy = PlacementPolicy.objects.filter(is_active=True).order_by(
        "-season").first()
    return policy.season if policy else str(timezone.now().year)


# -- Recruiter portal — the only unauthenticated surface in this module --------
@extend_schema(request=s.RecruiterInviteSerializer,
               responses=s.RecruiterInviteResultSerializer)
class RecruiterInviteView(_Scoped, APIView):
    permission_classes = [MODULE, HasPermission(P_MANAGE_COMPANIES)]

    def post(self, request):
        payload = s.RecruiterInviteSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        # Returned once, to the TPO who created it. Not stored.
        account, raw = recruiter_service.invite(
            invited_by_user_id=_actor(request).user_id, **payload.validated_data)
        return Response({"account_id": account.pk, "email": account.email,
                         "invite_token": raw,
                         "expires_at": account.invite_expires_at},
                        status=status.HTTP_201_CREATED)


@extend_schema(request=s.RecruiterAcceptSerializer,
               responses=s.DetailSerializer)
class RecruiterAcceptView(APIView):
    authentication_classes: list = []
    permission_classes: list = []
    throttle_scope = "recruiter_invite_accept"

    def post(self, request):
        payload = s.RecruiterAcceptSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        recruiter_service.accept_invite(**payload.validated_data)
        return Response({"detail": "Password set. You can now sign in."})


@extend_schema(request=s.RecruiterLoginSerializer,
               responses=s.RecruiterLoginResultSerializer)
class RecruiterLoginView(APIView):
    authentication_classes: list = []
    permission_classes: list = []
    throttle_scope = "recruiter_login"

    def post(self, request):
        payload = s.RecruiterLoginSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        try:
            session = recruiter_service.sign_in(
                ip=_client_ip(request), **payload.validated_data)
        except recruiter_service.Locked as exc:
            msg = ("Too many failed attempts. Contact the placement office."
                   if exc.minutes is None else
                   f"Too many failed attempts. Try again in {exc.minutes} minute(s).")
            return Response({"error": {"code": "locked", "message": msg,
                                       "details": [], "request_id": ""}},
                            status=status.HTTP_429_TOO_MANY_REQUESTS)
        response = Response({
            "expires_at": session.expires_at,
            "company_id": session.account.company_id,
            "csrf_token": csrf.token_for(session.raw_key),
        })
        # httpOnly so an XSS cannot exfiltrate it.
        response.set_cookie(
            RECRUITER_COOKIE, session.raw_key,
            max_age=int((session.expires_at - timezone.now()).total_seconds()),
            httponly=True, samesite="Lax", secure=not settings.DEBUG,
            path=RECRUITER_COOKIE_PATH,
        )
        return response


@extend_schema(request=None, responses=s.DetailSerializer)
class RecruiterLogoutView(_Scoped, APIView):
    permission_classes = [MODULE]

    def post(self, request):
        auth = request.META.get("HTTP_AUTHORIZATION", "")
        key = (auth.split(" ", 1)[1].strip() if auth.startswith("Recruiter ")
               else request.COOKIES.get(RECRUITER_COOKIE, ""))
        if key:
            recruiter_service.sign_out(session_key=key)
        # Already revoked server-side; this clears it from a shared browser.
        response = Response({"detail": "Signed out."})
        response.delete_cookie(RECRUITER_COOKIE, path=RECRUITER_COOKIE_PATH)
        return response


@extend_schema(responses=s.RecruiterMeSerializer)
class RecruiterMeView(_Scoped, APIView):
    """Their company, and nothing about the institute."""

    permission_classes = [MODULE]

    def get(self, request):
        actor = _actor(request)
        if getattr(actor, "kind", None) != "recruiter":
            raise NotFoundError("Not a recruiter session.")
        account = RecruiterAccount.objects.select_related("company").get(
            pk=actor.account_id)
        return Response({
            "csrf_token": csrf.token_for(request.auth or ""),
            "email": account.email, "full_name": account.full_name,
            "company": {"id": account.company_id, "name": account.company.name,
                        "approval_status": account.company.approval_status},
            "modules": list(actor.modules),
        })


# -- Placement Records (PR 445 / PBI 17) ---------------------------------------
class PlacementRecordUpdateView(_Scoped, generics.UpdateAPIView):
    serializer_class = s.PlacementRecordUpdateSerializer
    permission_classes = [
        MODULE,
        HasPermission("placement_cell.record.manage", "placement.manage_records", "tpo_admin"),
    ]

    def get_queryset(self):
        return scoping.placement_records_for(_actor(self.request))

    def update(self, request, *args, **kwargs):
        actor = _actor(request)
        payload = s.PlacementRecordUpdateSerializer(data=request.data, partial=True)
        payload.is_valid(raise_exception=True)
        data = dict(payload.validated_data)

        record = self.get_object()
        old_values = {
            "ctc_lpa": record.ctc_lpa,
            "kind": record.kind,
            "is_active": record.is_active,
            "recorded_by_user_id": record.recorded_by_user_id,
        }

        if "ctc_lpa" in data:
            record.ctc_lpa = data["ctc_lpa"]
        if "kind" in data:
            record.kind = data["kind"]
        if "is_active" in data:
            record.is_active = data["is_active"]
        if "verified_by_user_id" in data:
            record.recorded_by_user_id = data["verified_by_user_id"]
        if "is_accepted" in data and not data["is_accepted"]:
            record.is_active = False

        record.save()

        new_values = {
            "ctc_lpa": record.ctc_lpa,
            "kind": record.kind,
            "is_active": record.is_active,
            "recorded_by_user_id": record.recorded_by_user_id,
        }

        import structlog
        logger = structlog.get_logger("placement.audit")
        logger.info(
            "placement_record.updated",
            actor_id=getattr(actor, "user_id", None),
            record_id=record.pk,
            old=old_values,
            new=new_values,
        )

        return Response(s.PlacementRecordSerializer(record).data)

