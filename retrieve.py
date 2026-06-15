from __future__ import annotations

import ast
import re
from functools import lru_cache
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "DataSources"
SQL_DUMP_PATH = DATA_DIR / "restaurant_conversational_agent_db.sql"
POLICY_TEXT_PATH = DATA_DIR / "Restaurant Policies.txt"

STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "can",
    "do",
    "for",
    "from",
    "how",
    "i",
    "in",
    "is",
    "it",
    "me",
    "my",
    "of",
    "on",
    "or",
    "please",
    "tell",
    "the",
    "to",
    "what",
    "when",
    "where",
    "which",
    "who",
    "why",
    "we",
    "you",
}


@lru_cache(maxsize=1)
def load_policy_lines() -> list[str]:
    return [
        line.strip()
        for line in POLICY_TEXT_PATH.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


@lru_cache(maxsize=1)
def load_structured_data() -> dict[str, object]:
    sql_text = SQL_DUMP_PATH.read_text(encoding="utf-8")

    tables: dict[str, list[dict[str, object]]] = {}
    for table_name in [
        "allergen",
        "dietary_type",
        "ingredient",
        "menu_item",
        "restaurant_policy",
        "item_allergen",
        "item_dietary",
        "menu_ingredient",
    ]:
        tables[table_name] = _parse_insert_table(sql_text, table_name)

    allergens_by_id = {
        int(row["allergen_id"]): str(row["allergen_name"]) for row in tables["allergen"]
    }
    dietary_by_id = {
        int(row["dietary_id"]): str(row["dietary_name"]) for row in tables["dietary_type"]
    }
    ingredients_by_id = {
        int(row["ingredient_id"]): str(row["ingredient_name"]) for row in tables["ingredient"]
    }
    menu_items_by_id = {
        int(row["item_id"]): row for row in tables["menu_item"]
    }
    restaurant_policies = tables["restaurant_policy"]

    item_allergens: dict[int, list[str]] = {}
    for row in tables["item_allergen"]:
        item_id = int(row["item_id"])
        allergen_id = int(row["allergen_id"])
        item_allergens.setdefault(item_id, []).append(allergens_by_id.get(allergen_id, str(allergen_id)))

    item_dietary: dict[int, list[str]] = {}
    for row in tables["item_dietary"]:
        item_id = int(row["item_id"])
        dietary_id = int(row["dietary_id"])
        item_dietary.setdefault(item_id, []).append(dietary_by_id.get(dietary_id, str(dietary_id)))

    item_ingredients: dict[int, list[str]] = {}
    for row in tables["menu_ingredient"]:
        item_id = int(row["item_id"])
        ingredient_id = int(row["ingredient_id"])
        item_ingredients.setdefault(item_id, []).append(
            ingredients_by_id.get(ingredient_id, str(ingredient_id))
        )

    return {
        "tables": tables,
        "allergens_by_id": allergens_by_id,
        "dietary_by_id": dietary_by_id,
        "ingredients_by_id": ingredients_by_id,
        "menu_items_by_id": menu_items_by_id,
        "restaurant_policies": restaurant_policies,
        "item_allergens": item_allergens,
        "item_dietary": item_dietary,
        "item_ingredients": item_ingredients,
    }


def _parse_insert_table(sql_text: str, table_name: str) -> list[dict[str, object]]:
    pattern = re.compile(
        rf"INSERT INTO `{re.escape(table_name)}`\s*\((.*?)\) VALUES\s*(.*?);",
        re.S,
    )
    match = pattern.search(sql_text)
    if not match:
        return []

    columns = [column.strip().strip("`") for column in match.group(1).split(",")]
    values_block = match.group(2).strip()
    if not values_block:
        return []

    rows = ast.literal_eval(f"[{values_block}]")
    parsed_rows: list[dict[str, object]] = []
    for row in rows:
        if not isinstance(row, tuple):
            row = (row,)
        parsed_rows.append(dict(zip(columns, row, strict=False)))
    return parsed_rows


def _normalize_terms(text: str) -> set[str]:
    return {
        term
        for term in re.findall(r"[a-z0-9]+", text.lower())
        if term not in STOPWORDS
    }


def _score_text(query_terms: set[str], text: str) -> tuple[int, int]:
    text_terms = _normalize_terms(text)
    overlap = len(query_terms & text_terms)
    return overlap, -len(text)


def _best_match(query: str, candidates: list[str]) -> str | None:
    if not candidates:
        return None
    query_terms = _normalize_terms(query)
    if not query_terms:
        return candidates[0]
    return max(candidates, key=lambda candidate: _score_text(query_terms, candidate))


def _menu_item_answer(query: str, data: dict[str, object]) -> str | None:
    menu_items = data["menu_items_by_id"]
    query_terms = _normalize_terms(query)

    if not query_terms:
        return None

    if any(word in query_terms for word in {"calorie", "calories", "price", "priced", "cost", "description", "detail", "details", "menu"}):
        best_item = None
        best_score = (-1, 0)
        for item_id, item in menu_items.items():
            item_text = " ".join(
                str(item.get(field, "")) for field in ("item_name", "category", "description")
            )
            score = _score_text(query_terms, item_text)
            if score > best_score:
                best_score = score
                best_item = item

        if best_item is not None and best_score[0] > 0:
            parts = [f"{best_item['item_name']} ({best_item.get('category', 'Unknown')})"]
            if best_item.get("description"):
                parts.append(str(best_item["description"]))
            if best_item.get("price") is not None:
                parts.append(f"Price: ${float(best_item['price']):.2f}")
            if best_item.get("calories") is not None:
                parts.append(f"Calories: {best_item['calories']}")
            return " | ".join(parts)

    return None


def _lookup_related_items(query: str, data: dict[str, object]) -> str | None:
    query_terms = _normalize_terms(query)
    menu_items = data["menu_items_by_id"]
    item_allergens = data["item_allergens"]
    item_dietary = data["item_dietary"]
    item_ingredients = data["item_ingredients"]

    def matching_item_names(predicate):
        names: list[str] = []
        for item_id, item in menu_items.items():
            if predicate(item_id):
                names.append(str(item["item_name"]))
        return names

    allergen_terms = {
        "allergen",
        "allergy",
        "allergic",
        "contains",
        "contain",
        "free",
        "safe",
        "peanut",
        "nut",
        "egg",
        "milk",
        "soy",
        "gluten",
        "fish",
        "shellfish",
        "wheat",
        "sesame",
    }
    dietary_terms = {
        "diet",
        "dietary",
        "vegan",
        "vegetarian",
        "halal",
        "kosher",
        "gluten",
        "dairy",
        "nut",
        "soy",
        "egg",
        "fish",
        "shellfish",
        "protein",
        "low",
        "high",
    }

    def exact_name_match(query_text: str, names: list[str]) -> str | None:
        normalized_query = query_text.lower()
        exact_hits = [
            name
            for name in names
            if re.search(rf"\\b{re.escape(name.lower())}\\b", normalized_query)
        ]
        if exact_hits:
            return max(exact_hits, key=len)
        return _best_match(query_text, names)

    if query_terms & allergen_terms:
        target = exact_name_match(query, list(data["allergens_by_id"].values()) + list(data["ingredients_by_id"].values()))
        if target:
            target_lower = target.lower()
            allergen_names = {name.lower() for name in data["allergens_by_id"].values()}
            ingredient_names = {name.lower() for name in data["ingredients_by_id"].values()}

            if target_lower in allergen_names:
                matches = matching_item_names(
                    lambda item_id: target_lower in {value.lower() for value in item_allergens.get(item_id, [])}
                )
                if matches:
                    return f"Items containing {target}: {', '.join(matches)}"

            if target_lower in ingredient_names:
                matches = matching_item_names(
                    lambda item_id: target_lower in {value.lower() for value in item_ingredients.get(item_id, [])}
                )
                if matches:
                    return f"Items containing {target}: {', '.join(matches)}"

    if query_terms & dietary_terms:
        target = exact_name_match(query, list(data["dietary_by_id"].values()))
        if target:
            target_lower = target.lower()
            dietary_names = {name.lower() for name in data["dietary_by_id"].values()}
            if target_lower in dietary_names:
                matches = matching_item_names(
                    lambda item_id: target_lower in {value.lower() for value in item_dietary.get(item_id, [])}
                )
                if matches:
                    return f"Items matching {target}: {', '.join(matches)}"

    return None


def _policy_answer(query: str, data: dict[str, object]) -> str:
    policy_lines = load_policy_lines()
    policy_rows = data["restaurant_policies"]
    candidates = policy_lines + [
        f"{row['policy_name']}: {row['policy_description']}"
        for row in policy_rows
        if row.get("policy_description")
    ]
    best = _best_match(query, candidates)
    return best or "No matching policy found."


def get_answer(query: str) -> str:
    data = load_structured_data()
    query_lower = query.lower().strip()
    structured_keywords = {
        "allergen",
        "allergy",
        "allergic",
        "ingredient",
        "menu",
        "item",
        "items",
        "diet",
        "dietary",
        "vegan",
        "vegetarian",
        "halal",
        "kosher",
        "contains",
        "contain",
        "calorie",
        "calories",
        "price",
        "cost",
    }
    policy_keywords = {
        "policy",
        "policies",
        "rule",
        "rules",
        "outside food",
        "smoking",
        "reservation",
        "pet",
        "parking",
        "refund",
        "refunds",
    }

    is_structured_query = any(word in query_lower for word in structured_keywords)
    is_policy_query = any(word in query_lower for word in policy_keywords)

    structured_answer = _lookup_related_items(query_lower, data)
    if structured_answer:
        return structured_answer

    menu_answer = _menu_item_answer(query_lower, data)
    if menu_answer:
        return menu_answer

    if is_structured_query:
        return "No matching structured record found."

    if is_policy_query:
        return _policy_answer(query_lower, data)

    # Default to a broad policy match so the assistant still returns a useful answer.
    return _policy_answer(query_lower, data)


if __name__ == "__main__":
    query = input("Enter your query: ").strip()
    if query:
        print(get_answer(query))
