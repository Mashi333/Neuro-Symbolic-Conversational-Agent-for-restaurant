"""Step 13 tests - ASP constraint validation (asp_rules.lp + asp_reasoner.py).

The first group feeds hand-written fact sets into the real rules file and
checks the derived answers, using the exact numbers from the research brief
(Vegetarian + Budget + Avoid Peanut => valid item). The second group runs the
full database through clingo and checks the answers against the SQL data.
"""

from __future__ import annotations

import unittest

from asp_reasoner import RULES_TEXT, budget_to_usd, detect_request_actions, run_clingo, solve, user_facts
from intent_extractor import extract_constraints
from retrieve import load_structured_data


def _solve(facts: str) -> dict:
    return run_clingo(facts + "\n" + RULES_TEXT)


def _valid(facts: str) -> set[str]:
    atoms = _solve(facts)
    return {str(name) for [name] in atoms.get("valid_item", [])}


def _fails(facts: str) -> dict[str, str]:
    atoms = _solve(facts)
    return {
        str(item): str(why)
        for [item, why] in atoms.get("fails", [])
    }


class BudgetRuleTests(unittest.TestCase):
    def test_item_within_budget_is_valid(self):
        # The research-brief example: Vegetarian + Budget 1500 Rs + Avoid Peanut.
        # Rs 1500 -> USD 18.00 -> 1800 cents; pasta at $14.40 -> 1440 cents.
        facts = (
            'menu_item("veg_pasta").\n'
            'price("veg_pasta", 1440).\n'
            'dietary_tag("veg_pasta", "vegetarian").\n'
            'allergen("veg_pasta", "dairy").\n'
            'budget_limit(1800).\n'
            'diet_requested.\n'
            'wants_diet("vegetarian").\n'
            'avoid_allergen("peanut").\n'
        )
        self.assertIn("veg_pasta", _valid(facts))

    def test_item_over_budget_is_rejected_with_reason(self):
        facts = (
            'menu_item("veg_pasta").\n'
            'price("veg_pasta", 1950).\n'
            'budget_limit(1800).\n'
            'no_diet_requested.\n'
        )
        self.assertNotIn("veg_pasta", _valid(facts))
        self.assertEqual(_fails(facts)["veg_pasta"], "budget")


class CalorieRuleTests(unittest.TestCase):
    """calorie_limit/1 (from other_constraints) vs the calories/2 facts."""

    def test_item_within_calorie_limit_is_valid(self):
        facts = (
            'menu_item("light_salad").\n'
            'calories("light_salad", 350).\n'
            'calorie_limit(600).\n'
            'no_diet_requested.\n'
        )
        self.assertIn("light_salad", _valid(facts))

    def test_item_over_calorie_limit_fails_with_reason(self):
        facts = (
            'menu_item("big_pizza").\n'
            'calories("big_pizza", 650).\n'
            'calorie_limit(600).\n'
            'no_diet_requested.\n'
        )
        self.assertNotIn("big_pizza", _valid(facts))
        self.assertEqual(_fails(facts)["big_pizza"], "calories")

    def test_items_without_calorie_fact_survive_the_cap(self):
        facts = (
            'menu_item("unknown_calories").\n'
            'calorie_limit(600).\n'
            'no_diet_requested.\n'
        )
        self.assertIn("unknown_calories", _valid(facts))

    def test_other_constraints_emit_calorie_limit_fact(self):
        constraints = {
            "budget": None, "budget_currency": None,
            "dietary_requirements": [], "allergies": [],
            "ingredients_to_avoid": [],
            "other_constraints": ["under 600 calories"],
        }
        facts, warnings = user_facts(constraints)
        self.assertIn("calorie_limit(600).", facts)
        self.assertEqual(warnings, [])

    def test_constraints_without_calorie_cap_emit_no_fact(self):
        constraints = {
            "budget": None, "budget_currency": None,
            "dietary_requirements": [], "allergies": [],
            "ingredients_to_avoid": [], "other_constraints": [],
        }
        facts, _ = user_facts(constraints)
        self.assertNotIn("calorie_limit", facts)


class DietaryRuleTests(unittest.TestCase):
    def test_required_tag_satisfies_diet(self):
        facts = (
            'menu_item("veg_burger").\n'
            'dietary_tag("veg_burger", "vegetarian").\n'
            'diet_requested.\n'
            'wants_diet("vegetarian").\n'
            'no_budget_limit.\n'
        )
        self.assertIn("veg_burger", _valid(facts))

    def test_missing_tag_fails_diet(self):
        facts = (
            'menu_item("beef_burger").\n'
            'dietary_tag("beef_burger", "halal").\n'
            'diet_requested.\n'
            'wants_diet("vegetarian").\n'
            'no_budget_limit.\n'
        )
        self.assertNotIn("beef_burger", _valid(facts))
        self.assertEqual(_fails(facts)["beef_burger"], "diet")

    def test_no_diet_requested_rejects_nothing(self):
        facts = (
            'menu_item("beef_burger").\n'
            'dietary_tag("beef_burger", "halal").\n'
            'no_diet_requested.\n'
            'no_budget_limit.\n'
        )
        self.assertIn("beef_burger", _valid(facts))


class AllergyIngredientRuleTests(unittest.TestCase):
    def test_declared_allergen_matches_avoided_allergen(self):
        facts = (
            'menu_item("peanut_cookie").\n'
            'allergen("peanut_cookie", "peanut").\n'
            'no_diet_requested.\n'
            'no_budget_limit.\n'
            'avoid_allergen("peanut").\n'
        )
        self.assertNotIn("peanut_cookie", _valid(facts))
        self.assertEqual(_fails(facts)["peanut_cookie"], "allergy")

    def test_unrelated_allergen_does_not_count(self):
        facts = (
            'menu_item("veg_pasta").\n'
            'allergen("veg_pasta", "dairy").\n'
            'no_diet_requested.\n'
            'no_budget_limit.\n'
            'avoid_allergen("peanut").\n'
        )
        self.assertIn("veg_pasta", _valid(facts))

    def test_avoid_ingredient_rejects_item(self):
        facts = (
            'menu_item("veg_pasta").\n'
            'ingredient("veg_pasta", "pasta").\n'
            'no_diet_requested.\n'
            'no_budget_limit.\n'
            'avoid_ingredient("pasta").\n'
        )
        self.assertNotIn("veg_pasta", _valid(facts))
        self.assertEqual(_fails(facts)["veg_pasta"], "ingredient")


class PolicyRuleTests(unittest.TestCase):
    def test_forbidden_action_violates_policy(self):
        atoms = _solve(
            'policy("no_outside_food").\n'
            'forbids("no_outside_food", "bring_outside_food").\n'
            'request_action("bring_outside_food").\n'
        )
        self.assertFalse(atoms.get("policy_compliant"))
        self.assertEqual(
            [str(p) for [p] in atoms.get("policy_violation", [])],
            ["no_outside_food"],
        )
        self.assertIn("bring_outside_food", {str(a) for [a] in atoms.get("forbidden", [])})

    def test_no_requested_actions_are_compliant(self):
        atoms = _solve(
            'policy("no_pets").\n'
            'forbids("no_pets", "bring_pet").\n'
        )
        self.assertTrue(atoms.get("policy_compliant"))

    def test_unrelated_policy_is_not_a_violation(self):
        atoms = _solve(
            'policy("no_smoking").\n'
            'forbids("no_smoking", "smoke_inside").\n'
            'request_action("reserve_table").\n'
        )
        self.assertTrue(atoms.get("policy_compliant"))


class WrapperUnitTests(unittest.TestCase):
    def test_inr_budget_converts_to_usd(self):
        self.assertAlmostEqual(budget_to_usd(1500, "inr")[0], 18.0, places=2)

    def test_no_budget_gives_no_limit(self):
        self.assertEqual(budget_to_usd(None, "inr"), (None, None))

    def test_unknown_currency_warns_instead_of_filtering(self):
        converted, warning = budget_to_usd(10, "xyz")
        self.assertIsNone(converted)
        self.assertIsNotNone(warning)

    def test_unlabelled_budget_defaults_to_usd(self):
        # "under 7" with no unit defaults to dollars, matching retrieve.py.
        converted, warning = budget_to_usd(7, None)
        self.assertEqual(converted, 7.0)
        self.assertIsNone(warning)

    def test_reservation_intent_implies_reserve_action(self):
        actions = detect_request_actions(
            {"intent": "reservation", "other_constraints": []}
        )
        self.assertIn("reserve_table", actions)

    def test_cake_constraint_implies_outside_food_action(self):
        actions = detect_request_actions(
            {"intent": "restaurant_recommendation", "other_constraints": ["bring my own birthday cake"]}
        )
        self.assertIn("bring_outside_food", actions)

    def test_plain_recommendation_has_no_actions(self):
        self.assertEqual(
            detect_request_actions({"intent": "restaurant_recommendation", "other_constraints": []}),
            [],
        )


class IntegrationTests(unittest.TestCase):
    """Solve over the whole database; every answer must be true in SQL data."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.data = load_structured_data()

    def _expected(self, *, max_price: float | None = None, diet: str | None = None,
                 no_allergen: str | None = None) -> set[str]:
        expected: set[str] = set()
        for item in self.data["menu_items_by_id"].values():  # type: ignore[union-attr]
            item_id = int(item["item_id"])  # type: ignore[arg-type]
            name = str(item["item_name"]).lower()
            if max_price is not None and float(item["price"]) > max_price:  # type: ignore[arg-type]
                continue
            if diet is not None and diet not in {
                value.lower() for value in self.data["item_dietary"].get(item_id) or []  # type: ignore[union-attr]
            }:
                continue
            if no_allergen is not None and no_allergen in {
                value.lower() for value in self.data["item_allergens"].get(item_id) or []  # type: ignore[union-attr]
            }:
                continue
            expected.add(name)
        return expected

    def test_vegetarian_under_seven_without_peanut(self):
        constraints = extract_constraints("vegetarian meal under $7 without peanuts")
        result = solve(constraints, data=self.data)
        expected = self._expected(max_price=7.0, diet="vegetarian", no_allergen="peanut")
        self.assertTrue(result["valid_items"])
        self.assertTrue(set(result["valid_items"]) <= expected)
        for name in result["valid_items"]:
            self.assertIn(name, {
                str(item["item_name"]).lower()
                for item in self.data["menu_items_by_id"].values()  # type: ignore[union-attr]
            })

    def test_all_valid_items_meet_every_constraint(self):
        constraints = extract_constraints("vegan meal under $8 without dairy")
        result = solve(constraints, data=self.data)
        expected = self._expected(max_price=8.0, diet="vegan", no_allergen="milk")
        if result["valid_items"]:
            self.assertTrue(set(result["valid_items"]) <= expected)
        self.assertEqual(result["total_items"], 100)

    def test_no_constraints_returns_all_items(self):
        constraints = extract_constraints("menu")
        result = solve(constraints, data=self.data)
        self.assertEqual(result["valid_count"], result["total_items"])
        self.assertTrue(result["policy"]["compliant"])


if __name__ == "__main__":
    unittest.main(verbosity=2)