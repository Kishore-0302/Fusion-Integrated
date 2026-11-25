"""What the server tells the shell about this module (ADR-0010).

Nav items carry `required_permission` and the server filters before sending —
the client does zero filtering, so a link a role cannot use never reaches the
browser at all.
"""
MODULE = {
    "code": "placement_cell", "label": "Placement Cell", "icon": "Briefcase",
    "base_path": "/placement", "nav_section": "Placement", "sort_order": 10,
    "status": "active",
}

NAV_ITEMS = [
    # -- student: registration first, because rule 1 gates everything below ---
    {"code": "placement.registration", "label": "Season Registration",
     "icon": "Checks", "to": "/placement/registration",
     "required_permission": "placement_cell.registration.self",
     "sort_order": 5},
    {"code": "placement.postings", "label": "Opportunities",
     "icon": "ClipboardText", "to": "/placement/postings",
     "required_permission": "placement_cell.job_posting.view", "sort_order": 10},
    {"code": "placement.mine", "label": "My Applications",
     "icon": "UserCheck", "to": "/placement/mine",
     "required_permission": "placement_cell.application.view_self",
     "sort_order": 20},
    {"code": "placement.offers", "label": "My Offers",
     "icon": "Signature", "to": "/placement/offers",
     "required_permission": "placement_cell.offer.respond", "sort_order": 30},

    # -- staff (TPO / chairman) -------------------------------------------
    {"code": "placement.registrations", "label": "Registrations",
     "icon": "Checks", "to": "/placement/registration-approvals",
     "required_permission": "placement_cell.registration.manage",
     "sort_order": 55},
    {"code": "placement.applications", "label": "Applications",
     "icon": "Users", "to": "/placement/applications",
     "required_permission": "placement_cell.application.view", "sort_order": 50},
    {"code": "placement.companies", "label": "Companies",
     "icon": "Buildings", "to": "/placement/companies",
     "required_permission": "placement_cell.company.manage", "sort_order": 60},
    {"code": "placement.interviews", "label": "Interviews",
     "icon": "CalendarBlank", "to": "/placement/interviews",
     "required_permission": "placement_cell.interview.schedule",
     "sort_order": 70},
    {"code": "placement.announcements", "label": "Announcements",
     "icon": "Megaphone", "to": "/placement/announcements",
     "required_permission": "placement_cell.announcement.publish",
     "sort_order": 80},
    {"code": "placement.cpi", "label": "Student CPI",
     "icon": "GraduationCap", "to": "/placement/students-cpi",
     "required_permission": "placement_cell.academic_directory.view",
     "sort_order": 85},
    {"code": "placement.reports", "label": "Reports",
     "icon": "ChartBar", "to": "/placement/reports",
     "required_permission": "placement_cell.report.view", "sort_order": 90},
]

#: Every permission this module recognises; ROLE_GRANTS below says who holds each.
PERMISSIONS = [
    ("placement_cell.job_posting.view", "See job postings"),
    ("placement_cell.job_posting.manage", "Create and publish postings"),
    ("placement_cell.application.view", "See all applications"),
    ("placement_cell.application.view_self", "See one's own applications"),
    ("placement_cell.application.create", "Apply to a posting"),
    ("placement_cell.application.review", "Shortlist and reject applications"),
    ("placement_cell.application.delete", "Withdraw an application"),
    ("placement_cell.application.auto_withdraw", "System auto-withdrawal"),
    ("placement_cell.interview.schedule", "Schedule interview rounds"),
    ("placement_cell.offer.issue", "Extend an offer"),
    ("placement_cell.offer.respond", "Accept or decline an offer"),
    ("placement_cell.offer.revoke", "Revoke an issued offer"),
    ("placement_cell.offer.expire", "System offer expiry"),
    ("placement_cell.company.manage", "Register and approve companies"),
    ("placement_cell.announcement.publish", "Publish announcements"),
    ("placement_cell.report.view", "See operational reports"),
    ("placement_cell.registration.debar",
     "Record conduct incidents and impose placement sanctions"),
    ("placement_cell.registration.manage",
     "Approve late registrations and re-registrations"),
    ("placement_cell.registration.self",
     "Register yourself for a placement season"),
    ("placement_cell.record.manage",
     "Record off-campus placements and chase offer letters"),
    ("placement_cell.academic_directory.view",
     "Browse every student's declared CPI"),
]

#: Performed by a service or a scheduled task, so no designation holds them.
SYSTEM_PERMISSIONS = [
    "placement_cell.application.auto_withdraw",
    "placement_cell.offer.expire",
]

_STUDENT = [
    "placement_cell.registration.self",
    "placement_cell.job_posting.view",
    "placement_cell.application.view_self",
    "placement_cell.application.create",
    "placement_cell.application.delete",
    "placement_cell.offer.respond",
]

_COORDINATOR = [
    "placement_cell.job_posting.view",
    "placement_cell.application.view",
    "placement_cell.application.review",
    "placement_cell.report.view",
    "placement_cell.academic_directory.view",
]

_OFFICER = [
    *_COORDINATOR,
    "placement_cell.job_posting.manage",
    "placement_cell.interview.schedule",
    "placement_cell.offer.issue",
    "placement_cell.offer.revoke",
    "placement_cell.company.manage",
    "placement_cell.announcement.publish",
    "placement_cell.registration.manage",
    "placement_cell.registration.debar",
    "placement_cell.record.manage",
]

#: Oversees rather than operates: no shortlisting and no offers.
_CHAIRMAN = [
    "placement_cell.job_posting.view",
    "placement_cell.application.view",
    "placement_cell.report.view",
    "placement_cell.academic_directory.view",
    "placement_cell.announcement.publish",
]

#: Restricted read-only access for mentorship/networking
#: (PC-UC-017, PC-BR-019, PC-BR-020, PC-AFR-058..060).
_ALUMNI = [
    "placement_cell.job_posting.view",
]

#: Keyed by the designation name as it exists in globals_designation.
ROLE_GRANTS = {
    "student": _STUDENT,
    "alumni": _ALUMNI,
    "placement_coordinator": _COORDINATOR,
    "placement_officer": _OFFICER,
    "placement_chairman": _CHAIRMAN,
    "Dean Academic": _CHAIRMAN,
}
