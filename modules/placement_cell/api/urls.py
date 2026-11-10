from django.urls import path

from modules.placement_cell.api import views

app_name = "placement_cell_assignment7"

urlpatterns = [
    path("opportunities/<int:pk>/submit", views.CompanySubmitView.as_view(),
         name="company-submit"),
    path("opportunities/<int:pk>/publish", views.TpoPublishView.as_view(),
         name="tpo-publish"),
    path("opportunities/<int:pk>/apply", views.StudentApplyView.as_view(),
         name="student-apply"),
    path("applications/<int:pk>/review", views.CompanyReviewView.as_view(),
         name="company-review"),
    path("opportunities/<int:pk>/interviews", views.TpoScheduleView.as_view(),
         name="tpo-schedule-interviews"),
]
