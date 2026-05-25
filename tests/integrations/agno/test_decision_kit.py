"""
Tests for AgnoDecisionKit — decision intelligence Agno Toolkit.
"""

from __future__ import annotations

import json
import sys
import types
import unittest
from unittest.mock import MagicMock


# ---------------------------------------------------------------------------
# Stub agno Toolkit
# ---------------------------------------------------------------------------
def _stub_agno() -> None:
    if "agno" in sys.modules:
        return

    agno = types.ModuleType("agno")

    tools_pkg = types.ModuleType("agno.tools")
    tools_toolkit = types.ModuleType("agno.tools.toolkit")

    class Toolkit:
        def __init__(self, name="toolkit", **kw):
            self.name = name
            self._tools = []

        def register(self, fn):
            self._tools.append(fn)

    tools_toolkit.Toolkit = Toolkit  # type: ignore
    tools_pkg.toolkit = tools_toolkit
    agno.tools = tools_pkg  # type: ignore

    for name, mod in [
        ("agno", agno),
        ("agno.tools", tools_pkg),
        ("agno.tools.toolkit", tools_toolkit),
    ]:
        sys.modules.setdefault(name, mod)


_stub_agno()

from integrations.agno.decision_kit import AgnoDecisionKit  # noqa: E402


def _make_context() -> MagicMock:
    ctx = MagicMock()
    ctx.record_decision.return_value = "dec-test-001"
    ctx.find_precedents_advanced.return_value = [
        {"scenario": "past loan", "outcome": "approved", "confidence": 0.9, "category": "loan"}
    ]
    ctx.analyze_decision_influence.return_value = {"centrality": 0.75, "influenced": 3}
    ctx.get_context_insights.return_value = {"total_decisions": 5, "categories": ["loan"]}
    ctx.knowledge_graph = MagicMock()
    ctx.knowledge_graph.trace_decision_causality = MagicMock(return_value=["step1", "step2"])
    return ctx


class TestAgnoDecisionKitInit(unittest.TestCase):

    def test_creates_with_context(self):
        kit = AgnoDecisionKit(context=_make_context())
        self.assertIsNotNone(kit)

    def test_creates_without_context(self):
        # Should auto-create an AgentContext
        kit = AgnoDecisionKit()
        self.assertIsNotNone(kit)

    def test_tools_registered(self):
        kit = AgnoDecisionKit(context=_make_context())
        # Tools should be registered (Toolkit.register was called)
        self.assertTrue(len(kit._tools) >= 5)

    def test_policy_tool_can_be_disabled(self):
        kit = AgnoDecisionKit(context=_make_context(), enable_policy_check=False)
        tool_names = [fn.__name__ for fn in kit._tools]
        self.assertNotIn("check_policy", tool_names)


class TestRecordDecision(unittest.TestCase):

    def setUp(self):
        self.ctx = _make_context()
        self.kit = AgnoDecisionKit(context=self.ctx)

    def test_returns_json_with_decision_id(self):
        result = json.loads(self.kit.record_decision(
            category="loan",
            scenario="Customer A loan application",
            reasoning="Good credit score 740",
            outcome="approved",
            confidence=0.95,
        ))
        self.assertIn("decision_id", result)
        self.assertEqual(result["status"], "recorded")

    def test_delegates_to_context(self):
        self.kit.record_decision(
            category="content",
            scenario="Moderation check",
            reasoning="No violations",
            outcome="allowed",
            confidence=0.88,
        )
        self.ctx.record_decision.assert_called_once()

    def test_parses_entities_string(self):
        self.kit.record_decision(
            category="hr",
            scenario="Hire decision",
            reasoning="Qualified",
            outcome="hired",
            confidence=0.9,
            entities="Alice, ACME Corp, Senior Engineer",
        )
        call_kwargs = self.ctx.record_decision.call_args[1]
        self.assertIsInstance(call_kwargs["entities"], list)
        self.assertEqual(len(call_kwargs["entities"]), 3)

    def test_returns_error_json_on_failure(self):
        self.ctx.record_decision.side_effect = RuntimeError("DB unavailable")
        result = json.loads(self.kit.record_decision(
            category="x", scenario="y", reasoning="z", outcome="failed",
        ))
        self.assertEqual(result["status"], "failed")
        self.assertIn("error", result)

    def test_default_confidence_used(self):
        self.kit.record_decision(
            category="test",
            scenario="Default confidence test",
            reasoning="N/A",
            outcome="pass",
        )
        call_kwargs = self.ctx.record_decision.call_args[1]
        self.assertEqual(call_kwargs["confidence"], 0.8)


class TestFindPrecedents(unittest.TestCase):

    def setUp(self):
        self.ctx = _make_context()
        self.kit = AgnoDecisionKit(context=self.ctx)

    def test_returns_json_with_precedents(self):
        result = json.loads(self.kit.find_precedents("new loan application"))
        self.assertIn("precedents", result)
        self.assertIsInstance(result["precedents"], list)

    def test_count_in_result(self):
        result = json.loads(self.kit.find_precedents("test scenario"))
        self.assertIn("count", result)
        self.assertEqual(result["count"], len(result["precedents"]))

    def test_category_filter_passed(self):
        self.kit.find_precedents("scenario", category="finance")
        call_kwargs = self.ctx.find_precedents_advanced.call_args[1]
        self.assertEqual(call_kwargs.get("category"), "finance")

    def test_limit_applied(self):
        self.ctx.find_precedents_advanced.return_value = [
            {"scenario": f"s{i}", "outcome": "o", "confidence": 0.5, "category": "c"}
            for i in range(10)
        ]
        result = json.loads(self.kit.find_precedents("s", limit=3))
        self.assertTrue(result["count"] <= 3)

    def test_handles_exception_gracefully(self):
        self.ctx.find_precedents_advanced.side_effect = RuntimeError("fail")
        result = json.loads(self.kit.find_precedents("broken"))
        self.assertEqual(result["precedents"], [])
        self.assertIn("error", result)


class TestTraceCausalChain(unittest.TestCase):

    def setUp(self):
        self.ctx = _make_context()
        self.kit = AgnoDecisionKit(context=self.ctx)

    def test_returns_json_with_causal_chain(self):
        result = json.loads(self.kit.trace_causal_chain("dec-001"))
        self.assertIn("causal_chain", result)
        self.assertEqual(result["decision_id"], "dec-001")

    def test_fallback_on_attribute_error(self):
        del self.ctx.knowledge_graph.trace_decision_causality
        self.ctx.knowledge_graph.find_precedents = MagicMock(return_value=[])
        result = json.loads(self.kit.trace_causal_chain("dec-002"))
        self.assertIn("causal_chain", result)

    def test_depth_passed(self):
        self.kit.trace_causal_chain("dec-001", depth=5)
        # Should not raise


class TestAnalyzeImpact(unittest.TestCase):

    def setUp(self):
        self.ctx = _make_context()
        self.kit = AgnoDecisionKit(context=self.ctx)

    def test_returns_json_with_decision_id(self):
        result = json.loads(self.kit.analyze_impact("dec-001"))
        self.assertEqual(result["decision_id"], "dec-001")

    def test_includes_influence_metrics(self):
        result = json.loads(self.kit.analyze_impact("dec-001"))
        self.assertIn("centrality", result)


class TestCheckPolicy(unittest.TestCase):

    def setUp(self):
        self.ctx = _make_context()
        self.kit = AgnoDecisionKit(context=self.ctx)

    def test_returns_json_with_compliant_key(self):
        decision = json.dumps({"category": "loan", "outcome": "approved", "confidence": 0.9})
        result = json.loads(self.kit.check_policy(decision))
        self.assertIn("compliant", result)

    def test_invalid_json_returns_error(self):
        result = json.loads(self.kit.check_policy("{not valid json}"))
        # Implementation returns {"compliant": False, "violations": [...], "warnings": [...]}
        self.assertFalse(result["compliant"])
        violations = result.get("violations", [])
        self.assertGreater(len(violations), 0)


class TestGetDecisionSummary(unittest.TestCase):

    def setUp(self):
        self.ctx = _make_context()
        self.kit = AgnoDecisionKit(context=self.ctx)

    def test_returns_json(self):
        result_str = self.kit.get_decision_summary()
        result = json.loads(result_str)
        self.assertIsInstance(result, dict)

    def test_category_filter_stored(self):
        result = json.loads(self.kit.get_decision_summary(category="finance"))
        self.assertEqual(result.get("category_filter"), "finance")

    def test_handles_exception_gracefully(self):
        self.ctx.get_context_insights.side_effect = RuntimeError("insight fail")
        result = json.loads(self.kit.get_decision_summary())
        self.assertIn("error", result)


if __name__ == "__main__":
    unittest.main()
