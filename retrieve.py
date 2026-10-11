from __future__ import annotations

import ast
import re
from functools import lru_cache
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from order_state import OrderState

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "DataSources"
SQL_DUMP_PATH = DATA_DIR / "restaurant_conversational_agent_db.sql"
POLICY_TEXT_PATH = DATA_DIR / "Restaurant Policies.txt"

STOPWORDS = {
    "a",
    "about",
    "accept",
    "accepted",
    "accepts",
    "allow",
    "allowed",
    "also",
    "am",
    "an",
    "and",
    "any",
    "are",
    "available",
    "be",
    "been",
    "can",
    "could",
    "do",
    "does",
    "for",
    "from",
    "get",
    "give",
    "good",
    "has",
    "have",
    "how",
    "i",
    "if",
    "in",
    "is",
    "it",
    "its",
    "like",
    "may",
    "me",
    "might",
    "mine",
    "much",
    "must",
    "my",
    "need",
    "needed",
    "needs",
    "no",
    "not",
    "of",
    "offer",
    "offered",
    "offers",
    "on",
    "one",
    "or",
    "our",
    "please",
    "provide",
    "serve",
    "served",
    "serves",
    "some",
    "tell",
    "the",
    "their",
    "them",
    "then",
    "there",
    "they",
    "this",
    "to",
    "want",
    "was",
    "we",
    "well",
    "what",
    "when",
    "where",
    "which",
    "who",
    "why",
    "will",
    "with",
    "would",
    "you",
    "your",
}

PRICE_UNITS = r"(?P<currency>rs\.?|inr|â‚¹|\$|usd|dollars?|rupees?)?\s*"
PRICE_LIMIT_PREFIXES = (
    "under",
    "below",
    "less than",
    "lower than",
    "within",
    "up to",
    "not more than",
    "no more than",
    "maximum",
    "max",
    "cheaper than",
)
PRICE_LIMIT_PATTERNS = tuple(
    re.compile(rf"\b{re.escape(prefix)}\s+{PRICE_UNITS}(?P<amount>\d+(?:\.\d+)?)", re.IGNORECASE)
    for prefix in PRICE_LIMIT_PREFIXES
)
USD_UNITS = {"$", "usd", "dollar", "dollars"}
SIDE_CATEGORIES = {"Beverage", "Dessert", "Sides", "Appetizer", "Snack"}
NUT_ALLERGENS = (
    "Peanut",
    "Tree Nuts",
    "Almond",
    "Walnut",
    "Cashew",
    "Pistachio",
    "Hazelnut",
    "Pecan",
    "Brazil Nut",
    "Macadamia Nut",
)
FREE_FROM_ALLERGENS = {
    "gluten free": ("Gluten", "Wheat", "Barley", "Rye", "Oats"),
    "wheat free": ("Wheat",),
    "dairy free": ("Milk",),
    "nut free": NUT_ALLERGENS,
    "peanut free": ("Peanut",),
    "egg free": ("Egg",),
    "soy free": ("Soy",),
    "fish free": ("Fish",),
    "shellfish free": ("Shellfish", "Shrimp", "Crab", "Lobster", "Mollusks"),
}
ALLERGEN_ALIASES = {
    "dairy": "Milk",
    "dairy product": "Milk",
    "milk product": "Milk",
    "nut": "Tree Nuts",
    "tree nut": "Tree Nuts",
    "seafood": "Shellfish",
}
GENERIC_QUERY_TERMS = {
    "dish",
    "meal",
    "menu",
    "item",
    "option",
    "recommend",
    "recommendation",
    "suitable",
    "available",
    "today",
    "popular",
    "customer",
    "guest",
    "people",
    "serving",
    "portion",
    "preparation",
    "restaurant",
}


POLICY_TEXT_PATHS = (
    POLICY_TEXT_PATH,
    DATA_DIR / "Discount Policies.txt",
    DATA_DIR / "Restaurant FAQs.txt",
    DATA_DIR / "Allergy Guidelines.txt",
)


@lru_cache(maxsize=1)
def load_policy_lines() -> list[tuple[str, str]]:
    """Return (source_label, policy_line) pairs from every knowledge text file."""
    entries: list[tuple[str, str]] = []
    for path in POLICY_TEXT_PATHS:
        if not path.exists():
            continue
        label = path.stem
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line:
                entries.append((label, line))
    return entries


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


MATCH_PREFIX_LENGTH = 6


def _singular(term: str) -> str:
    if len(term) > 3 and term.endswith("s") and not term.endswith("ss"):
        return term[:-1]
    return term


def _normalize_terms(text: str) -> set[str]:
    """Lowercase words with a trailing plural 's' removed and stopwords dropped."""
    terms: set[str] = set()
    for token in re.findall(r"[a-z0-9]+", text.lower()):
        if token in STOPWORDS:
            continue
        singular = _singular(token)
        if singular in STOPWORDS:
            continue
        terms.add(singular)
    return terms


def _terms_overlap(query_terms: set[str], text_terms: set[str]) -> int:
    """Count shared words, treating words with a shared 6-character stem as equal."""
    overlap = len(query_terms & text_terms)
    matched_prefixes = set()
    for term in query_terms:
        if term in text_terms or len(term) < MATCH_PREFIX_LENGTH:
            continue
        for other in text_terms:
            if len(other) >= MATCH_PREFIX_LENGTH and other[:MATCH_PREFIX_LENGTH] == term[:MATCH_PREFIX_LENGTH]:
                matched_prefixes.add(term[:MATCH_PREFIX_LENGTH])
                break
    return overlap + len(matched_prefixes)


NAME_TOKEN_MAX_ITEMS = 6


def _categories_in_query(query: str, data: dict[str, object]) -> set[str]:
    query_terms = _normalize_terms(query)
    expanded_query_terms = query_terms | {
        term[:MATCH_PREFIX_LENGTH] for term in query_terms if len(term) >= MATCH_PREFIX_LENGTH
    }
    categories = {
        str(item.get("category") or "").lower()
        for item in data["menu_items_by_id"].values()  # type: ignore[union-attr]
    }
    matched = set()
    for category in categories:
        if not category:
            continue
        category_terms = _normalize_terms(category)
        if category_terms and category_terms <= expanded_query_terms:
            matched.add(category)
    return matched


def _items_named_in_query(query: str, data: dict[str, object]) -> list[dict[str, object]]:
    """Return items sharing a distinctive name word with the query (e.g. 'kottu')."""
    query_terms = _normalize_terms(query)
    if not query_terms:
        return []

    frequency: dict[str, int] = {}
    for item in data["menu_items_by_id"].values():  # type: ignore[union-attr]
        for token in _normalize_terms(str(item.get("item_name") or "")):
            frequency[token] = frequency.get(token, 0) + 1

    distinctive = {
        term
        for term in query_terms
        if 0 < frequency.get(term, 0) <= NAME_TOKEN_MAX_ITEMS
    }
    if not distinctive:
        return []

    return [
        item
        for item in data["menu_items_by_id"].values()  # type: ignore[union-attr]
        if distinctive & _normalize_terms(str(item.get("item_name") or ""))
    ]


def _score_text(query_terms: set[str], text: str) -> tuple[int, int]:
    text_terms = _normalize_terms(text)
    return _terms_overlap(query_terms, text_terms), -len(text)


def _best_match(query: str, candidates: list[str], min_overlap: int = 1) -> str | None:
    """Return the highest scoring candidate, or None when nothing matches well enough."""
    if not candidates:
        return None
    query_terms = _normalize_terms(query)
    if not query_terms:
        return candidates[0]
    best = max(candidates, key=lambda candidate: _score_text(query_terms, candidate))
    if _score_text(query_terms, best)[0] < min_overlap:
        return None
    return best


def _price_value(item: dict[str, object]) -> float | None:
    try:
        return float(item.get("price"))  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None


def _format_price(value: object) -> str:
    if value is None or value == "":
        return "Not listed"
    try:
        return f"${float(value):.2f}"
    except (TypeError, ValueError):
        return str(value)


def _format_calories(value: object) -> str:
    if value is None or value == "":
        return "Not listed"
    try:
        return f"{int(float(value))} kcal"
    except (TypeError, ValueError):
        return str(value)


def _sort_items(items: list[dict[str, object]]) -> list[dict[str, object]]:
    def sort_key(item: dict[str, object]) -> tuple[str, float, str]:
        price = _price_value(item)
        return (
            str(item.get("category") or "Other").lower(),
            price if price is not None else float("inf"),
            str(item.get("item_name") or "").lower(),
        )

    return sorted(items, key=sort_key)


def _menu_table(items: list[dict[str, object]]) -> str:
    rows = ["| Item | Category | Price | Calories |", "| :--- | :--- | ---: | ---: |"]
    for item in _sort_items(items):
        rows.append(
            f"| {item.get('item_name')} "
            f"| {item.get('category') or 'Other'} "
            f"| {_format_price(item.get('price'))} "
            f"| {_format_calories(item.get('calories'))} |"
        )
    return "\n".join(rows)


def _item_bullets(items: list[dict[str, object]]) -> str:
    return "\n".join(
        f"- **{item.get('item_name')}** - {_format_price(item.get('price'))}"
        f" ({item.get('category') or 'Other'})"
        for item in _sort_items(items)
    )


def _item_names(items: list[dict[str, object]]) -> list[str]:
    return [str(item.get("item_name")) for item in _sort_items(items)]


def _split_by_course(
    items: list[dict[str, object]],
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    """Split a long result set into real dishes and drink/starter/side extras."""
    mains: list[dict[str, object]] = []
    extras: list[dict[str, object]] = []
    for item in items:
        category = str(item.get("category") or "Other")
        if category in SIDE_CATEGORIES:
            extras.append(item)
        else:
            mains.append(item)
    if not mains:
        return items, []
    return mains, extras


def _item_card(item: dict[str, object], data: dict[str, object]) -> str:
    lines = [f"### {item.get('item_name')}", ""]
    if item.get("description"):
        lines.append(str(item["description"]))
        lines.append("")

    item_id = int(item["item_id"])  # type: ignore[arg-type]
    dietary = data["item_dietary"].get(item_id) or []  # type: ignore[union-attr]
    allergens = data["item_allergens"].get(item_id) or []  # type: ignore[union-attr]
    ingredients = data["item_ingredients"].get(item_id) or []  # type: ignore[union-attr]

    details = [
        f"**Category:** {item.get('category') or 'Other'}",
        f"**Price:** {_format_price(item.get('price'))}",
        f"**Calories:** {_format_calories(item.get('calories'))}",
    ]
    if dietary:
        details.append(f"**Suitable for:** {', '.join(sorted(dietary))}")
    if ingredients:
        details.append(f"**Ingredients:** {', '.join(sorted(ingredients))}")
    if allergens:
        details.append(f"**Contains allergens:** {', '.join(sorted(allergens))}")
    else:
        details.append("**Contains allergens:** None declared")

    lines.extend(f"- {detail}" for detail in details)
    return "\n".join(lines)


def _parse_price_limit(query: str) -> dict[str, object] | None:
    for pattern in PRICE_LIMIT_PATTERNS:
        match = pattern.search(query)
        if not match:
            continue
        try:
            amount = float(match.group("amount"))
        except (TypeError, ValueError):
            continue
        return {
            "limit": amount,
            "matched": match.group(0).strip(),
            "currency": (match.group("currency") or "").lower() or None,
        }
    return None


def _apply_price_limit(
    items: list[dict[str, object]],
    limit_info: dict[str, object] | None,
) -> tuple[list[dict[str, object]], list[str]]:
    if not limit_info:
        return items, []

    limit = float(limit_info["limit"])  # type: ignore[arg-type]
    matched = str(limit_info["matched"])
    currency = limit_info["currency"]

    if currency and str(currency) not in USD_UNITS:
        return items, [
            f"I could not filter by **{matched}** because menu prices are stored in USD "
            "and your budget is in a different currency. Every match is listed below."
        ]

    affordable = [
        item
        for item in items
        if (_price_value(item) is not None and _price_value(item) <= limit)
    ]
    if not affordable:
        cheapest = _sort_items([i for i in items if _price_value(i) is not None])[:5]
        note = f"No matching item is priced at or below **{matched}**."
        if cheapest:
            note += f" The cheapest matches start at {_format_price(cheapest[0].get('price'))}."
        return items, [note]
    if len(affordable) < len(items):
        return affordable, [
            f"Filtered to items at or below **{matched}** "
            f"({len(affordable)} of {len(items)} matches)."
        ]
    return items, [f"All {len(items)} matches are already at or below **{matched}**."]


def _results_block(
    heading: str,
    items: list[dict[str, object]],
    data: dict[str, object],
    *,
    limit_info: dict[str, object] | None = None,
    notes: tuple[str, ...] = (),
    categories: set[str] | None = None,
    as_bullets: bool = False,
) -> str:
    filtered, price_notes = _apply_price_limit(items, limit_info)
    if not filtered:
        return ""

    category_notes: list[str] = []
    if categories:
        in_category = [
            item
            for item in filtered
            if str(item.get("category") or "").lower() in categories
        ]
        if in_category and len(in_category) < len(filtered):
            category_notes.append(
                "Narrowed to the "
                + ", ".join(sorted(name.title() for name in categories))
                + f" category you asked about ({len(in_category)} of {len(filtered)} matches)."
            )
            filtered = in_category

    lines = [f"### {heading}", ""]
    all_notes = list(notes) + category_notes + price_notes
    for note in all_notes:
        lines.append(f"{note}")
        lines.append("")
    lines.append(f"{len(filtered)} item{'s' if len(filtered) != 1 else ''} found:")
    lines.append("")

    if as_bullets:
        lines.append(_item_bullets(filtered))
        return "\n".join(lines)

    mains, extras = _split_by_course(filtered)
    if mains and extras:
        lines.append("**Main dishes**")
        lines.append("")
        lines.append(_menu_table(mains))
        lines.append("")
        lines.append(
            f"**Also matches** ({len(extras)} drinks, starters, sides or desserts): "
            f"{', '.join(_item_names(extras))}"
        )
        return "\n".join(lines)

    lines.append(_menu_table(filtered))
    return "\n".join(lines)


def _full_menu_answer(data: dict[str, object]) -> str:
    groups: dict[str, list[dict[str, object]]] = {}
    for item in data["menu_items_by_id"].values():  # type: ignore[union-attr]
        groups.setdefault(str(item.get("category") or "Other"), []).append(item)

    total = sum(len(items) for items in groups.values())
    lines = [f"### Full Menu", "", f"{total} items across {len(groups)} categories.", ""]
    for category in sorted(groups):
        items = _sort_items(groups[category])
        lines.append(f"**{category}** ({len(items)})")
        lines.append("")
        lines.append(_menu_table(items))
        lines.append("")
    return "\n".join(lines).rstrip()


def _item_name_spans(query: str, data: dict[str, object]) -> list[tuple[int, int, dict[str, object]]]:
    """Every (start, end, item) whose full name is quoted in the query.

    A request can name more than one dish ("chicken kottu and mushroom soup"),
    so all quoted names are returned, in the order they appear. A name matched
    only because it sits inside a longer name (e.g. "tea" inside "iced tea") is
    dropped so a single dish is not reported twice.
    """
    normalized_query = query.lower()
    found: list[tuple[int, int, dict[str, object]]] = []
    for item in data["menu_items_by_id"].values():  # type: ignore[union-attr]
        name = str(item.get("item_name") or "")
        if not name:
            continue
        match = re.search(rf"\b{re.escape(name.lower())}s?\b", normalized_query)
        if match:
            found.append((match.start(), match.end(), item))

    found.sort(key=lambda entry: len(str(entry[2].get("item_name") or "")), reverse=True)
    chosen: list[tuple[int, int, dict[str, object]]] = []
    occupied: list[tuple[int, int]] = []
    for start, end, item in found:
        if any(start < other_end and end > other_start for other_start, other_end in occupied):
            continue
        chosen.append((start, end, item))
        occupied.append((start, end))
    chosen.sort(key=lambda entry: entry[0])
    return chosen


def _match_items_by_name(query: str, data: dict[str, object]) -> list[dict[str, object]]:
    """Every menu item whose full name is quoted in the query, in query order."""
    return [item for _, _, item in _item_name_spans(query, data)]


def _match_item_by_name(query: str, data: dict[str, object]) -> dict[str, object] | None:
    """Return the single item whose name is quoted most explicitly in the query."""
    matches = _match_items_by_name(query, data)
    if not matches:
        return None
    return max(matches, key=lambda item: len(str(item.get("item_name") or "")))


def _menu_item_answer(query: str, data: dict[str, object]) -> str | None:
    menu_items = data["menu_items_by_id"]
    query_terms = _normalize_terms(query)

    if not query_terms:
        return None

    named_items = _match_items_by_name(query, data)
    if len(named_items) == 1:
        return _item_card(named_items[0], data)
    if len(named_items) > 1:
        return "\n\n".join(_item_card(item, data) for item in named_items)

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
            return _item_card(best_item, data)

    return None


NUMBER_WORDS = {
    "a": 1, "an": 1, "one": 1, "single": 1, "another": 1,
    "two": 2, "three": 3, "four": 4, "five": 5,
    "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
    "couple": 2, "dozen": 12,
}

# Money-flavoured "give me the total" signals; "total calories" must not match.
ORDER_TOTAL_RE = re.compile(
    r"\b(total\s+(?:price|cost|bill|amount|order)|grand\s+total|"
    r"subtotal|altogether|in\s+total|combined|bill|"
    r"how\s+much(?:\s+\w+){0,4}\s+(?:altogether|in\s+total|total))\b"
)


def is_order_total(query: str) -> bool:
    """True when the user asks for a priced order total, not a recommendation."""
    return bool(ORDER_TOTAL_RE.search(query.lower()))


def _quantity_before(prefix: str) -> int:
    tokens = re.findall(r"[a-z0-9]+", prefix.lower())
    if not tokens:
        return 1
    last = tokens[-1]
    if last in {"more", "extra", "additional"} and len(tokens) >= 2:
        last = tokens[-2]
    if last.isdigit():
        return int(last)
    return NUMBER_WORDS.get(last, 1)


# Follow-up cues that extend the running order rather than starting a new one.
ADD_ORDER_RE = re.compile(
    r"\b(add|also\s+add|plus|in\s+addition|as\s+well|another|one\s+more)\b"
)

# Cues that shrink the running order; matched against the words just before a
# dish name so "remove X and add Y" classifies each dish independently.
REMOVE_ORDER_RE = re.compile(
    r"\b(remove|delete|drop|cancel|take\s+(?:out|off)|minus|without)\b"
)

# Re-show cues for an order that is already in the session ("my total").
ORDER_REVIEW_RE = re.compile(
    r"\b(my\s+order|the\s+order|your\s+order|order\s+so\s+far|"
    r"show\s+my\s+order|my\s+total|the\s+total|my\s+bill)\b"
)


def _has_add_cue(query: str) -> bool:
    return bool(ADD_ORDER_RE.search(query.lower()))


def _is_order_review(query: str) -> bool:
    return bool(ORDER_REVIEW_RE.search(query.lower()))


def _parse_order_items(query: str, data: dict[str, object]) -> list[tuple[dict, int]]:
    """(item, quantity) pairs for every dish named in the query, in order."""
    normalized = query.lower()
    return [
        (item, _quantity_before(normalized[:start]))
        for start, _, item in _item_name_spans(query, data)
    ]


def _parse_order_commands(query: str, data: dict[str, object]) -> list[tuple[str, dict, int]]:
    """(add|remove, item, quantity) per dish named in the query.

    Each dish is classified by the words just before it, so
    "remove chicken kottu and add two iced tea" removes one line and adds two.
    """
    normalized = query.lower()
    commands: list[tuple[str, dict, int]] = []
    for start, _, item in _item_name_spans(query, data):
        window = " ".join(re.findall(r"[a-z0-9]+", normalized[:start])[-6:])
        command = "remove" if REMOVE_ORDER_RE.search(window) else "add"
        commands.append((command, item, _quantity_before(normalized[:start])))
    return commands


def _handle_order_query(query: str, data: dict[str, object],
                        order: OrderState | None = None) -> str | None:
    """Answer order-total and add/remove-to-order requests.

    With no shared `order` state, a fresh order is priced from the query and
    discarded. With state, follow-ups mutate the running order and the total is
    recalculated, so the conversation carries forward. Two commands in one
    sentence each apply to its own dish ("remove X and add Y").
    """
    if order is None:
        if not is_order_total(query):
            return None
        parsed = _parse_order_items(query, data)
        if not parsed:
            return None
        return _format_order_lines(parsed)

    commands = _parse_order_commands(query, data)
    removing = [command for command in commands if command[0] == "remove"]
    adding = [command for command in commands if command[0] == "add"]

    if commands and (_has_add_cue(query) or removing):
        changed = False
        for _, item, _ in removing:
            if order.remove(item):
                changed = True
        for _, item, quantity in adding:
            order.add(item, quantity)
            changed = True
        if changed:
            return _format_shared_order(order)

    if is_order_total(query):
        if commands:
            order.replace([(item, quantity) for _, item, quantity in commands])
            return _format_shared_order(order)
        if order.items:
            return _format_shared_order(order)

    if _is_order_review(query) and order.items:
        return _format_shared_order(order)

    return None


def _format_order_lines(parsed: list[tuple[dict, int]]) -> str:
    lines = ["### Order total", ""]
    total = 0.0
    priced = 0
    for item, quantity in parsed:
        price = _price_value(item)
        name = item.get("item_name")
        if price is None:
            lines.append(f"- {quantity} x **{name}** - price not listed")
            continue
        line_total = price * quantity
        total += line_total
        priced += 1
        lines.append(
            f"- {quantity} x **{name}** ({_format_price(price)} each) "
            f"= {_format_price(line_total)}"
        )

    lines.append("")
    if priced:
        lines.append(f"**Total: {_format_price(total)}**")
        if priced < len(parsed):
            lines.append("")
            lines.append(
                "_Some items have no listed price, so they are not included in the total._"
            )
    else:
        lines.append("**Total unavailable** - none of those items has a listed price.")
    return "\n".join(lines)


def _format_shared_order(order: OrderState) -> str:
    lines = ["### Order total", ""]
    total = 0.0
    priced = 0
    for entry in order.items:
        quantity = entry.get("quantity") or 1
        name = entry.get("name") or "Unknown"
        price = entry.get("price")
        if price is None:
            lines.append(f"- {quantity} x **{name}** - price not listed")
            continue
        line_total = price * quantity
        total += line_total
        priced += 1
        lines.append(
            f"- {quantity} x **{name}** ({_format_price(price)} each) "
            f"= {_format_price(line_total)}"
        )

    lines.append("")
    if priced:
        lines.append(f"**Total: {_format_price(total)}**")
        if priced < len(order.items):
            lines.append("")
            lines.append(
                "_Some items have no listed price, so they are not included in the total._"
            )
    else:
        lines.append("**Total unavailable** - none of those items has a listed price.")
    return "\n".join(lines)


def _not_declared_answer(target: str, kind: str) -> str:
    return "\n".join(
        [
            f"### No menu item declares {target}",
            "",
            f"None of the 100 menu items list {target} as a {kind}, so there is nothing to show "
            "for that request.",
            "",
            "That can mean the dish genuinely avoids it, or that our records are incomplete. "
            "Ask staff before ordering if this is a medical allergy.",
        ]
    )


def _lookup_related_items(query: str, data: dict[str, object]) -> str | None:
    query_terms = _normalize_terms(query)
    menu_items = data["menu_items_by_id"]
    item_allergens = data["item_allergens"]
    item_dietary = data["item_dietary"]
    item_ingredients = data["item_ingredients"]
    limit_info = _parse_price_limit(query)
    categories = _categories_in_query(query, data)

    def matching_items(predicate) -> list[dict[str, object]]:
        return [
            item
            for item_id, item in menu_items.items()
            if predicate(item_id)
        ]

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
    } | {
        term
        for name in data["dietary_by_id"].values()
        for term in _normalize_terms(str(name))
    }

    def exact_name_match(query_text: str, names: list[str]) -> str | None:
        normalized_query = query_text.lower()
        exact_hits = [
            name
            for name in names
            if re.search(rf"\b{re.escape(name.lower())}s?\b", normalized_query)
        ]
        if exact_hits:
            return max(exact_hits, key=len)
        return _best_match(query_text, names)

    def resolve_target(names: list[str]) -> str | None:
        """Match a name, then try the aliases used when customers describe an allergen."""
        target = exact_name_match(query, names)
        if target:
            return target
        for alias, resolved in ALLERGEN_ALIASES.items():
            if alias in query_terms and resolved in names:
                return resolved
        return None

    recommendation_keywords = {"recommend", "safe", "okay", "ok", "good", "can", "suggest", "option", "alternative", "avoid", "eat", "food", "foods"}
    is_recommendation = bool(query_terms & recommendation_keywords)

    if query_terms & allergen_terms:
        target = resolve_target(list(data["allergens_by_id"].values()) + list(data["ingredients_by_id"].values()))
        if target:
            target_lower = target.lower()
            allergen_names = {name.lower() for name in data["allergens_by_id"].values()}
            ingredient_names = {name.lower() for name in data["ingredients_by_id"].values()}

            if target_lower in allergen_names:
                contains = matching_items(
                    lambda item_id: target_lower in {value.lower() for value in item_allergens.get(item_id, [])}
                )
                if is_recommendation:
                    safe = matching_items(
                        lambda item_id: target_lower not in {value.lower() for value in item_allergens.get(item_id, [])}
                    )
                    if safe:
                        total_items = len(menu_items)
                        if len(safe) == total_items:
                            headline_note = (
                                f"None of the {total_items} menu items declare {target} as an "
                                "allergen, so every item on the menu qualifies. That is unusually "
                                "broad, so treat the list as our records only."
                            )
                        else:
                            headline_note = (
                                f"{len(safe)} of {total_items} menu items do not declare {target}."
                            )
                        return _results_block(
                            f"Safe options without {target}",
                            safe,
                            data,
                            limit_info=limit_info,
                            categories=categories,
                            notes=(
                                headline_note,
                                "Kitchen cross-contamination is possible, so always confirm "
                                "with staff before ordering.",
                            ),
                        )
                if contains:
                    return _results_block(
                        f"Items containing {target}",
                        contains,
                        data,
                        limit_info=limit_info,
                        categories=categories,
                    )
                return _not_declared_answer(target, "allergen")

            if target_lower in ingredient_names:
                contains = matching_items(
                    lambda item_id: target_lower in {value.lower() for value in item_ingredients.get(item_id, [])}
                )
                if contains:
                    return _results_block(
                        f"Items containing the ingredient {target}",
                        contains,
                        data,
                        limit_info=limit_info,
                        categories=categories,
                    )

    if query_terms & dietary_terms:
        target = exact_name_match(query, list(data["dietary_by_id"].values()))
        if target:
            target_lower = target.lower()
            dietary_names = {name.lower() for name in data["dietary_by_id"].values()}
            if target_lower in dietary_names:
                matches = matching_items(
                    lambda item_id: target_lower in {value.lower() for value in item_dietary.get(item_id, [])}
                )
                if matches:
                    dietary_notes: list[str] = []
                    if target_lower == "vegetarian":
                        dietary_notes.append(
                            "Tags come from the item database, so some dishes may still need "
                            "ingredient checks for strict dietary needs."
                        )
                    others = [
                        name
                        for name in data["dietary_by_id"].values()
                        if name.lower() != target_lower
                        and name.lower() in _normalize_terms(query)
                    ]
                    if others:
                        dietary_notes.append(
                            "You also asked about "
                            + ", ".join(others)
                            + ". This list covers "
                            + target
                            + " only, so check the other tags before ordering."
                        )
                    return _results_block(
                        f"Menu items tagged {target}",
                        matches,
                        data,
                        limit_info=limit_info,
                        categories=categories,
                        notes=tuple(dietary_notes),
                    )

                excluded = FREE_FROM_ALLERGENS.get(target_lower)
                if excluded:
                    declared = {
                        allergen.lower()
                        for values in item_allergens.values()
                        for allergen in values
                    }
                    relevant = [
                        allergen
                        for allergen in excluded
                        if allergen.lower() in declared
                    ]
                    blocked = {allergen.lower() for allergen in relevant}
                    derived = matching_items(
                        lambda item_id: not (
                            blocked
                            & {value.lower() for value in item_allergens.get(item_id, [])}
                        )
                    )
                    if derived:
                        return _results_block(
                            f"{target} options",
                            derived,
                            data,
                            limit_info=limit_info,
                            categories=categories,
                            notes=(
                                f"No menu item carries the **{target}** tag, so this list was "
                                f"derived from allergen records instead"
                                + (
                                    f" (excluded: {', '.join(relevant)})."
                                    if relevant
                                    else " (no relevant allergens are declared anywhere on the menu)."
                                ),
                                "Cross-contamination is still possible in a shared kitchen, so "
                                "confirm with staff before ordering.",
                            ),
                        )

    return None


def _is_question_line(line: str) -> bool:
    return line.rstrip().endswith("?")


def _split_policy_line(line: str) -> tuple[str, str]:
    code, separator, body = line.partition(": ")
    if not separator:
        return "", line
    return code.strip(), body.strip()


def _rank_policies(
    query: str,
    data: dict[str, object],
    limit: int = 4,
    min_overlap: int = 1,
) -> list[tuple[str, str]]:
    query_terms = _normalize_terms(query)
    policy_rows = data["restaurant_policies"]

    # Named SQL rows come first so a readable name wins over a bare "POL006" code
    # when two sources hold the same policy text.
    candidates: list[tuple[str, str]] = [
        (
            "Restaurant Policies",
            f"{row['policy_name']}: {row['policy_description']}",
        )
        for row in policy_rows
        if row.get("policy_description")
    ]
    candidates.extend(load_policy_lines())

    seen_bodies: set[frozenset[str]] = set()
    unique_candidates: list[tuple[str, str]] = []
    for label, line in candidates:
        body_key = frozenset(_normalize_terms(_split_policy_line(line)[1] or line))
        if body_key and body_key in seen_bodies:
            continue
        if body_key:
            seen_bodies.add(body_key)
        unique_candidates.append((label, line))

    ranked: list[tuple[tuple[int, int], str, str]] = []
    for label, line in unique_candidates:
        overlap, _ = _score_text(query_terms, line)
        if overlap >= min_overlap:
            informative = 0 if _is_question_line(line) else 1
            ranked.append(((overlap, informative), label, line))
    ranked.sort(key=lambda entry: (-entry[0][0], -entry[0][1], len(entry[2])))
    return [(label, line) for _, label, line in ranked[:limit]]


def _policy_match_is_meaningful(query: str, line: str) -> bool:
    """Reject policy matches that only share vague words like 'dishes' or 'available'."""
    query_terms = _normalize_terms(query)
    line_terms = _normalize_terms(line)
    overlapping = {
        term for term in query_terms & line_terms if term not in GENERIC_QUERY_TERMS
    }
    if overlapping:
        return True
    query_prefixes = {
        term[:MATCH_PREFIX_LENGTH] for term in query_terms if len(term) >= MATCH_PREFIX_LENGTH
    }
    line_prefixes = {
        term[:MATCH_PREFIX_LENGTH] for term in line_terms if len(term) >= MATCH_PREFIX_LENGTH
    }
    shared = {
        prefix
        for prefix in query_prefixes & line_prefixes
        if prefix not in GENERIC_QUERY_TERMS
    }
    return bool(shared)


def _policy_answer(query: str, data: dict[str, object]) -> str:
    ranked = _rank_policies(query, data, limit=4)
    if not ranked or not _policy_match_is_meaningful(query, ranked[0][1]):
        return _no_match_answer(query, data, kind="policy")

    label, best = ranked[0]
    code, body = _split_policy_line(best)

    lines = [f"### {code or label}", ""]
    if _is_question_line(best):
        lines.append(f"**Question on record:** {body or best}")
        lines.append("")
        lines.append(
            "_The database stores this FAQ entry without an answer text, so treat it as a "
            "topic reference rather than a confirmed answer._"
        )
    else:
        lines.append(body or best)
    lines.append("")
    lines.append(f"_Source: {label}_")

    related = _rank_policies(query, data, limit=3, min_overlap=2)
    related = [entry for entry in related if entry[1] != best]
    if related:
        lines.append("")
        lines.append("**Related information**")
        lines.append("")
        for related_label, line in related:
            related_code, related_body = _split_policy_line(line)
            lines.append(f"- **{related_code or related_label}** {related_body}")
    return "\n".join(lines)


def _closest_items(query: str, data: dict[str, object], limit: int = 5) -> list[dict[str, object]]:
    query_terms = _normalize_terms(query)
    menu_items = data["menu_items_by_id"]
    scored: list[tuple[int, int, dict[str, object]]] = []
    for item in menu_items.values():
        item_text = " ".join(
            str(item.get(field, "")) for field in ("item_name", "category", "description")
        )
        overlap, length_tiebreak = _score_text(query_terms, item_text)
        scored.append((overlap, length_tiebreak, item))
    scored = [entry for entry in scored if entry[0] > 0]
    scored.sort(key=lambda entry: (-entry[0], entry[1]))
    return [item for _, _, item in scored[:limit]]


def _no_match_answer(query: str, data: dict[str, object], *, kind: str) -> str:
    if kind == "structured":
        lines = [
            "### No exact match",
            "",
            "I could not match that request to a menu item, dietary tag, or allergen in the database. "
            "Here are the closest matches so you can pick from real data instead of a dead end.",
        ]
    else:
        lines = [
            "### No matching policy",
            "",
            "None of our policies, discounts, FAQs or allergy guidelines matched that request. "
            "Here is what came closest.",
        ]

    closest = _closest_items(query, data)
    if closest:
        lines.append("")
        lines.append("**Closest menu matches**")
        lines.append("")
        lines.append(_menu_table(closest))

    limit_info = _parse_price_limit(query)
    if limit_info and not closest:
        lines.append("")
        lines.append(
            f"Your budget of **{limit_info['matched']}** was noted, but no menu item could be "
            "matched to the rest of the request."
        )

    ranked = _rank_policies(query, data, limit=3)
    if ranked:
        lines.append("")
        lines.append("**Closest policy information**")
        lines.append("")
        for label, line in ranked:
            code, body = _split_policy_line(line)
            lines.append(f"- **{code or label}** {body}")

    lines.append("")
    lines.append(
        "Try naming a **menu item** (e.g. *Margherita Pizza*), a **dietary tag** "
        "(*vegan*, *gluten free*), an **allergen** (*peanut*, *shellfish*), a **budget** "
        "(*under $10*), or a **policy topic** (*reservation*, *discount*, *parking*, *hours*)."
    )
    return "\n".join(lines)


def _has_informative_policy(query: str, data: dict[str, object]) -> bool:
    return any(
        not _is_question_line(line) and _policy_match_is_meaningful(query, line)
        for _, line in _rank_policies(query, data, limit=5)
    )


def get_answer(query: str, order: OrderState | None = None) -> str:
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

    full_menu_phrases = {"full menu", "whole menu", "entire menu", "complete menu", "show menu", "list menu", "menu items", "all items", "all menu", "on the menu", "menu list", "menu options", "show me the menu", "see the menu", "view the menu"}
    is_full_menu = any(phrase in query_lower for phrase in full_menu_phrases) or query_lower.strip() in {"menu", "items", "list", "menu items"}

    is_structured_query = any(word in query_lower for word in structured_keywords)
    is_policy_query = any(word in query_lower for word in policy_keywords)

    if is_full_menu:
        return _full_menu_answer(data)

    order_answer = _handle_order_query(query, data, order)
    if order_answer:
        return order_answer

    structured_answer = _lookup_related_items(query, data)
    if structured_answer:
        return structured_answer

    menu_answer = _menu_item_answer(query_lower, data)
    if menu_answer:
        return menu_answer

    named_matches = _items_named_in_query(query, data)
    categories = _categories_in_query(query, data)
    if named_matches and (categories or not _has_informative_policy(query, data)):
        block = _results_block(
            "Items that match the wording of your question",
            named_matches,
            data,
            limit_info=_parse_price_limit(query),
            categories=categories,
            notes=(
                "I matched this on the words in your question rather than an exact item name, "
                "so check the details below.",
            ),
        )
        if block:
            return block

    if is_structured_query:
        return _no_match_answer(query, data, kind="structured")

    if is_policy_query:
        return _policy_answer(query, data)

    # Default to a broad policy match so the assistant still returns a useful answer.
    return _policy_answer(query, data)


if __name__ == "__main__":
    query = input("Enter your query: ").strip()
    if query:
        print(get_answer(query))
