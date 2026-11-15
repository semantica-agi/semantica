"""Regression tests for the semantica://ontology/schema MCP resource (issue #2246).

The handler used to instantiate ``semantica.ontology.OntologyManager``, which
does not exist, and a broad ``except`` turned that into an
"Ontology manager not available" message for every call.
"""

from __future__ import annotations

import json
import os
import unittest
from unittest.mock import patch

os.environ["SEMANTICA_DISABLE_PROGRESS"] = "1"


class _FakeGraph:
    def find_nodes(self):
        return [
            {"id": "a", "type": "Person"},
            {"id": "b", "type": "Person"},
            {"id": "c", "type": "Organisation"},
            {"id": "d"},
        ]

    def find_edges(self):
        return [
            {"id": "e1", "type": "WORKS_AT"},
            {"id": "e2", "type": "WORKS_AT"},
            {"id": "e3", "type": "KNOWS"},
        ]


def _read(graph):
    from semantica_mcp.mcp.resources import registry

    with patch.object(registry, "get_graph", return_value=graph):
        return registry.handle_resource_read("semantica://ontology/schema")


class OntologySchemaResourceTests(unittest.TestCase):
    def test_reports_node_and_edge_types_with_counts(self):
        result = _read(_FakeGraph())
        self.assertEqual(result["uri"], "semantica://ontology/schema")
        self.assertEqual(result["mimeType"], "application/json")
        data = json.loads(result["text"])
        self.assertEqual(
            data["node_types"], {"Organisation": 1, "Person": 2, "Unknown": 1}
        )
        self.assertEqual(data["edge_types"], {"KNOWS": 1, "WORKS_AT": 2})

    def test_empty_graph_returns_empty_schema_not_a_fallback_message(self):
        class _Empty:
            def find_nodes(self):
                return []

            def find_edges(self):
                return []

        data = json.loads(_read(_Empty())["text"])
        self.assertEqual(data, {"node_types": {}, "edge_types": {}})
        self.assertNotIn("message", data)

    def test_graph_failure_is_reported_as_error(self):
        class _Broken:
            def find_nodes(self):
                raise RuntimeError("boom")

        data = json.loads(_read(_Broken())["text"])
        self.assertEqual(data, {"error": "boom"})

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
