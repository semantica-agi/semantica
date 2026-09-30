"""
Tests for AgnoContextStore — graph-backed Agno MemoryDb.

All tests run without a real Agno installation by mocking the base class
and using in-memory Semantica components only.
"""

from __future__ import annotations

import sys
import types
import unittest
from unittest.mock import MagicMock, patch


# ---------------------------------------------------------------------------
# Stub the agno package so the import succeeds without it installed
# ---------------------------------------------------------------------------
def _stub_agno() -> None:
    """Insert minimal agno stubs into sys.modules."""
    if "agno" in sys.modules:
        return  # real agno installed — no stub needed

    agno = types.ModuleType("agno")

    # agno.memory.db.base
    memory_pkg = types.ModuleType("agno.memory")
    memory_db_pkg = types.ModuleType("agno.memory.db")
    memory_db_base = types.ModuleType("agno.memory.db.base")

    class MemoryDb:  # noqa: D101
        def __init__(self, *a, **kw): ...  # noqa: E704

    memory_db_base.MemoryDb = MemoryDb  # type: ignore

    # agno.memory.db.row
    memory_db_row = types.ModuleType("agno.memory.db.row")

    class MemoryRow:  # noqa: D101
        def __init__(self, memory: str, id=None, user_id=None, **kw):
            self.memory = memory
            self.id = id
            self.user_id = user_id
            self.last_updated = 0.0
            self.topics = kw.get("topics", [])

    memory_db_row.MemoryRow = MemoryRow  # type: ignore

    memory_db_pkg.base = memory_db_base
    memory_db_pkg.row = memory_db_row
    memory_pkg.db = memory_db_pkg

    agno.memory = memory_pkg  # type: ignore

    for name, mod in [
        ("agno", agno),
        ("agno.memory", memory_pkg),
        ("agno.memory.db", memory_db_pkg),
        ("agno.memory.db.base", memory_db_base),
        ("agno.memory.db.row", memory_db_row),
    ]:
        sys.modules.setdefault(name, mod)


_stub_agno()


from integrations.agno.context_store import AgnoContextStore  # noqa: E402


class TestAgnoContextStoreInit(unittest.TestCase):
    """Construction and basic attribute checks."""

    def _make_store(self, **kwargs) -> AgnoContextStore:
        return AgnoContextStore(decision_tracking=True, graph_expansion=True, **kwargs)

    def test_creates_without_args(self):
        store = self._make_store()
        self.assertIsNotNone(store)

    def test_session_id_generated(self):
        store = self._make_store()
        self.assertIsInstance(store.session_id, str)
        self.assertTrue(len(store.session_id) > 0)

    def test_explicit_session_id(self):
        store = AgnoContextStore(session_id="abc-123")
        self.assertEqual(store.session_id, "abc-123")

    def test_decision_tracking_flag(self):
        store = AgnoContextStore(decision_tracking=False)
        self.assertFalse(store.decision_tracking)

    def test_context_property(self):
        store = self._make_store()
        self.assertIsNotNone(store.context)


class TestAgnoContextStoreMemoryDb(unittest.TestCase):
    """MemoryDb protocol methods."""

    def setUp(self):
        self.store = AgnoContextStore(decision_tracking=False)

    def _make_row(self, text: str, uid: str = "u1"):
        row = MagicMock()
        row.memory = text
        row.id = None
        row.user_id = uid
        row.last_updated = 0.0
        row.topics = []
        return row

    def test_table_exists(self):
        self.assertTrue(self.store.table_exists())

    def test_create_noop(self):
        # Should not raise
        self.store.create()

    def test_upsert_and_read(self):
        row = self._make_row("Hello world")
        self.store.upsert_memory(row)
        memories = self.store.read_memories()
        self.assertEqual(len(memories), 1)

    def test_upsert_sets_id(self):
        row = self._make_row("Test memory")
        self.store.upsert_memory(row)
        self.assertIsNotNone(row.id)

    def test_memory_exists_after_upsert(self):
        row = self._make_row("Exists check")
        self.store.upsert_memory(row)
        self.assertTrue(self.store.memory_exists(row))

    def test_memory_not_exists_before_upsert(self):
        row = self._make_row("Not yet")
        row.id = "unknown-id"
        self.assertFalse(self.store.memory_exists(row))

    def test_delete_memory(self):
        row = self._make_row("To delete")
        self.store.upsert_memory(row)
        mem_id = row.id
        self.store.delete_memory(mem_id)
        self.assertFalse(self.store.memory_exists(row))

    def test_read_memories_user_filter(self):
        row_a = self._make_row("User A memory", uid="alice")
        row_b = self._make_row("User B memory", uid="bob")
        self.store.upsert_memory(row_a)
        self.store.upsert_memory(row_b)

        alice_rows = self.store.read_memories(user_id="alice")
        self.assertEqual(len(alice_rows), 1)
        self.assertEqual(alice_rows[0].user_id, "alice")

    def test_read_memories_limit(self):
        for i in range(5):
            self.store.upsert_memory(self._make_row(f"Memory {i}"))
        rows = self.store.read_memories(limit=3)
        self.assertEqual(len(rows), 3)

    def test_clear(self):
        for i in range(3):
            self.store.upsert_memory(self._make_row(f"M{i}"))
        result = self.store.clear()
        self.assertTrue(result)
        self.assertEqual(len(self.store.read_memories()), 0)

    def test_drop_table(self):
        self.store.upsert_memory(self._make_row("Drop me"))
        self.store.drop_table()
        self.assertEqual(len(self.store.read_memories()), 0)


class TestAgnoContextStoreExtendedAPI(unittest.TestCase):
    """Extended Semantica-specific methods."""

    def setUp(self):
        self.store = AgnoContextStore(decision_tracking=True)
        # Patch the internal AgentContext to avoid real LLM/vector calls
        self.store._context = MagicMock()
        self.store._context.record_decision.return_value = "dec-001"
        self.store._context.find_precedents_advanced.return_value = []
        self.store._context.retrieve.return_value = []

    def test_record_decision_returns_id(self):
        did = self.store.record_decision(
            category="test",
            scenario="Unit test scenario",
            reasoning="Testing",
            outcome="pass",
            confidence=0.9,
        )
        self.assertEqual(did, "dec-001")
        self.store._context.record_decision.assert_called_once()

    def test_find_precedents_returns_list(self):
        result = self.store.find_precedents("some scenario")
        self.assertIsInstance(result, list)

    def test_retrieve_returns_list(self):
        result = self.store.retrieve("query text")
        self.assertIsInstance(result, list)

    def test_record_decision_passes_entities(self):
        self.store.record_decision(
            category="finance",
            scenario="Loan",
            reasoning="Good credit",
            outcome="approved",
            confidence=0.95,
            entities=["applicant", "loan"],
        )
        call_kwargs = self.store._context.record_decision.call_args[1]
        self.assertEqual(call_kwargs["entities"], ["applicant", "loan"])

    def test_upsert_with_decision_tracking(self):
        row = MagicMock()
        row.memory = "Important fact"
        row.id = None
        row.user_id = "u1"
        row.last_updated = 0.0
        row.topics = []
        self.store.upsert_memory(row)
        # decision should have been recorded
        self.store._context.record_decision.assert_called()


class TestAgnoContextStoreUpsertNERAttributes(unittest.TestCase):
    """upsert_memory() must read .text/.label from Entity, not .name/.type (#1737)."""

    def setUp(self):
        self.store = AgnoContextStore(decision_tracking=False)

    def _make_row(self, text: str):
        row = MagicMock()
        row.memory = text
        row.id = None
        row.user_id = "u1"
        row.last_updated = 0.0
        row.topics = []
        return row

    def test_upsert_indexes_entity_text_not_repr(self):
        """Entities added to the knowledge graph must use .text, not str(entity)."""
        from semantica.semantic_extract.types import Entity

        captured_node_ids: list = []
        fake_kg = MagicMock()
        fake_kg.add_node.side_effect = lambda node_id, node_type: captured_node_ids.append(node_id)

        fake_context = MagicMock()
        fake_context.store.return_value = None
        fake_context.knowledge_graph = fake_kg

        with patch(
            "integrations.agno.context_store.NERExtractor"
        ) as MockNER:
            instance = MockNER.return_value
            instance.extract_entities.return_value = [
                Entity(text="Alice Smith", label="PERSON", start_char=0, end_char=11),
                Entity(text="Acme Corp", label="ORG", start_char=20, end_char=29),
            ]
            self.store._context = fake_context
            self.store.upsert_memory(self._make_row("Alice Smith works at Acme Corp."))

        self.assertIn("Alice Smith", captured_node_ids)
        self.assertIn("Acme Corp", captured_node_ids)
        # Confirm no repr strings leaked through
        for node_id in captured_node_ids:
            self.assertNotIn("Entity(", node_id)

    def test_upsert_indexes_entity_label_as_type(self):
        """Node type must be the .label value (e.g. 'PERSON'), not an empty string."""
        from semantica.semantic_extract.types import Entity

        captured_types: list = []
        fake_kg = MagicMock()
        fake_kg.add_node.side_effect = lambda node_id, node_type: captured_types.append(node_type)

        fake_context = MagicMock()
        fake_context.store.return_value = None
        fake_context.knowledge_graph = fake_kg

        with patch(
            "integrations.agno.context_store.NERExtractor"
        ) as MockNER:
            instance = MockNER.return_value
            instance.extract_entities.return_value = [
                Entity(text="Alice Smith", label="PERSON", start_char=0, end_char=11),
            ]
            self.store._context = fake_context
            self.store.upsert_memory(self._make_row("Alice Smith is here."))

        self.assertIn("PERSON", captured_types)


if __name__ == "__main__":
    unittest.main()
