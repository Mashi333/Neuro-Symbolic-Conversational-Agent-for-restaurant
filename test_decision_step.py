"""Step 15 tests - decision handling after ASP validation.

Branches exercised:
  * valid options exist  -> invalid dropped, valid ranked, ONLY valid items
    are sent to the LLM (no-invention check on the prompt), answer returned.
  * no valid options     -> no recommendation invented, blockers diagnosed
    from ASP failure counts, relaxation suggested and asked.
"""

from __future__ import annotations

import json
import re
import unittest

from asp_validation import validate_items
from order_state import OrderState
from decision_step import (
    agent_answer,
    analyze_blockers,
    decide,
    rank_valid,
    remove_constraint,
)
from llm_client import LLMError, MockLLM
from retrieve import load_structured_data

ITEM_NAME_RE = re.compile(r'"item_name":\s*"([^"]+)"')


def _extraction_json(**overrides) -> str:
    base = {
        "intent": "restaurant_recommendation",
        "restaurant_preference": None,
        "budget": 7.0,
        "budget_currency": "usd",
        "dietary_requirements": ["vegetarian"],
        "allergies": ["peanut"],
        "ingredients_to_avoid": ["peanut"],
        "ingredients_preferred": [],
        "other_constraints": [],
    }
    base.update(overrides)
    return json.dumps(base)


def _verbose_responder(captured: dict) -> MockLLM:
    """MockLLM: standard extraction JSON, but records the generation prompt."""

    def responder(messages: list[dict], call: int) -> str:
        content = " ".join(message["content"] for message in messages)
        if "APPROVED ITEMS" in content:
            captured["prompt"].append(content)
            return "I recommend the Veg Sandwich and the Veggie Burger for your vegetarian meal."
        return _extraction_json()

    return MockLLM(responder)


class RankTests(unittest.TestCase):
    def test_ranks_by_similarity_then_cheapest(self):
        rows = [
            {"item_name": "pricey", "score": 0.5, "price": "$9.99", "rank": 1},
            {"item_name": "cheap", "score": 0.5, "price": "$4.99", "rank": 2},
            {"item_name": "best", "score": 0.9, "price": "$8.99", "rank": 3},
        ]
        ranked = rank_valid(rows)
        self.assertEqual([r["item_name"] for r in ranked], ["best", "cheap", "pricey"])

    def test_missing_price_goes_last_in_tie(self):
        rows = [
            {"item_name": "unknown_price", "score": 0.5, "price": None, "rank": 1},
            {"item_name": "known_price", "score": 0.5, "price": "$6.00", "rank": 2},
        ]
        self.assertEqual(
            [r["item_name"] for r in rank_valid(rows)], ["known_price", "unknown_price"]
        )


class BlockerTests(unittest.TestCase):
    def test_blocker_counts_labels_and_user_values(self):
        payload = {
            "constraints": {
                "budget": 7.0, "budget_currency": "usd",
                "dietary_requirements": ["vegetarian"],
                "allergies": [], "ingredients_to_avoid": [],
            },
            "invalid": [
                {"item_name": "a", "reasons": ["diet"]},
                {"item_name": "b", "reasons": ["diet", "budget"]},
                {"item_name": "c", "reasons": ["budget"]},
            ],
        }
        blockers = analyze_blockers(payload)
        by_reason = {b["reason"]: b for b in blockers}
        self.assertEqual(by_reason["diet"]["blocked_n"], 2)
        self.assertEqual(by_reason["diet"]["label"], "dietary requirement")
        self.assertEqual(by_reason["diet"]["user_value"], "vegetarian")
        self.assertEqual(by_reason["budget"]["user_value"], "7.0 usd")

    def test_remove_constraint_is_immutable_and_exhaustive(self):
        constraints = {
            "budget": 7.0, "budget_currency": "usd",
            "dietary_requirements": ["vegetarian"],
            "allergies": ["peanut"], "ingredients_to_avoid": ["peanut"],
            "other_constraints": [], "intent": "x",
        }
        for reason in ("budget", "diet", "allergy", "ingredient"):
            relaxed = remove_constraint(constraints, reason)
            self.assertEqual(constraints["budget"], 7.0)  # original untouched
        self.assertEqual(remove_constraint(constraints, "budget")["budget"], None)
        self.assertEqual(remove_constraint(constraints, "diet")["dietary_requirements"], [])
        self.assertEqual(remove_constraint(constraints, "allergy")["allergies"], [])
        self.assertEqual(
            remove_constraint(constraints, "ingredient")["ingredients_to_avoid"], []
        )


class DecideTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.data = load_structured_data()

    def _payload(self, constraints, ids):
        results = [
            {
                "item_id": item_id,
                "item_name": str(self.data["menu_items_by_id"][item_id]["item_name"]),
                "rank": rank + 1, "score": 0.5,
                "price": self.data["menu_items_by_id"][item_id]["price"],
            }
            for rank, item_id in enumerate(ids)
        ]
        verdicts = validate_items(results, constraints, data=self.data)
        return {"constraints": constraints, "results": results, **verdicts}

    def _plain_constraints(self, **overrides):
        base = {"budget": None, "budget_currency": None,
                "dietary_requirements": [], "allergies": [],
                "ingredients_to_avoid": [], "intent": "general",
                "other_constraints": []}
        base.update(overrides)
        return base

    def test_decide_recommends_when_valid_items_exist(self):
        ids = list(self.data["menu_items_by_id"])[:10]  # type: ignore[union-attr]
        payload = self._payload(self._plain_constraints(), ids)
        self.assertTrue(payload["valid"])
        decision = decide(payload, constraints=payload["constraints"], data=self.data)
        self.assertEqual(decision["decision"], "recommend")
        self.assertEqual(
            {r["item_name"] for r in decision["ranked"]},
            {r["item_name"] for r in payload["valid"]},
        )

    def test_decide_relaxes_with_zero_valid_and_simulates(self):
        # Menu prices all exceed $0.01, so every retrieved item fails budget.
        ids = list(self.data["menu_items_by_id"])[:5]  # type: ignore[union-attr]
        constraints = self._plain_constraints(budget=0.01, budget_currency="usd",
                                              intent="price_query")
        payload = self._payload(constraints, ids)
        self.assertFalse(payload["valid"])
        decision = decide(payload, constraints=constraints, data=self.data)
        self.assertEqual(decision["decision"], "relax")
        suggestion = decision["relaxation_suggestions"]["budget"]
        # Dropping the $0.01 limit unlocks every retrieved item.
        self.assertEqual(suggestion["relaxed_count"], len(ids))
        self.assertEqual(suggestion["extra"], len(ids))


class RecommendationBranchTests(unittest.TestCase):
    def test_only_valid_items_are_sent_to_the_llm(self):
        captured = {"prompt": []}
        llm = _verbose_responder(captured)
        result = agent_answer(
            "vegetarian meal under 7 dollars without peanuts", k=10, llm=llm
        )
        self.assertEqual(result["decision"], "recommend")
        self.assertTrue(result["ranked"])
        self.assertTrue(result["invalid"])  # invalid options existed and were dropped

        valid_names = {row["item_name"].lower() for row in result["valid"]}
        invalid_names = {row["item_name"].lower() for row in result["invalid"]}
        self.assertEqual(len(captured["prompt"]), 1)
        approved = {name.lower() for name in ITEM_NAME_RE.findall(captured["prompt"][0])}
        self.assertTrue(approved)
        self.assertTrue(approved <= valid_names)
        self.assertFalse(approved & invalid_names)  # nothing dropped slipped back in

        self.assertTrue(result["answer"])
        self.assertTrue(result["llm_used"])

    def test_llm_failure_falls_back_to_template(self):
        def broken(messages, call):
            raise LLMError("model unreachable")

        result = agent_answer(
            "vegetarian meal under 7 dollars without peanuts", k=10, llm=MockLLM(broken)
        )
        self.assertEqual(result["decision"], "recommend")
        self.assertFalse(result["llm_used"])
        self.assertIn("Veg Sandwich", result["answer"])


class NoMatchBranchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.data = load_structured_data()

    def test_impossible_request_explains_and_asks_to_relax(self):
        # A $1 budget cannot match any menu item, so no recommendation is valid.
        result = agent_answer("vegan meal under 1 dollars without soy", k=6)
        self.assertEqual(result["decision"], "relax")
        self.assertTrue(result["blockers"])
        self.assertIn("budget", {b["reason"] for b in result["blockers"]})
        self.assertFalse(result["llm_used"])
        for snippet in ("No item satisfies", "budget", "Would you like to relax"):
            self.assertIn(snippet, result["answer"])

    def test_answer_never_names_a_dish_when_nothing_is_valid(self):
        result = agent_answer("vegan meal under 1 dollars without soy", k=6)
        lowered = result["answer"].lower()
        for item in self.data["menu_items_by_id"].values():  # type: ignore[union-attr]
            self.assertNotIn(str(item["item_name"]).lower(), lowered)


class DirectRoutingTests(unittest.TestCase):
    """Lookup questions must be answered from the database, never turned
    into a food recommendation (the original wrong-answer bug)."""

    def test_price_query_answers_from_database(self):
        result = agent_answer("What is the price of a Margherita Pizza?")
        self.assertEqual(result["decision"], "direct")
        self.assertIn("Margherita", result["answer"])
        self.assertIn("8.99", result["answer"])
        self.assertFalse(result["llm_used"])
        self.assertEqual(result["valid"], [])
        self.assertEqual(result["invalid"], [])

    def test_discount_policy_query_answers_from_database(self):
        result = agent_answer("Do you offer any student discounts?")
        self.assertEqual(result["decision"], "direct")
        lowered = result["answer"].lower()
        self.assertTrue(
            "discount" in lowered or "student" in lowered,
            result["answer"],
        )

    def test_full_menu_query_answers_from_database(self):
        result = agent_answer("Show me the full menu")
        self.assertEqual(result["decision"], "direct")
        self.assertIn("Margherita Pizza", result["answer"])

    def test_vegan_query_stays_in_the_symbolic_loop(self):
        result = agent_answer("Which meals are suitable for vegans?", k=8)
        self.assertEqual(result["decision"], "recommend")
        self.assertTrue(result["ranked"])
        for row in result["ranked"]:
            tags = str(row.get("dietary_tags") or "").lower()
            self.assertIn("vegan", tags, row["item_name"])

    def test_allergy_query_stays_in_the_symbolic_loop(self):
        result = agent_answer(
            "Which dishes are safe for me if I have a peanut allergy?", k=8
        )
        self.assertNotEqual(result["decision"], "direct")
        self.assertTrue(result["constraints"]["allergies"])

    def test_multiple_named_dishes_are_all_answered(self):
        result = agent_answer("Can I get chicken kottu and mushroom soup?")
        self.assertEqual(result["decision"], "direct")
        self.assertIn("Chicken Kottu", result["answer"])
        self.assertIn("Mushroom Soup", result["answer"])
        self.assertNotIn("none of the options below", result["answer"])

    def test_order_total_is_a_lookup_with_prices_and_sum(self):
        result = agent_answer(
            "one chicken kottu, one mushroom soup, one iced tea - total price?"
        )
        self.assertEqual(result["decision"], "direct")
        for item in ("Chicken Kottu", "Mushroom Soup", "Iced Tea"):
            self.assertIn(item, result["answer"])
        self.assertIn("Total: $17.97", result["answer"])

    def test_order_total_honours_quantities(self):
        result = agent_answer("2 chicken kottu and 1 iced tea, give me the total price")
        self.assertEqual(result["decision"], "direct")
        self.assertIn("2 x **Chicken Kottu**", result["answer"])
        self.assertIn("Total: $20.97", result["answer"])


class OrderConversationTests(unittest.TestCase):
    """Follow-up "add X" must extend the running order, not restart lookup."""

    def setUp(self):
        self.order = OrderState()

    def test_add_follow_up_updates_the_total(self):
        first = agent_answer(
            "one chicken kottu, one mushroom soup, one iced tea - total price?",
            llm=None, order=self.order,
        )
        self.assertIn("Total: $17.97", first["answer"])

        second = agent_answer(
            "add one margherita pizza for this menu.", llm=None, order=self.order,
        )
        self.assertIn("Margherita Pizza", second["answer"])
        self.assertIn("Total: $26.96", second["answer"])
        self.assertEqual(len(self.order.items), 4)

    def test_add_merges_a_repeated_item(self):
        agent_answer("one iced tea - total price?", llm=None, order=self.order)
        agent_answer("add two more iced tea", llm=None, order=self.order)
        self.assertEqual(self.order.items[0]["quantity"], 3)

    def test_new_order_request_replaces_the_previous(self):
        agent_answer("one iced tea - total price?", llm=None, order=self.order)
        agent_answer("one chicken kottu - total price?", llm=None, order=self.order)
        self.assertEqual([e["name"] for e in self.order.items], ["Chicken Kottu"])

    def test_remove_and_add_in_one_sentence(self):
        agent_answer(
            "one chicken kottu, one mushroom soup - total price?", llm=None, order=self.order
        )
        agent_answer("add one margherita pizza for this menu.", llm=None, order=self.order)
        third = agent_answer(
            "remove chicken kottu and add two additional iced tea",
            llm=None, order=self.order,
        )
        names = [e["name"] for e in self.order.items]
        self.assertNotIn("Chicken Kottu", names)
        self.assertIn("Margherita Pizza", names)
        iced = next(e for e in self.order.items if e["name"] == "Iced Tea")
        self.assertEqual(iced["quantity"], 2)
        self.assertIn("Total: ", third["answer"])

    def test_remove_alone_empties_the_order(self):
        agent_answer("one iced tea - total price?", llm=None, order=self.order)
        agent_answer("remove the iced tea", llm=None, order=self.order)
        self.assertEqual(self.order.items, [])


if __name__ == "__main__":
    unittest.main(verbosity=2)