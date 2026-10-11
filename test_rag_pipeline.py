"""Tests for step 12 - LLM -> RAG pipeline.

Verifies the retrieval query is built from extracted constraints and that
every retrieved result is a REAL menu item from the database (the LLM's
structure never leaks into the item list).

Run:  python test_rag_pipeline.py
"""

from __future__ import annotations

import json
import unittest

from intent_extractor import default_output
from llm_client import MockLLM
from rag_pipeline import build_retrieval_query, retrieve_for_query
from retrieve import load_structured_data
from semantic_retrieval import build_index

EXAMPLE_QUERY = "I want a vegetarian meal under Rs. 1500 without peanuts."


class BuildRetrievalQueryTestCase(unittest.TestCase):
    def test_uses_positive_constraints(self) -> None:
        out = default_output()
        out.update(
            {
                "intent": "restaurant_recommendation",
                "restaurant_preference": "spicy",
                "dietary_requirements": ["vegetarian"],
                "ingredients_preferred": ["chicken"],
            }
        )
        query = build_retrieval_query(out)
        self.assertIn("recommend a meal", query)
        self.assertIn("spicy", query)
        self.assertIn("vegetarian", query)
        self.assertIn("chicken", query)

    def test_negatives_are_phrased_not_injected(self) -> None:
        out = default_output()
        out["allergies"] = ["peanut"]
        out["ingredients_to_avoid"] = ["shellfish"]
        query = build_retrieval_query(out)
        self.assertIn("without peanut", query)
        self.assertIn("without shellfish", query)

    def test_budget_stays_out_of_the_query_string(self) -> None:
        out = default_output()
        out["budget"] = 1500.0
        out["budget_currency"] = "inr"
        query = build_retrieval_query(out)
        self.assertIn("budget friendly", query)
        self.assertNotIn("1500", query)
        self.assertNotIn("inr", query)

    def test_other_constraints_are_carried_over(self) -> None:
        out = default_output()
        out["other_constraints"] = ["under 600 calories"]
        self.assertIn("under 600 calories", build_retrieval_query(out))

    def test_empty_constraints_still_produce_a_query(self) -> None:
        self.assertTrue(build_retrieval_query(default_output()).strip())

    def test_no_duplicate_tokens(self) -> None:
        out = default_output()
        out["allergies"] = ["peanut"]
        out["ingredients_to_avoid"] = ["peanut"]
        query = build_retrieval_query(out)
        self.assertEqual(query.count("without peanut"), 1)

    def test_negative_words_not_in_preferred_position(self) -> None:
        """The query must not place 'peanut' as a plain term that ranks
        peanut-containing documents higher."""
        out = default_output()
        out["allergies"] = ["peanut"]
        query = build_retrieval_query(out)
        self.assertNotIn("peanut options", query)
        self.assertNotIn("peanut meal", query)


class RAGPipelineTestCase(unittest.TestCase):
    db = None

    @classmethod
    def setUpClass(cls) -> None:
        cls.db = load_structured_data()
        build_index()

    def test_pipeline_returns_expected_shape(self) -> None:
        payload = retrieve_for_query(EXAMPLE_QUERY, llm=None)
        self.assertEqual(payload["user_query"], EXAMPLE_QUERY)
        self.assertEqual(payload["top_k"], 5)
        self.assertEqual(payload["constraints"]["method"], "fallback")
        self.assertIsInstance(payload["retrieval_query"], str)
        self.assertEqual(len(payload["results"]), 5)

    def test_scores_are_sorted_descending(self) -> None:
        payload = retrieve_for_query(EXAMPLE_QUERY, llm=None)
        scores = [row["score"] for row in payload["results"]]
        self.assertEqual(scores, sorted(scores, reverse=True))

    def test_results_are_real_database_items(self) -> None:
        """The LLM/retriever must never fabricate menu information."""
        payload = retrieve_for_query(EXAMPLE_QUERY, llm=None)
        real_names = {
            str(item["item_name"]) for item in self.db["menu_items_by_id"].values()
        }
        real_descriptions = {
            str(item["item_name"]): str(item["description"])
            for item in self.db["menu_items_by_id"].values()
        }
        for row in payload["results"]:
            self.assertIn(row["item_name"], real_names, "invented item name!")
            self.assertEqual(
                row["description"],
                real_descriptions[row["item_name"]],
                "invented description!",
            )
            self.assertTrue(row["price"].startswith("$"))
            self.assertTrue(row["calories"].endswith("kcal"))

    def test_llm_constraints_reach_retrieval_query(self) -> None:
        """With a mock LLM that answers, the pipeline must use those answers."""

        def responder(messages, n):
            return json.dumps(
                {
                    "intent": "restaurant_recommendation",
                    "restaurant_preference": None,
                    "budget": 1500.0,
                    "budget_currency": "inr",
                    "dietary_requirements": ["vegetarian"],
                    "allergies": ["peanut"],
                    "ingredients_to_avoid": [],
                    "ingredients_preferred": [],
                    "other_constraints": [],
                }
            )

        payload = retrieve_for_query(EXAMPLE_QUERY, k=3, llm=MockLLM(responder))
        self.assertEqual(payload["constraints"]["method"], "llm")
        self.assertIn("vegetarian", payload["retrieval_query"])
        self.assertIn("without peanut", payload["retrieval_query"])
        self.assertEqual(len(payload["results"]), 3)

    def test_llm_payload_is_structure_only(self) -> None:
        """The constraints output must only contain schema fields."""
        payload = retrieve_for_query(EXAMPLE_QUERY, llm=None)
        from intent_extractor import default_output

        extra_keys = set(payload["constraints"]) - set(default_output()) - {"method", "warnings"}
        self.assertEqual(extra_keys, set())


    def test_vegan_query_surfaces_vegan_items_in_top_k(self) -> None:
        """Diet queries used to lose every vegan item in the top-6 because
        the generic intent filler drowned the diet term in the embedding."""
        vegan_ids = {
            item_id
            for item_id, tags in self.db["item_dietary"].items()
            if any(str(tag).lower() == "vegan" for tag in tags)
        }
        constraints = default_output()
        constraints.update(
            {
                "intent": "restaurant_recommendation",
                "dietary_requirements": ["vegan"],
            }
        )
        payload = retrieve_for_query(
            "Which meals are suitable for vegans?",
            k=8,
            llm=None,
            constraints=constraints,
        )
        self.assertEqual(len(payload["results"]), 8)
        hits = sum(
            1 for row in payload["results"] if row["item_id"] in vegan_ids
        )
        self.assertGreaterEqual(hits, 6, f"only {hits}/8 retrieved items are vegan")

    def test_diet_terms_lead_the_retrieval_query(self) -> None:
        out = default_output()
        out.update(
            {
                "intent": "general",
                "dietary_requirements": ["vegan"],
            }
        )
        query = build_retrieval_query(out)
        self.assertTrue(query.startswith("vegan"))
        # The generic filler must not dilute a query that already has a
        # specific term.
        self.assertNotIn("restaurant menu information", query)


if __name__ == "__main__":
    unittest.main(verbosity=2)