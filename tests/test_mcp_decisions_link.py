"""
Tests for issue #1653 Part 1 — link_decisions MCP tool.

Covers:
- Validation (missing source, target, relationship)
- Successful link surfacing True from add_causal_relationship
- Skipped link (unknown IDs) surfacing False from add_causal_relationship
- Invalid relationship type returning an error dict (ValueError path)
- Unexpected exception returning an error dict
- Tool exposed in the embedded server (semantica.mcp_server)
- Tool exposed in the modular server (semantica_mcp.mcp)
- End-to-end: record two decisions → link → get_causal_chain observes the edge
"""

from __future__ import annotations

import json
import os
import sys
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from semantica_mcp.mcp.tools.decisions import handle_link_decisions


# ── Modular server: handle_link_decisions unit tests ─────────────────────────

class TestHandleLinkDecisions(unittest.TestCase):
    """Unit tests for semantica_mcp.mcp.tools.decisions.handle_link_decisions."""

    def test_missing_source_returns_error(self):
        result = handle_link_decisions({"target": "tgt_1", "relationship": "CAUSED"})
        self.assertIn("error", result)
        self.assertNotIn("linked", result)

    def test_missing_target_returns_error(self):
        result = handle_link_decisions({"source": "src_1", "relationship": "CAUSED"})
        self.assertIn("error", result)
        self.assertNotIn("linked", result)

    def test_missing_relationship_returns_error(self):
        result = handle_link_decisions({"source": "src_1", "target": "tgt_1"})
        self.assertIn("error", result)
        self.assertNotIn("linked", result)

    def test_empty_source_returns_error(self):
        result = handle_link_decisions(
            {"source": "   ", "target": "tgt_1", "relationship": "CAUSED"}
        )
        self.assertIn("error", result)

    @patch("semantica_mcp.mcp.tools.decisions.get_graph")
    def test_successful_link_returns_linked_true(self, mock_get_graph):
        """When add_causal_relationship returns True, linked must be True."""
        mock_graph = MagicMock()
        mock_graph.add_causal_relationship.return_value = True
        mock_get_graph.return_value = mock_graph

        result = handle_link_decisions(
            {"source": "dec_a", "target": "dec_b", "relationship": "CAUSED"}
        )

        mock_graph.add_causal_relationship.assert_called_once_with("dec_a", "dec_b", "CAUSED")
        self.assertEqual(
            result,
            {"source": "dec_a", "target": "dec_b", "relationship": "CAUSED", "linked": True},
        )

    @patch("semantica_mcp.mcp.tools.decisions.get_graph")
    def test_skipped_link_returns_linked_false(self, mock_get_graph):
        """When add_causal_relationship returns False (unknown ID), linked must be False."""
        mock_graph = MagicMock()
        mock_graph.add_causal_relationship.return_value = False
        mock_get_graph.return_value = mock_graph

        result = handle_link_decisions(
            {"source": "dec_a", "target": "unknown_id", "relationship": "INFLUENCED"}
        )

        self.assertNotIn("error", result)
        self.assertEqual(result["linked"], False)
        self.assertEqual(result["source"], "dec_a")
        self.assertEqual(result["target"], "unknown_id")
        self.assertEqual(result["relationship"], "INFLUENCED")

    @patch("semantica_mcp.mcp.tools.decisions.get_graph")
    def test_invalid_relationship_type_returns_error(self, mock_get_graph):
        """ValueError from add_causal_relationship (bad type) must surface as error dict."""
        mock_graph = MagicMock()
        mock_graph.add_causal_relationship.side_effect = ValueError(
            "Relationship type must be one of: ('CAUSED', 'INFLUENCED', 'PRECEDENT_FOR')"
        )
        mock_get_graph.return_value = mock_graph

        result = handle_link_decisions(
            {"source": "dec_a", "target": "dec_b", "relationship": "ZAPS"}
        )

        self.assertIn("error", result)
        self.assertIn("CAUSED", result["error"])
        self.assertNotIn("linked", result)

    @patch("semantica_mcp.mcp.tools.decisions.get_graph")
    def test_unexpected_exception_returns_error(self, mock_get_graph):
        """Any non-ValueError exception must surface as an error dict, not propagate."""
        mock_graph = MagicMock()
        mock_graph.add_causal_relationship.side_effect = RuntimeError("graph locked")
        mock_get_graph.return_value = mock_graph

        result = handle_link_decisions(
            {"source": "dec_a", "target": "dec_b", "relationship": "CAUSED"}
        )

        self.assertIn("error", result)
        self.assertEqual(result["error"], "graph locked")
        self.assertNotIn("linked", result)

    @patch("semantica_mcp.mcp.tools.decisions.get_graph")
    def test_passes_args_exactly_to_add_causal_relationship(self, mock_get_graph):
        """handler must forward source/target/relationship strings verbatim."""
        mock_graph = MagicMock()
        mock_graph.add_causal_relationship.return_value = True
        mock_get_graph.return_value = mock_graph

        handle_link_decisions(
            {"source": "  dec_x  ", "target": "  dec_y  ", "relationship": "PRECEDENT_FOR"}
        )

        # Strings must be stripped before forwarding.
        mock_graph.add_causal_relationship.assert_called_once_with(
            "dec_x", "dec_y", "PRECEDENT_FOR"
        )


# ── Modular server: tool discovery ───────────────────────────────────────────

class TestModularServerLinkDecisionsRegistration(unittest.TestCase):
    """Verify link_decisions is discoverable through the modular MCP server."""

    def test_link_decisions_in_tool_definitions(self):
        from semantica_mcp.mcp.tools import TOOL_DEFINITIONS

        names = [t["name"] for t in TOOL_DEFINITIONS]
        self.assertIn(
            "link_decisions",
            names,
            "link_decisions must be registered in TOOL_DEFINITIONS",
        )

    def test_link_decisions_handler_is_callable(self):
        from semantica_mcp.mcp.tools import TOOL_DEFINITIONS

        tool = next(t for t in TOOL_DEFINITIONS if t["name"] == "link_decisions")
        self.assertTrue(callable(tool["_handler"]))

    def test_link_decisions_schema_has_required_fields(self):
        from semantica_mcp.mcp.tools import TOOL_DEFINITIONS

        tool = next(t for t in TOOL_DEFINITIONS if t["name"] == "link_decisions")
        schema = tool["inputSchema"]
        self.assertEqual(set(schema["required"]), {"source", "target", "relationship"})

    def test_link_decisions_callable_via_call_tool(self):
        """call_tool must dispatch link_decisions without raising UnknownToolError."""
        from semantica_mcp.mcp.server import UnknownToolError, call_tool

        # Missing args hit our own validation before reaching the graph.
        result = call_tool("link_decisions", {})
        self.assertIn("error", result)
        self.assertNotIn("linked", result)
        # Must not raise UnknownToolError — the tool is registered.
        with self.assertRaises(UnknownToolError):
            call_tool("link_decisions_nonexistent", {})


# ── Embedded server: tool discovery ──────────────────────────────────────────

class TestEmbeddedServerLinkDecisionsRegistration(unittest.TestCase):
    """Verify link_decisions is discoverable through the embedded MCP server."""

    def test_link_decisions_in_tools_list(self):
        from semantica.mcp_server import TOOLS

        names = [t["name"] for t in TOOLS]
        self.assertIn(
            "link_decisions",
            names,
            "link_decisions must be registered in TOOLS",
        )

    def test_link_decisions_schema_required(self):
        from semantica.mcp_server import TOOLS

        tool = next(t for t in TOOLS if t["name"] == "link_decisions")
        schema = tool["inputSchema"]
        self.assertEqual(set(schema["required"]), {"source", "target", "relationship"})

    def test_link_decisions_handler_missing_args(self):
        """Embedded handler must return error dict on missing args, not raise."""
        from semantica.mcp_server import TOOLS

        handler = next(t["_handler"] for t in TOOLS if t["name"] == "link_decisions")
        result = handler({})
        self.assertIn("error", result)

    @patch("semantica.mcp_server._get_graph")
    def test_embedded_handler_calls_add_causal_relationship(self, mock_get_graph):
        """Embedded handler must forward source/target/relationship to add_causal_relationship."""
        from semantica.mcp_server import TOOLS

        mock_graph = MagicMock()
        mock_graph.add_causal_relationship.return_value = True
        mock_get_graph.return_value = mock_graph

        handler = next(t["_handler"] for t in TOOLS if t["name"] == "link_decisions")
        result = handler({"source": "s1", "target": "t1", "relationship": "CAUSED"})

        mock_graph.add_causal_relationship.assert_called_once_with("s1", "t1", "CAUSED")
        self.assertEqual(result["linked"], True)
        self.assertEqual(result["source"], "s1")
        self.assertEqual(result["target"], "t1")
        self.assertEqual(result["relationship"], "CAUSED")

    @patch("semantica.mcp_server._get_graph")
    def test_embedded_handler_surfaces_false_for_skip(self, mock_get_graph):
        """Embedded handler must surface linked=False when add_causal_relationship returns False."""
        from semantica.mcp_server import TOOLS

        mock_graph = MagicMock()
        mock_graph.add_causal_relationship.return_value = False
        mock_get_graph.return_value = mock_graph

        handler = next(t["_handler"] for t in TOOLS if t["name"] == "link_decisions")
        result = handler({"source": "s1", "target": "unknown", "relationship": "CAUSED"})

        self.assertNotIn("error", result)
        self.assertFalse(result["linked"])

    @patch("semantica.mcp_server._get_graph")
    def test_embedded_handler_invalid_relationship_type_returns_error(self, mock_get_graph):
        """Embedded handler must convert ValueError to error dict."""
        from semantica.mcp_server import TOOLS

        mock_graph = MagicMock()
        mock_graph.add_causal_relationship.side_effect = ValueError("bad type")
        mock_get_graph.return_value = mock_graph

        handler = next(t["_handler"] for t in TOOLS if t["name"] == "link_decisions")
        result = handler({"source": "s1", "target": "t1", "relationship": "BAD"})

        self.assertIn("error", result)
        self.assertNotIn("linked", result)


# ── End-to-end: record → link → get_causal_chain (modular server) ────────────

class TestLinkDecisionsEndToEnd(unittest.TestCase):
    """
    End-to-end test: two decisions are recorded, linked via link_decisions,
    and get_causal_chain must subsequently see the causal relationship.
    Uses the real ContextGraph with both handlers patched to share one graph.
    """

    def setUp(self):
        from semantica.context import ContextGraph

        self.graph = ContextGraph(advanced_analytics=False)
        self.cause_id = self.graph.record_decision(
            category="compliance",
            scenario="Adopt encryption at rest",
            reasoning="regulatory requirement",
            outcome="approved",
            confidence=0.95,
        )
        self.effect_id = self.graph.record_decision(
            category="compliance",
            scenario="Migrate database to encrypted volume",
            reasoning="follows from encryption decision",
            outcome="approved",
            confidence=0.90,
        )

    def _call_modular(self, tool_name, arguments):
        from semantica_mcp.mcp.server import _handle_tools_call

        with patch(
            "semantica_mcp.mcp.tools.decisions.get_graph", return_value=self.graph
        ):
            response = _handle_tools_call(1, {"name": tool_name, "arguments": arguments})
        self.assertNotIn("error", response, f"{tool_name} returned an error: {response}")
        return json.loads(response["result"]["content"][0]["text"])

    def test_link_then_causal_chain_observes_edge(self):
        """After link_decisions, get_causal_chain must return the linked decision."""
        # Step 1: link
        link_result = self._call_modular(
            "link_decisions",
            {"source": self.cause_id, "target": self.effect_id, "relationship": "CAUSED"},
        )
        self.assertTrue(link_result["linked"], "link_decisions must report linked=True")

        # Step 2: trace downstream from cause
        chain_result = self._call_modular(
            "get_causal_chain",
            {"decision_id": self.cause_id, "direction": "downstream"},
        )
        chain_ids = [d["decision_id"] for d in chain_result["chain"]]
        self.assertIn(
            self.effect_id,
            chain_ids,
            "get_causal_chain must see the effect decision after link_decisions",
        )

    def test_duplicate_link_returns_false(self):
        """Calling link_decisions twice with the same pair returns False on the second call."""
        first = self._call_modular(
            "link_decisions",
            {"source": self.cause_id, "target": self.effect_id, "relationship": "CAUSED"},
        )
        second = self._call_modular(
            "link_decisions",
            {"source": self.cause_id, "target": self.effect_id, "relationship": "CAUSED"},
        )
        self.assertTrue(first["linked"])
        self.assertFalse(second["linked"])

    def test_link_unknown_id_returns_false_not_error(self):
        """Linking to an unknown ID returns linked=False, not an error key."""
        result = self._call_modular(
            "link_decisions",
            {"source": self.cause_id, "target": "nonexistent_id", "relationship": "INFLUENCED"},
        )
        self.assertFalse(result["linked"])
        self.assertNotIn("error", result)


if __name__ == "__main__":
    unittest.main()


# ── Embedded server: None-argument regression (issue #1653 HIGH finding) ─────

class TestEmbeddedLinkDecisionsNoneArguments(unittest.TestCase):
    """Verify the embedded handler does not crash when any argument is None.

    JSON null becomes Python None in the args dict.  The handler must return
    a clean error dict — not raise AttributeError — for each case.
    """

    def _handler(self):
        from semantica.mcp_server import TOOLS
        return next(t["_handler"] for t in TOOLS if t["name"] == "link_decisions")

    def test_none_source_returns_error_not_exception(self):
        result = self._handler()({"source": None, "target": "dec_t", "relationship": "CAUSED"})
        self.assertIn("error", result)
        self.assertNotIn("linked", result)

    def test_none_target_returns_error_not_exception(self):
        result = self._handler()({"source": "dec_s", "target": None, "relationship": "CAUSED"})
        self.assertIn("error", result)
        self.assertNotIn("linked", result)

    def test_none_relationship_returns_error_not_exception(self):
        result = self._handler()({"source": "dec_s", "target": "dec_t", "relationship": None})
        self.assertIn("error", result)
        self.assertNotIn("linked", result)

    def test_all_none_returns_error_not_exception(self):
        result = self._handler()({"source": None, "target": None, "relationship": None})
        self.assertIn("error", result)
        self.assertNotIn("linked", result)
