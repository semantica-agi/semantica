"""Regression tests for issue #1798.

``add_entity`` forwarded ``label=`` to ``ContextGraph.add_node``, which takes no
such parameter: the keyword was swallowed into ``**properties`` and ``content``
fell back to the node id, so an entity created through MCP was stored under its
id and the caller's label was lost. The same call also dropped the ``content``
argument entirely and nested the metadata mapping under a single ``"metadata"``
key instead of spreading it over the node.

Both MCP packages ship their own ``add_entity`` handler -- ``semantica_mcp`` is
the current one, ``semantica.mcp_server`` the older single-module server -- and
both had the same call, so both are covered here.
"""

from __future__ import annotations

import os
import unittest
from unittest.mock import patch

import semantica.mcp_server as legacy_mcp
import semantica_mcp.mcp.session as package_session


def _env_without_kg_path() -> dict:
    """Environment with SEMANTICA_KG_PATH removed, so nothing touches disk."""
    return {k: v for k, v in os.environ.items() if k != "SEMANTICA_KG_PATH"}


class _IsolatedPackageSession:
    """Reset the semantica_mcp session singleton before and after a test."""

    def __enter__(self):
        package_session.reset_graph()
        return self

    def __exit__(self, *_):
        package_session.reset_graph()


class TestPackageAddEntity(unittest.TestCase):
    """semantica_mcp.mcp.tools.graph.handle_add_entity"""

    def _add(self, args: dict):
        from semantica_mcp.mcp.tools.graph import handle_add_entity

        with _IsolatedPackageSession():
            with patch.dict(os.environ, _env_without_kg_path(), clear=True):
                result = handle_add_entity(args)
            return result, package_session.get_graph()

    def test_label_becomes_content_when_no_content_is_supplied(self):
        result, graph = self._add({"id": "e1", "label": "Apple Inc."})
        self.assertNotIn("error", result, result)
        self.assertEqual(graph.nodes["e1"].content, "Apple Inc.")

    def test_supplied_content_is_stored_and_label_is_kept(self):
        result, graph = self._add(
            {"id": "e2", "label": "Apple Inc.", "content": "A tech company"}
        )
        self.assertNotIn("error", result, result)
        node = graph.nodes["e2"]
        self.assertEqual(node.content, "A tech company")
        self.assertEqual(node.properties.get("label"), "Apple Inc.")

    def test_metadata_is_spread_over_the_node(self):
        result, graph = self._add(
            {"id": "e3", "label": "Apple Inc.", "metadata": {"sector": "tech"}}
        )
        self.assertNotIn("error", result, result)
        node = graph.nodes["e3"]
        self.assertEqual(node.properties.get("sector"), "tech")
        self.assertNotIn("metadata", node.properties)

    def test_node_id_is_the_last_resort_for_content(self):
        result, graph = self._add({"id": "e4"})
        self.assertNotIn("error", result, result)
        self.assertEqual(graph.nodes["e4"].content, "e4")

    def test_non_string_content_is_rejected(self):
        for bad in ({"a": 1}, ["x"], 7):
            with self.subTest(content=bad):
                result, _ = self._add({"id": "e5", "label": "X", "content": bad})
                self.assertIn("error", result)

    def test_metadata_label_does_not_override_the_explicit_label(self):
        result, graph = self._add(
            {"id": "e6", "label": "Apple Inc.", "metadata": {"label": "Wrong"}}
        )
        self.assertNotIn("error", result, result)
        self.assertEqual(graph.nodes["e6"].properties.get("label"), "Apple Inc.")


class TestLegacyAddEntity(unittest.TestCase):
    """semantica.mcp_server._tool_add_entity"""

    def setUp(self):
        from semantica.context import ContextGraph

        self._saved_graph = legacy_mcp._graph
        legacy_mcp._graph = ContextGraph(advanced_analytics=False)
        self._env = patch.dict(os.environ, _env_without_kg_path(), clear=True)
        self._env.start()

    def tearDown(self):
        self._env.stop()
        legacy_mcp._graph = self._saved_graph

    def test_label_becomes_content_when_no_content_is_supplied(self):
        result = legacy_mcp._tool_add_entity({"id": "e1", "label": "Apple Inc."})
        self.assertNotIn("error", result, result)
        self.assertEqual(legacy_mcp._graph.nodes["e1"].content, "Apple Inc.")

    def test_supplied_content_is_stored_and_label_is_kept(self):
        result = legacy_mcp._tool_add_entity(
            {"id": "e2", "label": "Apple Inc.", "content": "A tech company"}
        )
        self.assertNotIn("error", result, result)
        node = legacy_mcp._graph.nodes["e2"]
        self.assertEqual(node.content, "A tech company")
        self.assertEqual(node.properties.get("label"), "Apple Inc.")

    def test_metadata_is_spread_over_the_node(self):
        result = legacy_mcp._tool_add_entity(
            {"id": "e3", "label": "Apple Inc.", "metadata": {"sector": "tech"}}
        )
        self.assertNotIn("error", result, result)
        node = legacy_mcp._graph.nodes["e3"]
        self.assertEqual(node.properties.get("sector"), "tech")
        self.assertNotIn("metadata", node.properties)

    def test_node_id_is_the_last_resort_for_content(self):
        result = legacy_mcp._tool_add_entity({"id": "e4"})
        self.assertNotIn("error", result, result)
        self.assertEqual(legacy_mcp._graph.nodes["e4"].content, "e4")

    def test_non_string_content_is_rejected(self):
        for bad in ({"a": 1}, ["x"], 7):
            with self.subTest(content=bad):
                result = legacy_mcp._tool_add_entity(
                    {"id": "e5", "label": "X", "content": bad}
                )
                self.assertIn("error", result)

    def test_metadata_label_does_not_override_the_explicit_label(self):
        result = legacy_mcp._tool_add_entity(
            {"id": "e6", "label": "Apple Inc.", "metadata": {"label": "Wrong"}}
        )
        self.assertNotIn("error", result, result)
        self.assertEqual(
            legacy_mcp._graph.nodes["e6"].properties.get("label"), "Apple Inc."
        )


class TestAddEntitySchemaDeclaresContent(unittest.TestCase):
    """The handlers accept ``content``, so both schemas have to advertise it."""

    def test_package_schema_declares_content(self):
        from semantica_mcp.mcp.schemas import ADD_ENTITY

        self.assertIn("content", ADD_ENTITY["properties"])
        self.assertEqual(ADD_ENTITY["properties"]["content"]["type"], "string")

    def test_legacy_schema_declares_content(self):
        [tool] = [t for t in legacy_mcp.TOOLS if t["name"] == "add_entity"]

        self.assertIn("content", tool["inputSchema"]["properties"])
        self.assertEqual(tool["inputSchema"]["properties"]["content"]["type"], "string")


if __name__ == "__main__":
    unittest.main()
