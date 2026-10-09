"""Regression tests: the MCP get_causal_chain tool failed on any non-empty chain.

``CausalChainAnalyzer.get_causal_chain()`` returns ``Decision`` dataclasses.
``_tool_get_causal_chain`` returned them as-is, and the tools/call handler then
``json.dumps`` the result, so every chain that found a decision came back as

    JSON-RPC -32603: Object of type Decision is not JSON serializable

An empty chain serializes as ``[]``, which is why a graph with no causal links
never showed the problem. These tests drive a real ContextGraph through the
same tools/call handler a client hits.
"""

import json
import unittest
from datetime import datetime

from semantica import mcp_server
from semantica.context import ContextGraph

SCENARIOS = ("Adopt HIPAA program", "Require BAA from vendors", "Host on AWS")


def _linked_graph():
    """Three decisions linked A -CAUSED-> B -CAUSED-> C."""
    graph = ContextGraph(advanced_analytics=False)
    ids = [
        graph.record_decision(
            category="compliance",
            scenario=scenario,
            reasoning="test",
            outcome="approved",
            confidence=0.9,
        )
        for scenario in SCENARIOS
    ]
    graph.add_causal_relationship(ids[0], ids[1], "CAUSED")
    graph.add_causal_relationship(ids[1], ids[2], "CAUSED")
    return graph, ids


class TestGetCausalChainTool(unittest.TestCase):

    def setUp(self):
        self._old_graph = mcp_server._graph
        self.graph, self.ids = _linked_graph()
        mcp_server._graph = self.graph

    def tearDown(self):
        mcp_server._graph = self._old_graph

    def _call(self, **arguments):
        response = mcp_server._handle({
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {"name": "get_causal_chain", "arguments": arguments},
        })
        # Before the fix this was {"error": {"code": -32603, ...}}.
        self.assertNotIn("error", response)
        payload = json.loads(response["result"]["content"][0]["text"])
        self.assertNotIn("error", payload)
        return payload["chain"]

    @staticmethod
    def _distances(chain):
        return {d["scenario"]: d["metadata"]["causal_distance"] for d in chain}

    def test_upstream_chain_serializes(self):
        chain = self._call(decision_id=self.ids[2], direction="upstream")
        self.assertEqual(
            self._distances(chain),
            {"Adopt HIPAA program": 2, "Require BAA from vendors": 1},
        )

    def test_downstream_chain_serializes(self):
        chain = self._call(decision_id=self.ids[0], direction="downstream")
        self.assertEqual(
            self._distances(chain),
            {"Require BAA from vendors": 1, "Host on AWS": 2},
        )

    def test_entries_are_plain_decision_dicts(self):
        chain = self._call(decision_id=self.ids[2], direction="upstream")
        for entry in chain:
            self.assertIsInstance(entry, dict)
            self.assertIn(entry["decision_id"], self.ids)
            self.assertIsInstance(entry["timestamp"], str)

    def test_non_json_metadata_is_stringified(self):
        """record_decision accepts arbitrary metadata values; a datetime or set
        in a chained decision must not break the response either."""
        cause = self.graph.record_decision(
            category="compliance",
            scenario="Audit finding",
            reasoning="test",
            outcome="approved",
            confidence=0.9,
            metadata={"reviewed_at": datetime(2026, 9, 1), "tags": {"hipaa"}},
        )
        self.graph.add_causal_relationship(cause, self.ids[0], "CAUSED")

        chain = self._call(decision_id=self.ids[0], direction="upstream")
        metadata = next(d["metadata"] for d in chain if d["scenario"] == "Audit finding")
        self.assertEqual(metadata["reviewed_at"], "2026-09-01 00:00:00")
        self.assertIsInstance(metadata["tags"], str)

    def test_unlinked_decision_still_returns_empty_chain(self):
        lone = self.graph.record_decision(
            category="compliance",
            scenario="Unrelated",
            reasoning="test",
            outcome="approved",
            confidence=0.9,
        )
        self.assertEqual(self._call(decision_id=lone, direction="upstream"), [])


if __name__ == "__main__":
    unittest.main()
