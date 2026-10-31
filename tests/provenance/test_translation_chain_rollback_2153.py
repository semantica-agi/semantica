"""Translation chain provenance rollback (#2153)."""

from typing import Optional

import pytest

from semantica.provenance import ProvenanceManager
from semantica.provenance.bridge_axiom import BridgeAxiom, create_translation_chain
from semantica.provenance.schemas import ProvenanceEntry
from semantica.provenance.storage import ProvenanceStorage
from semantica.utils.exceptions import ProvenanceRecordingError


def _axiom(axiom_id, coefficient=2.0):
    return BridgeAxiom(
        axiom_id=axiom_id,
        name=axiom_id,
        rule="r",
        coefficient=coefficient,
        source_doi="10.1/x",
        source_page="p1",
    )


def _input(entity_id="e1", value=3):
    return {"entity_id": entity_id, "value": value, "source": "doc"}


def _fail_second_step(manager):
    """Make the second track_entity call raise, the way a full disk would."""
    real_track = manager.track_entity
    calls = {"n": 0}

    def track(**kwargs):
        calls["n"] += 1
        if calls["n"] == 2:
            raise IOError("disk full")
        return real_track(**kwargs)

    manager.track_entity = track


def test_sqlite_chain_rolls_back_the_steps_before_the_failure(tmp_path):
    manager = ProvenanceManager(storage_path=str(tmp_path / "prov.db"))
    _fail_second_step(manager)

    with pytest.raises(ProvenanceRecordingError):
        create_translation_chain(_input(), [_axiom("A1"), _axiom("A2")], manager)

    assert manager.storage.retrieve("e1_transformed_A1") is None
    assert manager.storage.retrieve("e1_transformed_A1_transformed_A2") is None


def test_in_memory_chain_rolls_back_the_steps_before_the_failure():
    manager = ProvenanceManager()
    _fail_second_step(manager)

    with pytest.raises(ProvenanceRecordingError):
        create_translation_chain(_input(), [_axiom("A1"), _axiom("A2")], manager)

    assert manager.storage.retrieve("e1_transformed_A1") is None


class _NoTransactionStorage(ProvenanceStorage):
    """A backend that keeps the base transaction(), which cannot roll back."""

    def __init__(self, fail_on_store_call=None):
        self._entries = {}
        self._store_calls = 0
        self._fail_on_store_call = fail_on_store_call

    def store(self, entry):
        self._store_calls += 1
        if (
            self._fail_on_store_call is not None
            and self._store_calls >= self._fail_on_store_call
        ):
            raise IOError("disk full")
        self._entries[entry.entity_id] = entry

    def retrieve(self, entity_id):
        return self._entries.get(entity_id)

    def retrieve_all(self, entity_type: Optional[str] = None):
        if entity_type:
            return [e for e in self._entries.values() if e.entity_type == entity_type]
        return list(self._entries.values())

    def trace_lineage(self, entity_id: str, max_depth: Optional[int] = None):
        entry = self.retrieve(entity_id)
        return [entry] if entry else []

    def clear(self):
        count = len(self._entries)
        self._entries.clear()
        return count


def test_backend_without_transactions_reports_what_was_recorded():
    storage = _NoTransactionStorage(fail_on_store_call=2)
    manager = ProvenanceManager(storage=storage)

    with pytest.raises(ProvenanceRecordingError) as info:
        create_translation_chain(_input(), [_axiom("A1"), _axiom("A2")], manager)

    assert info.value.recorded_entities == ["e1_transformed_A1"]
    assert storage.retrieve("e1_transformed_A1") is not None


def test_best_effort_chain_reports_the_failed_step(tmp_path):
    manager = ProvenanceManager(storage_path=str(tmp_path / "prov.db"))
    _fail_second_step(manager)

    chain = create_translation_chain(
        _input(), [_axiom("A1"), _axiom("A2")], manager, require_provenance=False
    )

    assert len(chain.layers) == 4
    failed = [
        layer
        for layer in chain.layers
        if layer["type"] == "bridge_axiom" and not layer["provenance_recorded"]
    ]
    assert [layer["axiom_id"] for layer in failed] == ["A2"]
    assert chain.metadata["provenance_failures"][0]["axiom_id"] == "A2"
    assert manager.storage.retrieve("e1_transformed_A1") is not None
    assert manager.storage.retrieve("e1_transformed_A1_transformed_A2") is None


def test_successful_chain_keeps_the_hash_chain_contiguous(tmp_path):
    manager = ProvenanceManager(storage_path=str(tmp_path / "prov.db"))

    create_translation_chain(_input(), [_axiom("A1"), _axiom("A2")], manager)

    assert manager.storage.retrieve("e1_transformed_A1") is not None
    assert manager.storage.retrieve("e1_transformed_A1_transformed_A2") is not None
    assert manager.verify_chain()["valid"] is True


class _LegacyManager:
    """A duck-typed manager with an explicit signature and no **kwargs."""

    def __init__(self):
        self.entries = {}

    def track_entity(
        self,
        entity_id,
        source=None,
        entity_type=None,
        activity_id=None,
        source_location=None,
        source_quote=None,
        confidence=None,
        metadata=None,
    ):
        entry = ProvenanceEntry(
            entity_id=entity_id,
            entity_type=entity_type,
            activity_id=activity_id or "",
            metadata=metadata or {},
        )
        self.entries[entity_id] = entry
        return entry


def test_a_manager_with_an_explicit_signature_still_records():
    legacy = _LegacyManager()

    result = _axiom("A1").apply(input_entity="e1", input_value=3, prov_manager=legacy)

    assert result["provenance_recorded"] is True
    assert "e1_transformed_A1" in legacy.entries


def test_a_manager_with_an_explicit_signature_runs_a_chain():
    legacy = _LegacyManager()

    chain = create_translation_chain(_input(), [_axiom("A1"), _axiom("A2")], legacy)

    assert len(chain.layers) == 4
    assert chain.layers[-1]["value"] == 3 * 2.0 * 2.0
