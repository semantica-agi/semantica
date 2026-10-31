"""SQLite provenance schema migration: concurrent open and older writers (#2157)."""

import re
import sqlite3
import threading
import time
from unittest.mock import patch

from semantica.provenance.schemas import ProvenanceEntry
from semantica.provenance.storage import SQLiteStorage


def _entry(entity_id="e1"):
    return ProvenanceEntry(
        entity_id=entity_id,
        entity_type="entity",
        activity_id="extraction",
    )


def _columns(db_path):
    conn = sqlite3.connect(str(db_path))
    try:
        return {row[1] for row in conn.execute("PRAGMA table_info(provenance)")}
    finally:
        conn.close()


def _drop_column(db_path, column):
    conn = sqlite3.connect(str(db_path))
    try:
        conn.execute(f"ALTER TABLE provenance DROP COLUMN {column}")
        conn.commit()
    finally:
        conn.close()


def _column_value(db_path, column, entity_id="e1"):
    conn = sqlite3.connect(str(db_path))
    try:
        row = conn.execute(
            f"SELECT {column} FROM provenance WHERE entity_id = ?", (entity_id,)
        ).fetchone()
    finally:
        conn.close()
    return row[0] if row else None


class TestConcurrentMigration:
    def test_a_second_opener_waits_then_finds_the_column(self, tmp_path):
        """Two opens of an older DB: the second must not hit duplicate column."""
        db_path = tmp_path / "prov.db"
        SQLiteStorage(str(db_path))
        _drop_column(db_path, "supersedes")

        # Stand in for the first opener: take the write lock and add the
        # column, so an opener that starts now sees it as still missing.
        holder = sqlite3.connect(str(db_path))
        holder.execute("BEGIN IMMEDIATE")
        holder.execute("ALTER TABLE provenance ADD COLUMN supersedes TEXT")

        result = {}
        entered = threading.Event()
        original_migrate = SQLiteStorage._migrate_schema

        def migrate_and_notify(storage, conn):
            # Signal only after the unlocked read has happened, so the holder
            # commits while the opener is between that read and the lock.
            missing = storage._missing_columns(conn.cursor())
            entered.set()
            if not missing:
                return None
            return original_migrate(storage, conn)

        def open_storage():
            try:
                with patch.object(
                    SQLiteStorage, "_migrate_schema", migrate_and_notify
                ):
                    SQLiteStorage(str(db_path))
                result["error"] = None
            except Exception as error:  # reported through the assertion below
                result["error"] = error

        opener = threading.Thread(target=open_storage)
        opener.start()
        # Commit only once the opener has reached the migration, and then give
        # it a moment to get to the ALTER it is going to try. Without the lock
        # in _migrate_schema that ALTER is still blocked when the column lands,
        # so it fails with a duplicate; with the lock the opener never gets
        # that far.
        assert entered.wait(timeout=30)
        time.sleep(0.2)
        holder.commit()
        holder.close()
        opener.join(timeout=30)

        assert not opener.is_alive()
        assert result["error"] is None
        assert "supersedes" in _columns(db_path)

    def test_opening_an_up_to_date_database_twice_changes_nothing(self, tmp_path):
        db_path = tmp_path / "prov.db"
        SQLiteStorage(str(db_path))
        before = _columns(db_path)

        second = SQLiteStorage(str(db_path))
        second.store(_entry())

        assert _columns(db_path) == before
        assert second.retrieve("e1") is not None

    def test_opening_a_migrated_database_does_not_wait_for_a_write_lock(self, tmp_path):
        """An open that has nothing to migrate must not queue behind a writer."""
        db_path = tmp_path / "prov.db"
        SQLiteStorage(str(db_path))

        holder = sqlite3.connect(str(db_path))
        holder.execute("BEGIN IMMEDIATE")
        try:
            started = time.monotonic()
            SQLiteStorage(str(db_path))
            elapsed = time.monotonic() - started
        finally:
            holder.commit()
            holder.close()

        assert elapsed < 1.5


class TestOlderWriterOnMigratedTable:
    def test_an_extra_trailing_column_does_not_break_writes(self, tmp_path):
        """A table migrated by a later release has one more column than this
        release's positional INSERT supplied values for."""
        db_path = tmp_path / "prov.db"
        storage = SQLiteStorage(str(db_path))
        conn = sqlite3.connect(str(db_path))
        try:
            conn.execute("ALTER TABLE provenance ADD COLUMN future_column TEXT")
            conn.commit()
        finally:
            conn.close()

        storage.store(_entry())

        retrieved = storage.retrieve("e1")
        assert retrieved is not None
        assert retrieved.entity_type == "entity"

    def test_storing_again_keeps_the_extra_column(self, tmp_path):
        db_path = tmp_path / "prov.db"
        storage = SQLiteStorage(str(db_path))
        storage.store(_entry())
        conn = sqlite3.connect(str(db_path))
        try:
            conn.execute("ALTER TABLE provenance ADD COLUMN future_column TEXT")
            conn.execute(
                "UPDATE provenance SET future_column = 'kept' WHERE entity_id = 'e1'"
            )
            conn.commit()
        finally:
            conn.close()

        updated = _entry()
        updated.confidence = 0.5
        storage.store(updated)

        retrieved = storage.retrieve("e1")
        assert retrieved is not None
        assert retrieved.confidence == 0.5
        # REPLACE deletes the row and inserts it again, which would blank a
        # column this release does not know about.
        assert _column_value(db_path, "future_column") == "kept"


class TestUpsertColumnAlignment:
    """The INSERT column list and the ON CONFLICT ... DO UPDATE SET list are
    written out by hand next to a table defined somewhere else. A column
    dropped from the SET half still stores fine and still reads back — with
    the old value, silently. Nothing else in the suite notices, so check the
    three lists against the table here."""

    def test_the_upsert_lists_match_the_table(self, tmp_path, monkeypatch):
        statements = []
        real_connect = sqlite3.connect

        def connect(*args, **kwargs):
            conn = real_connect(*args, **kwargs)
            conn.set_trace_callback(statements.append)
            return conn

        monkeypatch.setattr(sqlite3, "connect", connect)
        db_path = tmp_path / "prov.db"
        storage = SQLiteStorage(str(db_path))
        storage.store(_entry())

        upsert = "INSERT INTO provenance"
        upserts = [s for s in statements if s.lstrip().startswith(upsert)]
        assert len(upserts) == 1, f"expected one upsert, got {len(upserts)}"
        sql = " ".join(upserts[0].split())

        insert_columns = sql[sql.index("(") + 1 : sql.index(") VALUES")]
        insert_columns = [column.strip() for column in insert_columns.split(",")]
        separator = ") VALUES ("
        values = sql[sql.index(separator) + len(separator) : sql.index(") ON CONFLICT")]
        set_columns = re.findall(r"(\w+) = excluded\.\w+", sql)

        table_columns = _columns(db_path)
        placeholders = len(values.split(","))
        assert placeholders == len(insert_columns), "one placeholder per column"
        assert set(insert_columns) == table_columns, "INSERT names every table column"
        assert len(insert_columns) == len(table_columns), "INSERT names a column twice"
        expected_set = [c for c in insert_columns if c != "entity_id"]
        assert set_columns == expected_set, "SET must update every column but entity_id"
