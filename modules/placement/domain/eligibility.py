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
    "cpi", "cgpa", "earned_credits", "active_backlogs", "semester",   # IAM projection
    "programme", "discipline", "branch", "batch_year", "year",        # IAM directory
    "is_placed", "is_registered", "offer_count",                      # this module
    "profile_complete",                                               # the ERP portal
    "skills",                                                         # authorized student skills
}

# List-valued facts, comparable only with the set operators (PC-AFR-022).
LIST_FIELDS: set[str] = {"skills"}
LIST_OPS = {"has_all", "has_any", "has_none"}

# Each scalar field's literal type, so a rule is checked when it is written.
NUMERIC_FIELDS = {"cpi", "cgpa", "earned_credits", "active_backlogs", "semester",
                  "batch_year", "year", "offer_count"}
TEXT_FIELDS = {"programme", "discipline", "branch"}
FLAG_FIELDS = {"is_placed", "is_registered", "profile_complete"}

EQUALITY_OPS = {"eq", "ne"}
MEMBERSHIP_OPS = {"in", "not_in"}
ORDER_OPS = {"gt", "gte", "lt", "lte"}
OPERATORS = EQUALITY_OPS | MEMBERSHIP_OPS | ORDER_OPS | LIST_OPS

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


def _same(field: str, actual, expected) -> bool | None:
    """Equality by value for numbers: a CPI stored as Decimal("8.10") equals 8.1."""
    if field not in NUMERIC_FIELDS:
        return actual == expected
    a, e = _num(actual), _num(expected)
    return None if a is None or e is None else a == e


def _compare(op: str, field: str, expected, actual) -> RuleOutcome:
    # A rule-authoring mistake still denies: guessing is how someone slips through.
    if (field in LIST_FIELDS) != (op in LIST_OPS):
        return RuleOutcome(field, op, expected, actual, False, "operator_not_valid_for_field")
    if op in LIST_OPS:
        return _compare_list(op, field, expected, actual or [])

    if actual is None:
        return RuleOutcome(field, op, expected, None, False, "missing_fact")

    if op in ("eq", "ne"):
        same = _same(field, actual, expected)
        if same is None:
            return RuleOutcome(field, op, expected, actual, False, "type_mismatch")
        ok = same if op == "eq" else not same
        return RuleOutcome(field, op, expected, actual, ok,
                           "" if ok else f"{field}_mismatch")
    if op in ("in", "not_in"):
        if not isinstance(expected, (list, tuple)):
            return RuleOutcome(field, op, expected, actual, False, "bad_rule")
        found = any(_same(field, actual, e) for e in expected)
        ok = found if op == "in" else not found
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
        actual = facts.get(field)
        if actual is None:
            if field == "cgpa":
                actual = facts.get("cpi")
            elif field == "branch":
                actual = facts.get("discipline")
            elif field == "year":
                actual = facts.get("batch_year")
        out = _compare(op, field, expected, actual)
        return Outcome(out.passed, [out])

    except Exception:                                          # noqa: BLE001
        return Outcome(False, [], "evaluation_error")          # malformed = deny


# Every denial carries the actual value and the required one, not just "no".
LABELS = {
    "cpi": "CPI", "cgpa": "CGPA", "earned_credits": "earned credits",
    "active_backlogs": "active backlogs", "semester": "semester",
    "programme": "programme", "discipline": "discipline", "branch": "branch",
    "batch_year": "batch year", "year": "year", "is_placed": "placement status",
    "is_registered": "season registration", "offer_count": "offers held",
    "profile_complete": "profile completeness", "skills": "skills",
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
        if outcome.field in ("cpi", "cgpa", "earned_credits", "active_backlogs", "semester"):
            return ("No declared result yet, so your academic standing cannot be "
                    "checked. Eligibility opens once your result is declared.")
        return f"{label} is not recorded on your profile yet."
    if outcome.op in ("in", "not_in"):
        allowed = ", ".join(str(x) for x in (outcome.required or []))
        return f"{label} is {outcome.actual} — this posting is open to {allowed}."
    if outcome.op in LIST_OPS:
        req = ", ".join(str(x) for x in (outcome.required or []))
        if outcome.op == "has_all":
            missing = outcome.reason.split(":", 1)[1] if ":" in outcome.reason else req
            return f"{label} missing required skill(s): {missing}."
        if outcome.op == "has_any":
            return f"{label} requires at least one of: {req}."
        if outcome.op == "has_none":
            disallowed = outcome.reason.split(":", 1)[1] if ":" in outcome.reason else req
            return f"{label} contains disallowed skill(s): {disallowed}."
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


# -- Authoring --------------------------------------------------------------------
@dataclass(frozen=True)
class Problem:
    path: str
    field: str
    reason: str


def validate(rule) -> list[Problem]:
    """Every reason a rule could not be evaluated as written; empty when it is sound."""
    if not rule:
        return []
    problems: list[Problem] = []
    _check(rule, "rule", 0, problems)
    return problems


def _check(node, path: str, depth: int, out: list[Problem]) -> None:
    if depth > MAX_DEPTH:
        out.append(Problem(path, "", "rule_too_complex"))
        return
    if not isinstance(node, dict) or len(node) != 1:
        out.append(Problem(path, "", "malformed_rule"))
        return
    (op, operand), = node.items()
    if op in ("all", "any"):
        if not isinstance(operand, list) or not operand:
            out.append(Problem(path, "", "malformed_rule"))
            return
        for i, sub in enumerate(operand):
            _check(sub, f"{path}.{op}[{i}]", depth + 1, out)
        return
    if op == "not":
        _check(operand, f"{path}.not", depth + 1, out)
        return
    if (not isinstance(operand, (list, tuple)) or len(operand) != 2
            or not isinstance(operand[0], str)):
        out.append(Problem(path, "", "malformed_rule"))
        return
    field, expected = operand
    reason = _comparison_problem(op, field, expected)
    if reason:
        out.append(Problem(path, field, reason))


def _comparison_problem(op: str, field: str, expected) -> str:
    if op not in OPERATORS:
        return "unknown_operator"
    if field not in FIELDS:
        return "unknown_field"
    if (field in LIST_FIELDS) != (op in LIST_OPS):
        return "operator_not_valid_for_field"
    if op in LIST_OPS:
        return "" if _norm_set(expected) else "type_mismatch"
    if op in ORDER_OPS and field not in NUMERIC_FIELDS:
        return "operator_not_valid_for_field"
    if op in MEMBERSHIP_OPS:
        if not isinstance(expected, list) or not expected:
            return "type_mismatch"
        return "" if all(_literal_fits(field, v) for v in expected) else "type_mismatch"
    return "" if _literal_fits(field, expected) else "type_mismatch"


def _literal_fits(field: str, value) -> bool:
    if field in NUMERIC_FIELDS:
        return isinstance(value, (int, float, Decimal)) and not isinstance(value, bool)
    if field in FLAG_FIELDS:
        return isinstance(value, bool)
    return isinstance(value, str) and bool(value.strip())
