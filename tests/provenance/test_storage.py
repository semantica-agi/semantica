"""
Test Provenance Storage Backends

Tests for InMemoryStorage and SQLiteStorage backends.
"""

import pytest
import sqlite3
import tempfile
import os
from semantica.provenance.schemas import ProvenanceEntry
from semantica.provenance.storage import InMemoryStorage, SQLiteStorage


class TestInMemoryStorage:
    """Test InMemoryStorage backend."""
    
    def test_store_and_retrieve(self):
        """Test storing and retrieving entries."""
        storage = InMemoryStorage()
        
        entry = ProvenanceEntry(
            entity_id="entity_1",
            entity_type="entity",
            activity_id="extraction"
        )
        
        storage.store(entry)
        retrieved = storage.retrieve("entity_1")
        
        assert retrieved is not None
        assert retrieved.entity_id == "entity_1"
    
    def test_retrieve_nonexistent(self):
        """Test retrieving non-existent entry."""
        storage = InMemoryStorage()
        
        retrieved = storage.retrieve("nonexistent")
        
        assert retrieved is None
    
    def test_retrieve_all(self):
        """Test retrieving all entries."""
        storage = InMemoryStorage()
        
        entry1 = ProvenanceEntry(
            entity_id="entity_1",
            entity_type="entity",
            activity_id="extraction"
        )
        entry2 = ProvenanceEntry(
            entity_id="entity_2",
            entity_type="chunk",
            activity_id="chunking"
        )
        
        storage.store(entry1)
        storage.store(entry2)
        
        all_entries = storage.retrieve_all()
        
        assert len(all_entries) == 2
    
    def test_retrieve_by_type(self):
        """Test retrieving entries by type."""
        storage = InMemoryStorage()
        
        entry1 = ProvenanceEntry(
            entity_id="entity_1",
            entity_type="entity",
            activity_id="extraction"
        )
        entry2 = ProvenanceEntry(
            entity_id="chunk_1",
            entity_type="chunk",
            activity_id="chunking"
        )
        
        storage.store(entry1)
        storage.store(entry2)
        
        entities = storage.retrieve_all(entity_type="entity")
        
        assert len(entities) == 1
        assert entities[0].entity_type == "entity"
    
    def test_trace_lineage(self):
        """Test tracing lineage."""
        storage = InMemoryStorage()
        
        # Create parent-child chain
        entry1 = ProvenanceEntry(
            entity_id="entity_1",
            entity_type="entity",
            activity_id="extraction"
        )
        entry2 = ProvenanceEntry(
            entity_id="entity_2",
            entity_type="entity",
            activity_id="transformation",
            parent_entity_id="entity_1"
        )
        entry3 = ProvenanceEntry(
            entity_id="entity_3",
            entity_type="entity",
            activity_id="transformation",
            parent_entity_id="entity_2"
        )
        
        storage.store(entry1)
        storage.store(entry2)
        storage.store(entry3)
        
        lineage = storage.trace_lineage("entity_3")
        
        assert len(lineage) == 3
        entity_ids = [e.entity_id for e in lineage]
        assert "entity_1" in entity_ids
        assert "entity_2" in entity_ids
        assert "entity_3" in entity_ids
    
    def test_clear(self):
        """Test clearing storage."""
        storage = InMemoryStorage()
        
        entry = ProvenanceEntry(
            entity_id="entity_1",
            entity_type="entity",
            activity_id="extraction"
        )
        
        storage.store(entry)
        count = storage.clear()

        assert count == 1
        assert len(storage.retrieve_all()) == 0

    def test_clear_resets_chain_state(self):
        """Issue #825 fix: clear() must reset chain state so get_chain_head()
        returns None and the first write after clear starts a fresh chain."""
        storage = InMemoryStorage()

        entry1 = ProvenanceEntry(
            entity_id="e1", entity_type="entity", activity_id="act",
            sequence_id=1, checksum="checksum_1",
        )
        storage.store(entry1)
        assert storage.get_chain_head() == (1, "checksum_1")

        storage.clear()

        # Chain head must be None after clear
        assert storage.get_chain_head() is None

        # First write after clear starts a fresh chain
        entry2 = ProvenanceEntry(
            entity_id="e2", entity_type="entity", activity_id="act",
            sequence_id=1, checksum="checksum_fresh",
        )
        storage.store(entry2)
        assert storage.get_chain_head() == (1, "checksum_fresh")

    def test_get_chain_head(self):
        """Issue #825, Part A item 2 — chain head reporting."""
        storage = InMemoryStorage()
        assert storage.get_chain_head() is None

        entry1 = ProvenanceEntry(
            entity_id="e1", entity_type="entity", activity_id="act",
            sequence_id=1, checksum="checksum_1",
        )
        storage.store(entry1)
        assert storage.get_chain_head() == (1, "checksum_1")

        entry2 = ProvenanceEntry(
            entity_id="e2", entity_type="entity", activity_id="act",
            sequence_id=2, checksum="checksum_2",
        )
        storage.store(entry2)
        assert storage.get_chain_head() == (2, "checksum_2")

    def test_trace_descendants(self):
        """Issue #825, Part A item 5 — reverse (downstream) lineage traversal."""
        storage = InMemoryStorage()
        storage.store(ProvenanceEntry(entity_id="a", entity_type="entity", activity_id="act"))
        storage.store(ProvenanceEntry(
            entity_id="b", entity_type="entity", activity_id="act", parent_entity_id="a"
        ))
        storage.store(ProvenanceEntry(
            entity_id="c", entity_type="entity", activity_id="act", parent_entity_id="b"
        ))
        storage.store(ProvenanceEntry(
            entity_id="d", entity_type="entity", activity_id="act", used_entities=["a"]
        ))

        descendants = storage.trace_descendants("a")
        entity_ids = {e.entity_id for e in descendants}
        assert entity_ids == {"b", "c", "d"}

    def test_trace_descendants_respects_max_depth(self):
        storage = InMemoryStorage()
        storage.store(ProvenanceEntry(entity_id="a", entity_type="entity", activity_id="act"))
        storage.store(ProvenanceEntry(
            entity_id="b", entity_type="entity", activity_id="act", parent_entity_id="a"
        ))
        storage.store(ProvenanceEntry(
            entity_id="c", entity_type="entity", activity_id="act", parent_entity_id="b"
        ))

        descendants = storage.trace_descendants("a", max_depth=1)
        entity_ids = {e.entity_id for e in descendants}
        assert entity_ids == {"b"}

    def test_trace_descendants_empty_for_leaf(self):
        storage = InMemoryStorage()
        storage.store(ProvenanceEntry(entity_id="leaf", entity_type="entity", activity_id="act"))
        assert storage.trace_descendants("leaf") == []


class TestSQLiteStorage:
    """Test SQLiteStorage backend."""

    def test_migrates_pre_existing_old_schema_database(self):
        """Regression test: SQLiteStorage._init_db() previously only ran
        CREATE TABLE IF NOT EXISTS, which does not alter an existing table.
        A provenance.db created before issue #825's Part A/B columns existed
        would otherwise break on every insert/select once the new code's
        wider positional INSERT and _row_to_entry's fixed indices no longer
        matched the old (narrower) row width. SQLiteStorage now migrates any
        missing columns in on open."""
        with tempfile.NamedTemporaryFile(delete=False, suffix=".db") as tmp:
            db_path = tmp.name

        try:
            # Simulate a database created by the pre-#825 code: only the
            # original 19 columns, no agent_type/sequence_id/valid_from/etc.
            conn = sqlite3.connect(db_path)
            conn.execute("""
                CREATE TABLE provenance (
                    entity_id TEXT PRIMARY KEY,
                    entity_type TEXT NOT NULL,
                    activity_id TEXT NOT NULL,
                    agent_id TEXT DEFAULT 'semantica',
                    source_document TEXT,
                    source_location TEXT,
                    source_quote TEXT,
                    timestamp TEXT NOT NULL,
                    first_seen TEXT,
                    last_updated TEXT,
                    confidence REAL DEFAULT 1.0,
                    checksum TEXT,
                    parent_entity_id TEXT,
                    used_entities TEXT,
                    start_index INTEGER,
                    end_index INTEGER,
                    credibility REAL,
                    metadata TEXT,
                    version TEXT DEFAULT '1.0'
                )
            """)
            conn.execute(
                "INSERT INTO provenance VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    "old_entity", "entity", "legacy_activity", "semantica", "doc1",
                    None, None, "2025-01-01T00:00:00", "2025-01-01T00:00:00",
                    "2025-01-01T00:00:00", 1.0, "oldchecksum", None, "[]",
                    None, None, None, "{}", "1.0",
                ),
            )
            conn.commit()
            conn.close()

            # Opening with the current SQLiteStorage must not crash, and must
            # migrate the table in place rather than requiring a fresh file.
            storage = SQLiteStorage(db_path)

            old_entry = storage.retrieve("old_entity")
            assert old_entry is not None
            assert old_entry.entity_id == "old_entity"
            assert old_entry.agent_type == "software_agent"  # new column default
            assert old_entry.sequence_id is None  # never assigned pre-migration

            # New writes against the migrated table must work too.
            new_entry = ProvenanceEntry(
                entity_id="new_entity", entity_type="entity", activity_id="act",
                agent_id="alice", sequence_id=1, checksum="chk1",
            )
            storage.store(new_entry)
            retrieved = storage.retrieve("new_entity")
            assert retrieved.agent_id == "alice"
            assert retrieved.sequence_id == 1
        finally:
            if os.path.exists(db_path):
                os.unlink(db_path)

    def test_all_fields_round_trip_through_sqlite(self):
        """Regression test: every ProvenanceEntry field, including issue #825
        Part A and Part B additions, must survive a SQLite store/retrieve
        round trip byte-for-byte. Part B's activity/actedOnBehalfOf/
        informedBy/revision/bundle fields were initially added to the
        dataclass and to export_prov() without updating SQLiteStorage's DDL/
        INSERT/_row_to_entry — InMemoryStorage stores the dataclass directly
        so it masked the gap, but SQLite silently dropped every one of those
        fields on write."""
        with tempfile.NamedTemporaryFile(delete=False, suffix=".db") as tmp:
            db_path = tmp.name

        try:
            storage = SQLiteStorage(db_path)
            entry = ProvenanceEntry(
                entity_id="entity_1",
                entity_type="entity",
                activity_id="extraction",
                agent_id="alice",
                agent_type="person",
                is_automated=False,
                role="approver",
                sequence_id=1,
                previous_checksum="prevchk",
                parent_entity_id="parent_1",
                used_entities=["u1", "u2"],
                previous_version_id="entity_1:v:1",
                derived_from_id="source_1",
                invalidated=True,
                invalidated_at_time="2026-01-01T00:00:00",
                invalidated_by="reviewer_jane",
                invalidation_reason="retracted",
                activity_started_at_time="2026-01-01T00:00:00",
                activity_ended_at_time="2026-01-01T00:00:05",
                acted_on_behalf_of="org1",
                informed_by_activities=["act_a", "act_b"],
                valid_from="2026-01-01",
                valid_until="2026-06-01",
                revision_type="correction",
                supersedes="old_claim",
                bundle_id="ingestion_run_1",
            )
            storage.store(entry)
            retrieved = storage.retrieve("entity_1")

            assert retrieved == entry
        finally:
            if os.path.exists(db_path):
                os.unlink(db_path)

    def test_store_and_retrieve(self):
        """Test storing and retrieving entries."""
        with tempfile.NamedTemporaryFile(delete=False, suffix=".db") as tmp:
            db_path = tmp.name
        
        try:
            storage = SQLiteStorage(db_path)
            
            entry = ProvenanceEntry(
                entity_id="entity_1",
                entity_type="entity",
                activity_id="extraction"
            )
            
            storage.store(entry)
            retrieved = storage.retrieve("entity_1")
            
            assert retrieved is not None
            assert retrieved.entity_id == "entity_1"
        finally:
            if os.path.exists(db_path):
                os.unlink(db_path)
    
    def test_persistence(self):
        """Test data persistence across connections."""
        with tempfile.NamedTemporaryFile(delete=False, suffix=".db") as tmp:
            db_path = tmp.name
        
        try:
            # Store entry
            storage1 = SQLiteStorage(db_path)
            entry = ProvenanceEntry(
                entity_id="entity_1",
                entity_type="entity",
                activity_id="extraction"
            )
            storage1.store(entry)
            
            # Retrieve with new connection
            storage2 = SQLiteStorage(db_path)
            retrieved = storage2.retrieve("entity_1")
            
            assert retrieved is not None
            assert retrieved.entity_id == "entity_1"
        finally:
            if os.path.exists(db_path):
                os.unlink(db_path)
    
    def test_trace_lineage(self):
        """Test tracing lineage in SQLite."""
        with tempfile.NamedTemporaryFile(delete=False, suffix=".db") as tmp:
            db_path = tmp.name
        
        try:
            storage = SQLiteStorage(db_path)
            
            # Create parent-child chain
            entry1 = ProvenanceEntry(
                entity_id="entity_1",
                entity_type="entity",
                activity_id="extraction"
            )
            entry2 = ProvenanceEntry(
                entity_id="entity_2",
                entity_type="entity",
                activity_id="transformation",
                parent_entity_id="entity_1"
            )
            
            storage.store(entry1)
            storage.store(entry2)
            
            lineage = storage.trace_lineage("entity_2")

            assert len(lineage) == 2
        finally:
            if os.path.exists(db_path):
                os.unlink(db_path)

    def test_get_chain_head(self):
        """Issue #825, Part A item 2 — chain head reporting."""
        with tempfile.NamedTemporaryFile(delete=False, suffix=".db") as tmp:
            db_path = tmp.name

        try:
            storage = SQLiteStorage(db_path)
            assert storage.get_chain_head() is None

            entry1 = ProvenanceEntry(
                entity_id="e1", entity_type="entity", activity_id="act",
                sequence_id=1, checksum="checksum_1",
            )
            storage.store(entry1)
            assert storage.get_chain_head() == (1, "checksum_1")

            entry2 = ProvenanceEntry(
                entity_id="e2", entity_type="entity", activity_id="act",
                sequence_id=2, checksum="checksum_2",
            )
            storage.store(entry2)
            assert storage.get_chain_head() == (2, "checksum_2")
        finally:
            if os.path.exists(db_path):
                os.unlink(db_path)

    def test_trace_descendants(self):
        """Issue #825, Part A item 5 — reverse (downstream) lineage traversal."""
        with tempfile.NamedTemporaryFile(delete=False, suffix=".db") as tmp:
            db_path = tmp.name

        try:
            storage = SQLiteStorage(db_path)
            storage.store(ProvenanceEntry(entity_id="a", entity_type="entity", activity_id="act"))
            storage.store(ProvenanceEntry(
                entity_id="b", entity_type="entity", activity_id="act", parent_entity_id="a"
            ))
            storage.store(ProvenanceEntry(
                entity_id="c", entity_type="entity", activity_id="act", parent_entity_id="b"
            ))
            storage.store(ProvenanceEntry(
                entity_id="d", entity_type="entity", activity_id="act", used_entities=["a"]
            ))

            descendants = storage.trace_descendants("a")
            entity_ids = {e.entity_id for e in descendants}
            assert entity_ids == {"b", "c", "d"}
        finally:
            if os.path.exists(db_path):
                os.unlink(db_path)

    def test_trace_descendants_empty_for_leaf(self):
        with tempfile.NamedTemporaryFile(delete=False, suffix=".db") as tmp:
            db_path = tmp.name

        try:
            storage = SQLiteStorage(db_path)
            storage.store(ProvenanceEntry(entity_id="leaf", entity_type="entity", activity_id="act"))
            assert storage.trace_descendants("leaf") == []
        finally:
            if os.path.exists(db_path):
                os.unlink(db_path)


class TestSQLiteStorageSchemaSelfHeal:
    """Schema 自愈回归：DB 文件在长驻进程存活期间被外部删除/替换后，
    后续操作必须重建 schema，而不是报 'no such table: provenance'。"""

    def test_schema_recreated_after_db_file_deleted(self):
        with tempfile.NamedTemporaryFile(delete=False, suffix=".db") as tmp:
            db_path = tmp.name

        try:
            storage = SQLiteStorage(db_path)
            storage.store(ProvenanceEntry(entity_id="a", entity_type="entity", activity_id="act"))
            assert storage.retrieve("a") is not None

            # 模拟部署事故：文件被外部清空（SQLite 对缺失文件静默建空库，
            # 长驻对象不再重建 schema 就会连续撞 no such table）
            for suffix in ("", "-wal", "-shm"):
                if os.path.exists(db_path + suffix):
                    os.unlink(db_path + suffix)

            # 读写两条路径各自重连后都应自愈
            assert storage.retrieve("a") is None
            storage.store(ProvenanceEntry(entity_id="b", entity_type="entity", activity_id="act"))
            assert storage.retrieve("b") is not None
            assert storage.retrieve_all() != []
        finally:
            for suffix in ("", "-wal", "-shm"):
                if os.path.exists(db_path + suffix):
                    os.unlink(db_path + suffix)

    def test_migrate_columns_on_existing_table(self):
        """旧库（原始 19 列 schema）缺迁移列时，任一连接打开即补全。"""
        with tempfile.NamedTemporaryFile(delete=False, suffix=".db") as tmp:
            db_path = tmp.name

        try:
            conn = sqlite3.connect(db_path)
            conn.execute("""
                CREATE TABLE provenance (
                    entity_id TEXT PRIMARY KEY,
                    entity_type TEXT NOT NULL,
                    activity_id TEXT NOT NULL,
                    agent_id TEXT DEFAULT 'semantica',
                    source_document TEXT,
                    source_location TEXT,
                    source_quote TEXT,
                    timestamp TEXT NOT NULL,
                    first_seen TEXT,
                    last_updated TEXT,
                    confidence REAL DEFAULT 1.0,
                    checksum TEXT,
                    parent_entity_id TEXT,
                    used_entities TEXT,
                    start_index INTEGER,
                    end_index INTEGER,
                    credibility REAL,
                    metadata TEXT,
                    version TEXT DEFAULT '1.0'
                )
            """)
            conn.commit()
            conn.close()

            storage = SQLiteStorage(db_path)
            storage.store(ProvenanceEntry(entity_id="x", entity_type="entity", activity_id="act"))
            assert storage.retrieve("x").entity_id == "x"
        finally:
            if os.path.exists(db_path):
                os.unlink(db_path)
