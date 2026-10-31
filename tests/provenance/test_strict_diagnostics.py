"""Strict tracking retains internal diagnostics without exposing payloads."""

import logging
import sqlite3
from contextlib import contextmanager

import pytest

from semantica.provenance import ProvenanceManager
from semantica.provenance.bridge_axiom import BridgeAxiom, ProvenanceRecordingError


@pytest.fixture
def manager(tmp_path):
    return ProvenanceManager(storage_path=str(tmp_path / "synthetic.db"))


def rows(manager):
    with sqlite3.connect(manager.storage.db_path) as conn:
        return conn.execute("SELECT * FROM provenance ORDER BY entity_id").fetchall()


def inject_failure(manager, monkeypatch, phase):
    error = sqlite3.OperationalError("synthetic internal diagnostic")

    def fail(*args, **kwargs):
        raise error

    if phase == "checksum":
        monkeypatch.setattr("semantica.provenance.manager.compute_checksum", fail)
    elif phase == "before_commit":
        transaction = manager.storage.transaction

        @contextmanager
        def fail_before_commit():
            with transaction() as conn:
                yield conn
                raise error

        monkeypatch.setattr(manager.storage, "transaction", fail_before_commit)
    else:
        method = {
            "begin": "transaction",
            "retrieve": "_retrieve_with_conn",
            "archive": "_store_with_conn",
            "store": "_store_with_conn",
        }[phase]
        monkeypatch.setattr(manager.storage, method, fail)
    return error


def diagnostics(caplog, manager):
    return [
        record
        for record in caplog.records
        if record.name == manager.logger.name and record.levelno >= logging.ERROR
    ]


@pytest.mark.parametrize(
    "phase", ["begin", "retrieve", "archive", "checksum", "store", "before_commit"]
)
@pytest.mark.parametrize("required", [True, False])
def test_bridge_strict_failure_logs_once_and_redacts_payloads(
    manager, monkeypatch, caplog, phase, required
):
    axiom = BridgeAxiom(
        "diagnostics",
        "synthetic",
        "r",
        2.0,
        "10.1/synthetic",
        "p1",
        source_quote="SYNTHETIC_QUOTE_CANARY",
    )
    if phase != "store":
        axiom.apply("input", 3, prov_manager=manager)
    before = rows(manager)
    error = inject_failure(manager, monkeypatch, phase)
    caplog.clear()

    with caplog.at_level(logging.ERROR, logger=manager.logger.name):
        if required:
            with pytest.raises(ProvenanceRecordingError) as caught:
                axiom.apply(
                    "input",
                    3,
                    prov_manager=manager,
                    payload="SYNTHETIC_PAYLOAD_CANARY",
                    api_key="SYNTHETIC_CREDENTIAL_CANARY",
                )
            public_error = str(caught.value)
            assert caught.value.__cause__ is error
        else:
            result = axiom.apply(
                "input",
                3,
                prov_manager=manager,
                require_provenance=False,
                payload="SYNTHETIC_PAYLOAD_CANARY",
                api_key="SYNTHETIC_CREDENTIAL_CANARY",
            )
            assert result["provenance_recorded"] is False
            public_error = result["provenance_error"]
            assert public_error == "OperationalError"

    records = diagnostics(caplog, manager)
    assert len(records) == 1
    assert records[0].exc_info[1] is error
    assert "synthetic internal diagnostic" in caplog.text
    assert "OperationalError" in public_error
    assert "synthetic internal diagnostic" not in public_error
    for canary in (
        "SYNTHETIC_PAYLOAD_CANARY",
        "SYNTHETIC_CREDENTIAL_CANARY",
        "SYNTHETIC_QUOTE_CANARY",
    ):
        assert canary not in public_error
        assert canary not in caplog.text
    assert rows(manager) == before
    assert manager.verify_chain()["valid"] is True


@pytest.mark.parametrize("strict", [True, False])
@pytest.mark.parametrize(
    "phase", ["begin", "retrieve", "checksum", "store", "before_commit"]
)
def test_manager_owned_logging_preserves_default_contract(
    manager, monkeypatch, caplog, strict, phase
):
    before = rows(manager)
    error = inject_failure(manager, monkeypatch, phase)
    caplog.clear()
    with caplog.at_level(logging.ERROR, logger=manager.logger.name):
        if strict:
            with pytest.raises(sqlite3.OperationalError) as caught:
                manager.track_entity("entity", "synthetic", raise_on_error=True)
            assert caught.value is error
        else:
            assert manager.track_entity("entity", "synthetic") is None
    records = diagnostics(caplog, manager)
    # Default store errors already log at both save and tracking boundaries.
    assert len(records) == (2 if phase == "store" and not strict else 1)
    assert all(record.exc_info[1] is error for record in records)
    assert rows(manager) == before


@pytest.mark.parametrize("strict", [True, False])
@pytest.mark.parametrize("phase", ["retrieve", "store"])
def test_shared_transaction_logging_is_unchanged(
    manager, monkeypatch, caplog, strict, phase
):
    before = rows(manager)
    error = inject_failure(manager, monkeypatch, phase)
    caplog.clear()
    with caplog.at_level(logging.ERROR, logger=manager.logger.name):
        with pytest.raises(sqlite3.OperationalError) as caught:
            with manager.storage.transaction() as conn:
                manager.track_entity(
                    "entity", "synthetic", _conn=conn, raise_on_error=strict
                )
    assert caught.value is error
    assert len(diagnostics(caplog, manager)) == (1 if phase == "store" else 0)
    assert rows(manager) == before


@pytest.mark.parametrize("caller", ["manager", "bridge_required", "bridge_best_effort"])
def test_diagnostic_handler_failure_preserves_tracking_error(
    manager, monkeypatch, caplog, caller
):
    class FailingHandler(logging.Handler):
        attempts = 0

        def emit(self, record):
            self.attempts += 1
            raise RuntimeError("synthetic diagnostic handler failure")

    handler = FailingHandler()
    monkeypatch.setattr(manager.logger, "handlers", [handler])
    error = inject_failure(manager, monkeypatch, "retrieve")
    before = rows(manager)
    axiom = BridgeAxiom("handler", "synthetic", "r", 2.0, "10.1/synthetic", "p1")
    with caplog.at_level(logging.ERROR, logger=manager.logger.name):
        if caller == "manager":
            with pytest.raises(sqlite3.OperationalError) as caught:
                manager.track_entity("entity", "synthetic", raise_on_error=True)
            assert caught.value is error
        elif caller == "bridge_required":
            with pytest.raises(ProvenanceRecordingError) as caught:
                axiom.apply("input", 3, prov_manager=manager)
            assert caught.value.__cause__ is error
        else:
            result = axiom.apply(
                "input", 3, prov_manager=manager, require_provenance=False
            )
            assert result["provenance_recorded"] is False
            assert result["provenance_error"] == "OperationalError"
    assert handler.attempts == 1
    assert rows(manager) == before


@pytest.mark.parametrize("required", [True, False])
def test_explicit_old_subclass_signature_requires_migration(manager, required):
    class LegacySubclass(ProvenanceManager):
        calls = 0

        def track_entity(
            self,
            entity_id,
            source,
            metadata=None,
            *,
            entity_type="entity",
            activity_id=None,
            source_location=None,
            source_quote=None,
            confidence=1.0,
        ):
            self.calls += 1
            return super().track_entity(
                entity_id,
                source,
                metadata,
                entity_type=entity_type,
                activity_id=activity_id,
                source_location=source_location,
                source_quote=source_quote,
                confidence=confidence,
            )

    subclass = LegacySubclass(storage=manager.storage)
    assert (
        subclass.track_entity("control", "synthetic", activity_id="control") is not None
    )
    before = rows(manager)
    axiom = BridgeAxiom("migration", "synthetic", "r", 2.0, "10.1/synthetic", "p1")
    if required:
        with pytest.raises(ProvenanceRecordingError) as caught:
            axiom.apply("input", 3, prov_manager=subclass)
        assert isinstance(caught.value.__cause__, TypeError)
    else:
        result = axiom.apply(
            "input", 3, prov_manager=subclass, require_provenance=False
        )
        assert result["provenance_recorded"] is False
        assert result["provenance_error"] == "TypeError"
    assert subclass.calls == 1  # No retry or silent legacy fallback.
    assert rows(manager) == before
