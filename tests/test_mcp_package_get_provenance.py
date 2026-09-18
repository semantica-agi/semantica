"""Regression tests for MCP get_provenance argument names (issue #1248).

Pre-fix bug
-----------
``GET_PROVENANCE`` (and therefore ``tools/list``) requires ``entity_id``, but
``handle_get_provenance`` only read ``node_id``. Every schema-compliant call
returned ``{"error": "node_id is required", "provenance": []}``.

Post-fix expectations
---------------------
- ``entity_id`` is accepted (the advertised contract).
- ``node_id`` remains a compatibility alias.
- When both are provided, ``entity_id`` wins.
- Missing / whitespace-only ids still error, naming ``entity_id``.
"""

from __future__ import annotations

import json
import os
import unittest
import warnings
from unittest.mock import patch

os.environ["SEMANTICA_DISABLE_PROGRESS"] = "1"


class _DummyTracker:
    """Stand-in for semantica.kg.ProvenanceTracker with a real get_provenance."""

    calls: list = []

    def get_provenance(self, node_id):
        _DummyTracker.calls.append(node_id)
        return [{"source": "unit-test", "origin": "fixture"}]


class _FakeGraph:
    """Minimal graph: handlers only need find_nodes() for the fallback path."""

    def find_nodes(self):
        return [
            {
                "id": "apple_inc",
                "type": "entity",
                "content": "apple_inc",
                "metadata": {"source": "wiki"},
            },
            {"id": "other", "type": "entity", "content": "other", "metadata": {}},
        ]


class _GraphSessionMixin:
    def setUp(self):
        import semantica_mcp.mcp.session as _session

        self._orig_graph = _session._graph
        _session._graph = _FakeGraph()
        _DummyTracker.calls = []

    def tearDown(self):
        import semantica_mcp.mcp.session as _session

        _session._graph = self._orig_graph
        _DummyTracker.calls = []


class TestGetProvenanceSchema(unittest.TestCase):
    """tools/list must keep advertising entity_id, not node_id."""

    def test_schema_requires_entity_id(self):
        from semantica_mcp.mcp.schemas import GET_PROVENANCE

        self.assertEqual(GET_PROVENANCE["required"], ["entity_id"])
        self.assertIn("entity_id", GET_PROVENANCE["properties"])
        self.assertNotIn("node_id", GET_PROVENANCE["properties"])

    def test_tools_list_advertises_entity_id(self):
        from semantica_mcp.mcp.server import _handle_tools_list

        response = _handle_tools_list(1, {})
        tools = response["result"]["tools"]
        provenance = next(t for t in tools if t["name"] == "get_provenance")
        schema = provenance["inputSchema"]
        self.assertEqual(schema["required"], ["entity_id"])
        self.assertIn("entity_id", schema["properties"])
        self.assertNotIn("node_id", schema["properties"])


class TestGetProvenanceArgs(_GraphSessionMixin, unittest.TestCase):
    """Handler reads entity_id (schema) and node_id (alias)."""

    def _call(self, args):
        from semantica_mcp.mcp.tools.export import handle_get_provenance

        with patch("semantica.kg.ProvenanceTracker", _DummyTracker):
            return handle_get_provenance(args)

    def test_entity_id_is_accepted(self):
        """The pre-fix failure: schema-compliant callers passed entity_id."""
        result = self._call({"entity_id": "apple_inc"})
        self.assertNotIn("error", result, result)
        self.assertEqual(result["node_id"], "apple_inc")
        self.assertEqual(_DummyTracker.calls, ["apple_inc"])
        self.assertEqual(result["count"], 1)
        self.assertEqual(result["provenance"][0]["source"], "unit-test")

    def test_legacy_node_id_still_works(self):
        result = self._call({"node_id": "apple_inc"})
        self.assertNotIn("error", result, result)
        self.assertEqual(result["node_id"], "apple_inc")
        self.assertEqual(_DummyTracker.calls, ["apple_inc"])

    def test_entity_id_wins_when_both_are_provided(self):
        result = self._call({"entity_id": "apple_inc", "node_id": "other"})
        self.assertNotIn("error", result, result)
        self.assertEqual(result["node_id"], "apple_inc")
        self.assertEqual(_DummyTracker.calls, ["apple_inc"])

    def test_empty_entity_id_falls_back_to_node_id(self):
        result = self._call({"entity_id": "   ", "node_id": "apple_inc"})
        self.assertNotIn("error", result, result)
        self.assertEqual(result["node_id"], "apple_inc")
        self.assertEqual(_DummyTracker.calls, ["apple_inc"])

    def test_entity_id_is_stripped(self):
        result = self._call({"entity_id": "  apple_inc  "})
        self.assertNotIn("error", result, result)
        self.assertEqual(result["node_id"], "apple_inc")
        self.assertEqual(_DummyTracker.calls, ["apple_inc"])

    def test_missing_id_errors_with_entity_id(self):
        result = self._call({})
        self.assertEqual(result["error"], "entity_id is required")
        self.assertEqual(result["provenance"], [])
        self.assertEqual(_DummyTracker.calls, [])

    def test_whitespace_only_errors(self):
        result = self._call({"entity_id": "  ", "node_id": "\t"})
        self.assertEqual(result["error"], "entity_id is required")
        self.assertEqual(result["provenance"], [])
        self.assertEqual(_DummyTracker.calls, [])

    def test_empty_strings_error(self):
        result = self._call({"entity_id": "", "node_id": ""})
        self.assertEqual(result["error"], "entity_id is required")
        self.assertEqual(_DummyTracker.calls, [])


class TestGetProvenanceDispatch(_GraphSessionMixin, unittest.TestCase):
    """JSON-RPC tools/call and call_tool use the same handler."""

    def test_call_tool_with_entity_id_is_not_an_error(self):
        from semantica_mcp.mcp.server import call_tool

        with patch("semantica.kg.ProvenanceTracker", _DummyTracker):
            result = call_tool("get_provenance", {"entity_id": "apple_inc"})
        self.assertNotIn("error", result, result)
        self.assertEqual(result["node_id"], "apple_inc")

    def test_tools_call_entity_id_is_not_iserror(self):
        from semantica_mcp.mcp.server import _handle_tools_call

        with patch("semantica.kg.ProvenanceTracker", _DummyTracker):
            response = _handle_tools_call(
                1, {"name": "get_provenance", "arguments": {"entity_id": "apple_inc"}}
            )
        self.assertNotIn("error", response)
        self.assertFalse(response["result"]["isError"])
        payload = json.loads(response["result"]["content"][0]["text"])
        self.assertNotIn("error", payload)
        self.assertEqual(payload["node_id"], "apple_inc")

    def test_tools_call_missing_id_is_error_content(self):
        from semantica_mcp.mcp.server import _handle_tools_call

        response = _handle_tools_call(1, {"name": "get_provenance", "arguments": {}})
        self.assertTrue(response["result"]["isError"])
        payload = json.loads(response["result"]["content"][0]["text"])
        self.assertEqual(payload["error"], "entity_id is required")


class TestGetProvenanceGraphFallback(_GraphSessionMixin, unittest.TestCase):
    """Production path: kg.ProvenanceTracker has no get_provenance method."""

    def test_entity_id_reaches_graph_fallback(self):
        from semantica_mcp.mcp.tools.export import handle_get_provenance

        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            result = handle_get_provenance({"entity_id": "apple_inc"})
        self.assertNotIn("error", result, result)
        self.assertEqual(result["node_id"], "apple_inc")
        self.assertGreater(result["count"], 0)
        self.assertIn("wiki", result.get("sources", []))


if __name__ == "__main__":
    unittest.main()
