"""The documented stdio server must persist causal links and undo failed saves."""

import json
import os
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from semantica import mcp_server
from semantica.context import ContextGraph


class TestLinkDecisionsPersistence(unittest.TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / "graph.json"
        self.env = patch.dict(os.environ, {"SEMANTICA_KG_PATH": str(self.path)})
        self.env.start()
        self.addCleanup(self.env.stop)
        self.graph = ContextGraph(advanced_analytics=False)
        self.ids = [
            self.graph.record_decision(
                category="test",
                scenario=scenario,
                reasoning="regression",
                outcome="approved",
                confidence=0.9,
            )
            for scenario in ("Cause", "Effect", "Unrelated")
        ]
        self.initial_edges = list(self.graph.edges)
        self.graph_patch = patch.multiple(
            mcp_server, _graph=self.graph, _kg_load_ok=True
        )
        self.graph_patch.start()
        self.addCleanup(self.graph_patch.stop)

    def _call(self, name, **arguments):
        response = mcp_server._handle(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/call",
                "params": {"name": name, "arguments": arguments},
            }
        )
        self.assertNotIn("error", response)
        return json.loads(response["result"]["content"][0]["text"])

    def _link(self, **arguments):
        return self._call(
            "link_decisions",
            **{
                "source": self.ids[0],
                "target": self.ids[1],
                "relationship": "CAUSED",
                **arguments,
            },
        )

    def _chain(self):
        result = self._call(
            "get_causal_chain", decision_id=self.ids[1], direction="upstream"
        )
        self.assertNotIn("error", result)
        return [decision["scenario"] for decision in result["chain"]]

    def test_link_survives_reload_through_handle(self):
        self.graph.save_to_file(str(self.path))
        self.assertTrue(self._link()["linked"])
        mcp_server._graph = None
        self.assertEqual(self._chain(), ["Cause"])

    def test_failed_save_rolls_back_only_new_edges_and_retry_works(self):
        self.graph.add_causal_relationship(self.ids[2], self.ids[1], "INFLUENCED")
        self.graph.save_to_file(str(self.path))
        original_file = self.path.read_bytes()
        original_edges = list(self.graph.edges)
        original_index = dict(self.graph._edge_index)
        original_adjacency = {
            key: list(edges) for key, edges in self.graph._adjacency.items()
        }
        original_types = {
            key: list(edges) for key, edges in self.graph.edge_type_index.items()
        }
        with patch.object(self.graph, "save_to_file", side_effect=OSError("disk full")):
            result = self._link()
        self.assertIn("Mutation rolled back", result.get("error", ""))
        self.assertEqual(self.path.read_bytes(), original_file)
        self.assertEqual(self.graph.edges, original_edges)
        self.assertEqual(self.graph._edge_index, original_index)
        self.assertEqual(self.graph._adjacency, original_adjacency)
        self.assertEqual(self.graph.edge_type_index, original_types)
        self.assertEqual(self._chain(), ["Unrelated"])

        self.assertTrue(self._link()["linked"])
        mcp_server._graph = None
        self.assertCountEqual(self._chain(), ["Cause", "Unrelated"])

    def test_failed_save_keeps_edges_added_during_save(self):
        def add_another_link_then_fail(*args):
            self.graph.add_causal_relationship(self.ids[2], self.ids[1], "INFLUENCED")
            raise OSError("disk full")

        with patch.object(
            self.graph, "save_to_file", side_effect=add_another_link_then_fail
        ):
            result = self._link()
        self.assertIn("Mutation rolled back", result.get("error", ""))
        self.assertEqual(self._chain(), ["Unrelated"])
        self.assertEqual(
            set(self.graph._edge_index), {edge.edge_id for edge in self.graph.edges}
        )

    def test_failed_save_keeps_edges_added_by_the_mutation_callback(self):
        def add_another_link(operation, *args):
            if operation == "ADD_EDGE":
                self.graph.mutation_callback = None
                self.graph.add_causal_relationship(
                    self.ids[2], self.ids[1], "INFLUENCED"
                )

        self.graph.mutation_callback = add_another_link
        with patch.object(self.graph, "save_to_file", side_effect=OSError("disk full")):
            result = self._link()
        self.assertIn("Mutation rolled back", result.get("error", ""))
        self.assertEqual(self._chain(), ["Unrelated"])
        self.assertEqual(
            set(self.graph._edge_index), {edge.edge_id for edge in self.graph.edges}
        )

    def test_unsafe_startup_file_is_not_overwritten(self):
        original = b"not a graph\n"
        self.path.write_bytes(original)
        mcp_server._graph = None
        graph = mcp_server._get_graph()
        self.assertFalse(mcp_server._kg_load_ok)
        # Populate the live graph without persisting over the failed startup file.
        self.ids = [
            graph.record_decision(
                category="test",
                scenario=scenario,
                reasoning="regression",
                outcome="approved",
                confidence=0.9,
            )
            for scenario in ("Cause", "Effect")
        ]
        original_edges = list(graph.edges)
        original_index = dict(graph._edge_index)
        with patch.object(graph, "save_to_file", wraps=graph.save_to_file) as save:
            result = self._link()
            save.assert_not_called()
        self.assertIn("Persistence blocked", result.get("error", ""))
        self.assertEqual(self.path.read_bytes(), original)
        self.assertEqual(graph.edges, original_edges)
        self.assertEqual(graph._edge_index, original_index)
        self.assertEqual(self._chain(), [])

    def test_no_path_keeps_link_in_memory_without_saving(self):
        os.environ.pop("SEMANTICA_KG_PATH")
        with patch.object(self.graph, "save_to_file") as save:
            self.assertTrue(self._link()["linked"])
            save.assert_not_called()
        self.assertEqual(self._chain(), ["Cause"])

    def test_duplicate_link_saves_nothing_extra(self):
        with patch.object(
            self.graph, "save_to_file", wraps=self.graph.save_to_file
        ) as save:
            self.assertTrue(self._link()["linked"])
            original = self.path.read_bytes()
            self.assertFalse(self._link()["linked"])
            save.assert_called_once_with(str(self.path))
        self.assertEqual(self.path.read_bytes(), original)
        self.assertEqual(len(self.graph.edges), len(self.initial_edges) + 1)

    def test_unknown_decision_saves_nothing(self):
        with patch.object(self.graph, "save_to_file") as save:
            self.assertFalse(self._link(source="missing")["linked"])
            save.assert_not_called()
        self.assertEqual(self.graph.edges, self.initial_edges)


if __name__ == "__main__":
    unittest.main()
