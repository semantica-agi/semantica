"""Persistence signals must describe actual SQLite writes, including retries."""

import sqlite3
from contextlib import contextmanager

import pytest

from semantica.provenance import ProvenanceManager
from semantica.provenance.bridge_axiom import BridgeAxiom, ProvenanceRecordingError


@pytest.fixture
def manager(tmp_path):
    return ProvenanceManager(storage_path=str(tmp_path / "synthetic.db"))


@pytest.fixture
def axiom():
    return BridgeAxiom("A1", "synthetic", "r", 2.0, "10.1/synthetic", "p1")


def rows(manager):
    """Read committed rows through a fresh connection, outside the manager."""
    with sqlite3.connect(manager.storage.db_path) as conn:
        return conn.execute("SELECT * FROM provenance ORDER BY entity_id").fetchall()


def reject_writes(manager, entity_id):
    """Let archival writes execute, but reject the requested current row."""
    with sqlite3.connect(manager.storage.db_path) as conn:
        conn.execute(
            "CREATE TRIGGER reject_current BEFORE INSERT ON provenance "
            f"WHEN NEW.entity_id = '{entity_id}' "
            "BEGIN SELECT RAISE(ABORT, 'synthetic private storage detail'); END"
        )


@pytest.mark.parametrize("require_provenance", [True, False])
@pytest.mark.parametrize("initial_value", [None, 3, 5])
def test_bridge_rejected_write(manager, axiom, initial_value, require_provenance):
    """New, identical, and changed retries all follow required/best-effort policy."""
    if initial_value is not None:
        axiom.apply("in", initial_value, prov_manager=manager)
    before = rows(manager)
    reject_writes(manager, "in_transformed_A1")

    if require_provenance:
        with pytest.raises(ProvenanceRecordingError) as caught:
            axiom.apply("in", 3, prov_manager=manager)
        assert caught.value.error_code == "SEM007"
        assert caught.value.entity_id == "in_transformed_A1"
        assert isinstance(caught.value.__cause__, sqlite3.IntegrityError)
        assert "IntegrityError" in str(caught.value)
        assert "private storage detail" not in str(caught.value)
    else:
        result = axiom.apply("in", 3, prov_manager=manager, require_provenance=False)
        assert result["output_value"] == 6.0
        assert result["provenance_recorded"] is False
        assert result["provenance_error"] == "IntegrityError"

    assert rows(manager) == before
    assert manager.verify_chain()["valid"] is True


@pytest.mark.parametrize("require_provenance", [True, False])
@pytest.mark.parametrize("existing", [True, False], ids=["stale", "none"])
def test_legacy_manager_override_failure(manager, axiom, existing, require_provenance):
    """Older overrides may accept but ignore the new strict option."""

    class BestEffortSubclass(ProvenanceManager):
        def track_entity(self, *args, **kwargs):
            kwargs.pop("raise_on_error", None)
            return super().track_entity(*args, **kwargs)

    subclass = BestEffortSubclass(storage=manager.storage)
    if existing:
        axiom.apply("in", 5, prov_manager=subclass)
    before = rows(manager)
    reject_writes(manager, "in_transformed_A1")

    if require_provenance:
        with pytest.raises(ProvenanceRecordingError, match="did not persist") as caught:
            axiom.apply("in", 3, prov_manager=subclass)
        assert caught.value.__cause__ is None
    else:
        result = axiom.apply("in", 3, prov_manager=subclass, require_provenance=False)
        assert result["output_value"] == 6.0
        assert result["provenance_recorded"] is False
        assert "did not persist" in result["provenance_error"]
        assert "private storage detail" not in result["provenance_error"]
    assert rows(manager) == before
    assert manager.verify_chain()["valid"] is True


@pytest.mark.parametrize("strict", [True, False])
@pytest.mark.parametrize("initial_metadata", [None, {"value": 3}, {"value": 5}])
def test_manager_rejected_write(manager, strict, initial_metadata):
    if initial_metadata is not None:
        manager.track_entity("entity", "doc", metadata=initial_metadata)
    previous = manager.storage.retrieve("entity")
    before = rows(manager)
    reject_writes(manager, "entity")
    options = {"raise_on_error": True} if strict else {}

    if strict:
        with pytest.raises(sqlite3.IntegrityError, match="private storage detail"):
            manager.track_entity("entity", "doc", {"value": 3}, **options)
    else:
        fallback = manager.track_entity("entity", "doc", {"value": 3})
        assert fallback == previous
        if fallback is not None:
            fallback.metadata["value"] = "changed locally"
            assert manager.storage.retrieve("entity") == previous

    assert rows(manager) == before
    assert manager.verify_chain()["valid"] is True


@pytest.mark.parametrize("strict", [True, False])
@pytest.mark.parametrize("initial_metadata", [None, {"value": 3}, {"value": 5}])
def test_manager_success_is_persisted(manager, strict, initial_metadata):
    if initial_metadata is not None:
        manager.track_entity("entity", "doc", metadata=initial_metadata)
    previous = manager.storage.retrieve("entity")
    options = {"raise_on_error": True} if strict else {}

    recorded = manager.track_entity("entity", "doc", {"value": 3}, **options)

    reader = ProvenanceManager(storage_path=manager.storage.db_path)
    assert reader.storage.retrieve("entity") == recorded
    assert recorded.metadata == {"value": 3}
    assert "raise_on_error" not in recorded.metadata
    assert len(rows(manager)) == (2 if previous else 1)
    if previous is not None:
        history = reader.storage.retrieve(recorded.previous_version_id)
        assert history.metadata == previous.metadata
        assert history.last_updated == previous.last_updated
        assert history.checksum == previous.checksum
    assert reader.verify_chain()["valid"] is True


@pytest.mark.parametrize("initial_value", [None, 3, 5])
def test_bridge_success_is_persisted(manager, axiom, initial_value):
    if initial_value is not None:
        axiom.apply("in", initial_value, prov_manager=manager)

    result = axiom.apply("in", 3, prov_manager=manager)

    reader = ProvenanceManager(storage_path=manager.storage.db_path)
    recorded = reader.storage.retrieve(result["output_entity"])
    assert recorded.metadata["output_value"] == result["output_value"] == 6.0
    assert recorded.metadata["input_value"] == 3
    assert result["provenance_recorded"] is True
    assert result["provenance_error"] is None
    assert len(rows(manager)) == (1 if initial_value is None else 2)
    assert reader.verify_chain()["valid"] is True


@pytest.mark.parametrize("strict", [True, False])
def test_shared_transaction_always_propagates_failure(manager, strict):
    manager.track_entity("entity", "doc", {"value": 1})
    before = rows(manager)
    reject_writes(manager, "entity")
    options = {"raise_on_error": True} if strict else {}

    with pytest.raises(sqlite3.IntegrityError):
        with manager.storage.transaction() as conn:
            manager.track_entity("other", "doc", _conn=conn)
            manager.track_entity("entity", "doc", _conn=conn, **options)

    assert rows(manager) == before
    assert manager.verify_chain()["valid"] is True


def test_batch_failure_rolls_back_only_failed_item(manager):
    manager.track_entity("entity", "doc", {"value": 1})
    previous = manager.storage.retrieve("entity")
    reject_writes(manager, "entity")

    count = manager.track_entities_batch(
        [{"id": "before"}, {"id": "entity"}, {"id": "after"}], "doc"
    )

    assert count == 2
    assert manager.storage.retrieve("entity") == previous
    assert {entry.entity_id for entry in manager.storage.retrieve_all()} == {
        "entity",
        "before",
        "after",
    }
    assert len(rows(manager)) == 3
    assert manager.verify_chain()["valid"] is True


@pytest.mark.parametrize("strict", [True, False])
def test_exception_before_commit_rolls_back(manager, monkeypatch, strict):
    """Inject an exception after real writes, before the connection's commit."""
    manager.track_entity("entity", "doc", {"value": 1})
    previous = manager.storage.retrieve("entity")
    before = rows(manager)
    transaction = manager.storage.transaction
    error = sqlite3.OperationalError("synthetic exception before commit")

    @contextmanager
    def fail_before_commit():
        with transaction() as conn:
            yield conn
            raise error

    monkeypatch.setattr(manager.storage, "transaction", fail_before_commit)
    if strict:
        with pytest.raises(sqlite3.OperationalError) as caught:
            manager.track_entity("entity", "doc", raise_on_error=True)
        assert caught.value is error
    else:
        assert manager.track_entity("entity", "doc") == previous
    assert rows(manager) == before


@pytest.mark.parametrize("strict", [True, False])
@pytest.mark.parametrize("phase", ["begin", "retrieve", "archive"])
def test_transaction_failures(manager, monkeypatch, strict, phase):
    manager.track_entity("entity", "doc")
    previous = manager.storage.retrieve("entity")
    before = rows(manager)
    error = OSError("synthetic storage failure")

    def fail(*args, **kwargs):
        raise error

    method = {
        "begin": "transaction",
        "retrieve": "_retrieve_with_conn",
        "archive": "_store_with_conn",
    }[phase]
    with monkeypatch.context() as patch:
        patch.setattr(manager.storage, method, fail)
        if strict:
            with pytest.raises(OSError) as caught:
                manager.track_entity("entity", "doc", raise_on_error=True)
            assert caught.value is error
        else:
            fallback = manager.track_entity("entity", "doc")
            assert fallback == (previous if phase == "archive" else None)
    assert rows(manager) == before


@pytest.mark.parametrize("require_provenance", [True, False])
def test_legacy_duck_typed_manager(axiom, require_provenance):
    class LegacyManager:
        def __len__(self):
            return 0

        def track_entity(
            self,
            entity_id,
            source,
            entity_type,
            activity_id,
            source_location,
            source_quote,
            confidence,
            metadata,
        ):
            self.recorded = (entity_id, metadata)
            return None  # Legacy success contract, with no strict keyword.

    manager = LegacyManager()
    result = axiom.apply(
        "in", 3, prov_manager=manager, require_provenance=require_provenance
    )
    assert result["provenance_recorded"] is True
    assert result["provenance_error"] is None
    assert manager.recorded[0] == result["output_entity"]
    assert manager.recorded[1]["output_value"] == 6.0
