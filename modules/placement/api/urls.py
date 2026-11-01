from django.urls import path

from modules.placement.api import academics as a
from modules.placement.api import audit as au
from modules.placement.api import clearance as cl
from modules.placement.api import conduct as c
from modules.placement.api import documents as d
from modules.placement.api import exports as e
from modules.placement.api import registration as reg
from modules.placement.api import views as v

urlpatterns = [
    # postings
    path("postings", v.PostingListView.as_view(), name="placement-postings"),
    path("postings/<int:pk>", v.PostingDetailView.as_view(),
         name="placement-posting"),
    path("postings/<int:pk>/publish", v.PostingPublishView.as_view(),
         name="placement-posting-publish"),
    path("postings/<int:pk>/eligibility", v.PostingEligibilityView.as_view(),
         name="placement-posting-eligibility"),

    # applications
    path("applications", v.ApplicationListView.as_view(),
         name="placement-applications"),
    path("applications/apply", v.ApplyView.as_view(), name="placement-apply"),
    path("applications/<int:pk>/transition", v.ApplicationTransitionView.as_view(),
         name="placement-application-transition"),
    path("applications/<int:pk>/history", au.ApplicationHistoryView.as_view(),
         name="placement-application-history"),
    path("applications/bulk-transition",
         v.ApplicationBulkTransitionView.as_view(),
         name="placement-application-bulk-transition"),

    # documents
    path("documents", d.MyDocumentsView.as_view(), name="placement-documents"),
    path("documents/<int:pk>", d.MyDocumentDetailView.as_view(),
         name="placement-document"),
    path("documents/<int:pk>/download", d.DocumentDownloadView.as_view(),
         name="placement-document-download"),

    # profile
    path("profile/resume", v.MyResumeView.as_view(), name="placement-my-resume"),
    path("profiles/<int:user_id>", v.ProfileDetailView.as_view(),
         name="placement-profile"),

    # companies
    path("companies", v.CompanyListView.as_view(), name="placement-companies"),
    path("companies/<int:pk>/<str:action>", v.CompanyApprovalView.as_view(),
         name="placement-company-approval"),

    # interviews
    path("interviews/rounds", v.InterviewRoundListView.as_view(),
         name="placement-rounds"),
    path("interviews/rounds/<int:pk>/candidates", v.RoundCandidatesView.as_view(),
         name="placement-round-candidates"),
    path("interviews/rounds/<int:pk>/outcome", v.RoundOutcomeView.as_view(),
         name="placement-round-outcome"),

    # offers
    path("offers", v.OfferListView.as_view(), name="placement-offers"),
    path("offers/issue", v.OfferIssueView.as_view(), name="placement-offer-issue"),
    path("offers/<int:pk>/respond", v.OfferRespondView.as_view(),
         name="placement-offer-respond"),

    # announcements
    path("announcements", v.AnnouncementListView.as_view(),
         name="placement-announcements"),
    path("announcements/<int:pk>/withdraw", v.AnnouncementWithdrawView.as_view(),
         name="placement-announcement-withdraw"),

    # CPI directory — the whole cohort's declared standing, staff only
    path("students/cpi", a.AcademicDirectoryView.as_view(),
         name="placement-cpi-directory"),
    path("students/cpi/filters", a.AcademicFiltersView.as_view(),
         name="placement-cpi-filters"),

    # registration (rules 1, 20, 21)
    path("registrations", reg.MyRegistrationsView.as_view(),
         name="placement-registrations"),
    path("registrations/terms", reg.MyRegistrationTermsView.as_view(),
         name="placement-registration-terms"),
    path("registrations/opt-out", reg.MyOptOutView.as_view(),
         name="placement-registration-opt-out"),
    path("registrations/approve-late", reg.LateRegistrationView.as_view(),
         name="placement-registration-late"),
    path("registrations/re-register", reg.ReRegistrationView.as_view(),
         name="placement-reregistration"),

    # post-offer obligations (rules 22, 24)
    path("records", cl.MyRecordsView.as_view(), name="placement-my-records"),
    path("records/clearance", cl.MyClearanceView.as_view(),
         name="placement-my-clearance"),
    path("records/<int:pk>/offer-letter", cl.SubmitOfferLetterView.as_view(),
         name="placement-submit-offer-letter"),
    path("records/<int:pk>/not-joining", cl.NotJoiningView.as_view(),
         name="placement-not-joining"),
    path("records/outstanding", cl.OutstandingLettersView.as_view(),
         name="placement-outstanding-letters"),
    path("records/off-campus", cl.OffCampusRecordView.as_view(),
         name="placement-off-campus-record"),
    path("records/<int:pk>/manage", cl.PlacementRecordManageView.as_view(),
         name="placement-record-manage"),

    # conduct and sanctions (rules 18, 19, 21)
    path("conduct/incidents", c.IncidentListView.as_view(),
         name="placement-incidents"),
    path("conduct/incidents/<int:pk>/waive", c.IncidentWaiveView.as_view(),
         name="placement-incident-waive"),
    path("conduct/sanctions", c.SanctionView.as_view(),
         name="placement-sanction"),
    path("conduct/sanctions/lift", c.SanctionLiftView.as_view(),
         name="placement-sanction-lift"),

    path("conduct/mine", au.MyConductRecordView.as_view(),
         name="placement-my-conduct"),

    # exports — bulk personal data, staff only and throttled
    path("exports/applications.csv", e.ApplicationExportView.as_view(),
         name="placement-export-applications"),
    path("exports/placements.csv", e.PlacementRecordExportView.as_view(),
         name="placement-export-placements"),

    # seasons and statistics
    path("seasons", v.SeasonListView.as_view(), name="placement-seasons"),
    path("stats", v.StatsView.as_view(), name="placement-stats"),

    # recruiter portal
    path("recruiters/invite", v.RecruiterInviteView.as_view(),
         name="placement-recruiter-invite"),
    path("recruiters/accept", v.RecruiterAcceptView.as_view(),
         name="placement-recruiter-accept"),
    path("recruiters/login", v.RecruiterLoginView.as_view(),
         name="placement-recruiter-login"),
    path("recruiters/logout", v.RecruiterLogoutView.as_view(),
         name="placement-recruiter-logout"),
    path("recruiters/me", v.RecruiterMeView.as_view(),
         name="placement-recruiter-me"),
]
