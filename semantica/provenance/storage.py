"""
Provenance Storage Backends

This module provides storage backends for provenance tracking, including
in-memory and persistent SQLite storage with W3C PROV-O compliance.

Storage Backends:
    - InMemoryStorage: Fast in-memory storage for development/testing
    - SQLiteStorage: Persistent SQLite storage for production use

Features:
    - W3C PROV-O compliant schema
    - Lineage tracing with BFS traversal
    - Efficient entity retrieval
    - Type-based filtering
    - Integrity verification support

Author: Semantica Contributors
License: MIT
"""

from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any, Tuple
import sqlite3
import json
import uuid
import threading
from collections import deque
from contextlib import contextmanager

from .schemas import ProvenanceEntry
from ..utils.logging import get_logger


class ProvenanceStorage(ABC):
    """
    Abstract storage interface for provenance tracking.
    
    All storage backends must implement these methods to ensure
    consistent provenance tracking across different storage types.
    """
    
    @abstractmethod
    def store(self, entry: ProvenanceEntry) -> None:
        """
        Store a provenance entry.
        
        Args:
            entry: ProvenanceEntry to store
        """
        pass
    
    @abstractmethod
    def retrieve(self, entity_id: str) -> Optional[ProvenanceEntry]:
        """
        Retrieve a provenance entry by entity ID.
        
        Args:
            entity_id: Entity identifier
            
        Returns:
            ProvenanceEntry if found, None otherwise
        """
        pass
    
    @abstractmethod
    def retrieve_all(self, entity_type: Optional[str] = None) -> List[ProvenanceEntry]:
        """
        Retrieve all provenance entries, optionally filtered by type.
        
        Args:
            entity_type: Optional entity type filter
            
        Returns:
            List of ProvenanceEntry objects
        """
        pass
    
    @abstractmethod
    def trace_lineage(self, entity_id: str, max_depth: Optional[int] = None) -> List[ProvenanceEntry]:
        """
        Trace complete lineage for an entity.
        
        Note:
            Custom storage backends implementing only trace_lineage(self, entity_id)
            remain backward compatible; ProvenanceManager automatically preserves
            one-argument invocations when max_depth is omitted or unsupported.
        
        Args:
            entity_id: Entity identifier
            max_depth: Optional maximum BFS depth (default: None)
            
        Returns:
            List of ProvenanceEntry objects in lineage chain
        """
        pass
    
    @abstractmethod
    def clear(self) -> int:
        """
        Clear all provenance data.
        
        Returns:
            Number of entries cleared
        """
        pass
    
    @contextmanager
    def transaction(self):
        """Default transaction context manager for storage backends."""
        yield None

    @contextmanager
    def savepoint(self, conn: Any = None):
        """Default savepoint context manager for nested transactions / per-item isolation."""
        yield conn

    def _store_with_conn(self, conn: Any, entry: ProvenanceEntry) -> None:
        """Internal store method using an active connection/transaction."""
        self.store(entry)

    def _retrieve_with_conn(self, conn: Any, entity_id: str) -> Optional[ProvenanceEntry]:
        """Internal retrieve method using an active connection/transaction."""
        return self.retrieve(entity_id)

    def get_chain_head(self, conn: Any = None) -> Optional[Tuple[int, str]]:
        """
        Return (sequence_id, checksum) of the most recently stored entry, or
        None if the store is empty or this backend doesn't support chaining.

        Used by ProvenanceManager._save_entry to link each new entry to its
        predecessor (issue #825, Part A item 2 — hash-chained integrity).
        Default implementation reports no chaining support; override in
        backends that maintain sequence_id.
        """
        return None

    def trace_descendants(
        self, entity_id: str, max_depth: Optional[int] = None
    ) -> List[ProvenanceEntry]:
        """
        Trace downstream descendants (reverse lineage) of an entity.

        Generic default implemented purely against retrieve_all(): builds a
        reverse adjacency map from parent_entity_id/previous_version_id/
        derived_from_id/used_entities, then BFS from entity_id. Correct for
        any backend; SQLiteStorage overrides this with indexed queries.

        Args:
            entity_id: Entity identifier to find descendants of
            max_depth: Optional maximum BFS depth

        Returns:
            List of ProvenanceEntry objects that (transitively) reference
            entity_id, in BFS order.
        """
        reverse_index: Dict[str, List[ProvenanceEntry]] = {}
        for entry in self.retrieve_all():
            referenced = set(
                filter(
                    None,
                    [
                        entry.parent_entity_id,
                        entry.previous_version_id,
                        entry.derived_from_id,
                    ],
                )
            )
            referenced.update(entry.used_entities or [])
            for ref_id in referenced:
                reverse_index.setdefault(ref_id, []).append(entry)

        descendants = []
        visited = {entity_id}
        queue = deque([(entity_id, 0)])

        while queue:
            current_id, depth = queue.popleft()
            if max_depth is not None and depth >= max_depth:
                continue
            for child in reverse_index.get(current_id, []):
                if child.entity_id in visited:
                    continue
                visited.add(child.entity_id)
                descendants.append(child)
                queue.append((child.entity_id, depth + 1))

        return descendants


class InMemoryStorage(ProvenanceStorage):
    """
    Fast in-memory storage for provenance tracking.
    
    Suitable for:
        - Development and testing
        - Short-lived processes
        - Small to medium datasets
        - When persistence is not required
    
    Features:
        - O(1) entity retrieval
        - BFS lineage tracing
        - Type-based filtering
        - No external dependencies
    
    Example:
        >>> storage = InMemoryStorage()
        >>> storage.store(entry)
        >>> lineage = storage.trace_lineage("entity_123")
    """
    
    def __init__(self):
        """Initialize in-memory storage."""
        self._entries: Dict[str, ProvenanceEntry] = {}
        self._local = threading.local()
        # Hash-chain state (issue #825, Part A item 2). Best-effort: this is
        # the dev/test backend, not the durable audit backend (SQLiteStorage).
        self._seq_lock = threading.Lock()
        self._seq_counter = 0
        self._chain_head: Optional[str] = None

    def _get_pending_stack(self) -> list:
        if not hasattr(self._local, "pending_stack"):
            self._local.pending_stack = []
        return self._local.pending_stack
    
    def store(self, entry: ProvenanceEntry) -> None:
        """
        Store a provenance entry in memory.

        Args:
            entry: ProvenanceEntry to store
        """
        with self._seq_lock:
            if entry.sequence_id is not None:
                self._seq_counter = max(self._seq_counter, entry.sequence_id)
            self._chain_head = entry.checksum
        self._entries[entry.entity_id] = entry
    
    def retrieve(self, entity_id: str) -> Optional[ProvenanceEntry]:
        """
        Retrieve a provenance entry by entity ID.
        
        Args:
            entity_id: Entity identifier
            
        Returns:
            ProvenanceEntry if found, None otherwise
        """
        return self._entries.get(entity_id)
    
    def retrieve_all(self, entity_type: Optional[str] = None) -> List[ProvenanceEntry]:
        """
        Retrieve all provenance entries, optionally filtered by type.
        
        Args:
            entity_type: Optional entity type filter
            
        Returns:
            List of ProvenanceEntry objects
        """
        if entity_type:
            return [
                entry for entry in self._entries.values()
                if entry.entity_type == entity_type
            ]
        return list(self._entries.values())
    
    def trace_lineage(self, entity_id: str, max_depth: Optional[int] = None) -> List[ProvenanceEntry]:
        """
        Trace complete lineage using BFS traversal.
        
        Traces both parent entities (wasDerivedFrom) and used entities
        to build complete provenance chain.
        
        Args:
            entity_id: Entity identifier
            max_depth: Optional maximum BFS depth
            
        Returns:
            List of ProvenanceEntry objects in lineage chain
        """
        lineage = []
        visited = set()
        queue = deque([(entity_id, 0)])
        
        while queue:
            current_id, depth = queue.popleft()
            
            if current_id in visited or (max_depth is not None and depth >= max_depth):
                continue
            
            visited.add(current_id)
            entry = self.retrieve(current_id)
            
            if entry:
                lineage.append(entry)
                
                # Add parent entity to queue
                if entry.parent_entity_id:
                    queue.append((entry.parent_entity_id, depth + 1))
                
                # Add used entities to queue
                for used_id in entry.used_entities:
                    if used_id not in visited:
                        queue.append((used_id, depth + 1))
        
        return lineage
    
    def clear(self) -> int:
        """
        Clear all provenance data.
        
        Returns:
            Number of entries cleared
        """
        count = len(self._entries)
        self._entries.clear()
        with self._seq_lock:
            self._seq_counter = 0
            self._chain_head = None
        return count

    @contextmanager
    def transaction(self):
        """In-memory transaction context manager with staging buffer rollback."""
        stack = self._get_pending_stack()
        stack.append({})
        try:
            yield "IN_MEMORY_TX"
            pending = stack.pop()
            if stack:
                stack[-1].update(pending)
            else:
                for entry in pending.values():
                    self.store(entry)
        except Exception:
            if stack:
                stack.pop()
            raise

    @contextmanager
    def savepoint(self, conn: Any = None):
        """In-memory savepoint context manager with staging buffer rollback."""
        with self.transaction() as tx:
            yield tx

    def _store_with_conn(self, conn: Any, entry: ProvenanceEntry) -> None:
        """Internal store method using an active connection/transaction."""
        stack = self._get_pending_stack()
        if stack:
            stack[-1][entry.entity_id] = entry
        else:
            self.store(entry)

    def _retrieve_with_conn(self, conn: Any, entity_id: str) -> Optional[ProvenanceEntry]:
        """Internal retrieve method using an active connection/transaction."""
        stack = self._get_pending_stack()
        for pending in reversed(stack):
            if entity_id in pending:
                return pending[entity_id]
        return self.retrieve(entity_id)

    def get_chain_head(self, conn: Any = None) -> Optional[Tuple[int, str]]:
        """Return (sequence_id, checksum) of the most recent entry, including
        entries staged but not yet committed within the current transaction.

        Must compare against the *committed* head too, not just the pending
        stack: a transaction can stage an unchanged relabel (track_entity's
        archival, or invalidate()'s pre-invalidation archive) whose
        sequence_id is older than the true head from a prior, already-
        committed transaction. Blindly preferring "last staged entry"
        understates the head and corrupts the chain for the next append.
        """
        with self._seq_lock:
            best_seq = self._seq_counter
            best_checksum = self._chain_head
        for pending in self._get_pending_stack():
            for staged_entry in pending.values():
                if staged_entry.sequence_id is not None and (
                    best_checksum is None or staged_entry.sequence_id > best_seq
                ):
                    best_seq = staged_entry.sequence_id
                    best_checksum = staged_entry.checksum
        if best_checksum is None:
            return None
        return (best_seq, best_checksum)


class SQLiteStorage(ProvenanceStorage):
    """
    Persistent SQLite storage for provenance tracking.
    
    Suitable for:
        - Production use
        - Long-term provenance tracking
        - Large datasets
        - Audit trail requirements
        - Regulatory compliance
    
    Features:
        - W3C PROV-O compliant schema
        - Persistent storage
        - Efficient indexing
        - Transaction support
        - Integrity verification
    
    Example:
        >>> storage = SQLiteStorage("provenance.db")
        >>> storage.store(entry)
        >>> lineage = storage.trace_lineage("entity_123")
    """
    
    def __init__(self, db_path: str = "provenance.db"):
        """
        Initialize SQLite storage.
        
        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = db_path
        self.logger = get_logger("sqlite_storage")
        self._init_db()

    def _configure_connection(self, conn: sqlite3.Connection) -> None:
        """
        Configure SQLite connection PRAGMAs.
        
        Architectural Decision (#807):
        We do NOT hold a persistent self._conn across calls like SQLiteVecStore does.
        Holding an open file handle across public method calls breaks Windows tests
        that call os.unlink(db_path) immediately after their last SQLiteStorage or
        ProvenanceManager call without calling .close() first (confirmed: none of
        them call .close() today). Instead: we scope one connection to the full
        duration of each PUBLIC method call (not per internal SQL statement), so
        multiple internal operations within one public call share a transaction,
        but the connection always closes before that public method returns —
        preserving exact current Windows-unlink safety while still fixing atomicity
        and connection churn within each call.
        
        PRAGMA busy_timeout is set to 5000ms (5 seconds) to prevent 'database is
        locked' OperationalErrors during concurrent process/thread access by
        instructing SQLite's default busy handler to retry for up to 5 seconds.
        """
        try:
            conn.execute("PRAGMA journal_mode=WAL")
        except sqlite3.OperationalError as e:
            self.logger.warning(
                f"WAL journal mode not supported ({e}), falling back to DELETE journal mode."
            )
            try:
                conn.execute("PRAGMA journal_mode=DELETE")
            except Exception:
                pass

        try:
            conn.execute("PRAGMA busy_timeout=5000")
        except sqlite3.OperationalError as e:
            self.logger.warning(f"busy_timeout PRAGMA not supported ({e})")

        try:
            conn.execute("PRAGMA synchronous=NORMAL")
        except sqlite3.OperationalError as e:
            self.logger.warning(f"synchronous PRAGMA not supported ({e})")

    @contextmanager
    def transaction(self):
        """
        Context manager providing an active SQLite connection within a transaction.
        
        Starts an IMMEDIATE write transaction (BEGIN IMMEDIATE) so read-modify-write
        sequences are serialized across concurrent connections.
        Commits on normal exit, rolls back on exception, and always closes the connection.
        Configures PRAGMAs (WAL, busy_timeout=5000, synchronous=NORMAL).
        """
        conn = sqlite3.connect(self.db_path)
        try:
            self._configure_connection(conn)
            # 自愈：文件被外部替换/删除后，此连接面对的可能是一个无表的新库
            self._ensure_schema(conn)
            conn.execute("BEGIN IMMEDIATE")
            yield conn
            conn.commit()
        except Exception:
            try:
                conn.rollback()
            except Exception:
                pass
            raise
        finally:
            conn.close()

    @contextmanager
    def savepoint(self, conn: Any = None):
        """
        Context manager providing a SAVEPOINT for per-item rollback isolation
        within an existing transaction.
        
        If no connection is provided, falls back to a full transaction.
        """
        if conn is None:
            with self.transaction() as tx:
                yield tx
            return

        sp_name = f"sp_{uuid.uuid4().hex}"
        conn.execute(f"SAVEPOINT {sp_name}")
        try:
            yield conn
            conn.execute(f"RELEASE {sp_name}")
        except Exception:
            try:
                conn.execute(f"ROLLBACK TO {sp_name}")
                conn.execute(f"RELEASE {sp_name}")
            except Exception:
                pass
            raise

    @contextmanager
    def _read_connection(self):
        """
        Context manager providing a configured SQLite connection for read-only
        operations, without taking SQLite's writer lock.

        `transaction()` uses BEGIN IMMEDIATE, which acquires the single RESERVED
        (writer) lock so read-modify-write sequences serialize correctly. That
        lock is unnecessary for plain reads (retrieve, trace_lineage) and, if
        used there, would serialize every read behind every other read/write —
        defeating WAL's readers-don't-block-writers concurrency. Reads use a
        connection with no explicit BEGIN instead.
        """
        conn = sqlite3.connect(self.db_path)
        try:
            self._configure_connection(conn)
            self._ensure_schema(conn)
            yield conn
        finally:
            conn.close()

    # Columns added after the table was first shipped (issue #825, Part A/B).
    # CREATE TABLE IF NOT EXISTS alone does not alter an existing table, so a
    # provenance.db created before these columns existed would otherwise fail
    # on every insert/select once the row width and _row_to_entry's fixed
    # indices grew past the old schema. _migrate_schema() adds any of these
    # that are missing from an already-existing table.
    _MIGRATION_COLUMNS: List[Tuple[str, str]] = [
        ("agent_type", "TEXT DEFAULT 'software_agent'"),
        ("is_automated", "INTEGER DEFAULT 1"),
        ("role", "TEXT"),
        ("sequence_id", "INTEGER"),
        ("previous_checksum", "TEXT"),
        ("previous_version_id", "TEXT"),
        ("derived_from_id", "TEXT"),
        ("invalidated", "INTEGER DEFAULT 0"),
        ("invalidated_at_time", "TEXT"),
        ("invalidated_by", "TEXT"),
        ("invalidation_reason", "TEXT"),
        ("activity_started_at_time", "TEXT"),
        ("activity_ended_at_time", "TEXT"),
        ("acted_on_behalf_of", "TEXT"),
        ("informed_by_activities", "TEXT"),
        ("valid_from", "TEXT"),
        ("valid_until", "TEXT"),
        ("revision_type", "TEXT"),
        ("supersedes", "TEXT"),
        ("bundle_id", "TEXT"),
    ]

    _CREATE_TABLE_SQL = """
        CREATE TABLE IF NOT EXISTS provenance (
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
                    version TEXT DEFAULT '1.0',
                    agent_type TEXT DEFAULT 'software_agent',
                    is_automated INTEGER DEFAULT 1,
                    role TEXT,
                    sequence_id INTEGER,
                    previous_checksum TEXT,
                    previous_version_id TEXT,
                    derived_from_id TEXT,
                    invalidated INTEGER DEFAULT 0,
                    invalidated_at_time TEXT,
                    invalidated_by TEXT,
                    invalidation_reason TEXT,
                    activity_started_at_time TEXT,
                    activity_ended_at_time TEXT,
                    acted_on_behalf_of TEXT,
                    informed_by_activities TEXT,
                    valid_from TEXT,
                    valid_until TEXT,
                    revision_type TEXT,
                    supersedes TEXT,
                    bundle_id TEXT
                )
            """

    _INDEX_DDL_SQLS: List[str] = [
        "CREATE INDEX IF NOT EXISTS idx_entity_type ON provenance(entity_type)",
        "CREATE INDEX IF NOT EXISTS idx_source_document ON provenance(source_document)",
        "CREATE INDEX IF NOT EXISTS idx_parent_entity ON provenance(parent_entity_id)",
        "CREATE INDEX IF NOT EXISTS idx_previous_version_id ON provenance(previous_version_id)",
        "CREATE INDEX IF NOT EXISTS idx_derived_from_id ON provenance(derived_from_id)",
        "CREATE INDEX IF NOT EXISTS idx_sequence_id ON provenance(sequence_id)",
        "CREATE INDEX IF NOT EXISTS idx_invalidated ON provenance(invalidated)",
        "CREATE INDEX IF NOT EXISTS idx_bundle_id ON provenance(bundle_id)",
    ]

    def _migrate_schema(self, conn: sqlite3.Connection) -> None:
        """Add any columns introduced after the table was first created to an
        already-existing table (see _MIGRATION_COLUMNS)."""
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(provenance)")
        existing_columns = {row[1] for row in cursor.fetchall()}
        for column_name, column_def in self._MIGRATION_COLUMNS:
            if column_name not in existing_columns:
                cursor.execute(
                    f"ALTER TABLE provenance ADD COLUMN {column_name} {column_def}"
                )

    def _ensure_schema(self, conn: sqlite3.Connection) -> None:
        """幂等建表/自愈：任一连接建立后调用，保证 provenance 表存在。

        根因：schema 只在构造时建一次，而每次操作都按 db_path 重开连接；
        SQLite 遇到"文件不存在/已被删空"不报错而是静默新建空库，长驻进程
        在文件被外部替换（备份恢复/目录重置/测试清理）后，所有后续操作都会
        撞上 'no such table: provenance'。这里先以只读方式探测 sqlite_master，
        缺表才重建；表已存在则只做幂等的缺列迁移，正常路径零额外写成本。
        """
        cursor = conn.cursor()
        exists = cursor.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='provenance'"
        ).fetchone()
        if exists is None:
            cursor.execute(self._CREATE_TABLE_SQL)
            for ddl in self._INDEX_DDL_SQLS:
                cursor.execute(ddl)
            # 新表已含 _MIGRATION_COLUMNS 全部最新列，无需迁移
        else:
            self._migrate_schema(conn)

    def _init_db(self) -> None:
        """初始化连接并确保 schema（幂等，可重复调用）。"""
        conn = sqlite3.connect(self.db_path)
        try:
            self._configure_connection(conn)
            self._ensure_schema(conn)
            conn.commit()
        finally:
            conn.close()

    def store(self, entry: ProvenanceEntry) -> None:
        """
        Store a provenance entry in SQLite database.
        
        Args:
            entry: ProvenanceEntry to store
        """
        with self.transaction() as conn:
            self._store_with_conn(conn, entry)

    def _store_with_conn(self, conn: sqlite3.Connection, entry: ProvenanceEntry) -> None:
        """Internal store method using an active connection/transaction."""
        cursor = conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO provenance VALUES (
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                ?, ?, ?, ?, ?, ?, ?, ?, ?
            )
        """, (
            entry.entity_id,
            entry.entity_type,
            entry.activity_id,
            entry.agent_id,
            entry.source_document,
            entry.source_location,
            entry.source_quote,
            entry.timestamp,
            entry.first_seen,
            entry.last_updated,
            entry.confidence,
            entry.checksum,
            entry.parent_entity_id,
            json.dumps(entry.used_entities),
            entry.start_index,
            entry.end_index,
            entry.credibility,
            json.dumps(entry.metadata),
            entry.version,
            entry.agent_type,
            1 if entry.is_automated else 0,
            entry.role,
            entry.sequence_id,
            entry.previous_checksum,
            entry.previous_version_id,
            entry.derived_from_id,
            1 if entry.invalidated else 0,
            entry.invalidated_at_time,
            entry.invalidated_by,
            entry.invalidation_reason,
            entry.activity_started_at_time,
            entry.activity_ended_at_time,
            entry.acted_on_behalf_of,
            json.dumps(entry.informed_by_activities),
            entry.valid_from,
            entry.valid_until,
            entry.revision_type,
            entry.supersedes,
            entry.bundle_id,
        ))
    
    def retrieve(self, entity_id: str) -> Optional[ProvenanceEntry]:
        """
        Retrieve a provenance entry by entity ID.
        
        Args:
            entity_id: Entity identifier
            
        Returns:
            ProvenanceEntry if found, None otherwise
        """
        with self._read_connection() as conn:
            return self._retrieve_with_conn(conn, entity_id)

    def _retrieve_with_conn(self, conn: sqlite3.Connection, entity_id: str) -> Optional[ProvenanceEntry]:
        """Internal retrieve method using an active connection/transaction."""
        cursor = conn.cursor()
        cursor.execute("""
            SELECT * FROM provenance WHERE entity_id = ?
        """, (entity_id,))
        
        row = cursor.fetchone()
        if not row:
            return None
        
        return self._row_to_entry(row)
    
    def retrieve_all(self, entity_type: Optional[str] = None) -> List[ProvenanceEntry]:
        """
        Retrieve all provenance entries, optionally filtered by type.
        
        Args:
            entity_type: Optional entity type filter
            
        Returns:
            List of ProvenanceEntry objects
        """
        conn = sqlite3.connect(self.db_path)
        try:
            self._configure_connection(conn)
            self._ensure_schema(conn)
            cursor = conn.cursor()
            if entity_type:
                cursor.execute("""
                    SELECT * FROM provenance WHERE entity_type = ?
                """, (entity_type,))
            else:
                cursor.execute("SELECT * FROM provenance")
            
            rows = cursor.fetchall()
            return [self._row_to_entry(row) for row in rows]
        finally:
            conn.close()
    
    def trace_lineage(self, entity_id: str, max_depth: Optional[int] = None) -> List[ProvenanceEntry]:
        """
        Trace complete lineage using batched BFS traversal (#807).
        
        Fetches frontiers in batched IN (...) queries chunked by 999 variables
        to stay safely within SQLite limits, while preserving exact BFS order,
        visited tracking, and optional max_depth semantics.
        
        Args:
            entity_id: Entity identifier
            max_depth: Optional maximum BFS depth
            
        Returns:
            List of ProvenanceEntry objects in lineage chain
        """
        lineage = []
        visited = set()
        frontier = [entity_id]
        depth = 0
        
        with self._read_connection() as conn:
            cursor = conn.cursor()
            while frontier and (max_depth is None or depth < max_depth):
                # Remove duplicates while preserving order, and filter out already visited IDs
                current_frontier = [id_ for id_ in dict.fromkeys(frontier) if id_ not in visited]
                if not current_frontier:
                    break
                
                visited.update(current_frontier)
                
                # Fetch all entries in current frontier using batched IN queries chunked by 999
                entries_map = {}
                for i in range(0, len(current_frontier), 999):
                    chunk = current_frontier[i : i + 999]
                    placeholders = ",".join("?" * len(chunk))
                    cursor.execute(f"""
                        SELECT * FROM provenance WHERE entity_id IN ({placeholders})
                    """, chunk)
                    for row in cursor.fetchall():
                        entry = self._row_to_entry(row)
                        entries_map[entry.entity_id] = entry
                
                # Append entries in exact BFS order and build next frontier
                next_frontier = []
                for current_id in current_frontier:
                    entry = entries_map.get(current_id)
                    if not entry:
                        continue
                    lineage.append(entry)
                    
                    if entry.parent_entity_id and entry.parent_entity_id not in visited:
                        next_frontier.append(entry.parent_entity_id)
                    for used_id in entry.used_entities:
                        if used_id not in visited:
                            next_frontier.append(used_id)
                
                frontier = next_frontier
                depth += 1

        return lineage

    def get_chain_head(self, conn: Any = None) -> Optional[Tuple[int, str]]:
        """Return (sequence_id, checksum) of the most recently stored entry.

        Reuses the caller's transaction connection when given, so the head
        read and the subsequent insert happen atomically under the existing
        BEGIN IMMEDIATE writer lock (issue #825, Part A item 2).
        """
        # Tie-break on rowid (SQLite's implicit row-order column) in addition
        # to sequence_id: during track_entity's archival, the just-relabeled
        # history row briefly shares its sequence_id with the still-present
        # (about-to-be-overwritten) live row it was copied from. rowid DESC
        # deterministically picks the most-recently-written row of the two,
        # which is the correct chain head — relying on sequence_id ordering
        # alone leaves the tie-break implementation-defined.
        query = (
            "SELECT sequence_id, checksum FROM provenance "
            "WHERE sequence_id IS NOT NULL "
            "ORDER BY sequence_id DESC, rowid DESC LIMIT 1"
        )
        if conn is not None:
            row = conn.cursor().execute(query).fetchone()
            return (row[0], row[1]) if row else None
        with self._read_connection() as read_conn:
            row = read_conn.cursor().execute(query).fetchone()
            return (row[0], row[1]) if row else None

    def trace_descendants(
        self, entity_id: str, max_depth: Optional[int] = None
    ) -> List[ProvenanceEntry]:
        """
        Trace downstream descendants (reverse lineage) using indexed lookups
        on parent_entity_id/previous_version_id/derived_from_id, plus an
        in-memory reverse index over used_entities (a JSON column, so not
        directly indexable in SQLite).

        Args:
            entity_id: Entity identifier to find descendants of
            max_depth: Optional maximum BFS depth

        Returns:
            List of ProvenanceEntry objects that (transitively) reference
            entity_id, in BFS order.
        """
        descendants: List[ProvenanceEntry] = []
        visited = {entity_id}
        frontier = [entity_id]
        depth = 0

        with self._read_connection() as conn:
            cursor = conn.cursor()

            cursor.execute(
                "SELECT entity_id, used_entities FROM provenance "
                "WHERE used_entities IS NOT NULL AND used_entities != '[]'"
            )
            used_reverse: Dict[str, List[str]] = {}
            for child_id, used_json in cursor.fetchall():
                try:
                    used_ids = json.loads(used_json) if used_json else []
                except (json.JSONDecodeError, TypeError):
                    used_ids = []
                for uid in used_ids:
                    used_reverse.setdefault(uid, []).append(child_id)

            while frontier and (max_depth is None or depth < max_depth):
                current_frontier = list(dict.fromkeys(frontier))
                if not current_frontier:
                    break

                child_ids = set()
                for i in range(0, len(current_frontier), 999):
                    chunk = current_frontier[i : i + 999]
                    placeholders = ",".join("?" * len(chunk))
                    cursor.execute(
                        f"""
                        SELECT entity_id FROM provenance
                        WHERE parent_entity_id IN ({placeholders})
                           OR previous_version_id IN ({placeholders})
                           OR derived_from_id IN ({placeholders})
                        """,
                        chunk * 3,
                    )
                    child_ids.update(row[0] for row in cursor.fetchall())

                for ref_id in current_frontier:
                    child_ids.update(used_reverse.get(ref_id, []))

                next_frontier = [cid for cid in child_ids if cid not in visited]
                if not next_frontier:
                    break
                visited.update(next_frontier)

                entries_map = {}
                for i in range(0, len(next_frontier), 999):
                    chunk = next_frontier[i : i + 999]
                    placeholders = ",".join("?" * len(chunk))
                    cursor.execute(
                        f"SELECT * FROM provenance WHERE entity_id IN ({placeholders})",
                        chunk,
                    )
                    for row in cursor.fetchall():
                        entry = self._row_to_entry(row)
                        entries_map[entry.entity_id] = entry

                for cid in next_frontier:
                    entry = entries_map.get(cid)
                    if entry:
                        descendants.append(entry)

                frontier = next_frontier
                depth += 1

        return descendants

    def clear(self) -> int:
        """
        Clear all provenance data.
        
        Returns:
            Number of entries cleared
        """
        conn = sqlite3.connect(self.db_path)
        try:
            self._configure_connection(conn)
            self._ensure_schema(conn)
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM provenance")
            count = cursor.fetchone()[0]
            
            cursor.execute("DELETE FROM provenance")
            conn.commit()
            
            return count
        finally:
            conn.close()
    
    def _row_to_entry(self, row: tuple) -> ProvenanceEntry:
        """
        Convert database row to ProvenanceEntry.
        
        Args:
            row: Database row tuple
            
        Returns:
            ProvenanceEntry object
        """
        return ProvenanceEntry(
            entity_id=row[0],
            entity_type=row[1],
            activity_id=row[2],
            agent_id=row[3],
            source_document=row[4] or "",
            source_location=row[5],
            source_quote=row[6],
            timestamp=row[7],
            first_seen=row[8],
            last_updated=row[9],
            confidence=row[10],
            checksum=row[11],
            parent_entity_id=row[12],
            used_entities=json.loads(row[13]) if row[13] else [],
            start_index=row[14],
            end_index=row[15],
            credibility=row[16],
            metadata=json.loads(row[17]) if row[17] else {},
            version=row[18],
            agent_type=row[19] or "software_agent",
            is_automated=bool(row[20]) if row[20] is not None else True,
            role=row[21],
            sequence_id=row[22],
            previous_checksum=row[23],
            previous_version_id=row[24],
            derived_from_id=row[25],
            invalidated=bool(row[26]) if row[26] is not None else False,
            invalidated_at_time=row[27],
            invalidated_by=row[28],
            invalidation_reason=row[29],
            activity_started_at_time=row[30],
            activity_ended_at_time=row[31],
            acted_on_behalf_of=row[32],
            informed_by_activities=json.loads(row[33]) if row[33] else [],
            valid_from=row[34],
            valid_until=row[35],
            revision_type=row[36],
            supersedes=row[37],
            bundle_id=row[38],
        )
