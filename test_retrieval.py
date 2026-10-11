"""Step 9 - Test semantic retrieval (RAG) independently.

Checks the retrieval pipeline on its own, before any LLM or ASP is added:
embedding -> vector search -> top-K results with similarity scores.

Run:  python test_retrieval.py
"""

from __future__ import annotations

import unittest

from semantic_retrieval import (
    COLLECTION_NAME,
    EMBEDDING_MODEL,
    build_index,
    get_embedding_model,
    semantic_search,
)

TEST_QUERY = "I want a cheap vegetarian meal."


class SemanticRetrievalTestCase(unittest.TestCase):
    collection = None

    @classmethod
    def setUpClass(cls) -> None:
        cls.collection = build_index()

    def test_index_holds_all_documents(self) -> None:
        self.assertEqual(self.collection.name, COLLECTION_NAME)
        self.assertEqual(self.collection.count(), 260)

    def test_embedding_model_matches_index(self) -> None:
        model = get_embedding_model()
        vector = model.embed_query("vegetarian meal")
        self.assertEqual(len(vector), 384, "all-MiniLM-L6-v2 produces 384-dim vectors")
        self.assertAlmostEqual(sum(x * x for x in vector) ** 0.5, 1.0, places=3)

    def test_returns_requested_number_of_results(self) -> None:
        matches = semantic_search(TEST_QUERY, k=5, doc_type="menu_item")
        self.assertEqual(len(matches), 5)
        self.assertEqual([m["rank"] for m in matches], [1, 2, 3, 4, 5])

    def test_scores_sorted_and_bounded(self) -> None:
        matches = semantic_search(TEST_QUERY, k=5, doc_type="menu_item")
        scores = [m["score"] for m in matches]
        for score in scores:
            self.assertGreaterEqual(score, -1.0)
            self.assertLessEqual(score, 1.0)
        self.assertEqual(scores, sorted(scores, reverse=True), "scores must rank best-first")
        for match in matches:
            self.assertAlmostEqual(match["score"], 1.0 - match["distance"], places=6)

    def test_menu_only_results_carry_menu_metadata(self) -> None:
        matches = semantic_search(TEST_QUERY, k=5, doc_type="menu_item")
        for match in matches:
            self.assertEqual(match["metadata"]["doc_type"], "menu_item")
            self.assertTrue(match["metadata"].get("item_name"))
            for field in ("Price:", "Calories:", "Category:"):
                self.assertIn(field, match["content"])

    def test_vegetarian_query_finds_vegetarian_dishes(self) -> None:
        matches = semantic_search("vegetarian meal options", k=5, doc_type="menu_item")
        hits = [m for m in matches if "Vegetarian" in m["content"]]
        self.assertGreaterEqual(len(hits), 3, "at least 3 of top 5 should be vegetarian")

    def test_allergy_query_finds_allergen_info(self) -> None:
        matches = semantic_search("peanut allergy what is safe", k=5, doc_type="all")
        contents = " ".join(m["content"].lower() + str(m["metadata"]).lower() for m in matches)
        self.assertTrue(
            "allergen" in contents or "allerg" in contents,
            "results should mention allergens",
        )

    def test_same_query_is_deterministic(self) -> None:
        first = semantic_search(TEST_QUERY, k=3, doc_type="menu_item")
        second = semantic_search(TEST_QUERY, k=3, doc_type="menu_item")
        self.assertEqual(
            [m["metadata"]["item_name"] for m in first],
            [m["metadata"]["item_name"] for m in second],
        )
        self.assertEqual([m["score"] for m in first], [m["score"] for m in second])

    def test_model_name_is_the_selected_one(self) -> None:
        self.assertEqual(EMBEDDING_MODEL, "sentence-transformers/all-MiniLM-L6-v2")


if __name__ == "__main__":
    unittest.main(verbosity=2)
