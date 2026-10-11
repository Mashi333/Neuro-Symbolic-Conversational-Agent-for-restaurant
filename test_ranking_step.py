"""Step 17 tests - soft ranking of ASP-valid items.

Focused invariants:
  * a hard-constraint violation is NEVER ranked (guard raises, ASP partition
    untouched), and the ranking output only contains ASP-valid items;
  * each soft factor is computed from real data fields and normalised to [0,1];
  * weights are reactive: similarity dominates when other factors are neutral,
    budget / preference / category shifts do change the order.
"""

from __future__ import annotations

import unittest

from asp_validation import validate_items
from ranking_step import (
    WEIGHTS,
    _price_dollars,
    price_fit,
    rank_valid,
    score_and_rank,
    similarity_score,
    soft_diet_match,
)
from retrieve import load_structured_data


class SimilarityTests(unittest.TestCase):
    def test_score_used_directly_without_set_stretching(self):
        # A 0.61 vs 0.60 retrieval gap must NOT become a 1.0 vs 0.0 swing.
        self.assertEqual(similarity_score(0.61), 0.61)
        self.assertEqual(similarity_score(0.60), 0.60)
        self.assertEqual(similarity_score(0.9), 0.9)

    def test_clipped_to_unit_interval(self):
        self.assertEqual(similarity_score(1.5), 1.0)
        self.assertEqual(similarity_score(-0.3), 0.0)


class PriceFitTests(unittest.TestCase):
    def test_cheaper_scores_higher_under_budget(self):
        self.assertGreater(price_fit(5.0, 10.0), price_fit(9.0, 10.0))

    def test_at_and_above_budget_clamped_to_zero(self):
        self.assertEqual(price_fit(0.0, 10.0), 1.0)  # $0 sits best under budget
        self.assertEqual(price_fit(10.0, 10.0), 0.0)
        self.assertEqual(price_fit(20.0, 10.0), 0.0)

    def test_no_budget_is_neutral(self):
        self.assertEqual(price_fit(8.0, None), 0.5)

    def test_price_dollar_parser(self):
        self.assertEqual(_price_dollars("$8.99"), 8.99)
        self.assertEqual(_price_dollars(6.5), 6.5)
        self.assertIsNone(_price_dollars("free range"))


class SeparationTests(unittest.TestCase):
    def test_invalid_item_is_never_ranked(self):
        data = load_structured_data()
        ids = list(data["menu_items_by_id"])[:12]  # type: ignore[union-attr]
        constraints = {
            "budget": 6.0, "budget_currency": "usd",
            "dietary_requirements": ["vegetarian"], "allergies": [],
            "ingredients_to_avoid": [], "other_constraints": [],
        }
        results = [{"item_id": i, "item_name": data["menu_items_by_id"][i]["item_name"],
                    "rank": n, "score": 0.9 - n * 0.01,
                    "price": data["menu_items_by_id"][i]["price"]}
                   for n, i in enumerate(ids, start=1)]
        payload = {"constraints": constraints, "results": results,
                   **validate_items(results, constraints, data=data)}
        self.assertTrue(payload["invalid"])  # some items fail the hard checks

        ranked = score_and_rank(payload["valid"], constraints=constraints,
                                data=data, validation=payload)
        ranked_names = {r["item_name"] for r in ranked}
        removed_names = {r["item_name"] for r in payload["invalid"]}
        self.assertTrue(ranked_names)                       # hard-valid subset
        self.assertFalse(ranked_names & removed_names)      # never a violation

    def test_guard_rejects_a_smuggled_invalid_item(self):
        data = load_structured_data()
        constraints = {"budget": 9.0, "budget_currency": "usd",
                       "dietary_requirements": [], "allergies": [],
                       "ingredients_to_avoid": [], "other_constraints": []}
        ids = list(data["menu_items_by_id"])[:3]  # type: ignore[union-attr]
        results = [{"item_id": i, "item_name": data["menu_items_by_id"][i]["item_name"],
                    "rank": n, "score": 0.5,
                    "price": data["menu_items_by_id"][i]["price"]}
                   for n, i in enumerate(ids, start=1)]
        payload = {"constraints": constraints, "results": results,
                   **validate_items(results, constraints, data=data)}
        self.assertGreater(len(payload["invalid"]), 0)  # $8.99 fits 9.0, rest don't
        smuggled = list(payload["valid"]) + [dict(payload["invalid"][0])]
        with self.assertRaises(ValueError):
            score_and_rank(smuggled, constraints=constraints,
                           data=data, validation=payload)


class FactorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.data = load_structured_data()

    def test_similarity_dominates_when_other_factors_neutral(self):
        # No budget, no wishes/preferences -> only similarity (then price) moves.
        rows = [
            {"item_id": 1, "item_name": "Margherita Pizza",
             "score": 0.9, "price": 8.99},
            {"item_id": 23, "item_name": "Spaghetti Bolognese",
             "score": 0.6, "price": 3.99},
        ]
        ranked = rank_valid(rows, data=self.data)
        self.assertEqual(ranked[0]["item_name"], "Margherita Pizza")

    def test_budget_fit_promotes_the_cheaper_item(self):
        rows = [
            {"item_id": 5, "item_name": "Cheese Burger", "score": 0.61, "price": 7.99},
            {"item_id": 6, "item_name": "Chicken Burger", "score": 0.60, "price": 7.49},
        ]
        ranked = rank_valid(
            rows, data=self.data,
            constraints={"budget": 8.0, "budget_currency": "usd"},
        )
        self.assertEqual(ranked[0]["item_name"], "Chicken Burger")

    def test_preferred_ingredient_boost(self):
        # Egg is in Fried Rice (id 27) but not in the pizza or the fries.
        constraints = {
            "ingredients_preferred": ["egg"],
            "other_constraints": [],
            "allergies": [], "ingredients_to_avoid": [], "budget": None,
        }
        rows = [
            {"item_id": 1, "item_name": "Margherita Pizza", "score": 0.8, "price": 8.99},
            {"item_id": 9, "item_name": "French Fries", "score": 0.7, "price": 3.99},
            {"item_id": 27, "item_name": "Fried Rice", "score": 0.5, "price": 8.99},
        ]
        ranked = score_and_rank(rows, constraints=constraints, data=self.data)
        scores = {r["item_name"]: r["scores"]["preference"] for r in ranked}
        self.assertEqual(scores["Fried Rice"], 1.0)
        self.assertEqual(scores["Margherita Pizza"], 0.0)
        self.assertGreater(scores["Fried Rice"], scores["French Fries"])

    def test_restaurant_category_preference_boost(self):
        ranked = score_and_rank(
            [
                {"item_id": 1, "item_name": "Margherita Pizza", "score": 0.6, "price": 8.99},
                {"item_id": 15, "item_name": "Caesar Salad", "score": 0.7, "price": 6.99},
            ],
            constraints={"restaurant_preference": "salad"},
            data=self.data,
            preferences=["salad"],
        )
        scores = {r["item_name"]: r["scores"]["restaurant"] for r in ranked}
        self.assertEqual(scores["Caesar Salad"], 1.0)
        self.assertEqual(scores["Margherita Pizza"], 0.0)
        self.assertEqual(ranked[0]["item_name"], "Caesar Salad")

    def test_soft_diet_wish_low_calorie(self):
        data = self.data
        low_cal = min(
            (i for i, it in data["menu_items_by_id"].items()
             if isinstance(it.get("calories"), int)),
            key=lambda i: data["menu_items_by_id"][i]["calories"],  # type: ignore[index]
        )
        high_cal = max(
            (i for i, it in data["menu_items_by_id"].items()
             if isinstance(it.get("calories"), int)),
            key=lambda i: data["menu_items_by_id"][i]["calories"],  # type: ignore[index]
        )
        self.assertGreater(
            soft_diet_match(data, low_cal, ["low calorie"]),
            soft_diet_match(data, high_cal, ["low calorie"]),
        )
        self.assertEqual(soft_diet_match(data, low_cal, []), 0.5)  # no wish -> neutral


class ExplainabilityTests(unittest.TestCase):
    def test_every_ranked_row_carries_scores_and_total(self):
        data = load_structured_data()
        ids = list(data["menu_items_by_id"])[:4]  # type: ignore[union-attr]
        rows = [{"item_id": i, "item_name": data["menu_items_by_id"][i]["item_name"],
                 "score": 0.5 + n * 0.1, "price": None}
                for n, i in enumerate(ids)]
        ranked = rank_valid(rows, data=data)
        self.assertEqual(len(ranked), 4)
        for row in ranked:
            self.assertEqual(set(row["scores"]), set(WEIGHTS))
            self.assertTrue(0.0 <= row["total"] <= 1.0)
            for value in row["scores"].values():
                self.assertTrue(0.0 <= value <= 1.0, f"{row['item_name']}: {value}")


if __name__ == "__main__":
    unittest.main(verbosity=2)