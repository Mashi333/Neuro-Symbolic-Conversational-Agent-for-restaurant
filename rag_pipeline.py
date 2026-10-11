"""Step 12 - Connect LLM -> RAG.

The agent pipeline that combines step 11 (constraint extraction) with the
semantic retriever (steps 8-9):

    user query
      -> LLM: intent + constraints          (step 11, never invents facts)
      -> build a retrieval query from them  (this module)
      -> embedding + vector search          (step 8)
      -> top-K menu items from the database (facts come only from the DB)

Guarding rules applied here:
  * The LLM only produces STRUCTURE (intent + constraints). It never lists
    dishes, prices or policies.
  * Every retrieved item is a real row of the vector index, which was built
    exclusively from the database dump and knowledge files.
  * Negative constraints (allergies, ingredients to avoid) are phrased as
    "without X" in the retrieval query, but the STRICT exclusion checks are
    intentionally left to the later ASP/validation stage, because embeddings
    cannot express "must NOT contain".

Run:  python rag_pipeline.py "I want a vegetarian meal under Rs. 1500 without peanuts."
"""

from __future__ import annotations

import argparse
import json

from intent_extractor import extract_constraints
from semantic_retrieval import _content_field, semantic_search

# A short, factual hint per intent that drives what kind of document is wanted.
INTENT_QUERIES = {
    "restaurant_recommendation": "recommend a meal",
    "menu_item_detail": "menu item",
    "dietary_query": "options",
    "allergy_query": "safe options",
    "price_query": "menu prices",
    "policy_query": "restaurant policy",
    "reservation": "reservation",
    "general": "restaurant menu information",
}


def build_retrieval_query(constraints: dict) -> str:
    """Turn extracted constraints into a single search sentence.

    Only POSITIVE signals are used as-is: intent, preference, dietary
    requirements and preferred ingredients. Negative constraints and the
    numeric budget are phrased as soft hints ("without X", "budget friendly")
    because a vector space cannot execute "must NOT contain" or numeric
    thresholds - a later stage applies them exactly.

    Order matters: the diet term leads (it identifies the right
    neighbourhood of the vector space on its own), and the generic
    "general" intent filler is dropped when a specific term is already
    present, because it only dilutes the embedding.
    """
    parts: list[str] = []

    for diet in constraints.get("dietary_requirements", []):
        parts.append(str(diet))

    preference = constraints.get("restaurant_preference")
    if preference:
        parts.append(str(preference))

    for ingredient in constraints.get("ingredients_preferred", []):
        parts.append(str(ingredient))

    intent = constraints.get("intent", "general")
    hint = INTENT_QUERIES.get(intent, INTENT_QUERIES["general"])
    if intent != "general" or not parts:
        parts.append(hint)

    for allergy in constraints.get("allergies", []):
        parts.append(f"without {allergy}")

    for ingredient in constraints.get("ingredients_to_avoid", []):
        parts.append(f"without {ingredient}")

    for constraint in constraints.get("other_constraints", []):
        parts.append(str(constraint))

    if constraints.get("budget") is not None:
        parts.append("budget friendly")

    # Deduplicate while keeping the natural order of appearance.
    return " ".join(dict.fromkeys(parts))


def _menu_item_result(match: dict) -> dict:
    """Pick the stored fields out of a retrieved menu document - nothing else."""
    content = match["content"]
    metadata = match["metadata"]
    return {
        "rank": match["rank"],
        "score": round(match["score"], 4),
        "item_name": metadata.get("item_name"),
        "item_id": metadata.get("item_id"),
        "category": metadata.get("category"),
        "price": _content_field(content, "Price"),
        "calories": _content_field(content, "Calories"),
        "description": _content_field(content, "Description"),
        "dietary_tags": _content_field(content, "Dietary tags"),
        "contains_allergens": _content_field(content, "Contains allergens"),
        "ingredients": _content_field(content, "Ingredients"),
    }


# Fixed score bonus for items carrying a requested dietary tag.
DIETARY_BOOST = 0.15
# Candidate pool size when a diet filter is active: the embedding scores the
# whole document, so the diet word in the query needs a wider pool before the
# top-K cut to reliably surface every tagged item.
DIETARY_POOL_MIN = 40


def _boost_dietary_matches(matches: list[dict], diets: list[str]) -> list[dict]:
    """Hybrid re-rank: items whose text carries a requested diet move up.

    This is a recall aid only - the strict filtering is still done later by
    the ASP, which checks the actual dietary_tag facts of the database.
    """
    boosted: list[dict] = []
    for match in matches:
        enriched = dict(match)
        content = str(match.get("content") or "").lower()
        if any(diet in content for diet in diets):
            enriched["score"] = float(match["score"]) + DIETARY_BOOST
        boosted.append(enriched)
    return sorted(boosted, key=lambda entry: -float(entry["score"]))


def retrieve_for_query(user_query: str, k: int = 5, llm=None,
                       constraints: dict | None = None) -> dict:
    """Full LLM -> RAG pipeline for one user query."""
    # 1. LLM understands the request (structure only, no facts invented).
    #    Callers that already extracted the constraints (e.g. decision_step
    #    for routing) pass them in so extraction happens exactly once.
    if constraints is None:
        constraints = extract_constraints(user_query, llm=llm)

    # 2. Build the vector-search sentence from the extracted constraints.
    retrieval_query = build_retrieval_query(constraints)

    # 3. Embed the retrieval query and search the vector store.
    diets = [str(diet).lower() for diet in constraints.get("dietary_requirements") or []]
    pool_k = max(k * 4, DIETARY_POOL_MIN) if diets else k
    matches = semantic_search(retrieval_query, k=pool_k, doc_type="menu_item")
    if diets:
        matches = _boost_dietary_matches(matches, diets)
    matches = matches[:k]
    for index, match in enumerate(matches, start=1):
        match["rank"] = index

    return {
        "user_query": user_query,
        "constraints": constraints,
        "retrieval_query": retrieval_query,
        "top_k": k,
        "results": [_menu_item_result(match) for match in matches],
    }


def _print_case_study(payload: dict) -> None:
    print("=" * 64)
    print("USER QUERY")
    print("-" * 64)
    print(payload["user_query"])

    print("\nSTEP 1 - EXTRACTED CONSTRAINTS (LLM, structure only)")
    print("-" * 64)
    print(json.dumps(payload["constraints"], indent=2))

    print("\nSTEP 2 - RETRIEVAL QUERY (built from constraints)")
    print("-" * 64)
    print(payload["retrieval_query"])

    print("\nSTEP 3 - RETRIEVED MENU ITEMS (from the vector database, top-5)")
    print("-" * 64)
    for row in payload["results"]:
        print(f"{row['rank']}. similarity={row['score']:.4f} | {row['item_name']}")
        print(f"   Category: {row['category']} | Price: {row['price']} | Calories: {row['calories']}")
        print(f"   Description: {row['description']}")
        if row["dietary_tags"]:
            print(f"   Dietary tags: {row['dietary_tags']}")
        if row["contains_allergens"]:
            print(f"   Contains allergens: {row['contains_allergens']}")
    print("=" * 64)


def main() -> None:
    parser = argparse.ArgumentParser(description="LLM -> RAG agent pipeline")
    parser.add_argument("query", nargs="+", help="user request in natural language")
    parser.add_argument("-k", type=int, default=5, help="number of results (default 5)")
    parser.add_argument("--json", action="store_true", help="print raw JSON result")
    args = parser.parse_args()

    payload = retrieve_for_query(" ".join(args.query), k=args.k)
    if args.json:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    else:
        _print_case_study(payload)


if __name__ == "__main__":
    main()