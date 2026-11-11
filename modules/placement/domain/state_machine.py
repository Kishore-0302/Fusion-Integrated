"""The application state machine (PC-WF-001, PC-WF-004..007).

A declarative table of legal moves, so an illegal transition is impossible to
express rather than merely rejected, and "who may do this?" has exactly one
answer per edge. Pure Python, so the rules test in milliseconds with no DB.
"""
from __future__ import annotations

from dataclasses import dataclass, field

DRAFT = "draft"
SUBMITTED = "submitted"
UNDER_REVIEW = "under_review"
SHORTLISTED = "shortlisted"
INTERVIEW_SCHEDULED = "interview_scheduled"
SELECTED = "selected"
REJECTED = "rejected"
WITHDRAWN = "withdrawn"
AUTO_WITHDRAWN = "auto_withdrawn"
OFFER_ISSUED = "offer_issued"
OFFER_ACCEPTED = "offer_accepted"
OFFER_DECLINED = "offer_declined"
OFFER_EXPIRED = "offer_expired"

TERMINAL = frozenset({REJECTED, WITHDRAWN, AUTO_WITHDRAWN, OFFER_ACCEPTED,
                      OFFER_DECLINED, OFFER_EXPIRED})

#: Still in the running, so the auto-withdraw sweep knows what to close.
IN_FLIGHT = frozenset({DRAFT, SUBMITTED, UNDER_REVIEW, SHORTLISTED,
                       INTERVIEW_SCHEDULED, SELECTED, OFFER_ISSUED})

# Explicit per transition rather than inferred, because a recruiter is an outsider.
STUDENT = "student"
STAFF = "staff"           # TPO / placement chairman, via IAM permissions
RECRUITER = "recruiter"   # a company's own account, scoped to its postings
SYSTEM = "system"         # scheduled sweeps: expiry, auto-withdraw


class InvalidTransition(Exception):
    def __init__(self, frm: str, to: str):
        super().__init__(f"Cannot move an application from {frm!r} to {to!r}.")
        self.frm, self.to = frm, to


class ActorNotAllowed(Exception):
    def __init__(self, actor_kind: str, frm: str, to: str):
        super().__init__(
            f"A {actor_kind} may not move an application from {frm!r} to {to!r}.")
        self.actor_kind, self.frm, self.to = actor_kind, frm, to


class GuardFailed(Exception):
    def __init__(self, guard: str, message: str = ""):
        super().__init__(message or f"Guard {guard!r} failed.")
        self.guard = guard


@dataclass(frozen=True)
class Transition:
    frm: str
    to: str
    permission: str
    actors: frozenset[str]
    guards: tuple[str, ...] = field(default_factory=tuple)


def _review(frm: str, to: str, *guards: str) -> Transition:
    """A review decision by the TPO (PC-BR-010) or the owning company
    (PC-BR-009). Which applications each can see is the selectors' business."""
    return Transition(frm, to, "placement_cell.application.review",
                      frozenset({STAFF, RECRUITER}), guards)


TRANSITIONS: tuple[Transition, ...] = (
    # -- the student's own moves ------------------------------------------
    Transition(DRAFT, SUBMITTED, "placement_cell.application.create",
               frozenset({STUDENT}),
               ("window_open", "profile_complete", "is_eligible", "may_apply")),

    # -- review and shortlisting (PC-WF-005) ------------------------------
    _review(SUBMITTED, UNDER_REVIEW),
    _review(SUBMITTED, REJECTED, "has_reason"),
    _review(UNDER_REVIEW, SHORTLISTED),
    _review(UNDER_REVIEW, REJECTED, "has_reason"),
    _review(SHORTLISTED, REJECTED, "has_reason"),

    # -- interviews (PC-WF-006) -------------------------------------------
    Transition(SHORTLISTED, INTERVIEW_SCHEDULED,
               "placement_cell.interview.schedule",
               frozenset({STAFF, RECRUITER}), ("has_scheduled_round",)),
    _review(INTERVIEW_SCHEDULED, SELECTED),
    _review(INTERVIEW_SCHEDULED, REJECTED, "has_reason"),
    _review(INTERVIEW_SCHEDULED, SHORTLISTED),        # round cancelled, back a step

    # -- offers (PC-WF-007) -----------------------------------------------
    Transition(SELECTED, OFFER_ISSUED, "placement_cell.offer.issue",
               frozenset({STAFF, RECRUITER}), ("company_authorized",)),
    Transition(SHORTLISTED, OFFER_ISSUED, "placement_cell.offer.issue",
               frozenset({STAFF, RECRUITER}), ("company_authorized",)),

    # The student answers. `offer_window_open` is PC-BR-013.
    Transition(OFFER_ISSUED, OFFER_ACCEPTED, "placement_cell.offer.respond",
               frozenset({STUDENT}), ("offer_window_open", "policy_allows_accept")),
    Transition(OFFER_ISSUED, OFFER_DECLINED, "placement_cell.offer.respond",
               frozenset({STUDENT}), ("offer_window_open",)),

    # System only, so nobody can quietly time a student out by hand.
    Transition(OFFER_ISSUED, OFFER_EXPIRED, "placement_cell.offer.expire",
               frozenset({SYSTEM}), ("offer_window_closed",)),

    # Staff only — a company revoking an offer goes through the TPO (PC-BR-029).
    Transition(OFFER_ISSUED, REJECTED, "placement_cell.offer.revoke",
               frozenset({STAFF}), ("has_reason",)),

    # -- withdrawal: a student may pull out of anything not already ended ---
    *(Transition(s, WITHDRAWN, "placement_cell.application.delete",
                 frozenset({STUDENT}))
      for s in (DRAFT, SUBMITTED, UNDER_REVIEW, SHORTLISTED,
                INTERVIEW_SCHEDULED, SELECTED, OFFER_ISSUED)),

    # Placed elsewhere: the sweep closes the rest, per pool_after_offer.
    *(Transition(s, AUTO_WITHDRAWN, "placement_cell.application.auto_withdraw",
                 frozenset({SYSTEM}))
      for s in (DRAFT, SUBMITTED, UNDER_REVIEW, SHORTLISTED,
                INTERVIEW_SCHEDULED, SELECTED, OFFER_ISSUED)),
)

_INDEX = {(t.frm, t.to): t for t in TRANSITIONS}


def resolve(frm: str, to: str, actor_kind: str | None = None) -> Transition:
    """The single lookup every write goes through. `actor_kind` is optional
    only so the table can be introspected; every service call supplies it."""
    t = _INDEX.get((frm, to))
    if t is None:
        raise InvalidTransition(frm, to)
    if actor_kind is not None and actor_kind not in t.actors:
        raise ActorNotAllowed(actor_kind, frm, to)
    return t


def is_legal(frm: str, to: str) -> bool:
    return (frm, to) in _INDEX


def allowed_targets(frm: str, actor_kind: str | None = None) -> list[str]:
    return sorted(t.to for t in TRANSITIONS
                  if t.frm == frm
                  and (actor_kind is None or actor_kind in t.actors))


def transition_application_state(current_state: str, action: str, actor_role: str) -> str:
    """Validate and compute state transitions for external callers (PR 445 / PBI 17)."""
    try:
        transition = resolve(current_state, action, actor_role)
    except (InvalidTransition, ActorNotAllowed) as exc:
        msg = f"Invalid transition from {current_state} to {action} for {actor_role}"
        raise ValueError(msg) from exc
    else:
        return transition.to


