"""Step 13 - ASP constraint validation for restaurant recommendations.

Bridges the LLM constraints (step 11) with an Answer Set Program written in
asp_rules.lp:

    constraints dict (JSON)
        --> generated FACTS (menu rows become price/dietary_tag/allergen/
            ingredient facts; constraints become budget_limit/wants_diet/
            avoid_* facts)
        --> + asp_rules.lp (rules)
        --> clingo solves
        --> valid_item(...) facts + fails(item, reason) explanations
        --> structured result

Two currencies never meet inside the logic program: the wrapper converts a
non-USD budget into USD first (documented exchange rates below), so the ASP
only ever compares prices in one unit.

Run:  python asp_reasoner.py "I want a vegetarian meal under Rs. 1500 without peanuts."
"""

from __future__ import annotations

import argparse
import json
import re

import clingo

from intent_extractor import extract_constraints
from llm_client import get_llm_client
from retrieve import BASE_DIR, load_structured_data

RULES_PATH = BASE_DIR / "asp_rules.lp"
with RULES_PATH.open(encoding="utf-8") as handle:
    RULES_TEXT = handle.read()

# Documented assumption for the research prototype. Rates are illustrative.
CURRENCY_TO_USD = {
    "usd": 1.0,
    "inr": 0.012,
    "lkr": 0.0031,
    "eur": 1.08,
    "gbp": 1.27,
}

# Curated subset of the restaurant's policy knowledge base (formalised from
# DataSources). One fact per rule: policy(name) + forbids(policy, action).
POLICY_FACTS = [
    'policy("no_outside_food").',
    'policy("no_pets").',
    'policy("no_smoking").',
    'forbids("no_outside_food", "bring_outside_food").',
    'forbids("no_pets", "bring_pet").',
    'forbids("no_smoking", "smoke_inside").',
]


def _q(value: object) -> str:
    """Render a value as a quoted lowercase clingo string constant."""
    return '"' + str(value).strip().lower() + '"'


# ------------------------------------------------------------- facts builder

def menu_facts(data: dict[str, object]) -> str:
    """Turn the relational data into facts: one line per menu item."""
    lines: list[str] = []
    for item in data["menu_items_by_id"].values():  # type: ignore[union-attr]
        item_id = int(item["item_id"])  # type: ignore[arg-type]
        name = str(item["item_name"])
        lines.append(f"menu_item({_q(name)}).")
        # clingo has no float literals, so prices are emitted as integer cents
        # (e.g. $8.99 -> price(name, 899)). Budgets are converted the same way.
        lines.append(f"price({_q(name)}, {int(round(float(item['price']) * 100))}).")  # type: ignore[arg-type]
        try:
            calories = int(float(item["calories"]))  # type: ignore[arg-type]
            lines.append(f"calories({_q(name)}, {calories}).")
        except (TypeError, ValueError):
            pass
        for tag in (round2 := data["item_dietary"].get(item_id)) or []:  # type: ignore[union-attr]
            lines.append(f"dietary_tag({_q(name)}, {_q(tag)}).")
        for allergen in data["item_allergens"].get(item_id) or []:  # type: ignore[union-attr]
            lines.append(f"allergen({_q(name)}, {_q(allergen)}).")
        for ingredient in data["item_ingredients"].get(item_id) or []:  # type: ignore[union-attr]
            lines.append(f"ingredient({_q(name)}, {_q(ingredient)}).")
    return "\n".join(lines)


def budget_to_usd(budget, currency) -> tuple[float | None, str | None]:
    """Convert a user budget into USD, or (None, warning) when not possible."""
    if budget is None:
        return None, None
    if currency is None:
        # No currency unit in the request. The entire menu is priced in USD
        # (and retrieve.py already applies an unlabelled budget as dollars),
        # so an unlabelled budget is treated as USD too.
        return float(budget), None
    if currency not in CURRENCY_TO_USD:
        return None, (
            f"budget currency {currency or 'unknown'} is not supported; "
            "no price filter was applied by the ASP"
        )
    return float(budget) * CURRENCY_TO_USD[currency], None


def user_facts(constraints: dict) -> tuple[str, list[str]]:
    """Generate user-constraint facts; second element is warnings."""
    lines: list[str] = []
    warnings: list[str] = []

    budget, warning = budget_to_usd(
        constraints.get("budget"), constraints.get("budget_currency")
    )
    if warning:
        warnings.append(warning)
    if budget is not None:
        lines.append(f"budget_limit({int(round(budget * 100))}).")  # USD cents
    else:
        lines.append("no_budget_limit.")

    diets = constraints.get("dietary_requirements") or []
    if diets:
        lines.append("diet_requested.")
        lines.extend(f"wants_diet({_q(diet)})." for diet in diets)
    else:
        lines.append("no_diet_requested.")

    lines.extend(
        f"avoid_allergen({_q(allergy)})." for allergy in constraints.get("allergies") or []
    )
    lines.extend(
        f"avoid_ingredient({_q(item)})."
        for item in constraints.get("ingredients_to_avoid") or []
    )

    # Numeric calorie cap from other_constraints ("under 600 calories" -> a
    # calorie_limit/1 fact; the rules compare it against calories/2 facts).
    for constraint in constraints.get("other_constraints") or []:
        match = re.search(r"under\s+(\d+)\s*(?:calories|kcal)", str(constraint), re.IGNORECASE)
        if match:
            lines.append(f"calorie_limit({int(match.group(1))}).")
            break  # one cap: the first stated limit wins
    return "\n".join(lines), warnings


def detect_request_actions(constraints: dict, query: str = "") -> list[str]:
    """Decide which actions the user's REQUEST asks for (for policies)."""
    text = " ".join(constraints.get("other_constraints") or [])
    text += " " + (query or "").lower()

    actions: list[str] = []
    if constraints.get("intent") == "reservation":
        actions.append("reserve_table")
    if re.search(r"\b(cake|outside food|own food|bring.*(food|bottle))\b", text):
        actions.append("bring_outside_food")
    if re.search(r"\b(pet|pets|dog|cat)\b", text):
        actions.append("bring_pet")
    if re.search(r"\bsmok\w*", text):
        actions.append("smoke_inside")
    return actions


def build_program(constraints: dict, query: str = "", data: dict[str, object] | None = None) -> tuple[str, list[str]]:
    """Full clingo program: menu facts + user facts + policy facts + rules."""
    data = data or load_structured_data()
    user_text, warnings = user_facts(constraints)

    actions = detect_request_actions(constraints, query)
    request_facts = "\n".join(
        f"request_action({_q(action)})." for action in actions
    )
    policy_facts = "\n".join(POLICY_FACTS)

    program = "\n".join([
        f"% ---------- menu facts ({len(data['menu_items_by_id'])} items) ----------",
        menu_facts(data),
        "% ---------- user constraints ----------",
        user_text,
        "% ---------- policies ----------",
        policy_facts,
        request_facts,
        "% ---------- rules ----------",
        RULES_TEXT,
    ])
    return program, warnings


# ------------------------------------------------------------- solver

def run_clingo(program: str) -> dict:
    """Solve one answer set and return all atoms grouped by predicate name."""
    control = clingo.Control(["1", "-W", "no-atom-undefined"])  # one answer set; quiet
    control.add("base", [], program)
    control.ground([("base", [])])

    atoms: dict[str, list[list[object]]] = {}
    had_model = False

    def on_model(model) -> None:
        nonlocal had_model
        had_model = True
        for symbol in model.symbols(atoms=True):
            args = [
                arg.string if arg.type == clingo.SymbolType.String else arg
                for arg in symbol.arguments
            ]
            atoms.setdefault(symbol.name, []).append(args)

    control.solve(on_model=on_model)
    if not had_model:
        raise ValueError("ASP program has no answer set (unsatisfiable).")
    return atoms


def solve(
    constraints: dict,
    query: str = "",
    data: dict[str, object] | None = None,
) -> dict:
    """Validate recommendations against the user constraints via ASP."""
    data = data or load_structured_data()
    program, warnings = build_program(constraints, query=query, data=data)
    atoms = run_clingo(program)

    valid = sorted(str(name) for [name] in atoms.get("valid_item", []))

    reasons: dict[str, int] = {}
    reason_examples: dict[str, list[str]] = {}
    for [item, why] in atoms.get("fails", []):
        why = str(why)
        item = str(item)
        reasons[why] = reasons.get(why, 0) + 1
        reason_examples.setdefault(why, [])
        if len(reason_examples[why]) < 5:
            reason_examples[why].append(item)

    violations = sorted(str(p) for [p] in atoms.get("policy_violation", []))
    forbidden = sorted(str(a) for [a] in atoms.get("forbidden", []))

    return {
        "valid_items": valid,
        "valid_count": len(valid),
        "total_items": len(data["menu_items_by_id"]),  # type: ignore[arg-type]
        "failure_counts": reasons,
        "failure_examples": reason_examples,
        "policy": {
            "compliant": bool(atoms.get("policy_compliant")),
            "violations": violations,
            "forbidden_actions": forbidden,
        },
        "request_actions": [
            str(a) for [a] in atoms.get("request_action", [])
        ],
        "warnings": warnings,
    }


# ------------------------------------------------------------- display

def _print_result(constraints: dict, result: dict) -> None:
    print("CONSTRAINTS (from LLM extraction, step 11)")
    print("-" * 60)
    for key in (
        "intent", "restaurant_preference", "budget", "budget_currency",
        "dietary_requirements", "allergies", "ingredients_to_avoid",
        "ingredients_preferred",
    ):
        print(f"  {key:26} {constraints.get(key)!r}")

    print("\nASP VALIDATION (asp_rules.lp + clingo)")
    print("-" * 60)
    print(f"  total menu items   : {result['total_items']}")
    print(f"  valid items        : {result['valid_count']}")
    for reason, count in sorted(result["failure_counts"].items()):
        examples = ", ".join(result["failure_examples"].get(reason, [])[:5])
        print(f"  rejected: {reason:12} {count:3}   (e.g. {examples})")

    policy = result["policy"]
    if policy["violations"]:
        print("\n  POLICY: NOT COMPLIANT")
        for violation in policy["violations"]:
            print(f"    - violates policy: {violation}")
        print(f"    forbidden actions: {policy['forbidden_actions']}")
    else:
        print("\n  POLICY: compliant")

    if result["warnings"]:
        print("\n  warnings:")
        for warning in result["warnings"]:
            print(f"    - {warning}")

    print("\n  valid items (first 12):")
    for name in result["valid_items"][:12]:
        print(f"    - {name}")


def main() -> None:
    parser = argparse.ArgumentParser(description="ASP validation of recommendations")
    parser.add_argument("query", nargs="+", help="user request in natural language")
    parser.add_argument("--json", action="store_true", help="print raw JSON output")
    args = parser.parse_args()
    query = " ".join(args.query)

    constraints = extract_constraints(query, llm=get_llm_client())
    result = solve(constraints, query=query)

    if args.json:
        print(json.dumps({"constraints": constraints, "result": result}, indent=2, ensure_ascii=False))
    else:
        _print_result(constraints, result)


if __name__ == "__main__":
    main()