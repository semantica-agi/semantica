"""Regression tests for the semantica://ontology/schema MCP resource (issue #2246).

The handler used to instantiate ``semantica.ontology.OntologyManager``, which
does not exist, and a broad ``except`` turned that into an
"Ontology manager not available" message for every call.
"""

from __future__ import annotations

import json
import os
import unittest
from collections import Counter
from unittest.mock import patch

os.environ["SEMANTICA_DISABLE_PROGRESS"] = "1"


def _read(graph):
    from semantica_mcp.mcp.resources import registry

    with patch.object(registry, "get_graph", return_value=graph):
        return registry.handle_resource_read("semantica://ontology/schema")


class OntologySchemaResourceTests(unittest.TestCase):
    def test_reports_node_and_edge_types_with_counts(self):
        from semantica.context import ContextGraph

        graph = ContextGraph()
        graph.add_node("a", "Person")
        graph.add_node("b", "Person")
        graph.add_node("c", "Organisation")
        graph.add_edge("a", "c", "WORKS_AT")
        graph.add_edge("b", "c", "WORKS_AT")
        graph.add_edge("a", "b", "KNOWS")

        result = _read(graph)
        self.assertEqual(result["uri"], "semantica://ontology/schema")
        self.assertEqual(result["mimeType"], "application/json")
        data = json.loads(result["text"])
        self.assertEqual(data["node_types"], {"Organisation": 1, "Person": 2})
        self.assertEqual(data["edge_types"], {"KNOWS": 1, "WORKS_AT": 2})

    def test_counts_match_find_nodes_for_nodes_without_a_type(self):
        from semantica.context import ContextGraph
        from semantica.context.context_graph import ContextNode

        graph = ContextGraph()
        graph.add_node("a", "Person")
        graph._add_internal_node(ContextNode("b", None, "no type"))
        graph._add_internal_node(ContextNode("c", "", "empty type"))

        expected = Counter(node["type"] for node in graph.find_nodes())
        data = json.loads(_read(graph)["text"])
        self.assertEqual(data["node_types"], dict(expected))
        self.assertEqual(data["node_types"], {"Person": 1, "entity": 2})

    def test_does_not_materialize_graph_records(self):
        from semantica.context import ContextGraph

        graph = ContextGraph()
        graph.add_node("a", "Person")
        with patch.object(
            graph, "find_nodes", side_effect=AssertionError
        ), patch.object(graph, "find_edges", side_effect=AssertionError):
            data = json.loads(_read(graph)["text"])
        self.assertEqual(data["node_types"], {"Person": 1})

    def test_empty_graph_returns_empty_schema_not_a_fallback_message(self):
        from semantica.context import ContextGraph

        data = json.loads(_read(ContextGraph())["text"])
        self.assertEqual(data, {"node_types": {}, "edge_types": {}})

    def test_graph_failure_is_logged_and_reported_as_error(self):
        class _Broken:
            def type_counts(self):
                raise RuntimeError("boom")

        with self.assertLogs("semantica.mcp.resources", level="ERROR") as logs:
            data = json.loads(_read(_Broken())["text"])
        self.assertEqual(data, {"error": "boom"})
        self.assertIn("RuntimeError: boom", logs.output[0])

    def test_graph_summary_reports_the_same_node_types(self):
        from semantica.context import ContextGraph
        from semantica_mcp.mcp.resources import registry

        graph = ContextGraph()
        graph.add_node("a", "Person")
        graph.add_node("b", "Organisation")
        graph.add_edge("a", "b", "WORKS_AT")

        with patch.object(registry, "get_graph", return_value=graph):
            result = registry.handle_resource_read("semantica://graph/summary")
        summary = json.loads(result["text"])
        schema = json.loads(_read(graph)["text"])
        self.assertEqual(summary["node_types"], schema["node_types"])
        self.assertEqual(summary["node_count"], 2)
        self.assertEqual(summary["edge_count"], 1)

    def test_works_against_a_real_context_graph(self):
        from semantica.context import ContextGraph

        graph = ContextGraph()
        graph.add_node("n1", "Person", content="Ada")
        graph.add_node("n2", "Person", content="Grace")
        graph.add_edge("n1", "n2", "KNOWS")

        data = json.loads(_read(graph)["text"])
        self.assertEqual(data["node_types"], {"Person": 2})
        self.assertEqual(data["edge_types"], {"KNOWS": 1})

    def test_resource_description_matches_behaviour(self):
        from semantica_mcp.mcp.resources.registry import RESOURCE_DEFINITIONS

        entry = next(
            r for r in RESOURCE_DEFINITIONS if r["uri"] == "semantica://ontology/schema"
        )
        self.assertNotIn("OntologyManager", entry["description"])


if __name__ == "__main__":
    unittest.main()
