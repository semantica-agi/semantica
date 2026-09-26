"""Regression tests for the MCP get_graph_analytics tool on a ContextGraph (issue #1747).

The handler reads whatever `_get_graph()` returns, and the default is a
ContextGraph. `calculate_pagerank` returns a nested result:

    {"centrality": {node: score}, "rankings": [(node, score), ...]}

The handler sorted that outer mapping instead, so its two entries (`centrality`,
a dict, and `rankings`, a list) were compared with each other and the sort raised
`'<' not supported between instances of 'dict' and 'list'`.

On `main` the failure is masked: `calculate_pagerank` raises before the handler
reaches the sort line (that is issue #1721). These tests pin the handler on its
own by stubbing the PageRank call, so the ranking path is covered without
depending on the ContextGraph conversion fix in #1744.
"""

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


if __name__ == "__main__":
    unittest.main()
