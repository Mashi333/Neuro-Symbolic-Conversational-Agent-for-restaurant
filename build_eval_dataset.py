"""Build the retrieval evaluation dataset (gold standard).

Derives the expected ("relevant") menu items for every evaluation query
directly from the relational database, so the gold standard is transparent
and reproducible, then freezes them into
evaluation/retrieval_test_dataset.json.

Gold definitions used in the dataset:
    vegetarian          -> dietary tag "Vegetarian"
    vegan / plant based -> dietary tag "Vegan" or "Plant Based"
    budget              -> price below the stated threshold
    allergy (gluten)    -> no Wheat/Gluten allergen declared
    allergy (shellfish) -> no Shellfish/Shrimp/Crab/Lobster/Mollusks allergen
    ingredient          -> ingredient name contains the word
    multiple            -> intersection of the constraint sets
    preference          -> menu category / cuisine family

Run:  python build_eval_dataset.py
"""

from __future__ import annotations

import json
from pathlib import Path

from retrieve import load_structured_data

OUTPUT_PATH = Path(__file__).resolve().parent / "evaluation" / "retrieval_test_dataset.json"

SHELLFISH_ALLERGENS = {"Shellfish", "Shrimp", "Crab", "Lobster", "Mollusks"}


def main() -> None:
    data = load_structured_data()
    items = data["menu_items_by_id"]
    dietary: dict[int, list[str]] = data["item_dietary"]
    allergens: dict[int, list[str]] = data["item_allergens"]
    ingredients: dict[int, list[str]] = data["item_ingredients"]

    def names(ids: list[int]) -> list[str]:
        return sorted(str(items[i]["item_name"]) for i in ids)

    def price(i: int) -> float:
        return float(items[i]["price"])  # type: ignore[arg-type]

    def category(i: int) -> str:
        return str(items[i]["category"] or "")

    all_ids = sorted(items)

    vegetarian = [i for i in all_ids if "Vegetarian" in dietary.get(i, [])]
    vegan = [
        i for i in all_ids
        if "Vegan" in dietary.get(i, []) or "Plant Based" in dietary.get(i, [])
    ]
    high_protein = [i for i in all_ids if "High Protein" in dietary.get(i, [])]

    under_5 = [i for i in all_ids if price(i) <= 5.00]
    under_6 = [i for i in all_ids if price(i) <= 6.00]
    under_7 = [i for i in all_ids if price(i) <= 7.00]

    no_gluten = [
        i for i in all_ids
        if not ({"Wheat", "Gluten"} & set(allergens.get(i, [])))
    ]
    no_shellfish = [
        i for i in all_ids
        if not (SHELLFISH_ALLERGENS & set(allergens.get(i, [])))
    ]

    chicken = [i for i in all_ids if any("Chicken" in x for x in ingredients.get(i, []))]
    cheese = [i for i in all_ids if any("Cheese" in x for x in ingredients.get(i, []))]
    rice = [
        i for i in all_ids
        if category(i) == "Rice" or any("Rice" in x for x in ingredients.get(i, []))
    ]

    seafood = [
        i for i in all_ids
        if category(i) == "Seafood"
        or ({"Fish", "Shellfish", "Shrimp", "Crab", "Lobster", "Mollusks"}
            & set(allergens.get(i, [])))
    ]
    dessert = [i for i in all_ids if category(i) == "Dessert"]

    def intersect(*groups: list[int]) -> list[int]:
        result = set(groups[0])
        for group in groups[1:]:
            result &= set(group)
        return sorted(result)

    queries = [
        ("RQ01", "Vegetarian", "vegetarian meal options",
         'dietary tag "Vegetarian"', vegetarian),
        ("RQ02", "Vegetarian", "I don't eat meat, what can I order?",
         'dietary tag "Vegetarian"', vegetarian),

        ("RQ03", "Vegan", "vegan dishes on the menu",
         'dietary tag "Vegan" or "Plant Based"', vegan),
        ("RQ04", "Vegan", "anything plant based and free of dairy?",
         'dietary tag "Vegan" or "Plant Based"', vegan),

        ("RQ05", "Budget", "meals under $6", "price <= 6.00", under_6),
        ("RQ06", "Budget", "what is the cheapest food you serve?",
         "price <= 5.00", under_5),
        ("RQ07", "Budget", "my budget is tight, anything below seven dollars?",
         "price <= 7.00", under_7),

        ("RQ08", "Allergy", "I have a gluten allergy, what can I eat?",
         "no Wheat or Gluten allergen declared", no_gluten),
        ("RQ09", "Allergy", "dishes without shellfish for my allergy",
         "no shellfish-family allergen declared", no_shellfish),
        ("RQ10", "Allergy", "gluten free dessert options",
         "Dessert category without Wheat/Gluten", intersect(dessert, no_gluten)),

        ("RQ11", "Ingredients", "dishes with chicken",
         'ingredient name contains "Chicken"', chicken),
        ("RQ12", "Ingredients", "meals containing cheese",
         'ingredient name contains "Cheese"', cheese),
        ("RQ13", "Ingredients", "what rice dishes do you have?",
         'category "Rice" or ingredient contains "Rice"', rice),

        ("RQ14", "Multiple Constraints", "vegetarian meal under $6",
         'Vegetarian tag AND price <= 6.00', intersect(vegetarian, under_6)),
        ("RQ15", "Multiple Constraints", "vegan and gluten free options",
         'Vegan/Plant Based tag AND no Wheat/Gluten', intersect(vegan, no_gluten)),
        ("RQ16", "Multiple Constraints", "cheap high protein food under $6",
         'High Protein tag AND price <= 6.00', intersect(high_protein, under_6)),

        ("RQ17", "Restaurant Preference", "I feel like seafood today",
         'category "Seafood" or fish/shellfish allergen', seafood),
        ("RQ18", "Restaurant Preference", "something sweet, do you have desserts?",
         'category "Dessert"', dessert),

        ("RQ19", "Natural Language Variation", "i'm in the mood for veggies, nothing meaty",
         'dietary tag "Vegetarian"', vegetarian),
        ("RQ20", "Natural Language Variation", "broke student here, feed me for under five bucks",
         "price <= 5.00", under_5),
        ("RQ21", "Natural Language Variation", "my friend can't eat wheat, is anything safe for her?",
         "no Wheat or Gluten allergen declared", no_gluten),
    ]

    dataset = {
        "name": "restaurant-rag-retrieval-eval",
        "version": 1,
        "relevance_pool": "menu_item documents (doc_type = menu_item)",
        "queries": [
            {
                "id": query_id,
                "category": category_name,
                "query": query,
                "gold_definition": definition,
                "expected_items": names(gold_ids),
                "expected_count": len(gold_ids),
            }
            for query_id, category_name, query, definition, gold_ids in queries
        ],
    }

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(
        json.dumps(dataset, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    print(f"Wrote {len(queries)} queries to {OUTPUT_PATH}")
    for query_id, category_name, query, definition, gold_ids in queries:
        print(f"  {query_id} [{category_name:24}] gold={len(gold_ids):3}  {query}")


if __name__ == "__main__":
    main()
