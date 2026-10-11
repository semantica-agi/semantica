"""Persisted graph revisions must reach both native MCP entry points."""

from __future__ import annotations

import json
import os
import queue
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import patch

import semantica.mcp_server as legacy
import semantica_mcp.mcp.session as session
from semantica.context import ContextGraph


class _GraphSourceFreshness:
    def setUp(self):
        directory = tempfile.TemporaryDirectory(prefix="mcp-graph-source-")
        self.addCleanup(directory.cleanup)
        self.path = Path(directory.name) / "graph.json"
        environment = patch.dict(
            os.environ,
            {"SEMANTICA_KG_PATH": str(self.path), "SEMANTICA_KG_AUTO_RELOAD": "true"},
        )
        environment.start()
        self.addCleanup(environment.stop)
        self.previous = (
            legacy._graph,
            legacy._kg_load_ok,
            session._graph,
            session._load_ok,
            getattr(legacy, "_graph_cache", None),
            getattr(session, "_graph_cache", None),
        )
        self.addCleanup(self.restore_sessions)
        legacy._graph = None
        legacy._graph_cache = None
        session.reset_graph()
        self.read = (
            legacy._get_graph if self.entry_point == "console" else session.get_graph
        )

    def restore_sessions(self):
        (
            legacy._graph,
            legacy._kg_load_ok,
            session._graph,
            session._load_ok,
            legacy._graph_cache,
            session._graph_cache,
        ) = self.previous

    def write_source(
        self, node_id="source:original", content="Complete original source."
    ):
        graph = ContextGraph(advanced_analytics=False)
        graph.add_nodes(
            [{"id": node_id, "type": "Document", "content": content, "properties": {}}]
        )
        graph.save_to_file(self.path)
        return self.path.read_bytes()

    def test_native_atomic_replacement_invalidates_the_cached_graph(self):
        read = self.read
        self.write_source()
        original = read()
        current = self.write_source("source:corrected", "Complete corrected source.")
        corrected = read()
        self.assertIsNot(corrected, original)
        self.assertFalse(corrected.has_node("source:original"))
        self.assertEqual(
            corrected.find_node("source:corrected")["content"],
            "Complete corrected source.",
        )
        self.assertEqual(self.path.read_bytes(), current)

    def test_replacement_with_equal_size_and_mtime_is_not_the_same_revision(self):
        read = self.read
        self.write_source(content="Before")
        previous = self.path.stat()
        read()
        self.write_source(content="After!")
        self.assertEqual(self.path.stat().st_size, previous.st_size)
        os.utime(self.path, ns=(previous.st_atime_ns, previous.st_mtime_ns))
        self.assertEqual(read().find_node("source:original")["content"], "After!")

    def test_unchanged_source_reuses_the_accepted_graph_without_loading_or_writing(
        self,
    ):
        read = self.read
        current = self.write_source()
        accepted = read()
        with patch.object(
            ContextGraph, "load_from_file", side_effect=AssertionError("reload")
        ):
            self.assertIs(read(), accepted)
        self.assertEqual(self.path.read_bytes(), current)

    def test_default_startup_only_session_behavior_is_preserved(self):
        with patch.dict(os.environ, {"SEMANTICA_KG_AUTO_RELOAD": "false"}):
            self.write_source()
            accepted = self.read()
            self.write_source("source:replacement")
            self.assertIs(self.read(), accepted)
            self.assertTrue(self.read().has_node("source:original"))
            self.assertFalse(self.read().has_node("source:replacement"))

    def test_corrupt_replacement_refuses_stale_data_and_recovers_after_native_repair(
        self,
    ):
        read = self.read
        self.write_source()
        read()
        self.path.write_text("{incomplete", encoding="utf-8")
        corrupt = self.path.read_bytes()
        with self.assertRaises((ValueError, OSError)):
            read()
        self.assertEqual(self.path.read_bytes(), corrupt)
        self.write_source("source:repaired")
        self.assertTrue(read().has_node("source:repaired"))

    def test_partial_load_is_never_published_and_a_repaired_source_can_retry(self):
        read = self.read
        self.write_source()
        accepted = read()
        data = json.loads(self.path.read_text(encoding="utf-8"))
        data["nodes"][0]["content"] = "Unaccepted partial revision."
        data["links"] = [42]
        self.path.write_text(json.dumps(data), encoding="utf-8")
        broken = self.path.read_bytes()
        with self.assertRaises(Exception):
            read()
        self.assertEqual(
            accepted.find_node("source:original")["content"],
            "Complete original source.",
        )
        self.assertEqual(self.path.read_bytes(), broken)
        self.write_source("source:repaired")
        self.assertTrue(read().has_node("source:repaired"))

    def test_a_populated_source_disappearing_or_truncating_is_not_a_fresh_destination(
        self,
    ):
        read = self.read
        for missing in (True, False):
            with self.subTest(missing=missing):
                self.write_source()
                read()
                if missing:
                    self.path.unlink()
                else:
                    self.path.write_bytes(b"")
                with self.assertRaises((ValueError, OSError)):
                    read()
                self.assertEqual(self.path.exists(), not missing)
                self.write_source("source:repaired")
                self.assertTrue(read().has_node("source:repaired"))

    def test_initial_destinations_and_memory_only_sessions_remain_valid(
        self,
    ):
        read = self.read
        self.path.unlink(missing_ok=True)
        graph = read()
        self.assertFalse(graph.find_nodes())
        self.path.write_bytes(b"")
        self.assertFalse(read().find_nodes())
        with patch.dict(os.environ, {"SEMANTICA_KG_PATH": ""}):
            memory = read()
            memory.add_node("memory:only", node_type="entity", label="In memory")
            self.assertIs(read(), memory)
            self.assertTrue(read().has_node("memory:only"))

    def test_source_changed_during_load_refuses_the_candidate_without_retry(self):
        load = ContextGraph.load_from_file
        read = self.read
        self.write_source()
        read()
        self.write_source("source:candidate")

        def change_after_load(graph, path, *args, **kwargs):
            load(graph, path, *args, **kwargs)
            self.write_source("source:successor")

        with patch.object(
            ContextGraph, "load_from_file", side_effect=change_after_load, autospec=True
        ) as mocked:
            with self.assertRaises((ValueError, OSError)):
                read()
            self.assertEqual(mocked.call_count, 1)
        self.assertTrue(read().has_node("source:successor"))

    def test_invalid_initial_source_refuses_writes_and_recovers_in_the_same_session(
        self,
    ):
        self.path.write_text("{incomplete", encoding="utf-8")
        invalid = self.path.read_bytes()
        with self.assertRaises((ValueError, OSError)):
            self.read()
        self.assertEqual(self.path.read_bytes(), invalid)
        self.write_source("source:repaired")
        self.assertTrue(self.read().has_node("source:repaired"))

    def test_native_replacement_rebuilds_decision_indexes(self):
        def save_decision(scenario):
            graph = ContextGraph(advanced_analytics=False)
            decision_id = graph.record_decision(
                category="storage",
                scenario=scenario,
                reasoning="Native file replacement is authoritative.",
                outcome="accepted",
                confidence=0.9,
            )
            graph.save_to_file(self.path)
            return decision_id

        previous = save_decision("Original source choice")
        self.assertTrue(self.read().has_node(previous))
        current = save_decision("Corrected source choice")
        graph = self.read()
        self.assertFalse(graph.has_node(previous))
        self.assertTrue(graph.has_node(current))
        precedents = graph.find_similar_decisions("Corrected source choice")
        self.assertTrue(precedents)
        self.assertNotIn(previous, repr(precedents))

    def test_repaired_empty_graph_is_a_valid_native_replacement(self):
        self.write_source()
        self.read()
        self.path.write_bytes(b"")
        with self.assertRaises((ValueError, OSError)):
            self.read()
        graph = ContextGraph(advanced_analytics=False)
        graph.save_to_file(self.path)
        repaired = self.read()
        self.assertFalse(repaired.find_nodes())
        self.assertTrue(
            legacy._kg_load_ok if self.entry_point == "console" else session._load_ok
        )

    def test_a_directory_source_is_refused_before_loading(self):
        self.write_source()
        self.read()
        self.path.unlink()
        self.path.mkdir()
        with self.assertRaises(OSError):
            self.read()
        self.path.rmdir()
        self.write_source("source:repaired")
        self.assertTrue(self.read().has_node("source:repaired"))

    def test_an_unreadable_changed_source_never_replaces_the_accepted_graph(self):
        self.write_source()
        accepted = self.read()
        current = self.write_source("source:replacement")
        with patch.object(ContextGraph, "load_from_file", side_effect=PermissionError):
            with self.assertRaises(OSError):
                self.read()
        self.assertTrue(accepted.has_node("source:original"))
        self.assertEqual(self.path.read_bytes(), current)
        self.assertTrue(self.read().has_node("source:replacement"))

    def test_native_stdio_mutation_replacement_refusal_and_recovery(self):
        """Keep one real server alive while its native source changes."""
        self.write_source()
        env = os.environ.copy()
        env["PYTHONPATH"] = str(Path(legacy.__file__).resolve().parents[2])
        if self.entry_point == "console":
            executable = "semantica-mcp.exe" if os.name == "nt" else "semantica-mcp"
            command = [str(Path(sys.executable).with_name(executable))]
        else:
            command = [sys.executable, "-m", "semantica_mcp.mcp"]
        responses = queue.Queue()
        deadline = time.monotonic() + 60
        with tempfile.TemporaryFile() as errors:
            process = subprocess.Popen(
                command,
                env=env,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=errors,
                text=True,
                encoding="utf-8",
            )

            def read_responses():
                for line in process.stdout:
                    responses.put(line)
                responses.put(None)

            reader = threading.Thread(target=read_responses, daemon=True)
            reader.start()
            request_id = 0

            def request(method, params):
                nonlocal request_id
                request_id += 1
                message = {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "method": method,
                    "params": params,
                }
                process.stdin.write(json.dumps(message) + "\n")
                process.stdin.flush()
                remaining = deadline - time.monotonic()
                self.assertGreater(remaining, 0, "Native stdio journey exceeded 60s")
                line = responses.get(timeout=remaining)
                self.assertIsNotNone(line, "Native server exited before responding")
                response = json.loads(line)
                self.assertEqual(response["jsonrpc"], "2.0")
                self.assertEqual(response["id"], request_id)
                return response

            def tool(name, arguments):
                return request("tools/call", {"name": name, "arguments": arguments})

            def exported_nodes():
                response = tool("export_graph", {"format": "json"})
                self.assertNotIn("error", response)
                payload = json.loads(response["result"]["content"][0]["text"])
                self.assertNotIn("error", payload)
                data = payload["data"]
                if isinstance(data, str):
                    data = json.loads(data)
                return {
                    node["id"]: node.get("content", node.get("text"))
                    for node in data.get("nodes", data.get("entities", []))
                }

            def assert_tool_refused(response):
                if "error" in response:
                    self.assertEqual(response["error"]["code"], -32603)
                else:
                    payload = json.loads(response["result"]["content"][0]["text"])
                    self.assertIn("error", payload)
                    self.assertIs(response["result"].get("isError"), True)

            try:
                initialized = request(
                    "initialize",
                    {
                        "protocolVersion": "2024-11-05",
                        "capabilities": {},
                        "clientInfo": {
                            "name": "graph-source-regression",
                            "version": "1",
                        },
                    },
                )
                self.assertIn("result", initialized)
                self.assertEqual(
                    exported_nodes(), {"source:original": "Complete original source."}
                )
                added = tool("add_entity", {"id": "source:native", "label": "Native"})
                self.assertNotIn("error", added)
                self.assertNotIn(
                    "error", json.loads(added["result"]["content"][0]["text"])
                )
                self.assertEqual(
                    set(exported_nodes()), {"source:original", "source:native"}
                )
                persisted = ContextGraph(advanced_analytics=False)
                persisted.load_from_file(self.path)
                self.assertTrue(persisted.has_node("source:native"))

                replacement = self.write_source(
                    "source:replacement", "Complete replacement source."
                )
                self.assertEqual(
                    exported_nodes(),
                    {"source:replacement": "Complete replacement source."},
                )
                self.assertEqual(self.path.read_bytes(), replacement)

                self.path.write_text("{incomplete", encoding="utf-8")
                invalid = self.path.read_bytes()
                assert_tool_refused(tool("export_graph", {"format": "json"}))
                assert_tool_refused(tool("add_entity", {"id": "source:refused"}))
                resource = request(
                    "resources/read", {"uri": "semantica://graph/summary"}
                )
                if "error" in resource:
                    self.assertEqual(resource["error"]["code"], -32603)
                else:
                    data = json.loads(resource["result"]["contents"][0]["text"])
                    self.assertIn("error", data)
                    self.assertNotIn("node_count", data)
                self.assertEqual(self.path.read_bytes(), invalid)

                self.write_source("source:repaired", "Complete repaired source.")
                self.assertEqual(
                    exported_nodes(), {"source:repaired": "Complete repaired source."}
                )
                self.path.unlink()
                assert_tool_refused(tool("export_graph", {"format": "json"}))
                self.assertFalse(self.path.exists())
                self.write_source("source:final", "Complete final source.")
                self.assertEqual(
                    exported_nodes(), {"source:final": "Complete final source."}
                )
                self.assertIsNone(
                    process.poll(), "Recovery must not restart the server"
                )
                process.stdin.close()
                process.wait(timeout=5)
            finally:
                if not process.stdin.closed:
                    process.stdin.close()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.terminate()
                    try:
                        process.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait(timeout=5)
                reader.join(timeout=5)
                process.stdout.close()
            self.assertFalse(reader.is_alive(), "The owned stdout reader must stop")
            errors.seek(0)
            self.assertEqual(process.returncode, 0, errors.read().decode("utf-8"))


class TestConsoleGraphSourceFreshness(_GraphSourceFreshness, unittest.TestCase):
    entry_point = "console"


class TestPackageGraphSourceFreshness(_GraphSourceFreshness, unittest.TestCase):
    entry_point = "package"


if __name__ == "__main__":
    unittest.main()
