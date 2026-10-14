"""Regression tests for community_count in the MCP get_graph_analytics tool (#1754).

`_tool_get_graph_analytics` took `len()` of the whole `detect_communities`
result. That result is a wrapper dict (`communities`, `node_assignments`,
`modularity`, `algorithm`), so the tool reported the key count — 4 for every
graph and every algorithm — instead of the number of communities.

These tests stub PageRank so the handler reaches the community-count path
without making that test depend on PageRank calculation details. The stub
matches the current structured PageRank return contract: `centrality` contains
the node-to-score mapping and `rankings` contains ordered `(node, score)` pairs.
"""

import unittest
from unittest import mock

from semantica import mcp_server
from semantica.context import ContextGraph
from semantica.kg import CentralityCalculator, CommunityDetector

PAGERANK_STUB = {
    "centrality": {"alice": 0.5, "bob": 0.3, "acme": 0.2},
    "rankings": [("alice", 0.5), ("bob", 0.3), ("acme", 0.2)],
}


def _one_cluster() -> ContextGraph:
    """Three nodes joined through one hub; Louvain finds a single community."""
    graph = ContextGraph(advanced_analytics=True)
    graph.add_node("alice", node_type="Person", content="Alice")
    graph.add_node("bob", node_type="Person", content="Bob")
    graph.add_node("acme", node_type="Organization", content="Acme")
    graph.add_edge("alice", "acme", edge_type="worksFor")
    graph.add_edge("bob", "acme", edge_type="worksFor")
    graph.add_edge("alice", "bob", edge_type="knows")
    return graph


def _two_clusters() -> ContextGraph:
    """Two pairs with no edge between them, so Louvain has to split them."""
    graph = ContextGraph(advanced_analytics=True)
    for name in ("alice", "bob", "carol", "dave"):
        graph.add_node(name, node_type="Person", content=name)
    graph.add_edge("alice", "bob", edge_type="knows")
    graph.add_edge("carol", "dave", edge_type="knows")
    return graph


class _StubbedHandlerCase(unittest.TestCase):
    """Runs the handler with PageRank stubbed, so the community line is reached."""

    def _run(self, graph: ContextGraph) -> dict:
        previous = mcp_server._graph
        mcp_server._graph = graph
        patcher = mock.patch.object(
            CentralityCalculator,
            "calculate_pagerank",
            return_value=PAGERANK_STUB,
        )
        patcher.start()
        try:
            return mcp_server._tool_get_graph_analytics({})
        finally:
            patcher.stop()
            mcp_server._graph = previous


class TestCommunityCountFromTheHandler(_StubbedHandlerCase):

    def test_reports_the_community_count_not_the_key_count(self):
        graph = _one_cluster()
        result = self._run(graph)
        self.assertNotIn("error", result, result)
        detected = CommunityDetector().detect_communities(graph)
        self.assertEqual(result["community_count"], len(detected["communities"]))
        self.assertEqual(result["community_count"], 1)

    def test_counts_every_community_when_the_graph_splits(self):
        """A single-community graph alone cannot tell a count from a constant."""
        result = self._run(_two_clusters())
        self.assertNotIn("error", result, result)
        self.assertEqual(result["community_count"], 2)

    def test_reports_zero_on_an_empty_graph(self):
        result = self._run(ContextGraph(advanced_analytics=True))
        self.assertNotIn("error", result, result)
        self.assertEqual(result["community_count"], 0)


class TestCommunityCountHelper(unittest.TestCase):

    def test_reads_the_groups_out_of_the_wrapper_dict(self):
        payload = {
            "communities": [frozenset({"alice", "bob"}), frozenset({"acme"})],
            "node_assignments": {"alice": 0, "bob": 0, "acme": 1},
            "modularity": 0.0,
            "algorithm": "louvain",
        }
        self.assertEqual(mcp_server._community_count(payload), 2)

    def test_accepts_a_plain_list_of_groups(self):
        self.assertEqual(mcp_server._community_count([{"alice"}, {"bob"}, {"acme"}]), 3)

    def test_reports_zero_for_missing_or_misshaped_groups(self):
        for payload in ({}, {"communities": None}, {"communities": 4}, None, 4, "4"):
            with self.subTest(payload=payload):
                self.assertEqual(mcp_server._community_count(payload), 0)


if __name__ == "__main__":
    unittest.main()
