"""Step 15 - Decision handling after ASP validation (LLM + RAG + ASP loop).

Routing (this module):

    extracted intent + constraints
      |
      +-- lookup query (detail / price / policy / reservation / general)
      |   with NO choice constraint  -> retrieve.get_answer: a direct
      |                                 database answer, decision = "direct"
      |
      +-- everything else (recommendation intent, or any diet / allergy /
          ingredient / budget / preference constraint)
          -> the neuro-symbolic loop below (steps 12-14)

Control flow after `retrieve_and_validate` (steps 11-14):

    ASP verdicts (valid / invalid + reasons)
      |
      +-- valid items exist ------------------------------------+
      |                                                          |
      | 1. DROP the invalid options                              |
      | 2. RANK the remaining valid options                      |
      | 3. SEND ONLY the ranked valid items to the LLM           |
      |    (the prompt carries only approved facts; the model is |
      |     told never to mention any other dish)                |
      V                                                          |
    FINAL RECOMMENDATION                                .........
                                                       ... see below ...
      +-- no valid items ----------------------------------------+
         1. NEVER invent a recommendation
         2. Explain that no item satisfies ALL constraints
         3. Diagnose WHICH constraint(s) caused the problem
            (counted from the ASP fails/2 reasons)
         4. Ask the user whether they want to RELAX a constraint,
            showing what each relaxation would unlock

The final natural-language text is written by response_step.generate_response:
it receives ONLY this decision payload, produces the answer through the LLM in
one of two modes (APPROVED ITEMS / NO VALID OPTION), and falls back to a
deterministic template when there is no model, the model fails, or the model's
text fails the grounding check (see response_step for the two-layer no-
invention guard).

Run:  python decision_step.py "I want a vegetarian meal under Rs. 1500 without peanuts."
"""

from __future__ import annotations

import argparse
import json
import re
from typing import TYPE_CHECKING

from asp_validation import retrieve_and_validate, validate_items
from intent_extractor import extract_constraints
from llm_client import get_llm_client
from response_step import generate_response
from retrieve import get_answer, is_order_total, load_structured_data

if TYPE_CHECKING:
    from order_state import OrderState

# reason -> (friendly noun, human name of the constraint)
CONSTRAINT_LABELS = {
    "budget": "budget",
    "diet": "dietary requirement",
    "allergy": "allergy",
    "ingredient": "ingredient rule",
    "calories": "calorie limit",
}

LIST_FIELDS = ("dietary_requirements", "allergies", "ingredients_to_avoid")

# Intents that are answered by a plain database lookup when the user set
# no choice constraint at all; everything else runs the RAG + ASP loop.
DIRECT_INTENTS = {"menu_item_detail", "price_query", "policy_query",
                  "reservation", "general"}

_CALORIE_RE = re.compile(r"under\s+\d+\s*(?:calories|kcal)", re.IGNORECASE)


def _has_choice_constraint(constraints: dict) -> bool:
    # restaurant_preference is deliberately NOT counted: it is a soft ranking
    # signal, and forcing e.g. "price of a Margherita Pizza" (preference
    # "italian" from the word "pizza") into the recommendation loop was a bug.
    return bool(
        constraints.get("dietary_requirements")
        or constraints.get("allergies")
        or constraints.get("ingredients_to_avoid")
        or constraints.get("ingredients_preferred")
        or constraints.get("other_constraints")
        or constraints.get("budget") is not None
    )


def _is_direct_query(constraints: dict) -> bool:
    """True for lookup questions that must NOT become a food recommendation."""
    return (
        constraints.get("intent", "general") in DIRECT_INTENTS
        and not _has_choice_constraint(constraints)
    )


# ------------------------------------------------------------- analysis

def analyze_blockers(payload: dict) -> list[dict]:
    """Count, for every ASP failure reason, how many retrieved items it blocked."""
    counts: dict[str, int] = {}
    for row in payload["invalid"]:
        for reason in row["reasons"]:
            counts[reason] = counts.get(reason, 0) + 1

    blockers: list[dict] = []
    for reason in sorted(counts, key=lambda r: (-counts[r], r)):
        blockers.append({
            "reason": reason,
            "label": CONSTRAINT_LABELS.get(reason, reason),
            "blocked_n": counts[reason],
            "user_value": _constraint_value(payload["constraints"], reason),
        })
    return blockers


def _constraint_value(constraints: dict, reason: str) -> str:
    if reason == "budget":
        budget = constraints.get("budget")
        if budget is None:
            return "no budget given"
        return f"{budget} {constraints.get('budget_currency') or 'usd'}"
    if reason == "calories":
        for constraint in constraints.get("other_constraints") or []:
            if _CALORIE_RE.search(str(constraint)):
                return str(constraint)
        return CONSTRAINT_LABELS["calories"]
    for field in LIST_FIELDS:
        if _reason_for(field) == reason:
            values = constraints.get(field) or []
            return ", ".join(values) if values else CONSTRAINT_LABELS.get(reason, reason)
    return reason


def _reason_for(field: str) -> str:
    return {"dietary_requirements": "diet",
            "allergies": "allergy",
            "ingredients_to_avoid": "ingredient"}.get(field, field)


def remove_constraint(constraints: dict, reason: str) -> dict:
    """Return a copy of the constraints with the given constraint dropped."""
    relaxed = {key: list(value) if isinstance(value, list) else value
               for key, value in constraints.items()}
    if reason == "budget":
        relaxed["budget"] = None
        relaxed["budget_currency"] = None
    if reason == "calories":
        relaxed["other_constraints"] = [
            constraint for constraint in relaxed.get("other_constraints") or []
            if not _CALORIE_RE.search(str(constraint))
        ]
    for field in LIST_FIELDS:
        if _reason_for(field) == reason:
            relaxed[field] = []
    return relaxed


# ------------------------------------------------------------- ranking

_PRICE_RE = re.compile(r"(\d+(?:\.\d+)?)")


def _price_cents(price) -> float | None:
    if price is None:
        return None
    try:
        return float(_PRICE_RE.search(str(price)).group(1)) * 100  # type: ignore[union-attr]
    except (AttributeError, TypeError, ValueError):
        return None


def rank_valid(
    valid: list[dict],
    constraints: dict | None = None,
    data: dict | None = None,
    preferences: list[str] | None = None,
    weights: dict[str, float] | None = None,
    validation: dict | None = None,
) -> list[dict]:
    """Rank valid options with the soft-factor scorer (ranking_step.score_and_rank)."""
    from ranking_step import score_and_rank

    return score_and_rank(
        valid, constraints=constraints, data=data,
        preferences=preferences, weights=weights, validation=validation,
    )


# ------------------------------------------------------------- orchestrator

def decide(payload: dict, constraints: dict | None = None, data: dict | None = None) -> dict:
    """Ask the ASP verdicts and branch into recommend / relax."""
    verdicts, payload_get = payload, payload.get
    constraints = constraints or payload["constraints"]

    if payload["valid"]:
        ranked = rank_valid(
            payload["valid"], constraints=constraints,
            data=data or load_structured_data(), validation=payload,
        )
        return {
            "decision": "recommend",
            "ranked": ranked,
            "constraints": constraints,
        }

    blockers = analyze_blockers(payload)
    relaxations = _simulate_relaxations(payload, constraints, data)
    return {
        "decision": "relax",
        "blockers": blockers,
        "relaxation_suggestions": relaxations,
        "constraints": constraints,
    }


def _simulate_relaxations(payload: dict, constraints: dict, data: dict | None) -> dict[str, dict]:
    """For each blocker, re-validate the SAME retrieved items without it."""
    data = data or load_structured_data()
    current = len(payload["valid"])
    suggestions: dict[str, dict] = {}
    for blocker in analyze_blockers(payload):
        relaxed = remove_constraint(constraints, blocker["reason"])
        verdict = validate_items(payload["results"], relaxed, data=data)
        relaxed_count = len(verdict["valid"])
        suggestions[blocker["reason"]] = {
            "relaxed_count": relaxed_count,
            "extra": max(0, relaxed_count - current),
        }
    return suggestions


def agent_answer(user_query: str, k: int = 10, llm=None, data: dict | None = None,
                 order: OrderState | None = None) -> dict:
    """The full loop: intent routing -> (LLM -> RAG -> ASP) -> decision -> response.

    Lookup questions (price, policy, item detail, plain "general") with no
    choice constraint are answered directly from the database via
    retrieve.get_answer (decision "direct"), so they never degrade into a
    food recommendation. Everything else runs the neuro-symbolic loop: the
    LLM participates in constraint extraction (silent rule-based fallback)
    and the final response (response_step.generate_response, silent template
    fallback plus the grounding check). Every fact in the final response
    comes from the database or the ASP-validated payload.
    """
    constraints = extract_constraints(user_query, llm=llm)

    # A priced order total is a database lookup even when the extractor labels
    # it a recommendation (e.g. the word "want" in "I want one kottu").
    if _is_direct_query(constraints) or (
        is_order_total(user_query) and not _has_choice_constraint(constraints)
    ):
        return {
            "user_query": user_query,
            "decision": "direct",
            "constraints": constraints,
            "valid": [],
            "invalid": [],
            "policy": {},
            "ranked": [],
            "blockers": [],
            "relaxation_suggestions": {},
            "answer": get_answer(user_query, order=order),
            "llm_used": False,
        }

    payload = retrieve_and_validate(
        user_query, k=k, llm=llm, data=data, constraints=constraints
    )
    decision = decide(payload, data=data)
    answer, llm_used = generate_response(user_query, decision, llm=llm, data=data)

    return {
        "user_query": user_query,
        "decision": decision["decision"],
        "constraints": payload["constraints"],
        "valid": payload["valid"],
        "invalid": payload["invalid"],
        "policy": payload["policy"],
        "ranked": decision.get("ranked", []),
        "blockers": decision.get("blockers", []),
        "relaxation_suggestions": decision.get("relaxation_suggestions", {}),
        "answer": answer,
        "llm_used": llm_used,
    }


# ------------------------------------------------------------- display

def _print_decision(result: dict) -> None:
    print("=" * 64)
    print(f"USER QUERY: {result['user_query']}")
    print(f"DECISION  : {result['decision'].upper()}")
    print("=" * 64)

    if result["decision"] == "direct":
        print("\nANSWER (direct database lookup, no RAG/ASP loop needed)")
        print("-" * 64)
        print(result["answer"])
        return

    print("\nASP verdicts")
    print("-" * 64)
    print(f"  valid  : {', '.join(r['item_name'] for r in result['valid']) or 'NONE'}")
    print(f"  invalid: {len(result['invalid'])} item(s)")
    for row in result["invalid"]:
        print(f"    - {row['item_name']}: {', '.join(row['reasons'])}")

    if result["decision"] == "recommend":
        print("\nRANKED valid options -> LLM")
        print("-" * 64)
        for row in result["ranked"]:
            print(f"  {row['rank']}. {row['item_name']} ({row['price']}) similarity={row['score']}")
        print(f"\nLLM was used: {result['llm_used']}")
    else:
        print("\nDIAGNOSIS (from ASP failure counts)")
        print("-" * 64)
        for blocker in result["blockers"]:
            extra = result["relaxation_suggestions"].get(blocker["reason"], {})
            line = (f"  {blocker['label']} ({blocker['user_value']}) blocked "
                    f"{blocker['blocked_n']} candidate(s)")
            if extra:
                line += f"  | relax -> +{extra['extra']} available"
            print(line)

    print("\nANSWER")
    print("-" * 64)
    print(result["answer"])
    if result["policy"].get("violations"):
        print("\nPOLICY NOTICE: " + ", ".join(result["policy"]["violations"]))


def main() -> None:
    parser = argparse.ArgumentParser(description="LLM + RAG + ASP decision loop")
    parser.add_argument("query", nargs="+", help="user request in natural language")
    parser.add_argument("-k", type=int, default=10, help="retrieve K items (default 10)")
    parser.add_argument("--json", action="store_true", help="print raw JSON result")
    args = parser.parse_args()

    result = agent_answer(" ".join(args.query), k=args.k, llm=get_llm_client())
    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        _print_decision(result)


if __name__ == "__main__":
    main()