"""Tests for step 11 - LLM intent & constraint extraction.

Uses MockLLM so no Ollama server is needed. Covers parsing, validation,
self-repair and the offline rule fallback.

Run:  python test_intent_extractor.py
"""

from __future__ import annotations

import json
import unittest

from intent_extractor import (
    EXTRACTION_SCHEMA,
    build_messages,
    cross_check,
    default_output,
    extract_constraints,
    fallback_extract,
    normalize_output,
    parse_json,
)
from llm_client import LLMUnavailableError, MockLLM

EXAMPLE_QUERY = "I want a vegetarian meal under Rs. 1500 without peanuts."


def valid_answer(**overrides) -> str:
    answer = default_output()
    answer.update(
        {
            "intent": "restaurant_recommendation",
            "budget": 1500.0,
            "budget_currency": "inr",
            "dietary_requirements": ["vegetarian"],
            "allergies": ["peanut"],
        }
    )
    answer.update(overrides)
    return json.dumps(answer)


class ExtractionTestCase(unittest.TestCase):
    def test_prompt_includes_schema_and_rules(self) -> None:
        messages = build_messages(EXAMPLE_QUERY)
        system = messages[0]["content"]
        self.assertEqual(messages[0]["role"], "system")
        self.assertEqual(messages[1]["role"], "user")
        self.assertIn("intent", system)
        self.assertIn("restaurant_recommendation", system)
        self.assertIn(json.dumps(EXTRACTION_SCHEMA, indent=2), system)
        self.assertIn("never", system.lower())

    def test_happy_path_llm_extraction(self) -> None:
        llm = MockLLM(lambda messages, n: valid_answer())
        result = extract_constraints(EXAMPLE_QUERY, llm=llm)
        self.assertEqual(result["method"], "llm")
        self.assertEqual(result["intent"], "restaurant_recommendation")
        self.assertEqual(result["budget"], 1500.0)
        self.assertEqual(result["budget_currency"], "inr")
        self.assertEqual(result["dietary_requirements"], ["vegetarian"])
        self.assertEqual(result["allergies"], ["peanut"])
        self.assertEqual(result["ingredients_to_avoid"], [])
        self.assertEqual(llm.calls, 1)

    def test_self_repair_on_invalid_but_parseable_json(self) -> None:
        responses = iter(
            [
                '{"intent": "pizza", "budget": 0}',
                valid_answer(),
            ]
        )
        llm = MockLLM(lambda messages, n: next(responses))
        result = extract_constraints(EXAMPLE_QUERY, llm=llm)
        self.assertEqual(result["method"], "llm_repaired")
        self.assertEqual(result["intent"], "restaurant_recommendation")
        self.assertEqual(llm.calls, 2)

    def test_repair_message_contains_error_feedback(self) -> None:
        seen_messages: list[list[dict]] = []

        def responder(messages: list[dict], n: int) -> str:
            seen_messages.append(messages)
            if n == 1:
                return '{"intent": "pizza"}'
            return valid_answer()

        llm = MockLLM(responder)
        extract_constraints(EXAMPLE_QUERY, llm=llm)
        last_user = seen_messages[1][-1]["content"].lower()
        self.assertIn("invalid intent", last_user)
        self.assertIn("corrected", last_user)

    def test_no_llm_falls_back_offline(self) -> None:
        result = extract_constraints(EXAMPLE_QUERY, llm=None)
        self.assertEqual(result["method"], "fallback")
        self.assertEqual(result["intent"], "restaurant_recommendation")
        self.assertEqual(result["budget"], 1500.0)
        self.assertEqual(result["budget_currency"], "inr")
        self.assertEqual(result["dietary_requirements"], ["vegetarian"])
        self.assertIn("peanut", result["allergies"])
        self.assertIn("peanut", result["ingredients_to_avoid"])

    def test_fallback_rejects_when_llm_unavailable(self) -> None:
        def broken(messages, n):
            raise LLMUnavailableError("server down")

        llm = MockLLM(broken)
        result = extract_constraints("vegan meal under $6", llm=llm)
        self.assertEqual(result["method"], "fallback")
        self.assertEqual(result["budget"], 6.0)
        self.assertEqual(result["budget_currency"], "usd")
        self.assertEqual(result["dietary_requirements"], ["vegan"])

    def test_fallback_reservation_detection(self) -> None:
        result = fallback_extract("Can I reserve a table for six tonight?")
        self.assertEqual(result["intent"], "reservation")
        self.assertIsNone(result["budget"])

    def test_fallback_policy_detection(self) -> None:
        result = fallback_extract("what is your cancellation policy?")
        self.assertEqual(result["intent"], "policy_query")

    def test_parse_json_tolerates_markdown_fences(self) -> None:
        wrapped = "```json\n" + valid_answer() + "\n```"
        parsed = parse_json(wrapped)
        self.assertEqual(parsed["intent"], "restaurant_recommendation")

    def test_parse_json_rejects_garbage(self) -> None:
        self.assertIsNone(parse_json("this is not json"))
        self.assertIsNone(parse_json(""))
        self.assertIsNone(parse_json('[1, 2, 3]'))

    def test_normalize_coerces_string_to_list(self) -> None:
        out, errors = normalize_output(
            {
                "intent": "restaurant_recommendation",
                "dietary_requirements": "vegetarian",
                "ingredients_preferred": [" chicken ", "Chicken"],
            }
        )
        self.assertEqual(errors, [])
        self.assertEqual(out["dietary_requirements"], ["vegetarian"])
        self.assertEqual(out["ingredients_preferred"], ["chicken"])

    def test_normalize_rejects_invalid_intent(self) -> None:
        out, errors = normalize_output({"intent": "pizza"})
        self.assertNotEqual(out["intent"], "pizza")
        self.assertTrue(any("intent" in error for error in errors))

    def test_normalize_rejects_negative_budget(self) -> None:
        _, errors = normalize_output({"intent": "price_query", "budget": -5})
        self.assertTrue(any("budget" in error for error in errors))

    def test_normalize_rejects_budget_without_currency(self) -> None:
        _, errors = normalize_output({"intent": "price_query", "budget": 5})
        self.assertTrue(any("budget_currency" in error for error in errors))

    def test_normalize_warns_on_unknown_keys(self) -> None:
        _, errors = normalize_output(
            {"intent": "general", "favorite_color": "blue"}
        )
        self.assertTrue(any("unknown" in error for error in errors))

    def test_cross_check_flags_unknown_values_and_currency(self) -> None:
        out = default_output()
        out["dietary_requirements"] = ["xenodiet"]
        out["allergies"] = ["xenonite"]
        alerts = cross_check(out)
        self.assertTrue(any("xenodiet" in alert for alert in alerts))
        self.assertTrue(any("xenonite" in alert for alert in alerts))

        out = default_output()
        out["budget_currency"] = "inr"
        alerts = cross_check(out)
        self.assertTrue(any("USD" in alert for alert in alerts))

    def test_cross_check_accepts_known_values(self) -> None:
        out = default_output()
        out["dietary_requirements"] = ["vegetarian"]
        out["allergies"] = ["peanut"]
        out["budget_currency"] = "usd"
        self.assertEqual(cross_check(out), [])

    def test_output_always_has_expected_shape(self) -> None:
        result = extract_constraints("", llm=None)
        self.assertEqual(
            set(result),
            set(default_output()) | {"method", "warnings"},
        )


class FallbackRobustnessTestCase(unittest.TestCase):
    """Regression tests for the wrong-answer bugs found in the full loop."""

    def test_plural_words_still_classify_policy(self) -> None:
        # "discounts"/"cancellations" used to fall through \b(discount)\b
        # and the query was answered as a food recommendation instead.
        for query in (
            "Do you offer any student discounts?",
            "What is your cancellation policy?",
            "Are there refunds if I cancel?",
        ):
            with self.subTest(query=query):
                self.assertEqual(fallback_extract(query)["intent"], "policy_query")

    def test_vegan_plural_and_vegetarian_plural(self) -> None:
        out = fallback_extract("Which meals are suitable for vegans?")
        self.assertEqual(out["intent"], "restaurant_recommendation")
        self.assertIn("vegan", out["dietary_requirements"])

    def test_hyphenated_dietary_tag_is_extracted(self) -> None:
        # The DB tag is "Low Calorie" (space) but users write "low-calorie".
        out = fallback_extract("Are there any low-calorie meal options?")
        self.assertIn("low calorie", out["dietary_requirements"])

    def test_meal_plural_still_classifies_as_recommendation(self) -> None:
        out = fallback_extract("What meals do you recommend?")
        self.assertEqual(out["intent"], "restaurant_recommendation")

    def test_calorie_constraint_keeps_the_actual_number(self) -> None:
        # "under N calories" must stay numeric so asp_reasoner can emit the
        # calorie_limit/1 fact (the old label dropped the number).
        out = fallback_extract("recommend something under 600 calories")
        self.assertIn("under 600 calories", out["other_constraints"])

    def test_dish_names_are_not_treated_as_allergies(self) -> None:
        # "chicken" and "mushroom" are registered allergens in the database,
        # but here they name dishes, so they must not become allergy filters
        # (the bug that filtered out the very dishes the user asked for).
        out = fallback_extract("Can I get chicken kottu and mushroom soup?")
        self.assertEqual(out["allergies"], [])
        self.assertEqual(out["ingredients_to_avoid"], [])

    def test_explicit_allergy_cue_still_detected(self) -> None:
        out = fallback_extract("I am allergic to chicken and mushroom")
        self.assertIn("chicken", out["allergies"])
        self.assertIn("mushroom", out["allergies"])

    def test_order_total_classifies_as_price_query(self) -> None:
        out = fallback_extract(
            "i want one chicken kottu and iced tea, give me a total price"
        )
        self.assertEqual(out["intent"], "price_query")


if __name__ == "__main__":
    unittest.main(verbosity=2)