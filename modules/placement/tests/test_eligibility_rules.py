"""Eligibility (PC-BR-002, PC-BR-004).

Two load-bearing properties: nothing reaches "eligible" by accident (the facts
come from a projection that can legitimately be empty), and every denial names
the actual value and the required one.
"""
from decimal import Decimal

from django.test import SimpleTestCase

from modules.placement.domain import eligibility as elig
from modules.placement.domain.eligibility import evaluate, failure_reasons, validate


def facts(**kw):
    base = {"cpi": Decimal("8.0"), "active_backlogs": 0, "discipline": "CSE",
            "programme": "B.Tech", "batch_year": 2023, "is_placed": False,
            "is_registered": True, "skills": ["python", "sql"],
            "profile_complete": True, "earned_credits": Decimal("120"),
            "semester": 6, "offer_count": 0}
    base.update(kw)
    return base


class FailClosedTests(SimpleTestCase):

    def test_no_rule_means_no_restriction(self):
        self.assertTrue(evaluate({}, facts()).is_eligible)
        self.assertTrue(evaluate(None, facts()).is_eligible)

    def test_a_missing_fact_denies(self):
        """A student with no declared result has no CPI. That must deny, not
        be skipped and not be read as zero."""
        out = evaluate({"gte": ["cpi", 7.0]}, facts(cpi=None))
        self.assertFalse(out.is_eligible)
        self.assertEqual(out.outcomes[0].reason, "missing_fact")

    def test_an_unknown_field_denies(self):
        out = evaluate({"gte": ["favourite_colour", 7]}, facts())
        self.assertFalse(out.is_eligible)
        self.assertEqual(out.error, "unknown_field")

    def test_a_malformed_rule_denies(self):
        for rule in ({"gte": "not-a-pair"}, {"gte": [1, 2, 3]},
                     {"nonsense": ["cpi", 7]}, {"all": "not-a-list"}):
            self.assertFalse(evaluate(rule, facts()).is_eligible, rule)

    def test_an_empty_any_denies(self):
        self.assertFalse(evaluate({"any": []}, facts()).is_eligible)

    def test_deep_nesting_denies_rather_than_recursing(self):
        rule = {"gte": ["cpi", 1]}
        for _ in range(12):
            rule = {"all": [rule]}
        out = evaluate(rule, facts())
        self.assertFalse(out.is_eligible)
        self.assertEqual(out.error, "rule_too_complex")


class ComparisonTests(SimpleTestCase):

    def test_cpi_threshold(self):
        rule = {"gte": ["cpi", 7.0]}
        self.assertTrue(evaluate(rule, facts(cpi=Decimal("7.0"))).is_eligible)
        self.assertFalse(evaluate(rule, facts(cpi=Decimal("6.99"))).is_eligible)

    def test_discipline_allow_list(self):
        rule = {"in": ["discipline", ["CSE", "ECE"]]}
        self.assertTrue(evaluate(rule, facts(discipline="ECE")).is_eligible)
        self.assertFalse(evaluate(rule, facts(discipline="ME")).is_eligible)

    def test_zero_backlogs(self):
        rule = {"eq": ["active_backlogs", 0]}
        self.assertTrue(evaluate(rule, facts(active_backlogs=0)).is_eligible)
        self.assertFalse(evaluate(rule, facts(active_backlogs=1)).is_eligible)

    def test_all_requires_every_branch(self):
        rule = {"all": [{"gte": ["cpi", 7.0]}, {"eq": ["active_backlogs", 0]}]}
        self.assertTrue(evaluate(rule, facts()).is_eligible)
        self.assertFalse(evaluate(rule, facts(active_backlogs=2)).is_eligible)

    def test_any_requires_one_branch(self):
        rule = {"any": [{"gte": ["cpi", 9.5]}, {"in": ["discipline", ["CSE"]]}]}
        self.assertTrue(evaluate(rule, facts()).is_eligible)
        self.assertFalse(evaluate(rule, facts(discipline="ME")).is_eligible)

    def test_not_inverts(self):
        rule = {"not": {"eq": ["is_placed", True]}}
        self.assertTrue(evaluate(rule, facts(is_placed=False)).is_eligible)
        self.assertFalse(evaluate(rule, facts(is_placed=True)).is_eligible)



class ExplanationTests(SimpleTestCase):

    def test_a_cpi_shortfall_names_both_numbers(self):
        out = evaluate({"gte": ["cpi", 7.0]}, facts(cpi=Decimal("6.80")))
        message = failure_reasons(out)[0]["message"]
        self.assertIn("6.80", message)
        self.assertIn("7.0", message)
        self.assertIn("CPI", message)

    def test_no_declared_result_says_so_plainly(self):
        out = evaluate({"gte": ["cpi", 7.0]}, facts(cpi=None))
        message = failure_reasons(out)[0]["message"]
        self.assertIn("declared", message.lower())


    def test_a_discipline_mismatch_lists_what_is_accepted(self):
        out = evaluate({"in": ["discipline", ["CSE", "ECE"]]},
                       facts(discipline="ME"))
        message = failure_reasons(out)[0]["message"]
        self.assertIn("CSE", message)
        self.assertIn("ME", message)

    def test_only_failures_are_reported(self):
        out = evaluate({"all": [{"gte": ["cpi", 7.0]},
                                {"eq": ["active_backlogs", 5]}]}, facts())
        reasons = failure_reasons(out)
        self.assertEqual(len(reasons), 1)
        self.assertEqual(reasons[0]["field"], "active_backlogs")

    def test_a_broken_rule_does_not_blame_the_student(self):
        out = evaluate({"gte": ["nonexistent_field", 1]}, facts())
        message = failure_reasons(out)[0]["message"]
        self.assertIn("placement office", message.lower())


class NumericEqualityTests(SimpleTestCase):

    def test_equal_cpi_matches_by_value(self):
        self.assertTrue(evaluate({"eq": ["cpi", 8.1]}, facts(cpi=Decimal("8.10"))).is_eligible)

    def test_unequal_cpi_does_not_match(self):
        self.assertFalse(evaluate({"eq": ["cpi", 8.1]}, facts(cpi=Decimal("8.11"))).is_eligible)

    def test_membership_compares_numbers_by_value(self):
        self.assertTrue(evaluate({"in": ["cpi", [8.1, 9]]}, facts(cpi=Decimal("8.10"))).is_eligible)
        self.assertFalse(evaluate({"not_in": ["cpi", [8.1]]}, facts(cpi=Decimal("8.10"))).is_eligible)

    def test_a_non_numeric_literal_denies_rather_than_passing_ne(self):
        out = evaluate({"ne": ["cpi", "high"]}, facts())
        self.assertFalse(out.is_eligible)
        self.assertEqual(out.outcomes[0].reason, "type_mismatch")


class AuthoringValidationTests(SimpleTestCase):
    """PC-BR-004: a malformed rule is refused when it is written, not when a student applies."""

    SOUND = (
        {},
        {"gte": ["cpi", 7.0]},
        {"in": ["discipline", ["CSE", "ECE"]]},
        {"lte": ["active_backlogs", 0]},
        {"eq": ["is_placed", False]},
        {"eq": ["discipline", "CSE"]},
        {"not": {"in": ["programme", ["M.Tech"]]}},
        {"all": [{"gte": ["cpi", 7]}, {"any": [{"eq": ["semester", 7]},
                                                {"gte": ["batch_year", 2022]}]}]},
    )

    BROKEN = (
        ({"approx": ["cpi", 7]}, "unknown_operator"),
        ({"between": ["batch_year", [2021, 2023]]}, "unknown_operator"),
        ({"gte": ["gpa", 7.0]}, "unknown_field"),
        ({"gte": ["cpi", "seven"]}, "type_mismatch"),
        ({"gte": ["cpi", True]}, "type_mismatch"),
        ({"eq": ["is_placed", "false"]}, "type_mismatch"),
        ({"eq": ["discipline", " "]}, "type_mismatch"),
        ({"in": ["discipline", "CSE"]}, "type_mismatch"),
        ({"in": ["discipline", []]}, "type_mismatch"),
        ({"in": ["semester", [7, "eight"]]}, "type_mismatch"),
        ({"gte": ["discipline", "CSE"]}, "operator_not_valid_for_field"),
        ({"has_all": ["discipline", ["CSE"]]}, "operator_not_valid_for_field"),
        ({"gte": ["cpi"]}, "malformed_rule"),
        ({"gte": [7, "cpi"]}, "malformed_rule"),
        ({"gte": ["cpi", 7], "lte": ["cpi", 9]}, "malformed_rule"),
        ({"all": "not-a-list"}, "malformed_rule"),
        ({"any": []}, "malformed_rule"),
        ({"not": "cpi"}, "malformed_rule"),
        (["gte", "cpi", 7], "malformed_rule"),
    )

    def test_sound_rules_have_no_problems(self):
        for rule in self.SOUND:
            with self.subTest(rule=rule):
                self.assertEqual(validate(rule), [])

    def test_each_broken_rule_names_its_reason(self):
        for rule, reason in self.BROKEN:
            with self.subTest(rule=rule):
                self.assertEqual([p.reason for p in validate(rule)], [reason])

    def test_a_problem_deep_in_the_tree_names_its_path(self):
        rule = {"all": [{"gte": ["cpi", 7]}, {"any": [{"approx": ["cpi", 7]}]}]}
        (problem,) = validate(rule)
        self.assertEqual((problem.path, problem.field), ("rule.all[1].any[0]", "cpi"))

    def test_every_problem_is_reported_not_only_the_first(self):
        rule = {"all": [{"approx": ["cpi", 7]}, {"gte": ["gpa", 7]}]}
        self.assertEqual([p.reason for p in validate(rule)], ["unknown_operator", "unknown_field"])

    def test_nesting_past_the_limit_is_too_complex(self):
        rule = {"gte": ["cpi", 7.0]}
        for _ in range(elig.MAX_DEPTH + 1):
            rule = {"all": [rule]}
        self.assertEqual([p.reason for p in validate(rule)], ["rule_too_complex"])

    def test_every_field_has_exactly_one_type(self):
        typed = [elig.NUMERIC_FIELDS, elig.TEXT_FIELDS, elig.FLAG_FIELDS, elig.LIST_FIELDS]
        self.assertEqual(set().union(*typed), elig.FIELDS)
        self.assertEqual(sum(len(s) for s in typed), len(elig.FIELDS))
