"""Step - Evaluate retrieval quality of the restaurant RAG system.

For every query in evaluation/retrieval_test_dataset.json the retriever
returns the top-5 menu items; the evaluator then checks how many of them
are in the query's gold ("expected_items") set.

Metrics (K in {1, 3, 5}):
    Precision@K = relevant items in top-K / K
    Recall@K    = relevant items in top-K / total relevant items
    Hit@K       = 1 if at least one relevant item in top-K, else 0
    MRR@5       = mean of 1 / (rank of first relevant item), 0 if none in top-5

Run:  python evaluate_retrieval.py
"""

from __future__ import annotations

import json
from pathlib import Path

from semantic_retrieval import semantic_search

EVAL_DIR = Path(__file__).resolve().parent / "evaluation"
DATASET_PATH = EVAL_DIR / "retrieval_test_dataset.json"
RESULTS_PATH = EVAL_DIR / "retrieval_results.json"

K_VALUES = (1, 3, 5)
MAX_K = max(K_VALUES)


# ---------------------------------------------------------------- metrics

def precision_at_k(retrieved: list[str], relevant: set[str], k: int) -> float:
    """How many of the top-K results are relevant (divided by K)."""
    if k <= 0:
        return 0.0
    hits = sum(1 for item in retrieved[:k] if item in relevant)
    return hits / k


def recall_at_k(retrieved: list[str], relevant: set[str], k: int) -> float:
    """How many of ALL relevant items were found in the top-K."""
    if not relevant:
        return 0.0
    hits = sum(1 for item in retrieved[:k] if item in relevant)
    return hits / len(relevant)


def hit_at_k(retrieved: list[str], relevant: set[str], k: int) -> float:
    """1.0 when the top-K contains at least one relevant item, else 0.0."""
    return 1.0 if any(item in relevant for item in retrieved[:k]) else 0.0


def reciprocal_rank(retrieved: list[str], relevant: set[str], k: int) -> float:
    """1 / rank of the first relevant item (1.0, 0.5, 0.33, ...)."""
    for rank, item in enumerate(retrieved[:k], start=1):
        if item in relevant:
            return 1.0 / rank
    return 0.0


# ---------------------------------------------------------------- helpers

def evaluate_query(retrieved: list[str], relevant: set[str]) -> dict:
    """All metrics for one query, evaluated at K = 1, 3 and 5."""
    scores: dict[str, float] = {}
    for k in K_VALUES:
        scores[f"precision@{k}"] = precision_at_k(retrieved, relevant, k)
        scores[f"recall@{k}"] = recall_at_k(retrieved, relevant, k)
        scores[f"hit@{k}"] = hit_at_k(retrieved, relevant, k)
    scores["reciprocal_rank"] = reciprocal_rank(retrieved, relevant, MAX_K)
    return scores


def macro_average(rows: list[dict]) -> dict[str, float]:
    """Average each metric across queries (every query counts equally)."""
    if not rows:
        return {}
    keys = rows[0]["scores"].keys()
    return {key: sum(row["scores"][key] for row in rows) / len(rows) for key in keys}


def format_table(rows: list[dict]) -> str:
    header = (
        f"{'ID':6} {'Category':26} {'P@1':>6} {'P@3':>6} {'P@5':>6} "
        f"{'R@3':>6} {'R@5':>6} {'Hit@5':>6} {'RR':>6}"
    )
    lines = [header, "-" * len(header)]
    for row in rows:
        s = row["scores"]
        lines.append(
            f"{row['id']:6} {row['category']:26} "
            f"{s['precision@1']:6.3f} {s['precision@3']:6.3f} {s['precision@5']:6.3f} "
            f"{s['recall@3']:6.3f} {s['recall@5']:6.3f} {s['hit@5']:6.3f} "
            f"{s['reciprocal_rank']:6.3f}"
        )
    return "\n".join(lines)


def format_summary(rows: list[dict]) -> str:
    overall = macro_average(rows)
    lines = ["", "OVERALL (macro-average over 21 queries)", "-" * 58]
    for k in K_VALUES:
        lines.append(
            f"  Precision@{k}: {overall[f'precision@{k}']:.3f}   "
            f"Recall@{k}: {overall[f'recall@{k}']:.3f}   "
            f"Hit@{k}: {overall[f'hit@{k}']:.3f}"
        )
    lines.append(f"  MRR@{MAX_K}: {overall['reciprocal_rank']:.3f}")

    categories: dict[str, list[dict]] = {}
    for row in rows:
        categories.setdefault(row["category"], []).append(row)
    lines += ["", "PER CATEGORY", "-" * 58]
    lines.append(
        f"{'Category':28} {'P@5':>7} {'R@5':>7} {'Hit@5':>7} {'MRR':>7} {'n':>4}"
    )
    for category, group in categories.items():
        avg = macro_average(group)
        lines.append(
            f"{category:28} {avg['precision@5']:7.3f} {avg['recall@5']:7.3f} "
            f"{avg['hit@5']:7.3f} {avg['reciprocal_rank']:7.3f} {len(group):4}"
        )
    return "\n".join(lines)


# ---------------------------------------------------------------- runner

def main() -> None:
    dataset = json.loads(DATASET_PATH.read_text(encoding="utf-8"))

    rows: list[dict] = []
    for entry in dataset["queries"]:
        retrieved = [
            match["metadata"].get("item_name", "")
            for match in semantic_search(entry["query"], k=MAX_K, doc_type="menu_item")
        ]
        relevant = set(entry["expected_items"])
        rows.append(
            {
                "id": entry["id"],
                "category": entry["category"],
                "query": entry["query"],
                "gold_definition": entry["gold_definition"],
                "expected_count": entry["expected_count"],
                "retrieved": retrieved,
                "scores": evaluate_query(retrieved, relevant),
            }
        )

    print("RETRIEVAL EVALUATION - top-5 menu items per query\n")
    print(format_table(rows))
    print(format_summary(rows))

    output = {
        "dataset": dataset["name"],
        "k_values": list(K_VALUES),
        "overall": macro_average(rows),
        "per_query": rows,
    }
    RESULTS_PATH.write_text(
        json.dumps(output, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(f"\nFull results saved to {RESULTS_PATH}")


if __name__ == "__main__":
    main()
