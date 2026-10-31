"""Regression tests for the MCP get_graph_analytics tool on a ContextGraph (issue #1747).

The handler reads whatever `_get_graph()` returns, and the default is a
ContextGraph. `calculate_pagerank` returns a nested result:

    {"centrality": {node: score}, "rankings": [(node, score), ...]}

The handler sorted that outer mapping instead, so its two entries (`centrality`,
a dict, and `rankings`, a list) were compared with each other and the sort raised
`'<' not supported between instances of 'dict' and 'list'`.

Before #1744 the failure was masked: `calculate_pagerank` raised on a
ContextGraph before the handler reached the sort line (that was issue #1721).
`TestGraphAnalyticsRankings` stubs the PageRank call so the ranking path is
pinned on its own; `TestGraphAnalyticsOnARealContextGraph` runs the whole path,
which is reachable now that #1744 is on `main`.
"""

import json
import unittest
from unittest import mock

from semantica import mcp_server
from semantica.context import ContextGraph
from semantica.kg import CentralityCalculator

PAGERANK_RESULT = {
    "centrality": {"alice": 0.5, "bob": 0.3, "acme": 0.2},
    "rankings": [("alice", 0.5), ("bob", 0.3), ("acme", 0.2)],
}


def _graph() -> ContextGraph:
    graph = ContextGraph(advanced_analytics=True)
    graph.add_node("alice", node_type="Person", content="Alice")
    graph.add_node("bob", node_type="Person", content="Bob")
    graph.add_node("acme", node_type="Organization", content="Acme")
    graph.add_edge("alice", "acme", edge_type="worksFor")
    graph.add_edge("bob", "acme", edge_type="worksFor")
    graph.add_edge("alice", "bob", edge_type="knows")
    return graph


class TestGraphAnalyticsRankings(unittest.TestCase):

    def setUp(self):
        self._old_graph = mcp_server._graph
        mcp_server._graph = _graph()
        patcher = mock.patch.object(
            CentralityCalculator, "calculate_pagerank", return_value=PAGERANK_RESULT
        )
        patcher.start()
        self.addCleanup(patcher.stop)

    def tearDown(self):
        mcp_server._graph = self._old_graph

    def test_returns_nodes_ranked_by_pagerank_score(self):
        result = mcp_server._tool_get_graph_analytics({})
        self.assertNotIn("error", result, result)
        self.assertEqual(
            result["top_nodes_by_pagerank"],
            [("alice", 0.5), ("bob", 0.3), ("acme", 0.2)],
        )

    def test_falls_back_to_the_centrality_mapping_without_rankings(self):
        """A result that carries only `centrality` is still ranked, not dropped."""
        with mock.patch.object(
            CentralityCalculator,
            "calculate_pagerank",
            return_value={"centrality": {"alice": 0.5, "bob": 0.3, "acme": 0.2}},
        ):
            result = mcp_server._tool_get_graph_analytics({})
        self.assertNotIn("error", result, result)
        self.assertEqual(
            result["top_nodes_by_pagerank"],
            [("alice", 0.5), ("bob", 0.3), ("acme", 0.2)],
        )

    def test_reports_the_context_graph_counts(self):
        """The counts in the same response come from `find_nodes()` and `stats()`."""
        result = mcp_server._tool_get_graph_analytics({})
        self.assertNotIn("error", result, result)
        self.assertEqual(result["node_count"], 3)
        self.assertEqual(result["edge_count"], 3)


class TestGraphAnalyticsOnARealContextGraph(unittest.TestCase):
    """The tool end to end, with no stubbed calculator."""

    def setUp(self):
        self._old_graph = mcp_server._graph
        mcp_server._graph = _graph()

    def tearDown(self):
        mcp_server._graph = self._old_graph

    def test_ranks_the_nodes_and_serialises_to_json(self):
        result = mcp_server._tool_get_graph_analytics({})
        self.assertNotIn("error", result, result)
        self.assertEqual(result["node_count"], 3)
        self.assertEqual(result["edge_count"], 3)
        self.assertEqual(result["community_count"], 1)

        ranked = result["top_nodes_by_pagerank"]
        self.assertEqual({node for node, _ in ranked}, {"alice", "bob", "acme"})
        scores = [score for _, score in ranked]
        self.assertEqual(scores, sorted(scores, reverse=True))

        # The response goes straight out over the MCP transport, so it has to
        # survive a plain dump with no encoder of its own.
        json.dumps(result)

    def test_keeps_the_error_response_for_an_empty_graph(self):
        """An empty graph still surfaces the calculator's own message.

        This one holds on the base revision too. It is here to pin the
        contract rather than to show the ranking fix, so that a later change
        cannot quietly turn an empty graph into a zero-filled response.
        """
        mcp_server._graph = ContextGraph(advanced_analytics=True)
        result = mcp_server._tool_get_graph_analytics({})
        self.assertIn("error", result)
        self.assertIn("No nodes found", result["error"])


if __name__ == "__main__":
    unittest.main()
