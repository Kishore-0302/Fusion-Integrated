"""Eligibility rules — a tiny JSON AST, evaluated fail-closed.

    {"all": [{"gte": ["cpi", 7.0]}, {"in": ["discipline", ["CSE","ECE"]]}]}

Fail-closed means an unknown field, a missing fact, or any error yields
INELIGIBLE with an explicit reason — never eligible-by-default. Students see
"CPI 6.80 — 7.00 required", not "not eligible".
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any

# PC-BR-004's closed vocabulary: an unknown field denies rather than being ignored.
FIELDS = {
    "cpi", "earned_credits", "active_backlogs", "semester",   # IAM projection
    "programme", "discipline", "batch_year",                  # IAM directory
    "is_placed", "is_registered", "offer_count",              # this module
    "profile_complete",                                       # the ERP portal
}

# List-valued facts, comparable only with the set operators. None today.
LIST_FIELDS: set[str] = set()
LIST_OPS = {"has_all", "has_any", "has_none"}

MAX_DEPTH = 5


@dataclass(frozen=True)
class RuleOutcome:
    field: str
    op: str
    required: Any
    actual: Any
    passed: bool
    reason: str


@dataclass(frozen=True)
class Outcome:
    is_eligible: bool
    outcomes: list[RuleOutcome]
    error: str | None = None


def _num(v):
    try:
        return Decimal(str(v))
    except (InvalidOperation, TypeError, ValueError):
        return None


def _norm_set(v) -> set[str] | None:
    """Case-insensitive, whitespace-trimmed. 'Python' matches 'python '."""
    if isinstance(v, str):
        v = [v]
    if not isinstance(v, (list, tuple, set)):
        return None
    return {str(x).strip().lower() for x in v if str(x).strip()}


def _compare_list(op: str, field: str, expected, actual) -> RuleOutcome:
    have, want = _norm_set(actual), _norm_set(expected)
    if have is None or want is None:
        return RuleOutcome(field, op, expected, actual, False, "type_mismatch")
    if op == "has_all":
        missing = sorted(want - have)
        return RuleOutcome(field, op, sorted(want), sorted(have), not missing,
                           "" if not missing else f"{field}_missing:{','.join(missing)}")
    if op == "has_any":
        ok = bool(want & have)
        return RuleOutcome(field, op, sorted(want), sorted(have), ok,
                           "" if ok else f"{field}_none_of_required")
    overlap = sorted(want & have)          # has_none
    return RuleOutcome(field, op, sorted(want), sorted(have), not overlap,
                       "" if not overlap else f"{field}_disallowed:{','.join(overlap)}")


def _compare(op: str, field: str, expected, actual) -> RuleOutcome:
    # A rule-authoring mistake still denies: guessing is how someone slips through.
    if (field in LIST_FIELDS) != (op in LIST_OPS):
        return RuleOutcome(field, op, expected, actual, False, "operator_not_valid_for_field")
    if op in LIST_OPS:
        return _compare_list(op, field, expected, actual or [])

    if actual is None:
        return RuleOutcome(field, op, expected, None, False, "missing_fact")

    if op in ("eq", "ne"):
        ok = (actual == expected) if op == "eq" else (actual != expected)
        return RuleOutcome(field, op, expected, actual, ok,
                           "" if ok else f"{field}_mismatch")
    if op in ("in", "not_in"):
        if not isinstance(expected, (list, tuple)):
            return RuleOutcome(field, op, expected, actual, False, "bad_rule")
        ok = (actual in expected) if op == "in" else (actual not in expected)
        return RuleOutcome(field, op, expected, actual, ok,
                           "" if ok else f"{field}_not_allowed")

    a, e = _num(actual), _num(expected)
    if a is None or e is None:
        return RuleOutcome(field, op, expected, actual, False, "type_mismatch")
    ok = {"gt": a > e, "gte": a >= e, "lt": a < e, "lte": a <= e}.get(op)
    if ok is None:
        return RuleOutcome(field, op, expected, actual, False, "unknown_operator")
    return RuleOutcome(field, op, expected, actual, ok,
                       "" if ok else f"{field}_out_of_range")


def evaluate(rule: dict | None, facts: dict, _depth: int = 0) -> Outcome:
    if not rule:
        return Outcome(True, [])                      # no rule = no restriction
    if _depth > MAX_DEPTH:
        return Outcome(False, [], "rule_too_complex")

    try:
        if "all" in rule:
            outs, ok = [], True
            for sub in rule["all"]:
                r = evaluate(sub, facts, _depth + 1)
                outs += r.outcomes
                ok = ok and r.is_eligible
                if r.error:
                    return Outcome(False, outs, r.error)
            return Outcome(ok, outs)

        if "any" in rule:
            branches = rule["any"]
            if not branches:
                return Outcome(False, [], "no_alternatives_satisfied")
            outs, ok = [], False
            for sub in branches:
                r = evaluate(sub, facts, _depth + 1)
                outs += r.outcomes
                ok = ok or r.is_eligible
            return Outcome(ok, outs)

        if "not" in rule:
            r = evaluate(rule["not"], facts, _depth + 1)
            return Outcome(not r.is_eligible, r.outcomes, r.error)

        (op, operand), = rule.items()
        field, expected = operand
        if field not in FIELDS:
            return Outcome(False, [RuleOutcome(field, op, expected, None, False,
                                               "unknown_field")], "unknown_field")
        out = _compare(op, field, expected, facts.get(field))
        return Outcome(out.passed, [out])

    except Exception:                                          # noqa: BLE001
        return Outcome(False, [], "evaluation_error")          # malformed = deny


# Every denial carries the actual value and the required one, not just "no".
LABELS = {
    "cpi": "CPI", "earned_credits": "earned credits",
    "active_backlogs": "active backlogs", "semester": "semester",
    "programme": "programme", "discipline": "discipline",
    "batch_year": "batch year", "is_placed": "placement status",
    "is_registered": "season registration", "offer_count": "offers held",
    "profile_complete": "profile completeness",
}

_OP_PHRASE = {
    "gte": "at least", "gt": "more than", "lte": "at most", "lt": "less than",
    "eq": "exactly", "ne": "anything other than",
}


def describe(outcome: RuleOutcome) -> str:
    label = LABELS.get(outcome.field, outcome.field)
    if outcome.passed:
        return f"{label} — met"
    if outcome.reason == "missing_fact":
        if outcome.field in ("cpi", "earned_credits", "active_backlogs", "semester"):
            return ("No declared result yet, so your academic standing cannot be "
                    "checked. Eligibility opens once your result is declared.")
        return f"{label} is not recorded on your profile yet."
    if outcome.op in ("in", "not_in"):
        allowed = ", ".join(str(x) for x in (outcome.required or []))
        return f"{label} is {outcome.actual} — this posting is open to {allowed}."
    phrase = _OP_PHRASE.get(outcome.op, outcome.op)
    return f"{label} is {outcome.actual} — this posting needs {phrase} {outcome.required}."


#: The rule is broken, not the student; never render these as a personal shortfall.
STRUCTURAL_ERRORS = {"unknown_field", "rule_too_complex", "evaluation_error"}


def failure_reasons(outcome: Outcome) -> list[dict]:
    """The per-rule denial list a student sees. Only failures, in rule order."""
    if outcome.error in STRUCTURAL_ERRORS:
        return [{"field": "", "reason": outcome.error, "required": None,
                 "actual": None,
                 "message": "This posting's eligibility rule could not be "
                            "evaluated. The placement office has been notified."}]
    return [
        {"field": o.field, "reason": o.reason, "required": o.required,
         "actual": o.actual, "message": describe(o)}
        for o in outcome.outcomes if not o.passed
    ]


# -- Dynamic eligibility verification (PR 445 / PBI 17) -----------------------

def evaluate_student_eligibility(
    student_facts: dict | None,
    posting_criteria: dict | None,
) -> tuple[bool, list[str]]:
    """Evaluate student eligibility against posting criteria.

    Supports both dictionary-based criteria (PR 445: min_cpi, eligible_branches,
    max_backlogs) and native AST rule dictionaries (Fusion: gte, all, in, etc.).
    """
    student_facts = student_facts or {}
    posting_criteria = posting_criteria or {}

    if student_facts.get("is_debarred"):
        return False, ["Student is debarred"]

    min_cpi = posting_criteria.get("min_cpi")
    if min_cpi is not None:
        cpi = student_facts.get("cpi")
        try:
            if cpi is None or float(cpi) < float(min_cpi):
                return False, ["CPI below cutoff"]
        except (ValueError, TypeError):
            return False, ["CPI below cutoff"]

    eligible_branches = posting_criteria.get("eligible_branches")
    if eligible_branches:
        discipline = student_facts.get("discipline")
        norm_branches = {str(b).strip().lower() for b in eligible_branches if str(b).strip()}
        if not discipline or str(discipline).strip().lower() not in norm_branches:
            return False, ["Branch not eligible"]

    max_backlogs = posting_criteria.get("max_backlogs")
    if max_backlogs is not None:
        active_backlogs = student_facts.get("active_backlogs", 0)
        try:
            if active_backlogs is not None and int(active_backlogs) > int(max_backlogs):
                return False, ["Active backlogs present"]
        except (ValueError, TypeError):
            return False, ["Active backlogs present"]

    # If posting_criteria is an AST rule, evaluate using the engine
    ast_ops = {"all", "any", "gte", "gt", "lte", "lt", "eq", "ne", "in", "not_in"}
    if any(k in ast_ops for k in posting_criteria):
        outcome = evaluate(posting_criteria, student_facts)
        if not outcome.is_eligible:
            reasons = [r["message"] for r in failure_reasons(outcome) if r.get("message")]
            return False, reasons or ["Ineligible according to posting criteria"]

    return True, []

