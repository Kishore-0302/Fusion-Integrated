"""The facts an eligibility rule is evaluated against.

Each has one owner: academic facts from the IAM's declared-CPI projection,
identity from its directory, placement state from this module, skills from the
the ERP portal's profile.

Gathered in a fixed number of queries however many students are asked about,
and fail-closed — a student with no declared result has no academic facts, and
the engine denies on a missing fact rather than reading absence as zero.
"""
from __future__ import annotations

import logging
from collections.abc import Sequence
from decimal import Decimal, InvalidOperation

from fusion_auth.client import IamUnavailable, get_client
from modules.directory import contracts as directory
from modules.placement.models import Application, PlacementRegistration

log = logging.getLogger("fusion.placement.facts")


def _dec(v):
    if v is None:
        return None
    try:
        return Decimal(str(v))
    except (InvalidOperation, TypeError, ValueError):
        return None


def academic_facts(user_ids: Sequence[int]) -> dict[int, dict]:
    """Declared CPI and friends from the IAM, batched. Absence is propagated,
    never filled in."""
    ids = sorted({int(i) for i in user_ids if i is not None})
    if not ids:
        return {}
    try:
        rows = get_client().get_academic_standings(ids)
    except IamUnavailable as exc:
        # Surfaced as a 503; guessing would freeze a wrong verdict into a snapshot.
        log.warning("placement.facts.iam_unavailable n=%d err=%s", len(ids), exc)
        raise

    out: dict[int, dict] = {}
    for uid, r in rows.items():
        out[uid] = {
            "cpi": _dec(r.get("cpi")),
            "earned_credits": _dec(r.get("earned_credits")),
            "active_backlogs": r.get("active_backlogs"),
            "semester": r.get("semester"),
            "_standing": {
                "semester": r.get("semester"),
                "semester_type": r.get("semester_type"),
                "declared_seq": r.get("declared_seq"),
                "synced_at": r.get("synced_at"),
                "computed_by": r.get("computed_by"),
            },
        }
    return out


def gather(user_ids: Sequence[int], *, policy) -> dict[int, dict]:
    """All eligibility facts for these students, in a fixed query count."""
    ids = sorted({int(i) for i in user_ids if i is not None})
    if not ids:
        return {}

    academic = academic_facts(ids)
    people = directory.get_users(ids)

    registrations = {r.user_id: r for r in
                     PlacementRegistration.objects.filter(user_id__in=ids,
                                                          policy=policy)}
    accepted = {}
    for uid in (Application.objects
                .filter(user_id__in=ids, status="offer_accepted",
                        posting__placement_year=policy.season)
                .values_list("user_id", flat=True)):
        accepted[uid] = accepted.get(uid, 0) + 1

    facts: dict[int, dict] = {}
    for uid in ids:
        person = people.get(uid)
        reg = registrations.get(uid)

        raw_skills = getattr(person, "skills", None)
        if raw_skills is None and person and hasattr(person, "extra"):
            raw_skills = person.extra.get("skills")
        if raw_skills is None:
            person_skills = []
        elif isinstance(raw_skills, (list, tuple, set)):
            person_skills = list(raw_skills)
        elif isinstance(raw_skills, str):
            person_skills = [s.strip() for s in raw_skills.split(",") if s.strip()]
        else:
            person_skills = []

        f: dict = {
            "programme": getattr(person, "programme", None) or None,
            "discipline": getattr(person, "discipline", None) or None,
            "branch": getattr(person, "discipline", None) or None,
            "batch_year": getattr(person, "batch_year", None),
            "year": getattr(person, "batch_year", None),
            "skills": person_skills,
            "is_placed": accepted.get(uid, 0) > 0,
            "offer_count": accepted.get(uid, 0),
            "is_registered": bool(reg and reg.status == "registered"),
            # Completed on the ERP portal, which owns the profile.
            "profile_complete": bool(getattr(person, "profile_completed", False)),
        }
        # Merged only if declared, so the rule denies with "missing_fact".
        ac = academic.get(uid, {})
        f.update(ac)
        if "cpi" in f and "cgpa" not in f:
            f["cgpa"] = f["cpi"]
        facts[uid] = f
    return facts
