"""Regression tests for the MCP abductive_reasoning handler (issue #2245).

Pre-fix the handler passed raw strings where ``Observation`` objects are
required, returned ``Hypothesis`` dataclasses that ``json.dumps`` rejects, and
capped results at the reasoner's default of 10 whatever ``max_hypotheses`` said.
"""

from __future__ import annotations

import json
import os
import unittest
from unittest.mock import patch

os.environ["SEMANTICA_DISABLE_PROGRESS"] = "1"

from semantica.reasoning import abductive_reasoner as abductive_module
from semantica.reasoning.reasoner import Rule
from semantica_mcp.mcp.server import _handle_tools_call
from semantica_mcp.mcp.tools.reasoning import handle_abductive_reasoning


def _reasoner_with_rules(count: int):
    """Patch AbductiveReasoner so the handler's reasoner already holds rules."""
    real_cls = abductive_module.AbductiveReasoner

    def factory(*args, **kwargs):
        reasoner = real_cls(*args, **kwargs)
        for i in range(count):
            reasoner.reasoner.add_rule(
                Rule(f"r{i}", f"cause_{i}", [f"Cause{i}(?x)"], "WetLawn(yard)")
            )
        return reasoner

    return patch.object(abductive_module, "AbductiveReasoner", factory)


class AbductiveReasoningHandlerTests(unittest.TestCase):
    def test_string_observations_yield_json_serialisable_hypotheses(self):
        with _reasoner_with_rules(1):
            result = handle_abductive_reasoning({"observations": ["WetLawn(yard)"]})

        self.assertNotIn("error", result)
        self.assertEqual(result["count"], 1)
        hypothesis = result["hypotheses"][0]
        self.assertIsInstance(hypothesis, dict)
        self.assertEqual(hypothesis["explanation"], "Hypothesis based on rule: cause_0")
        self.assertEqual(hypothesis["premises"], ["Cause0(?x)"])
        # server.py serialises the handler result outside the handler's try.
        json.dumps(result, ensure_ascii=False)

    def test_max_hypotheses_limits_the_result(self):
        with _reasoner_with_rules(4):
            result = handle_abductive_reasoning(
                {"observations": ["WetLawn(yard)"], "max_hypotheses": 2}
            )
        self.assertEqual(result["count"], 2)
        self.assertEqual(len(result["hypotheses"]), 2)

    def test_max_hypotheses_above_the_reasoner_default_is_honoured(self):
        with _reasoner_with_rules(12):
            result = handle_abductive_reasoning(
                {"observations": ["WetLawn(yard)"], "max_hypotheses": 12}
            )
        self.assertEqual(result["count"], 12)

    def test_no_rules_gives_an_empty_result_with_an_explanation(self):
        result = handle_abductive_reasoning({"observations": ["WetLawn(yard)"]})
        self.assertNotIn("error", result)
        self.assertEqual(result["hypotheses"], [])
        self.assertEqual(result["count"], 0)
        self.assertEqual(result["message"], "No rules available for abductive reasoning")

    def test_no_message_when_rules_are_present(self):
        with _reasoner_with_rules(1):
            result = handle_abductive_reasoning({"observations": ["WetLawn(yard)"]})
        self.assertNotIn("message", result)

    def test_result_survives_server_dispatch(self):
        # json.dumps in server.py runs outside the handler's try/except, so a
        # non-serialisable result fails the whole request rather than
        # becoming an "error" key. Go through the dispatch to cover that.
        with _reasoner_with_rules(1):
            response = _handle_tools_call(
                1,
                {"name": "abductive_reasoning", "arguments": {"observations": ["WetLawn(yard)"]}},
            )

        self.assertNotIn("error", response)
        self.assertFalse(response["result"]["isError"])
        payload = json.loads(response["result"]["content"][0]["text"])
        self.assertEqual(payload["count"], 1)
        self.assertEqual(payload["hypotheses"][0]["premises"], ["Cause0(?x)"])

    def test_no_rules_message_survives_server_dispatch(self):
        response = _handle_tools_call(
            1,
            {"name": "abductive_reasoning", "arguments": {"observations": ["WetLawn(yard)"]}},
        )
        payload = json.loads(response["result"]["content"][0]["text"])
        self.assertEqual(payload["count"], 0)
        self.assertEqual(payload["message"], "No rules available for abductive reasoning")

    def test_rules_argument_produces_hypotheses_end_to_end(self):
        response = _handle_tools_call(
            1,
            {
                "name": "abductive_reasoning",
                "arguments": {
                    "observations": ["WetLawn(yard)"],
                    "rules": ["IF Sprinkler(?x) THEN WetLawn(?x)"],
                },
            },
        )
        self.assertFalse(response["result"]["isError"])
        payload = json.loads(response["result"]["content"][0]["text"])
        self.assertEqual(payload["count"], 1)
        self.assertEqual(payload["hypotheses"][0]["premises"], ["Sprinkler(?x)"])
        self.assertNotIn("message", payload)

    def test_rules_that_do_not_explain_the_observation_give_no_hypotheses(self):
        result = handle_abductive_reasoning(
            {
                "observations": ["WetLawn(yard)"],
                "rules": ["IF Rain(?x) THEN WetRoad(?x)"],
            }
        )
        self.assertEqual(result["count"], 0)

    def test_malformed_rule_is_reported_as_error(self):
        result = handle_abductive_reasoning(
            {"observations": ["WetLawn(yard)"], "rules": ["garbage"]}
        )
        self.assertIn("error", result)
        self.assertEqual(result["hypotheses"], [])

    def test_invalid_max_hypotheses_is_reported_as_error(self):
        result = handle_abductive_reasoning(
            {"observations": ["WetLawn(yard)"], "max_hypotheses": "many"}
        )
        self.assertIn("error", result)
        self.assertEqual(result["hypotheses"], [])

    def test_missing_observations_still_errors(self):
        result = handle_abductive_reasoning({})
        self.assertEqual(result["error"], "observations list is required")


if __name__ == "__main__":
    unittest.main()
