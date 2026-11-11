"""Routes for the Assignment 7 Placement Cell use cases."""
from django.urls import path

from modules.placement_cell.api import views

urlpatterns = [
    # PC-UC-015: Company submits draft opportunity for TPO review
    path("opportunities/<int:pk>/submit", views.CompanySubmitView.as_view(),
         name="placement-cell-opportunity-submit"),

    # PC-UC-006: TPO publishes pending opportunity with frozen criteria
    path("opportunities/<int:pk>/publish", views.TpoPublishView.as_view(),
         name="placement-cell-opportunity-publish"),

    # PC-UC-003: Student applies to opportunity
    path("opportunities/<int:pk>/apply", views.StudentApplyView.as_view(),
         name="placement-cell-opportunity-apply"),

    # PC-UC-005: Student withdraws application
    path("applications/<int:pk>/withdraw", views.StudentWithdrawView.as_view(),
         name="placement-cell-application-withdraw"),

    # PC-UC-016: Company reviews applicant and records shortlist/rejection
    path("applications/<int:pk>/review", views.CompanyReviewView.as_view(),
         name="placement-cell-application-review"),

    # PC-UC-009: TPO schedules interview round with shortlisted candidates
    path("opportunities/<int:pk>/interviews", views.TpoScheduleView.as_view(),
         name="placement-cell-interview-schedule"),

    # PC-UC-022: Recruiter or TPO extends formal job offer
    path("applications/<int:pk>/offers", views.OfferIssueView.as_view(),
         name="placement-cell-offer-issue"),

    # PC-UC-008: Student accepts or declines extended offer
    path("offers/<int:pk>/respond", views.OfferRespondView.as_view(),
         name="placement-cell-offer-respond"),

    # PC-UC-010: TPO corrects placement record with mandatory reason
    path("records/<int:pk>/manage", views.PlacementRecordManageView.as_view(),
         name="placement-cell-record-manage"),

    # PC-UC-013: TPO publishes recruitment announcement
    path("announcements", views.AnnouncementPublishView.as_view(),
         name="placement-cell-announcement-publish"),

    # PC-UC-024: Student views anonymized statistics
    path("stats", views.StudentStatsView.as_view(),
         name="placement-cell-stats"),
]
