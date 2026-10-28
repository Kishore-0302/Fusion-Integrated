from django.urls import path

from modules.elm.api.views import (
    LeaveTypeListView,
    MyLeaveBalanceListView,
    MyLeaveRequestListCreateView,
    LeaveRequestActionView,
)

urlpatterns = [
    path("leave-types", LeaveTypeListView.as_view(), name="elm-leave-types"),
    path("balances", MyLeaveBalanceListView.as_view(), name="elm-my-balances"),
    path("requests", MyLeaveRequestListCreateView.as_view(), name="elm-my-requests"),
    path(
        "requests/<int:pk>/<str:action>",
        LeaveRequestActionView.as_view(),
        name="elm-request-action",
    ),
]
