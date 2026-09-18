"""
Regression tests for Issue #1247 — handle_query_decisions metadata filtering.
Verifies that category and outcome filters correctly inspect nested node metadata.
"""

import os
import sys
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from semantica_mcp.mcp.tools.decisions import (
    _get_decision_field,
    handle_query_decisions,
)


class TestMCPQueryDecisions(unittest.TestCase):
    """Test suite covering handle_query_decisions metadata resolution and filtering."""

    def test_get_decision_field_precedence(self):
        """Verify field extraction prioritizes metadata, properties, and falls back to root."""
        # 1. Nested in metadata (find_nodes output shape)
        node_meta = {"id": "1", "metadata": {"category": "security"}}
        self.assertEqual(_get_decision_field(node_meta, "category"), "security")

        # 2. Nested in properties
        node_props = {"id": "2", "properties": {"outcome": "approved"}}
        self.assertEqual(_get_decision_field(node_props, "outcome"), "approved")

        # 3. Root level fallback
        node_root = {"id": "3", "category": "architecture"}
        self.assertEqual(_get_decision_field(node_root, "category"), "architecture")

        # 4. Missing field
        self.assertIsNone(_get_decision_field({"id": "4"}, "category"))

        # 5. Non-dict input
        self.assertIsNone(_get_decision_field(None, "category"))

    @patch("semantica_mcp.mcp.tools.decisions.get_graph")
    def test_filter_by_category_nested_metadata(self, mock_get_graph):
        """Issue #1247: verify category filter correctly finds nodes where category is in metadata."""
        mock_graph = MagicMock()
        mock_graph.find_nodes.return_value = [
            {
                "id": "dec_1",
                "type": "decision",
                "content": "Use Postgres",
                "metadata": {"category": "architecture", "outcome": "approved"},
            },
            {
                "id": "dec_2",
                "type": "decision",
                "content": "Enable 2FA",
                "metadata": {"category": "security", "outcome": "approved"},
            },
        ]
        mock_get_graph.return_value = mock_graph

        res = handle_query_decisions({"category": "architecture"})
        self.assertEqual(res["count"], 1)
        self.assertEqual(len(res["decisions"]), 1)
        self.assertEqual(res["decisions"][0]["id"], "dec_1")

    @patch("semantica_mcp.mcp.tools.decisions.get_graph")
    def test_filter_by_outcome_nested_metadata(self, mock_get_graph):
        """Issue #1247: verify outcome filter correctly evaluates nested metadata."""
        mock_graph = MagicMock()
        mock_graph.find_nodes.return_value = [
            {
                "id": "dec_1",
                "type": "decision",
                "metadata": {"category": "architecture", "outcome": "approved"},
            },
            {
                "id": "dec_2",
                "type": "decision",
                "metadata": {"category": "architecture", "outcome": "rejected"},
            },
        ]
        mock_get_graph.return_value = mock_graph

        res = handle_query_decisions({"outcome": "rejected"})
        self.assertEqual(res["count"], 1)
        self.assertEqual(len(res["decisions"]), 1)
        self.assertEqual(res["decisions"][0]["id"], "dec_2")

    @patch("semantica_mcp.mcp.tools.decisions.get_graph")
    def test_combined_category_and_outcome_filter(self, mock_get_graph):
        """Verify combined category and outcome filtering acts as an intersection."""
        mock_graph = MagicMock()
        mock_graph.find_nodes.return_value = [
            {
                "id": "dec_1",
                "type": "decision",
                "metadata": {"category": "infra", "outcome": "approved"},
            },
            {
                "id": "dec_2",
                "type": "decision",
                "metadata": {"category": "infra", "outcome": "rejected"},
            },
            {
                "id": "dec_3",
                "type": "decision",
                "metadata": {"category": "security", "outcome": "approved"},
            },
        ]
        mock_get_graph.return_value = mock_graph

        res = handle_query_decisions({"category": "infra", "outcome": "approved"})
        self.assertEqual(res["count"], 1)
        self.assertEqual(len(res["decisions"]), 1)
        self.assertEqual(res["decisions"][0]["id"], "dec_1")

    @patch("semantica_mcp.mcp.tools.decisions.get_graph")
    def test_query_with_category_and_outcome(self, mock_get_graph):
        """Verify natural language query passes category and filters outcome.

        find_similar_decisions()/find_precedents_by_scenario() wrap each match as
        {"decision": {...}, "similarity": ...} — the mock must reflect that real
        shape, not the flat find_nodes() shape, or the test can't catch a
        regression in the wrapper-unwrapping logic.
        """
        mock_graph = MagicMock()
        mock_graph.find_similar_decisions.return_value = [
            {
                "decision": {"id": "dec_1", "category": "infra", "outcome": "approved"},
                "similarity": 0.9,
            },
            {
                "decision": {"id": "dec_2", "category": "infra", "outcome": "rejected"},
                "similarity": 0.8,
            },
        ]
        mock_get_graph.return_value = mock_graph

        res = handle_query_decisions(
            {
                "query": "database migration",
                "category": "infra",
                "outcome": "approved",
                "limit": 5,
            }
        )
        # An outcome filter is present, so the handler must over-fetch (limit * 5)
        # before filtering rather than asking the graph for only `limit` results.
        mock_graph.find_similar_decisions.assert_called_once_with(
            "database migration",
            category="infra",
            max_results=25,
        )
        self.assertEqual(res["count"], 1)
        self.assertEqual(res["decisions"][0]["decision"]["id"], "dec_1")

    @patch("semantica_mcp.mcp.tools.decisions.get_graph")
    def test_query_outcome_filter_does_not_drop_lower_ranked_matches(
        self, mock_get_graph
    ):
        """Regression: a matching decision ranked below the requested limit must
        not be dropped by truncating to `limit` before the outcome filter runs.
        """
        candidates = [
            {
                "decision": {
                    "id": f"dec_{i}",
                    "category": "infra",
                    "outcome": "rejected",
                },
                "similarity": 1.0 - i * 0.01,
            }
            for i in range(5)
        ] + [
            {
                "decision": {
                    "id": "dec_match",
                    "category": "infra",
                    "outcome": "approved",
                },
                "similarity": 0.5,
            }
        ]

        def fake_find_similar_decisions(query, category=None, max_results=10):
            # Mirrors the real graph: sort/slice happens inside the backend.
            return candidates[:max_results]

        mock_graph = MagicMock()
        mock_graph.find_similar_decisions.side_effect = fake_find_similar_decisions
        mock_get_graph.return_value = mock_graph

        res = handle_query_decisions(
            {"query": "db change", "outcome": "approved", "limit": 3}
        )
        self.assertEqual(res["count"], 1)
        self.assertEqual(res["decisions"][0]["decision"]["id"], "dec_match")

    @patch("semantica_mcp.mcp.tools.decisions.get_graph")
    def test_query_no_match_returns_empty_list(self, mock_get_graph):
        """Verify non-matching filter returns 0 count and empty list without errors."""
        mock_graph = MagicMock()
        mock_graph.find_nodes.return_value = [
            {
                "id": "dec_1",
                "type": "decision",
                "metadata": {"category": "infra", "outcome": "approved"},
            }
        ]
        mock_get_graph.return_value = mock_graph

        res = handle_query_decisions({"category": "nonexistent"})
        self.assertEqual(res, {"decisions": [], "count": 0})

    @patch("semantica_mcp.mcp.tools.decisions.get_graph")
    def test_query_exception_returns_error_shape(self, mock_get_graph):
        """Verify exception returns standardized error shape."""
        mock_get_graph.side_effect = RuntimeError("Graph unavailable")
        res = handle_query_decisions({"category": "infra"})
        self.assertEqual(res, {"error": "Graph unavailable", "decisions": []})


if __name__ == "__main__":
    unittest.main()
