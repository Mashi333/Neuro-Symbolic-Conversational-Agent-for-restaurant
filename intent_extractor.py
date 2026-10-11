"""Step 11 - Extract structured intent & constraints from natural language.

The LLM's first job is understanding, NOT recommending. This module turns a
free-text user request into a fixed JSON structure:

    "I want a vegetarian meal under Rs. 1500 without peanuts."

    -> {
         "intent": "restaurant_recommendation",
         "restaurant_preference": null,
         "budget": 1500.0,
         "budget_currency": "inr",
         "dietary_requirements": ["vegetarian"],
         "allergies": ["peanut"],
         "ingredients_to_avoid": [],
         "ingredients_preferred": [],
         "other_constraints": [],
       }

Reliability strategy (prompt -> parse -> validate -> repair -> fallback):
  1. A fixed JSON schema is sent inside the prompt.
  2. The reply is parsed as JSON (tolerating markdown fences).
  3. The output is validated/normalised (types, ranges, enums, known menus).
  4. On failure the model is asked ONCE to fix its own answer (self-repair).
  5. If that still fails, a deterministic rule extractor produces the answer
     offline, so the pipeline never crashes and always returns JSON.

Run:  python intent_extractor.py "I want a vegetarian meal under Rs. 1500"
"""

from __future__ import annotations

import argparse
import json
import re

from llm_client import BaseLLM, LLMError, LLMUnavailableError, get_llm_client
from retrieve import (
    ALLERGEN_ALIASES,
    _parse_price_limit,
    is_order_total,
    load_structured_data,
)

INTENTS = (
    "restaurant_recommendation",
    "menu_item_detail",
    "allergy_query",
    "dietary_query",
    "price_query",
    "policy_query",
    "reservation",
    "general",
)

ALL_FIELDS = (
    "intent",
    "restaurant_preference",
    "budget",
    "budget_currency",
    "dietary_requirements",
    "allergies",
    "ingredients_to_avoid",
    "ingredients_preferred",
    "other_constraints",
)

LIST_FIELDS = (
    "dietary_requirements",
    "allergies",
    "ingredients_to_avoid",
    "ingredients_preferred",
    "other_constraints",
)

CURRENCY_ALIASES = {
    "$": "usd",
    "usd": "usd",
    "dollar": "usd",
    "dollars": "usd",
    "rs.": "inr",
    "rs": "inr",
    "rupee": "inr",
    "rupees": "inr",
    "inr": "inr",
    "lkr": "lkr",
    "€": "eur",
    "eur": "eur",
    "euro": "eur",
    "euros": "eur",
    "£": "gbp",
    "gbp": "gbp",
    "pound": "gbp",
    "pounds": "gbp",
}

DIET_ALIASES = {
    "veggie": "vegetarian",
    "veg": "vegetarian",
    "plant-based": "plant based",
    "plant based": "plant based",
    "gf": "gluten free",
    "no dairy": "dairy free",
    "dairy-free": "dairy free",
    "no meat": "vegetarian",
    "meat-free": "vegetarian",
    "meat free": "vegetarian",
}

EXTRACTION_SCHEMA = {
    "type": "object",
    "properties": {
        "intent": {"type": "string", "enum": list(INTENTS)},
        "restaurant_preference": {"type": ["string", "null"]},
        "budget": {"type": ["number", "null"]},
        "budget_currency": {"type": ["string", "null"]},
        "dietary_requirements": {"type": "array", "items": {"type": "string"}},
        "allergies": {"type": "array", "items": {"type": "string"}},
        "ingredients_to_avoid": {"type": "array", "items": {"type": "string"}},
        "ingredients_preferred": {"type": "array", "items": {"type": "string"}},
        "other_constraints": {"type": "array", "items": {"type": "string"}},
    },
    "required": list(ALL_FIELDS),
    "additionalProperties": False,
}

SYSTEM_PROMPT = f"""You are the natural-language understanding component of a restaurant
conversational agent. Your ONLY job is to extract the customer's request into
a JSON object. You must NEVER recommend dishes, answer questions, or add
anything that is not in the user's sentence.

Reply with exactly one valid JSON object matching this schema:

{json.dumps(EXTRACTION_SCHEMA, indent=2)}

Rules:
- "intent" is the user's goal. Pick one of: restaurant_recommendation
  (asking for a dish or meal suggestion), menu_item_detail (asking facts about
  one item, e.g. price or calories), allergy_query (whether items contain an
  allergen), dietary_query (gluten-free/vegan/vegetarian availability),
  price_query (about menu prices/budget), policy_query (rules, discounts,
  reservations policy), reservation (booking a table), general (anything else).
- "restaurant_preference": a cuisine or kind of food the user asks for
  (e.g. "seafood", "italian", "spicy", "dessert"), or null if unspoken.
- "budget": the maximum price as a NUMBER ONLY (no currency symbol or word),
  or null. Example: "under Rs. 1500" -> 1500.
- "budget_currency": lowercase code of the money the user used: "usd", "inr",
  "lkr", "eur", "gbp", or null. Do not invent a currency.
- Put diet words (vegetarian, vegan, gluten free, halal, kosher, dairy free,
  low calorie, high protein, ketogenic, ...) into "dietary_requirements".
- Put anything the user must avoid because of allergy or intolerance into
  "allergies" (peanut, shellfish, milk, gluten, egg, soy, ...).
- Put ingredients the user explicitly wants avoided into "ingredients_to_avoid"
  and wanted ingredients into "ingredients_preferred".
- Anything else that limits the choice (e.g. "under 600 calories",
  "good for children", "not spicy") goes into "other_constraints" as phrases.
- If a field is not mentioned use [] or null. NEVER guess or invent values.
- Write every word lowercase, singular, exactly as the user said it, trimmed.
- Output the JSON object only: no prose, no markdown fences."""


def default_output() -> dict:
    return {
        "intent": "general",
        "restaurant_preference": None,
        "budget": None,
        "budget_currency": None,
        "dietary_requirements": [],
        "allergies": [],
        "ingredients_to_avoid": [],
        "ingredients_preferred": [],
        "other_constraints": [],
    }


# ------------------------------------------------------------------ prompt

def build_messages(query: str) -> list[dict]:
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": f"User request: {query}"},
    ]


def build_repair_messages(query: str, bad_answer: dict, errors: list[str]) -> list[dict]:
    """Second chance: show the model its rejected output and the errors."""
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": f"User request: {query}"},
        {"role": "assistant", "content": json.dumps(bad_answer)},
        {
            "role": "user",
            "content": (
                "Your previous JSON was rejected for these reasons:\n- "
                + "\n- ".join(errors)
                + "\nReturn ONLY a corrected valid JSON object."
            ),
        },
    ]


# ------------------------------------------------------------------ parsing

def parse_json(text: str) -> dict | None:
    """Parse the model's reply, tolerating markdown fences and stray text."""
    if not text:
        return None
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    try:
        result = json.loads(text)
    except json.JSONDecodeError:
        result = None
    if isinstance(result, dict):
        return result
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        try:
            result = json.loads(text[start : end + 1])
        except json.JSONDecodeError:
            return None
        if isinstance(result, dict):
            return result
    return None


# ------------------------------------------------------------------ validation

def _clean_string_list(value, field: str, errors: list[str]) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        value = [value]
    if not isinstance(value, (list, tuple)):
        errors.append(f"{field} must be an array of strings, got {type(value).__name__}")
        return []
    cleaned: list[str] = []
    for item in value:
        if not isinstance(item, str):
            errors.append(f"{field} contains a non-string value {item!r}")
            continue
        item = item.strip().lower()
        if item and item not in cleaned:
            cleaned.append(item)
    return cleaned


def normalize_output(obj: dict) -> tuple[dict, list[str]]:
    """Validate and normalise one extracted object into the fixed shape."""
    errors: list[str] = []
    if not isinstance(obj, dict):
        return default_output(), ["model output is not a JSON object"]

    unknown = set(obj) - set(ALL_FIELDS)
    if unknown:
        errors.append(f"unknown keys ignored: {sorted(unknown)}")

    out = default_output()

    intent = obj.get("intent")
    if isinstance(intent, str) and intent.strip().lower() in INTENTS:
        out["intent"] = intent.strip().lower()
    else:
        errors.append(f"invalid intent ({intent!r}); expected one of {INTENTS}")

    preference = obj.get("restaurant_preference")
    if isinstance(preference, str) and preference.strip().lower() != "null":
        out["restaurant_preference"] = preference.strip() or None

    budget = obj.get("budget")
    if budget is None:
        pass
    elif isinstance(budget, bool):  # bool is an int subclass; reject it
        errors.append("budget must be a number")
    elif isinstance(budget, (int, float)):
        if budget > 0:
            out["budget"] = float(budget)
        else:
            errors.append(f"budget must be positive, got {budget}")
    elif isinstance(budget, str):
        try:
            amount = float(re.sub(r"[^\d.+-]", "", budget))
        except ValueError:
            errors.append(f"budget is not a number: {budget!r}")
        else:
            if amount <= 0:
                errors.append(f"budget must be positive, got {amount}")
            else:
                out["budget"] = amount
    else:
        errors.append(f"budget has unexpected type {type(budget).__name__}")

    currency = obj.get("budget_currency")
    if isinstance(currency, str):
        key = currency.strip().lower()
        out["budget_currency"] = CURRENCY_ALIASES.get(key, key or None)
    elif currency is not None:
        errors.append("budget_currency must be a string or null")
    if out["budget"] is not None and out["budget_currency"] is None:
        errors.append("budget was given but budget_currency is missing")

    for field in LIST_FIELDS:
        out[field] = _clean_string_list(obj.get(field), field, errors)

    return out, errors


# ------------------------------------------------------------------ cross-check

def _resource_lookup() -> tuple[set[str], set[str], set[str]]:
    """Known dietary tags, allergens and ingredients from the database."""
    data = load_structured_data()
    diets = {str(name).lower() for name in data["dietary_by_id"].values()}
    allergens = {str(name).lower() for name in data["allergens_by_id"].values()}
    ingredients = {str(name).lower() for name in data["ingredients_by_id"].values()}
    return diets, allergens, ingredients


def cross_check(out: dict) -> list[str]:
    """Warnings when extracted values are unknown to the menu database."""
    warnings: list[str] = []
    known_diets, known_allergens, known_ingredients = _resource_lookup()
    diets, allergens, ingredients = known_diets, known_allergens, known_ingredients

    for item in out["dietary_requirements"]:
        if item not in diets and item not in DIET_ALIASES:
            warnings.append(f"dietary requirement {item!r} is not a known diet tag")
    for item in out["allergies"]:
        item = ALLERGEN_ALIASES.get(item, item)
        if item not in allergens and item not in ingredients:
            warnings.append(f"allergy {item!r} is not a declared allergen")
    for item in out["ingredients_to_avoid"] + out["ingredients_preferred"]:
        if item not in ingredients and item not in allergens:
            warnings.append(f"ingredient {item!r} is not on the ingredient list")
    if out["budget_currency"] not in (None, "usd"):
        warnings.append(
            f"menu prices are stored in USD but the budget is in "
            f"{out['budget_currency']}"
        )
    return warnings


# ------------------------------------------------------------------ fallback (no LLM)

FALLBACK_PATTERNS = {
    "reservation": (re.compile(r"\b(reserve|reservation|book|booking|table for)\b"),),
    "policy_query": (
        re.compile(r"\b(policy|policies|cancel|cancellation|cancellations|refund|refunds|discount|discounts|parking|pets?|smoking|outside food|deliver(y|ies))\b"),
    ),
    "allergy_query": (re.compile(r"\b(allerg|allergic|contains?|safe for me|free of)\b"),),
    "dietary_query": (re.compile(r"\b(vegans?|vegetarians?|vegetables?|gluten[\s-]free|halal|kosher|diet|dietary)\b"),),
    "price_query": (re.compile(r"\b(price|prices|cost|cheap|affordable|budget|under|below)\b"),),
    "menu_item_detail": (re.compile(r"\b(price of|calories of|details about|tell me about|what is)\b"),),
}

RESTAURANT_PREFERENCES = {
    "seafood": ("seafood", "fish", "shrimp", "prawn"),
    "spicy": ("spicy", "hot"),
    "dessert": ("dessert", "sweet"),
    "grill": ("grilled", "grill", "bbq"),
    "burgers": ("burger", "burgers"),
    "italian": ("italian", "pasta", "pizza"),
    "indian": ("indian", "curry", "biryani"),
    "sri lankan": ("kottu", "sri lankan"),
    "rice dishes": ("rice", "fried rice"),
}


def detect_intent(query: str) -> str:
    lower = query.lower()
    # "give me a total price" for a list of dishes is an arithmetic lookup, not
    # a recommendation, so it must not be caught by the "want" keyword below.
    if is_order_total(lower):
        return "price_query"
    if any(pattern.search(lower) for pattern in FALLBACK_PATTERNS["reservation"]):
        return "reservation"
    if any(pattern.search(lower) for pattern in FALLBACK_PATTERNS["policy_query"]):
        return "policy_query"
    if any(pattern.search(lower) for pattern in FALLBACK_PATTERNS["allergy_query"]):
        return "allergy_query"
    if any(pattern.search(lower) for pattern in FALLBACK_PATTERNS["menu_item_detail"]):
        return "menu_item_detail"
    if re.search(r"\b(recommend\w*|suggest\w*|looking for|want|meals?|dishes|options?|what.*(eat|order)|any)\b", lower):
        return "restaurant_recommendation"
    if any(pattern.search(lower) for pattern in FALLBACK_PATTERNS["dietary_query"]):
        return "dietary_query"
    if any(pattern.search(lower) for pattern in FALLBACK_PATTERNS["price_query"]):
        return "price_query"
    return "general"


def detect_preference(query: str) -> str | None:
    lower = query.lower()
    for preference, keywords in RESTAURANT_PREFERENCES.items():
        if any(keyword in lower for keyword in keywords):
            return preference
    return None


def detect_budget(query: str) -> tuple[float | None, str | None]:
    info = _parse_price_limit(query)
    if not info:
        return None, None
    currency = info["currency"]
    normalized = CURRENCY_ALIASES.get(str(currency).lower()) if currency else None
    return float(info["limit"]), normalized


def detect_dietary(query: str) -> list[str]:
    # The database tag vocabulary mixes spaces and hyphens ("Low Calorie"),
    # so both sides are normalised before the substring comparison.
    lower = query.lower()
    normalized = re.sub(r"[\s-]+", " ", lower)
    diets: list[str] = []
    known_diets, _, _ = _resource_lookup()
    for diet in sorted(known_diets):
        if re.sub(r"[\s-]+", " ", diet) in normalized and diet not in diets:
            diets.append(diet)
    for alias, resolved in DIET_ALIASES.items():
        alias_pattern = r"[\s-]+".join(
            re.escape(part) for part in re.split(r"[\s-]+", alias) if part
        )
        if re.search(rf"\b{alias_pattern}\b", lower) and resolved not in diets:
            diets.append(resolved)
    return diets


# A bare food word is not an allergy: "chicken kottu and mushroom soup" names
# two dishes, it does not say the customer must avoid chicken or mushroom. An
# explicit avoidance cue is required before a declared allergen is treated as
# an allergy (the previous bare-substring scan filtered those dishes out).
ALLERGY_CUE_RE = re.compile(
    r"\b(allerg\w*|intoleran\w*|anaphyla\w*|avoid\w*|without|free|"
    r"can'?t\s+eat|cannot\s+eat|can\s+not\s+eat|don'?t\s+eat)\b"
)


def detect_allergies(query: str) -> list[str]:
    lower = query.lower()
    if not ALLERGY_CUE_RE.search(lower):
        return []
    _, known_allergens, _ = _resource_lookup()
    allergies: list[str] = []
    for allergen in sorted(known_allergens):
        pattern = rf"(?<![a-z]){re.escape(allergen)}(?![a-z])"
        if re.search(pattern, lower) and allergen not in allergies:
            allergies.append(allergen)
    for alias, resolved in ALLERGEN_ALIASES.items():
        if re.search(rf"\b{re.escape(alias)}\b", lower) and resolved.lower() not in allergies:
            allergies.append(resolved)
    return allergies


STOP_TOKENS = {
    "and", "or", "with", "without", "but", "please", "thanks", "thank",
    "the", "a", "an", "for", "me", "i", "do", "you", "have", "in", "on",
}


def _capture_phrase(text: str, keyword: str) -> str:
    """Words that follow a keyword like 'without' until the phrase stops."""
    rest = text[text.find(keyword) + len(keyword):]
    tokens = [match.group(0) for match in re.finditer(r"[a-z]+", rest)
              if match.group(0) not in STOP_TOKENS]
    return " ".join(tokens)


def detect_avoid_and_prefer(query: str) -> tuple[list[str], list[str]]:
    lower = query.lower()
    avoid: list[str] = []
    prefer: list[str] = []
    known_dict = load_structured_data()
    ingredients = {str(name).lower() for name in known_dict["ingredients_by_id"].values()}
    allergens = {str(name).lower() for name in known_dict["allergens_by_id"].values()}
    candidates = ingredients | allergens

    avoid_phrases = []
    for keyword in ("without", "no", "not"):
        for match in re.finditer(rf"\b{keyword}\b", lower):
            phrase = _capture_phrase(lower, keyword).strip()
            if phrase:
                avoid_phrases.append(phrase)

    prefer_phrases = []
    for keyword in ("with", "containing", "contains", "made with"):
        for match in re.finditer(rf"\b{re.escape(keyword)}\b", lower):
            phrase = _capture_phrase(lower, keyword).strip()
            if phrase:
                prefer_phrases.append(phrase)

    for phrases, target in ((avoid_phrases, avoid), (prefer_phrases, prefer)):
        for phrase in phrases:
            for candidate in candidates:
                if candidate in phrase and candidate not in target:
                    target.append(candidate)
    return avoid, prefer


def detect_other_constraints(query: str) -> list[str]:
    lower = query.lower()
    constraints: list[str] = []
    patterns = [
        # None label -> keep the matched text, so "under 600 calories" stays
        # numeric for the ASP calorie_limit fact (asp_reasoner.user_facts).
        (re.compile(r"under\s+\d+\s*(?:calories|kcal)"), None),
        (re.compile(r"\b(good|great|suitable)\s+for\s+children\b"), "child friendly"),
    ]
    for pattern, label in patterns:
        match = pattern.search(lower)
        if match:
            constraints.append(match.group(0) if label is None else label)
    return constraints


def fallback_extract(query: str) -> dict:
    """Deterministic offline extraction (baseline + crash-guard)."""
    budget, currency = detect_budget(query)
    avoid, prefer = detect_avoid_and_prefer(query)
    allergies = detect_allergies(query)
    for term in avoid:
        if term not in allergies:
            allergies.append(term)
    return {
        "intent": detect_intent(query),
        "restaurant_preference": detect_preference(query),
        "budget": budget,
        "budget_currency": currency,
        "dietary_requirements": detect_dietary(query),
        "allergies": allergies,
        "ingredients_to_avoid": avoid,
        "ingredients_preferred": prefer,
        "other_constraints": detect_other_constraints(query),
    }


# ------------------------------------------------------------------ public API

def extract_constraints(query: str, llm: BaseLLM | None = None) -> dict:
    """Extract structured constraints from a user query.

    Returns the fixed schema plus "method" ("llm", "llm_repaired" or
    "fallback") and "warnings" so callers know how the answer was produced.
    """
    query = query.strip()
    if llm is None:
        llm = get_llm_client()

    if llm is not None:
        try:
            raw = llm.complete(build_messages(query))
        except LLMUnavailableError:
            raw = None
        except LLMError:
            raw = None
        if raw:
            parsed = parse_json(raw)
            if parsed is not None:
                out, errors = normalize_output(parsed)
                if not errors:
                    result = out
                    result["method"] = "llm"
                    result["warnings"] = cross_check(result)
                    return result
                # One self-repair attempt with the validation errors as feedback.
                try:
                    repaired = llm.complete(build_repair_messages(query, parsed, errors))
                except (LLMError, LLMUnavailableError):
                    repaired = None
                if repaired:
                    reparsed = parse_json(repaired)
                    if reparsed is not None:
                        out, errors = normalize_output(reparsed)
                        if not errors:
                            result = out
                            result["method"] = "llm_repaired"
                            result["warnings"] = cross_check(result)
                            return result

    result = fallback_extract(query)
    result["method"] = "fallback"
    result["warnings"] = cross_check(result)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Extract structured constraints with the LLM")
    parser.add_argument("query", nargs="+", help="user request in natural language")
    args = parser.parse_args()
    query = " ".join(args.query)

    result = extract_constraints(query)
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()