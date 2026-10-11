"""Step 17 - soft ranking of ASP-valid items.

Hard constraints and soft ranking factors are kept STRICTLY apart:

  * HARD  -> Answer Set Programming (asp_rules.lp). Any item that violates a
             literal of the constraint program is dropped in the ASP step and
             is NEVER ranked. The ranking function only ever receives the
             `valid` partition produced by asp_validation.validate_items, and
             it refuses to anyone who tries to pass it an invalid item
             (ValueError), so a hard violation can not "leak" into the
             recommendation list.

  * SOFT  -> this module. Five factors, each normalised to [0, 1], combined
             with fixed, interpretable weights:

                 similarity    0.40   semantic relevance of the retrieved item
                 price_fit     0.25   how far UNDER the (hard) budget it sits
                 dietary_match 0.15   alignment with soft diet wishes
                 preference    0.15   preferred ingredients / free-text wishes
                 restaurant    0.05   cuisine / menu-category preference

             total = sum(weight_i * factor_i); ties broken by price (cheaper
             first), then name. The per-factor scores are kept on every row so
             the final ranking is fully explainable.

The DB we rank against is a single restaurant, so "restaurant preference" is
realised as a cuisine/menu-category preference (the `category` column of
menu_item).
"""

from __future__ import annotations

import argparse
import re

from asp_validation import retrieve_and_validate
from asp_reasoner import budget_to_usd
from retrieve import load_structured_data

WEIGHTS: dict[str, float] = {
    "similarity": 0.40,
    "price_fit": 0.25,
    "dietary_match": 0.15,
    "preference": 0.15,
    "restaurant": 0.05,
}

# Soft diet wishes that can be checked against real data fields.
LOW_CALORIE_THRESHOLD = 350  # kcal per serving
HIGH_PROTEIN_TERMS = {"chicken", "beef", "egg", "paneer", "seafood", "fish", "shrimp"}
PLANT_BASED_TAGS = {"plant based", "vegan", "vegetarian"}


# ------------------------------------------------------------- normalisation

def _norm(value: object) -> str:
    return re.sub(r"[^a-z0-9 ]", " ", str(value or "").lower())


def _tokens(value: object) -> set[str]:
    return {t for t in _norm(value).split() if t}


def _price_dollars(price: object) -> float | None:
    if isinstance(price, (int, float)):
        return float(price)
    if isinstance(price, str):
        match = re.search(r"\d+(?:\.\d+)?", price)
        return float(match.group(0)) if match else None
    return None


def _item_text(data: dict, item_id: int) -> str:
    item = data["menu_items_by_id"].get(item_id, {})  # type: ignore[union-attr]
    tags = data["item_dietary"].get(item_id, [])  # type: ignore[union-attr]
    ingredients = data["item_ingredients"].get(item_id, [])  # type: ignore[union-attr]
    fields = [
        item.get("item_name"), item.get("category"), item.get("description"),
        *tags, *ingredients,
    ]
    return _norm(" ".join(str(f) for f in fields if f))


# ------------------------------------------------------------- factors

def similarity_score(score: float) -> float:
    """Retrieval score clipped to [0, 1].

    The raw score is used directly (NOT min-max over the valid set): min-max
    would stretch a 0.61 vs 0.60 retrieval gap into a full 1.0 vs 0.0 swing,
    which would let similarity dominate every other factor regardless of the
    configured weight.
    """
    return max(0.0, min(1.0, float(score)))


def price_fit(price: float | None, budget: float | None) -> float:
    """How comfortably the price sits under the (hard) budget: 1 - price/budget.

    All budget-checks are ASP-hard, so here we only trade *head-room against
    value*. No budget -> neutral 0.5 (price must not steer the ranking).
    """
    if budget is None or budget <= 0 or price is None:
        return 0.5
    return max(0.0, min(1.0, 1.0 - price / budget))


def soft_diet_match(data: dict, item_id: int, wishes: list[str]) -> float:
    """Alignment with soft diet wishes (e.g. 'low-calorie', 'healthy')."""
    if not wishes:
        return 0.5
    item = data["menu_items_by_id"].get(item_id, {})  # type: ignore[union-attr]
    calories = item.get("calories")
    text = _item_text(data, item_id)
    hits = 0
    for wish in wishes:
        w = _norm(wish)
        if re.search(r"low[ -]?cal", w):
            if isinstance(calories, (int, float)) and calories <= LOW_CALORIE_THRESHOLD:
                hits += 1
        elif re.search(r"high[ -]?protein", w):
            if text and any(term in text for term in HIGH_PROTEIN_TERMS):
                hits += 1
        elif re.search(r"plant[ -]?based", w):
            tags = {_norm(t) for t in data["item_dietary"].get(item_id, [])}  # type: ignore[union-attr]
            if tags & PLANT_BASED_TAGS:
                hits += 1
        elif _tokens(wish) and _tokens(wish) <= _tokens(text):
            hits += 1
    return hits / len(wishes)


def preference_match(
    data: dict, item_id: int, preferred: list[str], preferences: list[str] | None
) -> float:
    """Explicit preferred ingredients, plus optional free-text preferences."""
    items = [p for p in list(preferred) + (list(preferences or []) if preferences else [])]
    if not items:
        return 0.5
    text = _item_text(data, item_id)
    hit = sum(1 for it in items if _tokens(it) and (_tokens(it) & _tokens(text)))
    return hit / len(items)


def _category_wish(constraints: dict, preferences: list[str] | None) -> str | None:
    phrases = [constraints.get("restaurant_preference")]
    if preferences:
        phrases += list(preferences)
    phrases += list(constraints.get("other_constraints", []) or [])
    for phrase in phrases:
        if not phrase:
            continue
        tokens = _tokens(phrase) - _tokens("restaurant the a an serve serve serving")
        if tokens:
            return next(iter(tokens))
    return None


def restaurant_score(data: dict, item_id: int, wish: str | None) -> float:
    """1.0 when the wished category matches, 0.5 when no wish is expressed."""
    if not wish:
        return 0.5
    item = data["menu_items_by_id"].get(item_id, {})  # type: ignore[union-attr]
    item_category = _norm(item.get("category"))
    if wish in _tokens(item_category):
        return 1.0
    all_text = _item_text(data, item_id)
    return 1.0 if wish in _tokens(all_text) else 0.0


def _resolve_item_id(row: dict, data: dict) -> int | None:
    """Row -> DB item_id, by id or by (lower-cased) item name.

    asp_validation.validate_items partitions rows by name and does not keep
    item_id, so name lookup is the primary resolution path in the real
    pipeline; items that resolve to nothing stay on the neutral factors.
    """
    item_id = row.get("item_id")
    if item_id is not None:
        try:
            return int(item_id)
        except (TypeError, ValueError):
            return None
    name = str(row.get("item_name") or "").strip().lower()
    if not name:
        return None
    for candidate, item in data["menu_items_by_id"].items():  # type: ignore[union-attr]
        if str(item.get("item_name") or "").strip().lower() == name:
            return int(candidate)
    return None


# ------------------------------------------------------------- orchestrator

def score_and_rank(
    valid_rows: list[dict],
    constraints: dict | None = None,
    data: dict | None = None,
    preferences: list[str] | None = None,
    weights: dict[str, float] | None = None,
    validation: dict | None = None,
) -> list[dict]:
    """Score and sort the ASP-valid items; never touches invalid ones.

    `validation` (the asp_validation payload) hard-guards the separation: any
    row whose item_name is not in the ASP `valid` partition raises ValueError,
    so a hard violation can never be ranked. Every row returned carries
    `scores` (one value per factor) and `total`.
    """
    data = data or load_structured_data()
    constraints = constraints or {}
    weights = weights or WEIGHTS

    if validation is not None:
        allowed = {str(r.get("item_name") or "").strip().lower()
                   for r in validation["valid"]}
        for row in valid_rows:
            if str(row.get("item_name") or "").strip().lower() not in allowed:
                raise ValueError(
                    f"hard-constraint violation cannot be ranked: "
                    f"{row.get('item_name')}"
                )

    budget = budget_to_usd(constraints.get("budget"), constraints.get("budget_currency"))[0]
    wishes = list(constraints.get("other_constraints", []) or [])
    preferred = list(constraints.get("ingredients_preferred", []) or [])
    wish_category = _category_wish(constraints, preferences)

    scored = []
    for row in valid_rows:
        item_id = _resolve_item_id(row, data)
        price = _price_dollars(row.get("price"))
        if price is None and item_id is not None:
            item = data["menu_items_by_id"].get(item_id, {})  # type: ignore[union-attr]
            price = _price_dollars(item.get("price"))
        score = row.get("score")
        sim_f = 0.5 if score is None else similarity_score(score)

        scores = {
            "similarity": sim_f,
            "price_fit": price_fit(price, budget),
            "dietary_match": soft_diet_match(data, item_id, wishes) if item_id else 0.5,
            "preference": preference_match(data, item_id, preferred, preferences) if item_id else 0.5,
            "restaurant": restaurant_score(data, item_id, wish_category) if item_id else 0.5,
        }
        total = sum(weights[k] * scores[k] for k in WEIGHTS)
        entry = dict(row)
        entry["scores"] = scores
        entry["total"] = total
        scored.append(entry)

    scored.sort(
        key=lambda r: (-r["total"], _price_dollars(r.get("price")) or float("inf"),
                       _norm(r.get("item_name")))
    )
    return scored


def rank_valid(
    rows: list[dict],
    constraints: dict | None = None,
    data: dict | None = None,
    preferences: list[str] | None = None,
    weights: dict[str, float] | None = None,
    validation: dict | None = None,
) -> list[dict]:
    """Backwards-compatible name; delegates to the weighted scorer."""
    return score_and_rank(rows, constraints, data, preferences, weights, validation)


# ------------------------------------------------------------- CLI

def main() -> None:
    parser = argparse.ArgumentParser(description="Rank ASP-valid options (soft factors)")
    parser.add_argument("query", nargs="+", help="user request in natural language")
    parser.add_argument("-k", type=int, default=10, help="retrieve K items (default 10)")
    parser.add_argument("--json", action="store_true", help="print raw JSON result")
    args = parser.parse_args()

    query = " ".join(args.query)
    payload = retrieve_and_validate(query, k=args.k)
    ranked = score_and_rank(payload["valid"], constraints=payload["constraints"],
                            data=payload.get("data"), validation=payload)

    print(f"USER QUERY : {query}")
    print(f"DECISION   : recommend on {len(ranked)}/{payload['retrieved_count']} "
          f"candidate item(s)\n")
    print(f"{'#':<3} {'item':<22} {'sim':>6} {'budget':>7} {'diet':>6} "
          f"{'pref':>6} {'rest':>6}  total")
    print("-" * 70)
    for position, row in enumerate(ranked, start=1):
        s = row["scores"]
        print(f"{position:<3} {row['item_name'][:21]:<22} {s['similarity']:.3f} "
              f"{s['price_fit']:.3f} {s['dietary_match']:.3f} {s['preference']:.3f} "
              f"{s['restaurant']:.3f}  {row['total']:.3f}")
    print("\nWEIGHTS:", ", ".join(f"{k}={v:g}" for k, v in WEIGHTS.items()))
    if args.json:
        import json as _json

        print(_json.dumps(ranked, indent=2, default=str))


if __name__ == "__main__":
    main()