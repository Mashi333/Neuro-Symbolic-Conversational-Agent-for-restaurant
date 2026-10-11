"""Tests for the retrieval evaluation metrics.

Every expected value below is worked out by hand from the toy example:

    retrieved (top-5) = [A, B, C, D, E]
    relevant set      = {B, X, Y}          (only B is retrieved)

    rank of first relevant item = 2  ->  RR = 1/2

Run:  python test_evaluation.py
"""

from __future__ import annotations

import unittest

from evaluate_retrieval import (
    evaluate_query,
    hit_at_k,
    macro_average,
    precision_at_k,
    recall_at_k,
    reciprocal_rank,
)

RETRIEVED = ["A", "B", "C", "D", "E"]
RELEVANT = {"B", "X", "Y"}


class MetricTestCase(unittest.TestCase):
    def test_precision_at_k(self) -> None:
        self.assertEqual(precision_at_k(RETRIEVED, RELEVANT, 1), 0.0)
        self.assertAlmostEqual(precision_at_k(RETRIEVED, RELEVANT, 3), 1 / 3)
        self.assertAlmostEqual(precision_at_k(RETRIEVED, RELEVANT, 5), 1 / 5)

    def test_recall_at_k(self) -> None:
        self.assertEqual(recall_at_k(RETRIEVED, RELEVANT, 1), 0.0)
        self.assertAlmostEqual(recall_at_k(RETRIEVED, RELEVANT, 3), 1 / 3)
        self.assertAlmostEqual(recall_at_k(RETRIEVED, RELEVANT, 5), 1 / 3)

    def test_hit_at_k(self) -> None:
        self.assertEqual(hit_at_k(RETRIEVED, RELEVANT, 1), 0.0)
        self.assertEqual(hit_at_k(RETRIEVED, RELEVANT, 3), 1.0)
        self.assertEqual(hit_at_k(RETRIEVED, RELEVANT, 5), 1.0)

    def test_reciprocal_rank(self) -> None:
        self.assertEqual(reciprocal_rank(RETRIEVED, RELEVANT, 5), 0.5)
        self.assertEqual(reciprocal_rank(["A", "B"], RELEVANT, 1), 0.0)
        self.assertEqual(reciprocal_rank(["B", "A"], RELEVANT, 5), 1.0)
        self.assertEqual(reciprocal_rank(["A", "C"], RELEVANT, 5), 0.0)

    def test_perfect_ranking(self) -> None:
        scores = evaluate_query(["B", "X", "Y", "A", "C"], RELEVANT)
        self.assertEqual(scores["precision@1"], 1.0)
        self.assertEqual(scores["recall@3"], 1.0)
        self.assertEqual(scores["hit@5"], 1.0)
        self.assertEqual(scores["reciprocal_rank"], 1.0)

    def test_total_miss(self) -> None:
        scores = evaluate_query(["A", "C", "D", "E", "F"], RELEVANT)
        for key, value in scores.items():
            self.assertEqual(value, 0.0, f"{key} should be 0 on a total miss")

    def test_evaluate_query_keys(self) -> None:
        scores = evaluate_query(RETRIEVED, RELEVANT)
        expected_keys = {
            "precision@1", "precision@3", "precision@5",
            "recall@1", "recall@3", "recall@5",
            "hit@1", "hit@3", "hit@5",
            "reciprocal_rank",
        }
        self.assertEqual(set(scores), expected_keys)

    def test_macro_average(self) -> None:
        rows = [
            {"scores": {"precision@5": 1.0, "reciprocal_rank": 1.0}},
            {"scores": {"precision@5": 0.0, "reciprocal_rank": 0.5}},
        ]
        average = macro_average(rows)
        self.assertEqual(average["precision@5"], 0.5)
        self.assertEqual(average["reciprocal_rank"], 0.75)

    def test_gold_sets_are_valid(self) -> None:
        """Every dataset query must have a non-empty expected set."""
        import json

        from evaluate_retrieval import DATASET_PATH

        dataset = json.loads(DATASET_PATH.read_text(encoding="utf-8"))
        self.assertGreaterEqual(len(dataset["queries"]), 20)
        names = set()
        for entry in dataset["queries"]:
            self.assertGreater(len(entry["expected_items"]), 0, entry["id"])
            names.update(entry["expected_items"])
        self.assertLessEqual(len(names), 100, "gold sets must be menu item names")


if __name__ == "__main__":
    unittest.main(verbosity=2)
