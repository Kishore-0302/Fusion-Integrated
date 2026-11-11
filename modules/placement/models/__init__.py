"""Placement domain tables, split by aggregate."""
from modules.placement.models.announcements import (
    Announcement,
    ConductIncident,
    NotificationOutbox,
    PlacementStatsSnapshot,
)
from modules.placement.models.applications import (
    Application,
    ApplicationTransition,
)
from modules.placement.models.companies import (
    Company,
    CompanyContact,
    RecruiterAccount,
    RecruiterLoginAttempt,
    RecruiterSession,
)
from modules.placement.models.interviews import (
    InterviewRound,
    RoundParticipation,
)
from modules.placement.models.offers import (
    Offer,
    PlacementRecord,
)
from modules.placement.models.policy import (
    PlacementPolicy,
    PolicyCategory,
)
from modules.placement.models.postings import (
    JobPosting,
)
from modules.placement.models.students import (
    DebarmentRecord,
    PlacementRegistration,
    ProfileDocument,
    StudentClearance,
)

__all__ = [
    "Announcement",
    "Application",
    "ApplicationTransition",
    "Company",
    "CompanyContact",
    "ConductIncident",
    "DebarmentRecord",
    "InterviewRound",
    "JobPosting",
    "NotificationOutbox",
    "Offer",
    "PlacementPolicy",
    "PlacementRecord",
    "PlacementRegistration",
    "PlacementStatsSnapshot",
    "PolicyCategory",
    "ProfileDocument",
    "RecruiterAccount",
    "RecruiterLoginAttempt",
    "RecruiterSession",
    "RoundParticipation",
    "StudentClearance",
]
