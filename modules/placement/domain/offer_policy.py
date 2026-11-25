"""Placement Policy 2026-27, encoded as rules (PC-BR-015).

A student belongs to a discipline group (CSE/ECE, Core, Design); within it are
one or two categories defined by CTC bands. Accepting an offer locks the
category; switching needs the new offer to clear a multiple of the held one,
and each category caps how many switches are allowed.

Four overrides sit on top:

    marquee     once placed, no switching at all              (rule 8)
    dream slot  a placed student may still appear             (rule 7)
    core -> IT  a Core-placed student may never move to IT    (rule 2B)
    IT -> core  a non-CSE student holding IT may sit for Core (rule 10)

Pure Python, so the whole truth table is testable without a database.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal

# -- discipline groups (rule 2 A / B / C) ------------------------------------
CSE_ECE = "cse_ece"
CORE = "core"
DESIGN = "design"

# Overridable per season: the policy names groups, not discipline codes.
DEFAULT_GROUP_MAP: dict[str, str] = {
    "CSE": CSE_ECE, "ECE": CSE_ECE,
    "ME": CORE, "SM": CORE, "MT": CORE,
    "DES.": DESIGN, "DES": DESIGN, "DESIGN": DESIGN,
}

# -- sector, for the Core/IT rules -------------------------------------------
IT = "it"
CORE_SECTOR = "core"
OTHER = "other"


def group_for(discipline: str | None, mapping: dict[str, str] | None = None) -> str | None:
    """The policy group for a discipline code, or None if unmapped.

    None rather than a guess — inventing a group would apply CSE's switch
    limits to someone the policy says nothing about.
    """
    if not discipline:
        return None
    table = mapping or DEFAULT_GROUP_MAP
    return table.get(discipline.strip().upper())


@dataclass(frozen=True)
class CategorySpec:
    """One category within a discipline group (rule 2). The CTC band decides
    which category an offer belongs to."""

    group: str
    number: int
    ctc_min: Decimal | None          # inclusive
    ctc_max: Decimal | None          # inclusive
    switch_multiplier: Decimal       # new offer must be >= this x held
    switch_floor: Decimal | None = None   # rule 2.B: must also exceed this
    exit_above: Decimal | None = None     # rule 2.C: holding above this ends it
    max_switches: int | None = 1          # None = unlimited

    def contains(self, ctc: Decimal | None) -> bool:
        if ctc is None:
            return False
        return not ((self.ctc_min is not None and ctc < self.ctc_min)
                    or (self.ctc_max is not None and ctc > self.ctc_max))


def default_categories() -> tuple[CategorySpec, ...]:
    """The 2026-27 bands, verbatim from the signed policy."""
    d = Decimal
    return (
        # 2.A — CSE & ECE
        CategorySpec(CSE_ECE, 1, None, d("10"), d("1.5"), max_switches=1),
        CategorySpec(CSE_ECE, 2, d("10.01"), d("16.5"), d("2"), max_switches=1),
        # 2.B — ME, SM and Core. One category; the switch must also clear 11.5.
        CategorySpec(CORE, 1, d("6.5"), d("11.5"), d("1.5"),
                     switch_floor=d("11.5"), max_switches=1),
        # 2.C — Design. Switches repeatedly at 1.5x until above 12, then out.
        CategorySpec(DESIGN, 1, None, d("7.5"), d("1.5"),
                     exit_above=d("12"), max_switches=None),
        CategorySpec(DESIGN, 2, d("7.5"), d("12"), d("1.5"),
                     exit_above=d("12"), max_switches=None),
    )


@dataclass(frozen=True)
class PolicySpec:
    season: str
    categories: tuple[CategorySpec, ...] = field(default_factory=default_categories)
    group_map: dict[str, str] = field(default_factory=lambda: dict(DEFAULT_GROUP_MAP))
    mandatory_from: object | None = None
    min_cpi_to_register: Decimal | None = None
    allow_backlog_registration: bool = True

    def categories_for(self, group: str | None) -> tuple[CategorySpec, ...]:
        return tuple(c for c in self.categories if c.group == group)

    def category(self, group: str | None, number: int | None) -> CategorySpec | None:
        if group is None or number is None:
            return None
        for c in self.categories:
            if c.group == group and c.number == number:
                return c
        return None

    def category_for_offer(self, group: str | None,
                           ctc: Decimal | None) -> CategorySpec | None:
        """Which category a company's offer falls into, by its CTC band."""
        for c in self.categories_for(group):
            if c.contains(ctc):
                return c
        return None


@dataclass(frozen=True)
class StudentState:
    discipline: str | None = None
    is_registered: bool = False
    is_debarred: bool = False

    category_number: int | None = None    # locked on the first accepted offer
    accepted_offer_count: int = 0
    switches_used: int = 0

    held_ctc_lpa: Decimal | None = None
    held_offer_id: int | None = None
    held_is_marquee: bool = False
    held_sector: str | None = None      # it | core | other


@dataclass(frozen=True)
class OfferSpec:
    offer_id: int | None = None
    ctc_lpa: Decimal | None = None
    is_marquee: bool = False
    is_dream_slot: bool = False
    sector: str | None = None           # it | core | other
    has_core_undertaking: bool = False  # rule 10: no undertaking, no exception


@dataclass(frozen=True)
class Decision:
    allowed: bool
    rule: str
    message: str
    supersedes_offer_id: int | None = None
    facts: dict = field(default_factory=dict)

    def as_json(self) -> dict:
        """Persisted onto Offer.policy_decision, so an appeal gets the rule
        name and the numbers it compared."""
        return {
            "allowed": self.allowed, "rule": self.rule, "message": self.message,
            "supersedes_offer_id": self.supersedes_offer_id, "facts": self.facts,
        }


_MONEY = Decimal("0.01")


def _d(v) -> Decimal | None:
    return None if v is None else Decimal(str(v))


def money(v) -> str:
    """Trim a CTC for display: 12.0000 -> 12, 12.50 -> 12.5.

    Figures computed from DecimalFields otherwise reach students as
    "12.0000 LPA", which reads as a bug.
    """
    d = _d(v)
    if d is None:
        return "—"
    return f"{d.quantize(_MONEY).normalize():f}"   # :f undoes 1.2E+1


def _facts(policy, student, offer, group, category) -> dict:
    return {
        "season": policy.season,
        "discipline": student.discipline,
        "group": group,
        "category": category.number if category else None,
        "accepted_offer_count": student.accepted_offer_count,
        "switches_used": student.switches_used,
        "held_ctc_lpa": money(student.held_ctc_lpa)
        if student.held_ctc_lpa is not None else None,
        "held_sector": student.held_sector,
        "held_is_marquee": student.held_is_marquee,
        "offer_ctc_lpa": money(offer.ctc_lpa)
        if offer.ctc_lpa is not None else None,
        "offer_sector": offer.sector,
        "offer_is_marquee": offer.is_marquee,
        "offer_is_dream_slot": offer.is_dream_slot,
    }


# -- Acceptance ----------------------------------------------------------------
def can_accept(policy: PolicySpec, student: StudentState,
               offer: OfferSpec) -> Decision:
    """May this student accept this offer?

    Hardest bar first, so the recorded reason is the most fundamental one.
    """
    group = group_for(student.discipline, policy.group_map)
    held_category = policy.category(group, student.category_number)
    if (held_category is None and student.category_number is None
            and student.held_ctc_lpa is not None):
        held_category = policy.category_for_offer(group, student.held_ctc_lpa)
    facts = _facts(policy, student, offer, group, held_category)

    # -- hard bars ---------------------------------------------------------
    if student.is_debarred:
        return Decision(False, "debarred",
                        "You are debarred from placement for this season.",
                        facts=facts)
    if not student.is_registered:
        return Decision(False, "not_registered",
                        "You are not registered for this placement season "
                        "(rule 1).", facts=facts)

    # PC-AFR-014: multiple-offer handling applied only to extent explicit logic exists
    if not policy.categories:
        return Decision(True, "no_policy_restriction",
                        "No multiple-offer restriction is configured for this season.",
                        facts=facts)

    # -- first offer -------------------------------------------------------
    if student.accepted_offer_count == 0:
        new_category = policy.category_for_offer(group, offer.ctc_lpa)
        facts["category_locked_to"] = new_category.number if new_category else None
        return Decision(
            True, "first_offer",
            "Offer may be accepted." + (
                f" This locks you into Category {new_category.number} for the "
                f"season (rule 2)." if new_category else ""),
            facts=facts)

    # -- rule 8: marquee is terminal --------------------------------------
    if student.held_is_marquee:
        return Decision(
            False, "marquee_no_switch",
            "You are placed with a Marquee organisation. Policy rule 8 does "
            "not permit switching out of a Marquee company, whatever is "
            "offered elsewhere.", facts=facts)

    # -- rule 2B: Core placements may never move to IT ---------------------
    if student.held_sector == CORE_SECTOR and offer.sector == IT:
        return Decision(
            False, "no_core_to_it",
            "Policy rule 2.B does not allow a switch from a Core company to "
            "an IT company, irrespective of the package.", facts=facts)

    if held_category is None:
        if group is not None and not policy.categories_for(group):
            return Decision(
                True, "no_policy_restriction",
                f"No multiple-offer restriction configured for group '{group}'.",
                facts=facts)
        # Deny rather than guess a multiplier for an unmapped discipline.
        return Decision(
            False, "no_category_for_discipline",
            "Your discipline is not mapped to a placement category, so a "
            "switch cannot be assessed. Contact the placement office.",
            facts=facts)

    held = _d(student.held_ctc_lpa)
    new = _d(offer.ctc_lpa)

    # -- rule 2C: above the ceiling ends the season ------------------------
    if held_category.exit_above is not None and held is not None \
            and held > held_category.exit_above:
        return Decision(
            False, "exited_above_ceiling",
            f"Your current package of {money(held)} LPA is above the "
            f"{money(held_category.exit_above)} LPA ceiling, so you are out of "
            f"further processes (rule 2.C).", facts=facts)

    # -- switch allowance --------------------------------------------------
    if held_category.max_switches is not None \
            and student.switches_used >= held_category.max_switches:
        return Decision(
            False, "switch_allowance_used",
            f"Category {held_category.number} permits "
            f"{held_category.max_switches} switch(es); you have used "
            f"{student.switches_used} and are out of the process (rule 2).",
            facts=facts)

    if new is None:
        return Decision(False, "offer_ctc_unknown",
                        "This offer has no CTC recorded, so it cannot be "
                        "checked against the switch rule.", facts=facts)
    if held is None:
        return Decision(False, "held_ctc_unknown",
                        "Your current offer has no CTC recorded, so a switch "
                        "cannot be assessed. Contact the placement office.",
                        facts=facts)

    # -- rule 3: a higher category ends the season -------------------------
    new_category = policy.category_for_offer(group, new)
    if new_category is not None and new_category.number > held_category.number:
        # Check the multiple first so the message names the real blocker.
        required = held * held_category.switch_multiplier
        if new < required:
            return _below_multiple(held_category, held, new, required, facts)
        facts["moves_to_category"] = new_category.number
        return Decision(
            True, "higher_category",
            f"Accepting moves you to Category {new_category.number}. Under "
            f"rule 3 you will not be eligible for any further company in any "
            f"category.",
            supersedes_offer_id=student.held_offer_id, facts=facts)

    required = held * held_category.switch_multiplier
    facts["required_ctc_lpa"] = money(required)
    if new < required:
        return _below_multiple(held_category, held, new, required, facts)

    if held_category.switch_floor is not None and new <= held_category.switch_floor:
        return Decision(
            False, "below_switch_floor",
            f"A switch must exceed {money(held_category.switch_floor)} LPA "
            f"(rule 2.B). This offer is {money(new)} LPA.", facts=facts)

    return Decision(
        True, "switch_permitted",
        f"{money(new)} LPA clears {money(held_category.switch_multiplier)}x "
        f"your current {money(held)} LPA.",
        supersedes_offer_id=student.held_offer_id, facts=facts)


def _below_multiple(category, held, new, required, facts) -> Decision:
    facts["required_ctc_lpa"] = money(required)
    return Decision(
        False, "below_switch_multiple",
        f"A switch needs at least {money(category.switch_multiplier)}x your "
        f"current {money(held)} LPA, i.e. {money(required)} LPA. This offer is "
        f"{money(new)} LPA.",
        facts=facts)


# -- Applying ------------------------------------------------------------------
def can_apply(policy: PolicySpec, student: StudentState,
              offer: OfferSpec | None = None) -> Decision:
    """May this student appear for this posting?

    Season-level, and deliberately more permissive than `can_accept`: rule 9
    allows parallel processes, so whether the resulting offer may be accepted
    is decided later with the real numbers.
    """
    offer = offer or OfferSpec()
    group = group_for(student.discipline, policy.group_map)
    category = policy.category(group, student.category_number)
    if category is None and student.category_number is None and student.held_ctc_lpa is not None:
        category = policy.category_for_offer(group, student.held_ctc_lpa)
    facts = _facts(policy, student, offer, group, category)

    if student.is_debarred:
        return Decision(False, "debarred",
                        "You are debarred from placement for this season.",
                        facts=facts)
    if not student.is_registered:
        return Decision(False, "not_registered",
                        "Register with the Placement Cell before applying "
                        "(rule 1).", facts=facts)

    if not policy.categories:
        return Decision(True, "no_policy_restriction",
                        "No multiple-offer restriction is configured for this season.",
                        facts=facts)

    if student.accepted_offer_count == 0:
        return Decision(True, "unplaced", "You may apply.", facts=facts)

    # -- rule 7: a dream slot is open to placed students too ---------------
    if offer.is_dream_slot:
        return Decision(True, "dream_slot",
                        "This is a Dream Slot company, open to placed and "
                        "unplaced students alike (rule 7).", facts=facts)

    # -- rule 10: non-CSE holding IT may sit for a Core company ------------
    if (offer.sector == CORE_SECTOR and student.held_sector == IT
            and group != CSE_ECE):
        if not offer.has_core_undertaking:
            return Decision(
                False, "core_undertaking_required",
                "You hold an IT offer. Rule 10 allows you to appear for a Core "
                "company only after submitting a written undertaking to "
                "decline the IT offer.", facts=facts)
        return Decision(True, "core_exception",
                        "Rule 10 exception: appearing for a Core company on "
                        "your written undertaking.", facts=facts)

    if student.held_is_marquee:
        return Decision(False, "marquee_no_switch",
                        "You are placed with a Marquee organisation and may "
                        "not appear for other companies (rule 8).", facts=facts)

    if student.held_sector == CORE_SECTOR and offer.sector == IT:
        return Decision(False, "no_core_to_it",
                        "A Core placement cannot be switched to IT (rule 2.B).",
                        facts=facts)

    if category is None:
        if group is not None and not policy.categories_for(group):
            return Decision(
                True, "no_policy_restriction",
                f"No multiple-offer restriction configured for group '{group}'.",
                facts=facts)
        return Decision(False, "no_category_for_discipline",
                        "Your discipline is not mapped to a placement "
                        "category. Contact the placement office.", facts=facts)

    held = _d(student.held_ctc_lpa)
    if category.exit_above is not None and held is not None \
            and held > category.exit_above:
        return Decision(False, "exited_above_ceiling",
                        f"Your package is above the {money(category.exit_above)} "
                        f"LPA ceiling; you are out of further processes "
                        f"(rule 2.C).", facts=facts)

    if category.max_switches is not None \
            and student.switches_used >= category.max_switches:
        return Decision(False, "switch_allowance_used",
                        "You have used your switch allowance and are out of "
                        "the process (rule 2).", facts=facts)

    if held is not None:
        required = held * category.switch_multiplier
        facts["required_ctc_lpa"] = money(required)
        return Decision(
            True, "may_switch",
            f"You may appear. To accept, an offer must be at least "
            f"{money(required)} LPA ({money(category.switch_multiplier)}x your "
            f"current {money(held)} LPA).",
            facts=facts)

    return Decision(True, "may_switch", "You may appear.", facts=facts)


# -- Rule 6 — mandatory participation from September ---------------------------
def participation_is_mandatory(policy: PolicySpec, student: StudentState,
                               today) -> bool:
    """Whether an eligible unplaced student must appear (rule 6).

    Advisory only — rule 19's consequences follow a human decision.
    """
    if policy.mandatory_from is None or student.is_debarred:
        return False
    if not student.is_registered or student.accepted_offer_count > 0:
        return False
    return today >= policy.mandatory_from
