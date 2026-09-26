"""Regression tests for issue #1721 - MCP get_graph_analytics on a ContextGraph.

Two defects sat on the same call path:

1. ``CentralityCalculator.calculate_pagerank()`` decided whether to convert
   the graph with ``hasattr(graph, "nodes")``.  ``ContextGraph.nodes`` is a
   dict, so the attribute exists, the conversion was skipped, and
   ``_filter_nodes_by_labels()`` then called that dict - "TypeError: 'dict'
   object is not callable".  The other four centrality measures convert
   unconditionally and were unaffected.

2. ``handle_get_graph_analytics()`` treated every centrality result as
   ``{node: score}``.  The calculators return
   ``{"centrality": {...}, "rankings": [...]}``, so sorting the outer dict
   raised "'<' not supported", every metric came back under a ``*_error``
   key, and the community count came from ``len(dict)`` while the group list
   was forced to ``[]``.

These tests pin both: a ContextGraph has to survive pagerank, and the tool
has to return values instead of errors.
"""

from __future__ import annotations

import json
import os
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))


def _make_context_graph():
    """A ContextGraph with three nodes and two edges."""
    from semantica.context.context_graph import ContextGraph

    graph = ContextGraph()
    graph.add_node("alice", "person", "Alice")
    graph.add_node("bob", "person", "Bob")
    graph.add_node("acme", "org", "Acme")
    graph.add_edge("alice", "bob", "knows")
    graph.add_edge("bob", "acme", "works_at")
    return graph


class TestPagerankAcceptsContextGraph(unittest.TestCase):
    """Defect 1: the graph-kind check read a dict attribute as callable."""

    @classmethod
    def setUpClass(cls):
        cls.graph = _make_context_graph()

    def test_context_graph_nodes_is_a_dict(self):
        # The premise of the bug: the attribute exists but is not callable.
        self.assertTrue(hasattr(self.graph, "nodes"))
        self.assertFalse(callable(self.graph.nodes))

    def test_calculate_pagerank_returns_scores(self):
        from semantica.kg import CentralityCalculator

        result = CentralityCalculator().calculate_pagerank(self.graph)
        self.assertIsInstance(result, dict)
        self.assertEqual(set(result["centrality"]), {"alice", "bob", "acme"})

    def test_pagerank_agrees_with_sibling_measures(self):
        """The other measures already accepted a ContextGraph; pagerank did not."""
        from semantica.kg import CentralityCalculator

        calculator = CentralityCalculator()
        for name in (
            "calculate_pagerank",
            "calculate_degree_centrality",
            "calculate_betweenness_centrality",
            "calculate_closeness_centrality",
            "calculate_eigenvector_centrality",
        ):
            with self.subTest(measure=name):
                result = getattr(calculator, name)(self.graph)
                self.assertEqual(set(result["centrality"]), {"alice", "bob", "acme"})


class TestGraphAnalyticsTool(unittest.TestCase):
    """Defect 2: the handler mis-unpacked the calculator results."""

    @classmethod
    def setUpClass(cls):
        cls.graph = _make_context_graph()

    def _call_handler(self, args):
        from semantica_mcp.mcp.tools import graph as graph_tools

        with patch.object(graph_tools, "get_graph", return_value=self.graph):
            return graph_tools.handle_get_graph_analytics(args)

    def test_all_metrics_return_values_not_errors(self):
        result = self._call_handler({"metrics": ["all"], "top_n": 5})
        for key in ("pagerank", "betweenness", "degree"):
            with self.subTest(metric=key):
                self.assertNotIn(f"{key}_error", result)
                self.assertTrue(result[key])
                self.assertIn("node", result[key][0])
                self.assertIn("score", result[key][0])
        self.assertNotIn("communities_error", result)

    def test_communities_match_the_reported_count(self):
        result = self._call_handler({"metrics": ["all"], "top_n": 5})
        self.assertEqual(result["community_count"], len(result["communities"]))
        self.assertTrue(result["communities"])

    def test_result_is_json_serialisable(self):
        # Community groups are sets; the stdio transport needs them as lists.
        result = self._call_handler({"metrics": ["all"], "top_n": 5})
        json.dumps(result)

    def test_metric_selection_limits_the_output(self):
        result = self._call_handler({"metrics": ["pagerank"], "top_n": 1})
        self.assertEqual(len(result["pagerank"]), 1)
        self.assertNotIn("degree", result)
        self.assertNotIn("betweenness", result)

    def test_top_n_is_respected(self):
        result = self._call_handler({"metrics": ["degree"], "top_n": 1})
        self.assertEqual(len(result["degree"]), 1)


if __name__ == "__main__":
    unittest.main()
