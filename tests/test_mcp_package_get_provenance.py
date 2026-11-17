"""Regression tests for MCP get_provenance (issues #1248 and #2253).

#1248 ensured the handler accepts the advertised ``entity_id`` key (with
``node_id`` kept as a legacy alias).

#2253 fixes the data source: the handler must read the configured
``ProvenanceManager`` store instead of treating arbitrary graph metadata as
provenance, and must return an explicit ``not_configured`` status when no
provenance database is configured.
"""

from __future__ import annotations

import json
import os
import unittest
from unittest.mock import patch

import pytest

os.environ["SEMANTICA_DISABLE_PROGRESS"] = "1"


class _DummyManager:
    """Minimal ProvenanceManager shape used by the handler."""

    calls: list = []

    def get_provenance(self, entity_id):
        self.calls.append(("get_provenance", entity_id))
        return {
            "entity_id": entity_id,
            "source_document": "unit-test",
            "confidence": 0.9,
        }

    def get_lineage(self, entity_id):
        self.calls.append(("get_lineage", entity_id))
        return {
            "entity_id": entity_id,
            "entries": [
                {
                    "entity_id": entity_id,
                    "source_document": "unit-test",
                }
            ],
            "lineage_chain": [
                {
                    "entity_id": entity_id,
                    "source_document": "unit-test",
                }
            ],
            "source_documents": ["unit-test"],
            "first_seen": "2026-01-01T00:00:00+00:00",
            "last_updated": "2026-01-01T00:00:00+00:00",
            "entity_count": 1,
            "integrity_verified": True,
        }


class _ManagerTestMixin:
    def setUp(self):
        _DummyManager.calls = []

    def tearDown(self):
        _DummyManager.calls = []

    def _call(self, args):
        from semantica_mcp.mcp.tools.export import handle_get_provenance

        with patch(
            "semantica_mcp.mcp.tools.export.get_provenance_manager",
            return_value=_DummyManager(),
        ):
            return handle_get_provenance(args)


class TestGetProvenanceSchema(unittest.TestCase):
    """tools/list must keep advertising entity_id, not node_id."""

    def test_schema_requires_entity_id(self):
        from semantica_mcp.mcp.schemas import GET_PROVENANCE

        self.assertEqual(GET_PROVENANCE["required"], ["entity_id"])
        self.assertIn("entity_id", GET_PROVENANCE["properties"])
        self.assertIn("include_metadata", GET_PROVENANCE["properties"])
        self.assertNotIn("node_id", GET_PROVENANCE["properties"])

    def test_tools_list_advertises_entity_id(self):
        from semantica_mcp.mcp.server import _handle_tools_list

        response = _handle_tools_list(1, {})
        tools = response["result"]["tools"]
        provenance = next(t for t in tools if t["name"] == "get_provenance")
        schema = provenance["inputSchema"]
        self.assertEqual(schema["required"], ["entity_id"])
        self.assertIn("entity_id", schema["properties"])
        self.assertIn("include_metadata", schema["properties"])
        self.assertNotIn("node_id", schema["properties"])


class TestGetProvenanceArgs(_ManagerTestMixin, unittest.TestCase):
    """Handler reads entity_id (schema) and node_id (alias)."""

    def test_entity_id_is_accepted(self):
        """The pre-fix failure: schema-compliant callers passed entity_id."""
        result = self._call({"entity_id": "apple_inc"})
        self.assertNotIn("error", result, result)
        self.assertEqual(result["node_id"], "apple_inc")
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["count"], 1)
        self.assertEqual(result["provenance"][0]["source_document"], "unit-test")
        self.assertEqual(result["sources"], ["unit-test"])
        self.assertIn(("get_lineage", "apple_inc"), _DummyManager.calls)

    def test_legacy_node_id_still_works(self):
        result = self._call({"node_id": "apple_inc"})
        self.assertNotIn("error", result, result)
        self.assertEqual(result["node_id"], "apple_inc")
        self.assertEqual(result["status"], "ok")
        self.assertIn(("get_lineage", "apple_inc"), _DummyManager.calls)

    def test_entity_id_wins_when_both_are_provided(self):
        result = self._call({"entity_id": "apple_inc", "node_id": "other"})
        self.assertNotIn("error", result, result)
        self.assertEqual(result["node_id"], "apple_inc")
        self.assertNotIn(("get_provenance", "other"), _DummyManager.calls)

    def test_empty_entity_id_falls_back_to_node_id(self):
        result = self._call({"entity_id": "   ", "node_id": "apple_inc"})
        self.assertNotIn("error", result, result)
        self.assertEqual(result["node_id"], "apple_inc")

    def test_entity_id_is_stripped(self):
        result = self._call({"entity_id": "  apple_inc  "})
        self.assertNotIn("error", result, result)
        self.assertEqual(result["node_id"], "apple_inc")

    def test_include_metadata_false_omits_sources(self):
        result = self._call({"entity_id": "apple_inc", "include_metadata": False})
        self.assertNotIn("error", result, result)
        self.assertNotIn("sources", result)

    def test_missing_id_errors_with_entity_id(self):
        result = self._call({})
        self.assertEqual(result["error"], "entity_id is required")
        self.assertEqual(result["provenance"], [])
        self.assertEqual(_DummyManager.calls, [])

    def test_whitespace_only_errors(self):
        result = self._call({"entity_id": "  ", "node_id": "\t"})
        self.assertEqual(result["error"], "entity_id is required")
        self.assertEqual(result["provenance"], [])
        self.assertEqual(_DummyManager.calls, [])

    def test_empty_strings_error(self):
        result = self._call({"entity_id": "", "node_id": ""})
        self.assertEqual(result["error"], "entity_id is required")
        self.assertEqual(_DummyManager.calls, [])


class TestGetProvenanceDispatch(_ManagerTestMixin, unittest.TestCase):
    """JSON-RPC tools/call and call_tool use the same handler."""

    def test_call_tool_with_entity_id_is_not_an_error(self):
        from semantica_mcp.mcp.server import call_tool

        with patch(
            "semantica_mcp.mcp.tools.export.get_provenance_manager",
            return_value=_DummyManager(),
        ):
            result = call_tool("get_provenance", {"entity_id": "apple_inc"})
        self.assertNotIn("error", result, result)
        self.assertEqual(result["node_id"], "apple_inc")
        self.assertEqual(result["status"], "ok")

    def test_tools_call_entity_id_is_not_iserror(self):
        from semantica_mcp.mcp.server import _handle_tools_call

        with patch(
            "semantica_mcp.mcp.tools.export.get_provenance_manager",
            return_value=_DummyManager(),
        ):
            response = _handle_tools_call(
                1,
                {
                    "name": "get_provenance",
                    "arguments": {"entity_id": "apple_inc"},
                },
            )
        self.assertNotIn("error", response)
        self.assertFalse(response["result"]["isError"])
        payload = json.loads(response["result"]["content"][0]["text"])
        self.assertNotIn("error", payload)
        self.assertEqual(payload["node_id"], "apple_inc")
        self.assertEqual(payload["status"], "ok")

    def test_tools_call_missing_id_is_error_content(self):
        from semantica_mcp.mcp.server import _handle_tools_call

        response = _handle_tools_call(1, {"name": "get_provenance", "arguments": {}})
        self.assertTrue(response["result"]["isError"])
        payload = json.loads(response["result"]["content"][0]["text"])
        self.assertEqual(payload["error"], "entity_id is required")


class TestGetProvenanceNoStore(unittest.TestCase):
    """No configured provenance DB must not fall back to graph metadata."""

    def test_no_store_returns_not_configured(self):
        from semantica_mcp.mcp.tools.export import handle_get_provenance

        with patch(
            "semantica_mcp.mcp.tools.export.get_provenance_manager",
            return_value=None,
        ):
            result = handle_get_provenance({"entity_id": "apple_inc"})

        self.assertEqual(
            result,
            {
                "node_id": "apple_inc",
                "provenance": [],
                "count": 0,
                "lineage": [],
                "lineage_count": 0,
                "status": "not_configured",
            },
        )

    def test_metadata_is_not_returned_as_provenance(self):
        from semantica_mcp.mcp.tools.export import handle_get_provenance

        with (
            patch(
                "semantica_mcp.mcp.tools.export.get_provenance_manager",
                return_value=None,
            ),
            patch(
                "semantica_mcp.mcp.tools.export.get_graph",
                side_effect=AssertionError("graph metadata must not be read"),
            ),
        ):
            result = handle_get_provenance({"entity_id": "apple_inc"})

        self.assertEqual(result["provenance"], [])
        self.assertNotIn("sources", result)


class TestGetProvenanceLineageSemantics(unittest.TestCase):
    def test_lineage_without_current_record_is_not_promoted(self):
        """A lineage-only manager must not label an ancestor as the requested entity."""
        from semantica_mcp.mcp.tools.export import handle_get_provenance

        class LineageOnlyManager:
            def get_provenance(self, entity_id):
                return None

            def get_lineage(self, entity_id):
                return {
                    "lineage_chain": [{"entity_id": "ancestor"}],
                    "source_documents": ["ancestor-source"],
                    "integrity_verified": True,
                }

        with patch(
            "semantica_mcp.mcp.tools.export.get_provenance_manager",
            return_value=LineageOnlyManager(),
        ):
            result = handle_get_provenance({"entity_id": "apple_inc"})

        self.assertEqual(result["provenance"], [])
        self.assertEqual(result["count"], 0)
        self.assertEqual(result["status"], "not_found")
        self.assertEqual(result["lineage_count"], 1)

    def test_list_records_are_normalized_to_dicts(self):
        from semantica_mcp.mcp.tools.export import handle_get_provenance

        class Entry:
            def to_dict(self):
                return {"entity_id": "apple_inc", "source_document": "wiki"}

        class ListManager:
            def get_provenance(self, entity_id):
                return [Entry(), {"entity_id": entity_id}, "not-a-dict"]

            def get_lineage(self, entity_id):
                return {}

        with patch(
            "semantica_mcp.mcp.tools.export.get_provenance_manager",
            return_value=ListManager(),
        ):
            result = handle_get_provenance({"entity_id": "apple_inc"})

        self.assertEqual(result["count"], 2)
        self.assertTrue(all(isinstance(item, dict) for item in result["provenance"]))
        self.assertNotIn("not-a-dict", result["provenance"])

    def test_integrity_failure_is_reported(self):
        from semantica_mcp.mcp.tools.export import handle_get_provenance

        class UnverifiedManager:
            def get_provenance(self, entity_id):
                return {"entity_id": entity_id, "source_document": "wiki"}

            def get_lineage(self, entity_id):
                return {
                    "lineage_chain": [
                        {"entity_id": entity_id, "source_document": "wiki"}
                    ],
                    "source_documents": ["wiki"],
                    "integrity_verified": False,
                }

        with patch(
            "semantica_mcp.mcp.tools.export.get_provenance_manager",
            return_value=UnverifiedManager(),
        ):
            result = handle_get_provenance({"entity_id": "apple_inc"})

        self.assertEqual(result["status"], "integrity_failed")
        self.assertFalse(result["integrity_verified"])

    def test_lineage_only_integrity_failure_is_reported(self):
        from semantica_mcp.mcp.tools.export import handle_get_provenance

        class LineageOnlyUnverifiedManager:
            def get_provenance(self, entity_id):
                return None

            def get_lineage(self, entity_id):
                return {
                    "lineage_chain": [{"entity_id": "ancestor"}],
                    "source_documents": ["ancestor-source"],
                    "integrity_verified": False,
                }

        with patch(
            "semantica_mcp.mcp.tools.export.get_provenance_manager",
            return_value=LineageOnlyUnverifiedManager(),
        ):
            result = handle_get_provenance({"entity_id": "apple_inc"})

        self.assertEqual(result["status"], "integrity_failed")
        self.assertFalse(result["integrity_verified"])
        self.assertEqual(result["provenance"], [])

    def test_missing_store_is_reported(self):
        from semantica_mcp.mcp.tools.export import handle_get_provenance

        with patch(
            "semantica_mcp.mcp.tools.export.get_provenance_manager",
            side_effect=FileNotFoundError("missing"),
        ):
            result = handle_get_provenance({"entity_id": "apple_inc"})

        self.assertEqual(result["status"], "invalid_store")
        self.assertIn("error", result)
        self.assertEqual(result["provenance"], [])


def test_corrupt_store_is_reported(tmp_path, monkeypatch):
    import semantica_mcp.mcp.session as session

    db_path = tmp_path / "not-a-database.db"
    db_path.write_text("this is not sqlite", encoding="utf-8")
    monkeypatch.setenv("SEMANTICA_PROVENANCE_DB", str(db_path))
    session.reset_provenance_manager()
    try:
        from semantica_mcp.mcp.tools.export import handle_get_provenance

        result = handle_get_provenance({"entity_id": "apple_inc"})
    finally:
        session.reset_provenance_manager()

    assert result["status"] == "invalid_store"
    assert "error" in result
    assert result["provenance"] == []


def test_tracked_entity_is_returned_from_store(tmp_path):
    """A real ProvenanceManager record is returned, not graph metadata."""
    from semantica.provenance import ProvenanceManager
    from semantica_mcp.mcp.tools.export import handle_get_provenance

    manager = ProvenanceManager(storage_path=str(tmp_path / "provenance.db"))
    manager.track_entity("apple_inc", source="wiki", confidence=0.9)

    with patch(
        "semantica_mcp.mcp.tools.export.get_provenance_manager",
        return_value=manager,
    ):
        result = handle_get_provenance({"entity_id": "apple_inc"})

    assert result["status"] == "ok"
    assert result["count"] == 1
    assert result["provenance"][0]["entity_id"] == "apple_inc"
    assert result["provenance"][0]["source_document"] == "wiki"
    assert result["sources"] == ["wiki"]
    assert result["lineage_count"] >= 1
    assert result["integrity_verified"] is True


def test_invalidated_record_is_flagged(tmp_path):
    from semantica.provenance import ProvenanceManager
    from semantica_mcp.mcp.tools.export import handle_get_provenance

    manager = ProvenanceManager(storage_path=str(tmp_path / "provenance.db"))
    manager.track_entity("apple_inc", source="wiki")
    manager.invalidate("apple_inc", agent_id="tester", reason="superseded")

    with patch(
        "semantica_mcp.mcp.tools.export.get_provenance_manager",
        return_value=manager,
    ):
        result = handle_get_provenance({"entity_id": "apple_inc"})

    assert result["status"] == "ok"
    assert result["provenance"][0]["invalidated"] is True
    assert result["invalidated"] is True


def test_alias_only_graph_node_returns_no_provenance(tmp_path):
    """The exact #2253 reproduction: only aliases in graph metadata."""
    from semantica.context.context_graph import ContextGraph
    from semantica.provenance import ProvenanceManager
    from semantica_mcp.mcp.tools.export import handle_get_provenance

    graph = ContextGraph()
    graph.add_node("apple_inc", "entity", aliases=["Apple"])
    manager = ProvenanceManager(storage_path=str(tmp_path / "provenance.db"))

    with (
        patch(
            "semantica_mcp.mcp.tools.export.get_provenance_manager",
            return_value=manager,
        ),
        patch(
            "semantica_mcp.mcp.tools.export.get_graph",
            return_value=graph,
        ),
    ):
        result = handle_get_provenance({"entity_id": "apple_inc"})

    assert result["status"] == "not_found"
    assert result["provenance"] == []
    assert result["count"] == 0
    assert result["sources"] == []
    assert "Apple" not in json.dumps(result)


def test_malformed_json_row_is_reported_as_invalid_store(tmp_path):
    import sqlite3

    from semantica.provenance import ProvenanceManager
    from semantica_mcp.mcp.tools.export import handle_get_provenance

    db_path = tmp_path / "provenance.db"
    manager = ProvenanceManager(storage_path=str(db_path))
    manager.track_entity("apple_inc", source="wiki")

    with sqlite3.connect(db_path) as conn:
        conn.execute(
            "UPDATE provenance SET metadata = ? WHERE entity_id = ?",
            ("{not-json", "apple_inc"),
        )

    with patch(
        "semantica_mcp.mcp.tools.export.get_provenance_manager",
        return_value=manager,
    ):
        result = handle_get_provenance({"entity_id": "apple_inc"})

    assert result["status"] == "invalid_store"
    assert result["provenance"] == []
    assert "error" in result


def test_configured_store_without_record_returns_not_found(tmp_path):
    from semantica.provenance import ProvenanceManager
    from semantica_mcp.mcp.tools.export import handle_get_provenance

    manager = ProvenanceManager(storage_path=str(tmp_path / "provenance.db"))

    with patch(
        "semantica_mcp.mcp.tools.export.get_provenance_manager",
        return_value=manager,
    ):
        result = handle_get_provenance({"entity_id": "missing"})

    assert result["status"] == "not_found"
    assert result["provenance"] == []
    assert result["lineage"] == []
    assert result["sources"] == []


def test_get_provenance_manager_none_without_env(monkeypatch):
    import semantica_mcp.mcp.session as session

    monkeypatch.delenv("SEMANTICA_PROVENANCE_DB", raising=False)
    monkeypatch.delenv("EXPLORER_PROVENANCE_DB", raising=False)
    session.reset_provenance_manager()
    try:
        assert session.get_provenance_manager() is None
    finally:
        session.reset_provenance_manager()


def test_get_provenance_manager_treats_whitespace_as_unset(monkeypatch):
    import semantica_mcp.mcp.session as session

    monkeypatch.setenv("SEMANTICA_PROVENANCE_DB", "   ")
    monkeypatch.delenv("EXPLORER_PROVENANCE_DB", raising=False)
    session.reset_provenance_manager()
    try:
        assert session.get_provenance_manager() is None
    finally:
        session.reset_provenance_manager()


def test_get_provenance_manager_uses_env(monkeypatch, tmp_path):
    from semantica.provenance import ProvenanceManager
    import semantica_mcp.mcp.session as session

    db_path = tmp_path / "provenance.db"
    ProvenanceManager(storage_path=str(db_path)).track_entity("seed", source="test")
    monkeypatch.setenv("SEMANTICA_PROVENANCE_DB", str(db_path))
    session.reset_provenance_manager()
    try:
        manager = session.get_provenance_manager()
        assert manager is not None
        assert manager.storage.db_path == str(db_path)
        assert manager.get_provenance("missing") is None
    finally:
        session.reset_provenance_manager()


def test_get_provenance_manager_rejects_missing_db(monkeypatch, tmp_path):
    import semantica_mcp.mcp.session as session

    db_path = tmp_path / "missing.db"
    monkeypatch.setenv("SEMANTICA_PROVENANCE_DB", str(db_path))
    session.reset_provenance_manager()
    try:
        with pytest.raises(FileNotFoundError):
            session.get_provenance_manager()
        assert not db_path.exists()
    finally:
        session.reset_provenance_manager()


def test_whitespace_primary_falls_back_to_explorer_env(monkeypatch, tmp_path):
    from semantica.provenance import ProvenanceManager
    import semantica_mcp.mcp.session as session

    db_path = tmp_path / "provenance.db"
    ProvenanceManager(storage_path=str(db_path)).track_entity("seed", source="test")
    monkeypatch.setenv("SEMANTICA_PROVENANCE_DB", "   ")
    monkeypatch.setenv("EXPLORER_PROVENANCE_DB", str(db_path))
    session.reset_provenance_manager()
    try:
        manager = session.get_provenance_manager()
        assert manager is not None
        assert manager.storage.db_path == str(db_path)
    finally:
        session.reset_provenance_manager()
