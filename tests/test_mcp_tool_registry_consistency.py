"""Regression tests for MCP tool-registry consistency.

Verifies that every surface that advertises available tools stays in sync
with the authoritative TOOL_DEFINITIONS list:

1. semantica://schema/info resource — must list exactly the same tool names
   as TOOL_DEFINITIONS (was hard-coded at 17, missing link_decisions and all
   4 retrieval tools).

2. EXPORT_GRAPH inputSchema enum — must include every format that the
   handler implementation actually accepts (was missing "graphml" and
   "parquet").

These are documentation/discovery surfaces; a mismatch does not break the
tools themselves but misleads MCP clients that use tools/list or
semantica://schema/info to discover capabilities.
"""

import json
import os
import sys
import unittest

os.environ.setdefault("SEMANTICA_DISABLE_PROGRESS", "1")

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))


class TestSchemaInfoToolList(unittest.TestCase):
    """semantica://schema/info must expose exactly the tools in TOOL_DEFINITIONS."""

    def _schema_info_tools(self):
        from semantica_mcp.mcp.resources.registry import _read_schema_info
        resource = _read_schema_info("semantica://schema/info")
        return json.loads(resource["text"])["tools"]

    def _defined_tool_names(self):
        from semantica_mcp.mcp.tools import TOOL_DEFINITIONS
        return [t["name"] for t in TOOL_DEFINITIONS]

    def test_schema_info_tool_list_matches_tool_definitions(self):
        """The schema/info resource must list every registered tool and nothing
        more — it must not be a stale hard-coded subset."""
        self.assertEqual(self._schema_info_tools(), self._defined_tool_names())

    def test_schema_info_tool_count_is_22(self):
        """TOOL_DEFINITIONS currently registers 22 tools; the resource must
        reflect that exact count."""
        self.assertEqual(len(self._schema_info_tools()), 22)

    def test_schema_info_includes_link_decisions(self):
        """link_decisions was missing from the old hard-coded list."""
        self.assertIn("link_decisions", self._schema_info_tools())

    def test_schema_info_includes_store_document(self):
        self.assertIn("store_document", self._schema_info_tools())

    def test_schema_info_includes_retrieve_context(self):
        self.assertIn("retrieve_context", self._schema_info_tools())

    def test_schema_info_includes_update_document(self):
        self.assertIn("update_document", self._schema_info_tools())

    def test_schema_info_includes_remove_document(self):
        self.assertIn("remove_document", self._schema_info_tools())

    def test_schema_info_tool_list_order_matches_tool_definitions(self):
        """Order must also match so clients see a stable, predictable list."""
        self.assertEqual(self._schema_info_tools(), self._defined_tool_names())


class TestExportGraphSchemaEnum(unittest.TestCase):
    """EXPORT_GRAPH inputSchema enum must include every format the handler
    actually accepts (was missing graphml and parquet)."""

    def _export_graph_enum(self):
        from semantica_mcp.mcp.tools import TOOL_DEFINITIONS
        tool = next(t for t in TOOL_DEFINITIONS if t["name"] == "export_graph")
        return tool["inputSchema"]["properties"]["format"]["enum"]

    def test_enum_includes_graphml(self):
        """graphml was handled by the implementation but absent from the schema."""
        self.assertIn("graphml", self._export_graph_enum())

    def test_enum_includes_parquet(self):
        """parquet was handled by the implementation but absent from the schema."""
        self.assertIn("parquet", self._export_graph_enum())

    def test_enum_preserves_existing_formats(self):
        """Adding graphml/parquet must not remove any previously declared format."""
        existing = {"turtle", "ttl", "nt", "xml", "json-ld", "json", "csv"}
        enum_set = set(self._export_graph_enum())
        self.assertTrue(
            existing.issubset(enum_set),
            f"Missing previously-declared formats: {existing - enum_set}",
        )

    def test_enum_total_count_is_ten(self):
        """7 original + graphml + parquet + jsonld alias = 10."""
        self.assertEqual(len(self._export_graph_enum()), 10)

    def test_export_graph_schema_enum_matches_handler_supported_formats(self):
        """Schema enum and the handler's accepted-format set must agree in
        both directions:

        - every format in the schema enum is accepted by the handler
          (no schema entry produces "Unsupported format");
        - every format accepted by the handler is present in the schema enum
          (no silently-reachable format is hidden from MCP clients).

        The authoritative handler-side set is derived from the handler's own
        _FORMAT_ALIASES mapping (RDF inputs) plus the four non-RDF branches
        (json, csv, graphml, parquet).
        """
        from semantica_mcp.mcp.tools.export import _FORMAT_ALIASES, handle_export_graph
        import semantica_mcp.mcp.session as _session

        # Derive the authoritative handler-accepted set from the implementation,
        # not from a hard-coded list that could drift.
        handler_accepted = {"json", "csv", "graphml", "parquet"} | set(_FORMAT_ALIASES.keys())

        # Set up a minimal graph so the handler can actually run each branch.
        # Separate the environmental check from the graph mutation so that
        # cleanup is guaranteed regardless of where setup fails.
        try:
            from semantica.context.context_graph import ContextGraph
        except ImportError:
            self.skipTest("ContextGraph not importable in this environment")

        orig = _session._graph
        try:
            _session._graph = ContextGraph()
            _session._graph.add_node("n1", node_type="entity")

            schema_enum = set(self._export_graph_enum())

            # Direction 1: every schema-declared format must be accepted by the handler.
            for fmt in schema_enum:
                with self.subTest(direction="schema→handler", fmt=fmt):
                    result = handle_export_graph({"format": fmt})
                    if "error" in result:
                        # Optional-dependency errors (pyarrow absent, GraphML
                        # library absent) are graceful — the format IS handled,
                        # just unavailable at runtime. Only "Unsupported format"
                        # means the handler truly does not recognise the value.
                        self.assertNotIn(
                            "Unsupported format",
                            result["error"],
                            f"Format {fmt!r} is in the schema enum but the "
                            f"handler says it is unsupported: {result['error']}",
                        )

            # Direction 2: every handler-accepted format must be in the schema enum.
            missing_from_schema = handler_accepted - schema_enum
            self.assertEqual(
                missing_from_schema,
                set(),
                f"The handler accepts format(s) that are absent from the "
                f"EXPORT_GRAPH schema enum: {missing_from_schema}. "
                f"MCP clients inspecting the schema will not discover them.",
            )
        finally:
            _session._graph = orig


if __name__ == "__main__":
    unittest.main()
