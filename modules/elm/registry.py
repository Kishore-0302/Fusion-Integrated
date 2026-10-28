"""Fusion module registry for Employee Leave Management."""

MODULE = {
    "code": "elm",
    "label": "Employee Leave Management",
    "icon": "CalendarBlank",
    "base_path": "/elm",
    "nav_section": "Human Resources",
    "sort_order": 20,
    "status": "active",
}

NAV_ITEMS = [
    {
        "code": "elm.requests",
        "label": "My Leave Requests",
        "icon": "CalendarBlank",
        "to": "/elm",
        "required_permission": "elm.leave_request.view_self",
        "sort_order": 10,
    },
]

PERMISSIONS = [
    ("elm.leave_type.view", "View active leave types"),
    ("elm.leave_request.view_self", "View own leave requests and balances"),
    ("elm.leave_request.create", "Create a leave request"),
    ("elm.leave_request.submit", "Submit a leave request"),
    ("elm.leave_request.withdraw", "Withdraw a pending leave request"),
    ("elm.leave_request.approve", "Approve or reject leave requests"),
    ("elm.leave_request.cancel", "Cancel an approved leave request"),
]

SYSTEM_PERMISSIONS = []
ROLE_GRANTS = {}
