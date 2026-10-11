% =====================================================================
% asp_rules.lp  -  Answer Set Programming rules for validating
%                 restaurant recommendations (step 13).
%
% The Python module asp_reasoner.py generates the FACTS below and prepends
% them to this file, then asks clingo for the answer set:
%
%   Part A - menu facts            Part B - user constraints
%     menu_item/1                    budget_limit/1, no_budget_limit/0
%     price/2, calories/2            diet_requested/0, no_diet_requested/0
%     dietary_tag/2                  wants_diet/1
%     allergen/2, ingredient/2       avoid_allergen/1, avoid_ingredient/1
%     policy/1, forbids/2            calorie_limit/1, request_action/1
%
%  PRICES AND BUDGETS ARE INTEGER USD CENTS: clingo has no float literals,
%  so $8.99 is price(item, 899) and the wrapper converts budgets to cents too.
%
% =====================================================================


% ---------------------------------------------------------------------
% 0. INTEGRITY - mutually exclusive user markers.
%    "Contradictory user facts (e.g. both 'diet requested' and 'no diet
%     requested') would let the rules derive an item as BOTH valid and
%     diet-failing. These constraints make such input unsatisfiable, so
%     the program fails loudly instead of reporting nonsense."
% ---------------------------------------------------------------------
:- diet_requested, no_diet_requested.
:- budget_limit(_), no_budget_limit.


% ---------------------------------------------------------------------
% 1. BUDGET
%    "An item is 'above_budget' when its known price is higher than the
%     budget the user set. The wrapper converts the user's currency into
%     USD first, so clingo only ever compares prices in one currency."
% ---------------------------------------------------------------------
above_budget(I) :- price(I, P), budget_limit(L), P > L.


% ---------------------------------------------------------------------
% 2. DIETARY REQUIREMENTS
%    "An item satisfies the diet need when it carries a required dietary
%     tag (e.g. a 'vegetarian' item satisfies 'wants_diet(vegetarian)')."
% ---------------------------------------------------------------------
satisfies_diet(I) :- menu_item(I), dietary_tag(I, D), wants_diet(D).

%    "If the user had no dietary requirement, EVERY item satisfies diet,
%     so the rule can never wrongly reject anything."
satisfies_diet(I) :- menu_item(I), no_diet_requested.


% ---------------------------------------------------------------------
% 3. ALLERGIES
%    "An item violates an allergy constraint when it declares that
%     allergen. Only the user's allergens matter - any OTHER allergen the
%     dish contains (e.g. dairy) is irrelevant to a peanut allergy."
% ---------------------------------------------------------------------
violates_allergen(I) :- allergen(I, A), avoid_allergen(A).


% ---------------------------------------------------------------------
% 4. INGREDIENTS TO AVOID
%    "Same idea as allergens, but against the ingredient list."
% ---------------------------------------------------------------------
violates_ingredient(I) :- ingredient(I, G), avoid_ingredient(G).


% ---------------------------------------------------------------------
% 4a. CALORIE LIMIT
%    "An item breaks a stated calorie cap when its known calorie count is
%     higher than the limit the user set. Items without a calories/2 fact
%     are never rejected by this rule (unknown != over the limit)."
% ---------------------------------------------------------------------
above_calories(I) :- calories(I, C), calorie_limit(L), C > L.


% ---------------------------------------------------------------------
% 5. VALID RECOMMENDATION
%    "A menu item is a valid recommendation when it satisfies the diet
%     need AND is not over budget AND is within the calorie limit AND
%     declares none of the avoided allergens AND contains none of the
%     avoided ingredients."
% ---------------------------------------------------------------------
valid_item(I) :- menu_item(I),
                 satisfies_diet(I),
                 not above_budget(I),
                 not above_calories(I),
                 not violates_allergen(I),
                 not violates_ingredient(I).


% ---------------------------------------------------------------------
% 6. EXPLANATIONS ("why is this item NOT valid?")
%    Each failure reason is derived independently so the agent can tell
%    the user exactly which constraint a dish breaks.
% ---------------------------------------------------------------------
fails(I, budget)     :- menu_item(I), above_budget(I).
fails(I, diet)       :- menu_item(I), diet_requested, not satisfies_diet(I).
fails(I, allergy)    :- menu_item(I), violates_allergen(I).
fails(I, ingredient) :- menu_item(I), violates_ingredient(I).
fails(I, calories)   :- menu_item(I), above_calories(I).


% ---------------------------------------------------------------------
% 7. RESTAURANT POLICIES
%    Policies are validated at the REQUEST level, not the item level:
%    the user's request asks for certain actions (bring a cake, reserve a
%    table, bring a pet), and a policy states which actions are forbidden.
% ---------------------------------------------------------------------
%    "An action is forbidden when some policy forbids it."
forbidden(A) :- request_action(A), forbids(P, A).

%    "The request is policy-compliant when NO action it asks for is
%     forbidden."
policy_compliant :- not forbidden(_).

%    "Report WHICH policy was violated, for the explanation message."
policy_violation(P) :- request_action(A), forbids(P, A).


% ---------------------------------------------------------------------
% Output: keep the answer set readable.
% ---------------------------------------------------------------------
#show valid_item/1.
#show fails/2.
#show policy_compliant/0.
#show policy_violation/1.
#show forbidden/1.


% =====================================================================
% EXTENSIONS (commented - enable when needed)
% =====================================================================
%
% 8. CALORIE LIMIT: implemented as rule 4a above (calorie_limit/1 is
%    emitted by asp_reasoner.user_facts from other_constraints).
%
% 9. DERIVED TAGS instead of exact matches, e.g. an item with no meat
%    ingredient can be deduced vegetarian:
%    meat(dummy_id) :- ingredient(dummy_id, beef).
%    vegetarian_derived(I) :- menu_item(I), not meat(I).
%    (replace the exact-tag rule for more robust reasoning).
%
% 10. MULTIPLE RESTAURANTS:  at(Restaurant, Item) links items to places.
%    valid_at(R, I) :- at(R, I), valid_item(I).
%    #show valid_at/2.   ("make a reservation" can then pick R).
%
% 11. OPTIMISATION (cheapest first): with clingo -n 0
%    #minimize { P, I : price(I, P), valid_item(I) }.
%
% 12. MINIMUM COVER: only answer when a minimum number of options exists.
%    :- { valid_item(I) } < 3.      (unsat when fewer than 3 options)
% =====================================================================