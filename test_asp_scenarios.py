"""ASP-only scenario tests - run BEFORE connecting the solver to RAG.

Each scenario builds a small, fixed knowledge base (KB_FACTS: 5 menu items +
restaurant policy) and a per-case set of USER CONSTRAINT FACTS, then solves
KB + constraints + asp_rules.lp with clingo. Unlike test_asp_reasoner.py this
never touches the SQL dump, the vector store, or the LLM - it is a pure logic
white-box test of the rules in asp_rules.lp.

Scenarios:
  S1 valid budget          S4 vegan requirement        S7 multiple constraints
  S2 budget violation      S5 allergy violation       S8 no valid menu item
  S3 vegetarian req.       S6 ingredient avoidance    S9 policy violation
  I1/I2 integrity (contradictory markers)
"""

from __future__ import annotations

import unittest

from asp_reasoner import RULES_TEXT, run_clingo

# ---------------------------------------------------------------------------
# INPUT FACTS - a fixed, independent knowledge base (stand-in for the SQL dump)
# ---------------------------------------------------------------------------
KB_FACTS = """
% --- menu items ---
menu_item("veg_pasta").
price("veg_pasta", 899).                      % $8.99
dietary_tag("veg_pasta", "vegetarian").
allergen("veg_pasta", "dairy").
ingredient("veg_pasta", "pasta").
ingredient("veg_pasta", "tomato").

menu_item("vegan_bowl").
price("vegan_bowl", 1099).                    % $10.99
dietary_tag("vegan_bowl", "vegan").
dietary_tag("vegan_bowl", "vegetarian").
allergen("vegan_bowl", "soy").
ingredient("vegan_bowl", "quinoa").
ingredient("vegan_bowl", "vegetables").

menu_item("peanut_cookie").
price("peanut_cookie", 399).                  % $3.99
allergen("peanut_cookie", "peanut").
ingredient("peanut_cookie", "peanut butter").
ingredient("peanut_cookie", "sugar").

menu_item("steak").
price("steak", 2499).                         % $24.99
ingredient("steak", "beef").

menu_item("veg_platter").
price("veg_platter", 3999).                   % $39.99
dietary_tag("veg_platter", "vegetarian").
ingredient("veg_platter", "vegetables").

% --- restaurant policy knowledge base ---
policy("no_outside_food").
policy("no_pets").
policy("no_smoking").
forbids("no_outside_food", "bring_outside_food").
forbids("no_pets", "bring_pet").
forbids("no_smoking", "smoke_inside").
"""


def _signatures(atoms: dict) -> set[tuple[str, ...]]:
    """Flatten atoms into ('predicate', arg1, arg2, ...) string tuples."""
    return {
        (name,) + tuple(str(arg) for arg in args)
        for name, arglists in atoms.items()
        for args in arglists
    }


def _solve(constraints: str) -> set[tuple[str, ...]]:
    return _signatures(run_clingo(KB_FACTS + "\n" + constraints + "\n" + RULES_TEXT))


# ---------------------------------------------------------------------------
# SCENARIO SPECS - one dict per case, with the five required sections.
#   user        : the natural-language request (for the report)
#   constraints : ASP facts for that user only
#   expect      : answer-set atoms that MUST be present
#   reject      : answer-set atoms that MUST be absent
#   explains    : plain-language reasoning
# Rules are always the whole asp_rules.lp (relevant rule numbers in explains).
# ---------------------------------------------------------------------------
SCENARIOS = [
    {
        "id": "S1",
        "title": "Valid budget",
        "user": "Budget = $10, no diet, no allergies.",
        "constraints": 'budget_limit(1000).\nno_diet_requested.',
        "expect": [
            ("valid_item", "veg_pasta"),
            ("valid_item", "peanut_cookie"),
            ("policy_compliant",),
        ],
        "reject": [
            ("valid_item", "vegan_bowl"),
            ("valid_item", "steak"),
            ("valid_item", "veg_platter"),
            ("fails", "veg_pasta", "budget"),
            ("fails", "peanut_cookie", "diet"),
        ],
        "explains": (
            "Rule 1: above_budget is false for veg_pasta (899 <= 1000) and "
            "peanut_cookie (399 <= 1000), true for the other three. Rule 2: "
            "no_diet_requested makes every item satisfy diet. Rule 5 combines "
            "them. Rule 6 records budget failures only for items actually over "
            "budget. No request actions => Rule 7 reports policy_compliant."
        ),
    },
    {
        "id": "S2",
        "title": "Budget violation",
        "user": "Budget = $4, no diet, no allergies.",
        "constraints": 'budget_limit(400).\nno_diet_requested.',
        "expect": [
            ("valid_item", "peanut_cookie"),
            ("fails", "veg_pasta", "budget"),
            ("fails", "vegan_bowl", "budget"),
            ("fails", "steak", "budget"),
            ("fails", "veg_platter", "budget"),
        ],
        "reject": [
            ("valid_item", "veg_pasta"),
            ("fails", "peanut_cookie", "budget"),
        ],
        "explains": (
            "Rule 1 uses strict greater-than (P > 400), so an item priced "
            "exactly $4.00 would NOT be above budget - budget is inclusive "
            "('at most'). Only peanut_cookie (399) survives. Note the semantic "
            "choice: 'under $4' in speech often means < $4; current rules mean "
            "'up to $4'. Flagged, not changed, to match the extractor."
        ),
    },
    {
        "id": "S3",
        "title": "Vegetarian requirement",
        "user": "Vegetarian, no budget, no allergies.",
        "constraints": 'diet_requested.\nwants_diet("vegetarian").\nno_budget_limit.',
        "expect": [
            ("valid_item", "veg_pasta"),
            ("valid_item", "vegan_bowl"),
            ("valid_item", "veg_platter"),
            ("fails", "peanut_cookie", "diet"),
            ("fails", "steak", "diet"),
        ],
        "reject": [
            ("valid_item", "peanut_cookie"),
            ("valid_item", "steak"),
            ("fails", "veg_pasta", "diet"),
        ],
        "explains": (
            "Rule 2 matches items carrying the literal 'vegetarian' tag. "
            "vegan_bowl passes because our knowledge base tags it vegetarian "
            "as well (vegan implies vegetarian by data, not by rule). "
            "peanut_cookie and steak carry no vegetarian tag, so "
            "satisfies_diet is false and Rule 5 rejects them; Rule 6 records "
            "the diet failure. Rule 4 (no_budget_limit) provides no above_budget."
        ),
    },
    {
        "id": "S4",
        "title": "Vegan requirement",
        "user": "Vegan, no budget, no allergies.",
        "constraints": 'diet_requested.\nwants_diet("vegan").\nno_budget_limit.',
        "expect": [
            ("valid_item", "vegan_bowl"),
            ("fails", "veg_pasta", "diet"),
            ("fails", "veg_platter", "diet"),
            ("fails", "peanut_cookie", "diet"),
            ("fails", "steak", "diet"),
        ],
        "reject": [
            ("valid_item", "veg_pasta"),
            ("valid_item", "veg_platter"),
        ],
        "explains": (
            "Vegan is STRICTER than vegetarian: Rule 2 requires the exact "
            "'vegan' tag, so vegetarian-only items are rejected. Correct logic; "
            "but it exposes a data limitation - a dish that is truly vegan yet "
            "only tagged vegetarian would be wrongly rejected. This is why the "
            "DERIVED-TAGS extension (rule 9 in asp_rules.lp) infers 'vegan' "
            "from ingredients instead of relying on tags alone."
        ),
    },
    {
        "id": "S5",
        "title": "Allergy violation",
        "user": "Allergic to peanuts, no diet, no budget.",
        "constraints": 'no_diet_requested.\nno_budget_limit.\navoid_allergen("peanut").',
        "expect": [
            ("valid_item", "veg_pasta"),
            ("valid_item", "vegan_bowl"),
            ("valid_item", "steak"),
            ("valid_item", "veg_platter"),
            ("fails", "peanut_cookie", "allergy"),
        ],
        "reject": [
            ("valid_item", "peanut_cookie"),
            ("fails", "veg_pasta", "allergy"),
        ],
        "explains": (
            "Rule 3: violates_allergen only when an item DECLARES an allergen "
            "the user AVOIDS. peanut_cookie declares peanut => rejected. "
            "veg_pasta declares only dairy, which is not avoided, so it stays "
            "valid - allergy matching is exact-set, not 'any allergen counts'."
        ),
    },
    {
        "id": "S6",
        "title": "Ingredient avoidance",
        "user": "Avoid beef as an ingredient, no diet, no budget.",
        "constraints": 'no_diet_requested.\nno_budget_limit.\navoid_ingredient("beef").',
        "expect": [
            ("valid_item", "veg_pasta"),
            ("valid_item", "vegan_bowl"),
            ("valid_item", "peanut_cookie"),
            ("valid_item", "veg_platter"),
            ("fails", "steak", "ingredient"),
        ],
        "reject": [
            ("valid_item", "steak"),
            ("fails", "peanut_cookie", "ingredient"),
        ],
        "explains": (
            "Rule 4 works like Rule 3 but against ingredients. Only steak lists "
            "beef, so only steak fails. Note peanut_cookie lists the ingredient "
            "'peanut butter', not 'peanut' - exact symbol equality keeps it "
            "valid unless the avoid word equals a stored ingredient verbatim."
        ),
    },
    {
        "id": "S7",
        "title": "Multiple constraints",
        "user": "Vegetarian, budget $10, allergic to peanuts and soy.",
        "constraints": (
            'budget_limit(1000).\n'
            'diet_requested.\nwants_diet("vegetarian").\n'
            'avoid_allergen("peanut").\navoid_allergen("soy").'
        ),
        "expect": [
            ("valid_item", "veg_pasta"),
            ("fails", "peanut_cookie", "diet"),
            ("fails", "peanut_cookie", "allergy"),
            ("fails", "vegan_bowl", "budget"),
            ("fails", "vegan_bowl", "allergy"),
            ("fails", "veg_platter", "budget"),
            ("fails", "steak", "budget"),
            ("fails", "steak", "diet"),
        ],
        "reject": [
            ("valid_item", "vegan_bowl"),
            ("valid_item", "steak"),
            ("valid_item", "veg_platter"),
            ("valid_item", "peanut_cookie"),
        ],
        "explains": (
            "Each rule acts independently, so ONE item can fail MANY "
            "constraints: peanut_cookie fails diet AND allergy; vegan_bowl "
            "fails budget AND allergy; steak fails budget AND diet. Only "
            "veg_pasta passes every check (Rule 5 requires ALL to pass and "
            "violating none). The fails/2 set gives the explainer every reason, "
            "not just the first."
        ),
    },
    {
        "id": "S8",
        "title": "No valid menu item",
        "user": "Vegan and allergic to soy. (Only vegan item contains soy.)",
        "constraints": 'diet_requested.\nwants_diet("vegan").\navoid_allergen("soy").',
        "expect": [
            ("fails", "vegan_bowl", "allergy"),
            ("fails", "veg_pasta", "diet"),
            ("fails", "veg_platter", "diet"),
            ("fails", "peanut_cookie", "diet"),
            ("fails", "steak", "diet"),
            ("policy_compliant",),
        ],
        "reject": [
            ("valid_item", "vegan_bowl"),
            ("valid_item", "veg_pasta"),
            ("valid_item", "steak"),
            ("valid_item", "peanut_cookie"),
            ("valid_item", "veg_platter"),
        ],
        "explains": (
            "Constraints are individually satisfiable but mutually exclusive: "
            "the only vegan item contains the avoided soy -> valid_item is "
            "EMPTY. The answer set is still satisfiable (valid_item absent, not "
            "program-unsatisfiable), and fails/2 explains EVERY rejection. "
            "Recognition of 'no match' comes from empty valid_item + non-empty "
            "fails. Optional hardening: the minimum-cover extension "
            "(:- { valid_item(I) } < 3.) would turn this into an explicit "
            "no-answer signal; the agent must then answer from fails/2."
        ),
    },
    {
        "id": "S9",
        "title": "Restaurant policy violation",
        "user": "Recommend under $5; also: bring my own birthday cake.",
        "constraints": (
            'budget_limit(500).\nno_diet_requested.\n'
            'request_action("bring_outside_food").'
        ),
        "expect": [
            ("valid_item", "peanut_cookie"),
            ("forbidden", "bring_outside_food"),
            ("policy_violation", "no_outside_food"),
        ],
        "reject": [
            ("policy_compliant",),
            ("valid_item", "veg_pasta"),
        ],
        "explains": (
            "Rule 7 checks the REQUEST, not the items: request_action(bring_"
            "outside_food) + forbids(no_outside_food, ...) => forbidden + "
            "policy_violation, and policy_compliant is absent. Item filtering "
            "still runs (peanut_cookie remains valid), because Rule 7 does not "
            "gate Rule 5. DESIGN NOTE: the agent must surface the policy "
            "violation separately; recommendations are not automatically "
            "withheld."
        ),
    },
]

INTEGRITY_CHECKS = [
    {
        "id": "I1",
        "title": "Both diet markers present",
        "constraints": "diet_requested.\nno_diet_requested.\nno_budget_limit.",
    },
    {
        "id": "I2",
        "title": "Both budget markers present",
        "constraints": "budget_limit(1000).\nno_budget_limit.\nno_diet_requested.",
    },
]


class ScenarioTests(unittest.TestCase):
    def test_all_scenarios(self) -> None:
        for scenario in SCENARIOS:
            with self.subTest(scenario=scenario["id"]):
                got = _solve(scenario["constraints"])
                for expected in scenario["expect"]:
                    self.assertIn(expected, got,
                                  f"[{scenario['id']}] missing {expected}")
                for rejected in scenario["reject"]:
                    self.assertNotIn(rejected, got,
                                     f"[{scenario['id']}] unexpected {rejected}")

    def test_integrity_markers_cause_unsatisfiable_program(self) -> None:
        for check in INTEGRITY_CHECKS:
            with self.subTest(check=check["id"]):
                with self.assertRaises(ValueError, msg=f"[{check['id']}] should be unsat"):
                    _solve(check["constraints"])


def report() -> str:
    lines = ["ASP scenario report (rules: asp_rules.lp)", "=" * 60]
    for scenario in SCENARIOS:
        lines.append(f"\n[{scenario['id']}] {scenario['title']}")
        lines.append(f"  User        : {scenario['user']}")
        lines.append(f"  Constraints : {scenario['constraints']!r}")
        lines.append(f"  Expect      : {scenario['expect']}")
        lines.append(f"  Reject      : {scenario['reject']}")
    return "\n".join(lines)


if __name__ == "__main__":
    print(report())
    unittest.main(verbosity=2)