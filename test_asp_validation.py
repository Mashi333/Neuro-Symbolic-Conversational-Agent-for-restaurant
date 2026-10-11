"""Step 14 tests - RAG -> ASP connection (asp_validation.py).

Assumptions checked:
  * No invention: every ASP fact describes a real DB row the retriever
    returned, with values copied verbatim from that row.
  * Exact partition: valid + invalid == retrieved set (RAG rank preserved).
  * Reasons are truthful: every reason attached to an invalid item is
    provable from the database.
  * Policy violations still flow through the combined pipeline.
"""

from __future__ import annotations

import unittest

from asp_reasoner import build_program, CURRENCY_TO_USD
from asp_validation import _restricted_data, retrieve_and_validate
from retrieve import load_structured_data

BRIEF_QUERY = "I want a vegetarian meal under Rs. 1500 without peanuts."


class NoInventionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.data = load_structured_data()
        cls.payload = retrieve_and_validate(BRIEF_QUERY, k=10, data=cls.data)
        cls.retrieved_ids = {
            int(row["item_id"]) for row in cls.payload["user_query"] and [] or []
        }

    def _restricted_facts_text(self) -> str:
        restricted, _ = _restricted_data(self.payload["results"], self.data)
        program, _ = build_program(self.payload["constraints"], data=restricted)
        return program

    def test_every_valid_and_invalid_item_came_from_the_database(self):
        valid = {row["item_name"] for row in self.payload["valid"]}
        invalid = {row["item_name"] for row in self.payload["invalid"]}
        retrieved = {str(row["item_name"]) for row in self.payload["results"]}
        self.assertEqual(valid | invalid, retrieved)
        self.assertEqual(len(self.payload["results"]),
                         len(valid) + len(invalid))

    def test_final_verdicts_are_a_subset_of_retrieved_items(self):
        # No item can appear that RAG did not retrieve -> ASP cannot invent.
        retrieved_names = {str(r["item_name"]).lower() for r in self.payload["results"]}
        for row in self.payload["valid"] + self.payload["invalid"]:
            self.assertIn(str(row["item_name"]).lower(), retrieved_names)

    def test_all_fact_values_exist_verbatim_in_the_database(self):
        for row in self.payload["results"]:
            item = self.data["menu_items_by_id"][int(row["item_id"])]  # type: ignore[union-attr]
            item_id = int(item["item_id"])  # type: ignore[arg-type]
            name = str(item["item_name"]).lower()
            cents = int(round(float(item["price"]) * 100))  # type: ignore[arg-type]

            program = self._restricted_facts_text()
            self.assertIn(f'menu_item("{name}").', program)
            self.assertIn(f'price("{name}", {cents}).', program)
            for tag in {t.lower() for t in self.data["item_dietary"].get(item_id) or []}:  # type: ignore[union-attr]
                self.assertIn(f'dietary_tag("{name}", "{tag}").', program)
            for allergen in {a.lower() for a in self.data["item_allergens"].get(item_id) or []}:  # type: ignore[union-attr]
                self.assertIn(f'allergen("{name}", "{allergen}").', program)
            for ingredient in {g.lower() for g in self.data["item_ingredients"].get(item_id) or []}:  # type: ignore[union-attr]
                self.assertIn(f'ingredient("{name}", "{ingredient}").', program)


class TruthfulnessTests(unittest.TestCase):
    """Every advertised reason must be provable from the database."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.data = load_structured_data()
        cls.payload = retrieve_and_validate(
            "vegetarian meal under $7 without peanuts", k=20, data=cls.data
        )
        cls.by_name = {
            int(row["item_id"]): row for row in cls.payload["results"]
        }
        cls.id_by_name = {
            str(item["item_name"]).lower(): int(item["item_id"])  # type: ignore[arg-type]
            for item in cls.data["menu_items_by_id"].values()  # type: ignore[union-attr]
        }

    def _db_truth(self, item_id: int) -> dict:
        dietary = {v.lower() for v in self.data["item_dietary"].get(item_id) or []}  # type: ignore[union-attr]
        allergens = {v.lower() for v in self.data["item_allergens"].get(item_id) or []}  # type: ignore[union-attr]
        ingredients = {v.lower() for v in self.data["item_ingredients"].get(item_id) or []}  # type: ignore[union-attr]
        price_cents = int(round(float(self.data["menu_items_by_id"][item_id]["price"]) * 100))  # type: ignore[arg-type,index]
        return {
            "diet": "vegetarian" not in dietary,
            "budget": price_cents > 700,
            "allergy": "peanut" in allergens,
            "ingredient": "peanut" in ingredients,
        }

    def test_invalid_reasons_are_true_in_database(self):
        for row in self.payload["invalid"]:
            truth = self._db_truth(self.id_by_name[str(row["item_name"]).lower()])
            self.assertTrue(row["reasons"], f"{row['item_name']} has no reason")
            for reason in row["reasons"]:
                self.assertTrue(truth[reason],
                                f"{row['item_name']} wrongly blamed for {reason}")

    def test_valid_items_pass_every_check_in_database(self):
        for row in self.payload["valid"]:
            truth = self._db_truth(self.id_by_name[str(row["item_name"]).lower()])
            self.assertFalse(any(truth.values()),
                             f"{row['item_name']} is valid but DB flags it: {truth}")

    def test_valid_order_preserves_ranking(self):
        ranks = [row["rank"] for row in self.payload["valid"]]
        self.assertEqual(ranks, sorted(ranks))


class EndToEndTests(unittest.TestCase):
    def test_brief_example_returns_valid_and_invalid(self):
        payload = retrieve_and_validate(BRIEF_QUERY, k=10)
        self.assertTrue(payload["valid"], "expected at least one valid item")
        self.assertTrue(payload["invalid"], "expected at least one invalid item")
        # Currency-aware filtering is on: no valid item may exceed $18.
        budget_cents = int(round(1500 * CURRENCY_TO_USD["inr"] * 100))
        data = load_structured_data()
        for row in payload["valid"]:
            item_id = next(
                iid for iid, item in data["menu_items_by_id"].items()  # type: ignore[union-attr]
                if str(item["item_name"]).lower() == str(row["item_name"]).lower()
            )
            price_cents = int(round(float(data["menu_items_by_id"][item_id]["price"]) * 100))  # type: ignore[arg-type,index]
            self.assertLessEqual(price_cents, budget_cents)
        self.assertTrue(payload["policy"]["compliant"])

    def test_policy_violation_flows_through_pipeline(self):
        payload = retrieve_and_validate(
            "Can I bring my birthday cake? recommend a dessert under $10", k=10
        )
        self.assertFalse(payload["policy"]["compliant"])
        self.assertIn("no_outside_food", payload["policy"]["violations"])
        self.assertIn("bring_outside_food", payload["policy"]["forbidden_actions"])
        self.assertTrue(payload["valid"])


if __name__ == "__main__":
    unittest.main(verbosity=2)