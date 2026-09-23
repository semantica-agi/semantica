"""Integration: annotated ``ContextGraph`` exports are accepted verbatim.

``ContextGraph.to_kg_dict()`` emits ``source_id``/``target_id`` and keeps
non valid-time bounds inside ``metadata`` (and ``properties`` for entities), so
these tests pin the adapter against the real export instead of hand-written
dictionaries only.
"""

from datetime import datetime, timezone

import pytest

from semantica.reasoning import Rule, TemporalTruthMaintenanceAdapter
from semantica.utils.exceptions import ValidationError

context_graph = pytest.importorskip("semantica.context.context_graph")
ContextGraph = context_graph.ContextGraph


def at(day, month=9):
    return datetime(2026, month, day, tzinfo=timezone.utc)


def adapter():
    return TemporalTruthMaintenanceAdapter(
        rules=[Rule("eligibility", "Eligibility", ["Employed(?x)"], "Eligible(?x)")]
    )


def exported(*, employer_recorded_at=at(1), valid_until=at(30)):
    graph = ContextGraph()
    graph.add_node(
        "alice", "Person", content="Alice", valid_from=at(1), recorded_at=at(1)
    )
    graph.add_node(
        "acme",
        "Company",
        content="Acme",
        valid_from=at(1),
        recorded_at=employer_recorded_at,
    )
    graph.add_edge(
        "alice",
        "acme",
        "EMPLOYED_BY",
        valid_from=at(1),
        valid_until=valid_until,
        recorded_at=at(1),
        truth_maintenance={"support_id": "hr-v1", "fact": "Employed(Alice)"},
    )
    return graph.to_kg_dict()


def test_export_uses_canonical_endpoint_keys_and_nested_bounds():
    record = exported()
    relationship = record["relationships"][0]
    entity = record["entities"][0]
    assert "source" not in relationship and relationship["source_id"] == "alice"
    assert "target" not in relationship and relationship["target_id"] == "acme"
    assert "recorded_at" not in relationship
    assert relationship["metadata"]["recorded_at"] == at(1)
    assert "recorded_at" not in entity
    assert entity["properties"]["recorded_at"] == at(1)


def test_exported_context_graph_can_sync_without_manual_rewriting():
    managed = adapter()
    managed.sync(exported(), valid_at=at(10), known_at=at(10))
    assert managed.facts == frozenset({"Employed(Alice)", "Eligible(Alice)"})
    assert managed.explain("Employed(Alice)").explicit_support_ids == ("hr-v1",)


def test_exported_relationship_expiry_retracts_derived_facts():
    managed = adapter()
    managed.sync(exported(), valid_at=at(10), known_at=at(10))
    managed.advance(valid_at=at(30), known_at=at(30))
    assert not managed.facts
    assert managed.query_at(valid_at=at(10), known_at=at(30)).facts


def test_exported_relationship_known_time_start_is_honoured():
    managed = adapter()
    managed.sync(exported(), valid_at=at(10), known_at=at(31, month=8))
    assert not managed.facts
    managed.advance(valid_at=at(10), known_at=at(1))
    assert managed.facts


def test_exported_endpoint_known_time_gates_selection_independently():
    managed = adapter()
    managed.sync(exported(employer_recorded_at=at(5)), valid_at=at(10), known_at=at(3))
    assert not managed.facts
    managed.advance(valid_at=at(10), known_at=at(5))
    assert managed.facts


def test_conflicting_endpoint_keys_are_rejected():
    record = exported()
    record["relationships"][0]["source"] = "bob"
    with pytest.raises(ValidationError, match="Conflicting source"):
        adapter().sync(record, valid_at=at(10), known_at=at(10))


def test_matching_duplicate_endpoint_keys_are_accepted():
    record = exported()
    record["relationships"][0]["source"] = "alice"
    managed = adapter()
    managed.sync(record, valid_at=at(10), known_at=at(10))
    assert managed.facts


def test_conflicting_duplicate_temporal_bounds_are_rejected():
    record = exported()
    record["relationships"][0]["recorded_at"] = at(2)
    with pytest.raises(ValidationError, match="Conflicting recorded_at"):
        adapter().sync(record, valid_at=at(10), known_at=at(10))


def test_matching_duplicate_temporal_bounds_are_accepted():
    record = exported()
    record["relationships"][0]["recorded_at"] = at(1)
    managed = adapter()
    managed.sync(record, valid_at=at(10), known_at=at(10))
    assert managed.facts
