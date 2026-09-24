"""Public temporal adapter behavior, using real PR1 and temporal primitives."""

from copy import deepcopy
from dataclasses import FrozenInstanceError
from datetime import datetime, timezone

import pytest

from semantica import reasoning
from semantica.reasoning import FactSupport, Rule
from semantica.utils.exceptions import ProcessingError, ValidationError


def at(day):
    return datetime(2026, 9, day, tzinfo=timezone.utc)


def evidence(support_id="hr-v1", fact="Employed(Alice)", **temporal):
    return {
        "source": "alice",
        "target": "acme",
        "type": "EMPLOYED_BY",
        "valid_from": at(1),
        "valid_until": at(30),
        "recorded_at": at(1),
        "metadata": {
            "truth_maintenance": {"support_id": support_id, "fact": fact},
        },
        **temporal,
    }


def graph(*records):
    return {
        "entities": [{"id": "alice"}, {"id": "acme"}],
        "relationships": list(records),
    }


def adapter():
    return reasoning.TemporalTruthMaintenanceAdapter(
        rules=[Rule("eligibility", "Eligibility", ["Employed(?x)"], "Eligible(?x)")]
    )


def test_expiration_retracts_derived_facts_at_exclusive_end():
    managed = adapter()
    source = graph(evidence(valid_until=at(15)))
    original = deepcopy(source)
    delta = managed.sync(source, valid_at=at(14), known_at=at(14))
    assert delta.added_facts == frozenset({"Employed(Alice)", "Eligible(Alice)"})
    assert managed.explain("Eligible(Alice)").active

    delta = managed.advance(valid_at=at(15), known_at=at(15))
    assert delta.removed_supports == (FactSupport("hr-v1", "Employed(Alice)"),)
    assert delta.removed_facts == frozenset({"Employed(Alice)", "Eligible(Alice)"})
    assert managed.facts == frozenset()
    assert managed.graph_revision == 1
    assert source == original


def test_late_correction_distinguishes_valid_time_from_known_time():
    managed = adapter()
    old = evidence()
    managed.sync(graph(old), valid_at=at(15), known_at=at(15))
    corrected = graph(
        {**old, "superseded_at": at(20)},
        evidence("hr-v2", valid_until=at(10), recorded_at=at(20)),
    )
    delta = managed.sync(corrected, valid_at=at(15), known_at=at(20))
    assert delta.removed_facts == frozenset({"Employed(Alice)", "Eligible(Alice)"})
    live_state = (managed.facts, managed.version, managed.valid_at, managed.known_at)

    then = managed.query_at(valid_at=at(15), known_at=at(15))
    hindsight = managed.query_at(valid_at=at(15), known_at=at(20))
    assert then.facts == frozenset({"Employed(Alice)", "Eligible(Alice)"})
    assert then.explain("Eligible(Alice)").derivations[0].premises == (
        "Employed(Alice)",
    )
    assert then.active_supports == (FactSupport("hr-v1", "Employed(Alice)"),)
    assert hindsight.facts == frozenset()
    assert not hindsight.explain("Eligible(Alice)").active
    assert then.graph_revision == hindsight.graph_revision == 2
    assert live_state == (
        managed.facts,
        managed.version,
        managed.valid_at,
        managed.known_at,
    )


def test_source_replacement_is_one_batch_without_fact_churn():
    managed = adapter()
    source = graph(
        evidence(superseded_at=at(20)),
        evidence("hr-v2", recorded_at=at(20)),
    )
    managed.sync(source, valid_at=at(10), known_at=at(19))
    previous_version = managed.version
    delta = managed.advance(valid_at=at(10), known_at=at(20))
    assert not delta.added_facts and not delta.removed_facts
    assert delta.removed_supports == (FactSupport("hr-v1", "Employed(Alice)"),)
    assert delta.added_supports == (FactSupport("hr-v2", "Employed(Alice)"),)
    assert managed.version == previous_version + 1
    assert managed.explain("Employed(Alice)").explicit_support_ids == ("hr-v2",)


def test_an_independent_source_preserves_conclusion_until_both_expire():
    managed = adapter()
    managed.sync(
        graph(evidence(valid_until=at(10)), evidence("other", valid_until=at(20))),
        valid_at=at(9),
        known_at=at(9),
    )
    delta = managed.advance(valid_at=at(10), known_at=at(10))
    assert not delta.removed_facts
    assert managed.explain("Employed(Alice)").explicit_support_ids == ("other",)
    managed.advance(valid_at=at(20), known_at=at(20))
    assert not managed.facts


def state(managed):
    return (
        managed.facts,
        managed.version,
        managed.graph_revision,
        managed.valid_at,
        managed.known_at,
        managed.query_at(valid_at=at(10), known_at=at(10)),
    )


@pytest.mark.parametrize(
    "change",
    [
        "drop",
        "fact",
        "start",
        "end",
        "recorded",
        "source",
        "relation",
        "entity",
    ],
)
def test_existing_evidence_cannot_be_erased_or_rewritten(change):
    managed = adapter()
    source = graph(evidence())
    managed.sync(source, valid_at=at(10), known_at=at(10))
    before = state(managed)
    revised = deepcopy(source)
    record = revised["relationships"][0]
    if change == "drop":
        revised["relationships"] = []
    elif change == "fact":
        record["metadata"]["truth_maintenance"]["fact"] = "Employed(Bob)"
    elif change == "start":
        record["valid_from"] = at(2)
    elif change == "end":
        record["valid_until"] = at(12)
    elif change == "recorded":
        record["recorded_at"] = at(2)
    elif change == "source":
        record["source"] = "acme"
    elif change == "relation":
        record["type"] = "OTHER"
    elif change == "entity":
        revised["entities"] = []
    with pytest.raises(ValidationError):
        managed.sync(revised, valid_at=at(20), known_at=at(20))
    assert state(managed) == before


def test_closed_transaction_interval_cannot_be_reopened():
    managed = adapter()
    source = graph(evidence(superseded_at=at(20)))
    managed.sync(source, valid_at=at(10), known_at=at(21))
    with pytest.raises(ValidationError):
        managed.sync(graph(evidence()), valid_at=at(10), known_at=at(21))
    assert not managed.facts
    assert managed.query_at(valid_at=at(10), known_at=at(19)).facts


def test_inactive_records_are_checked_for_rule_arity_and_for_each_other():
    for rules, records in [
        ([Rule("r", "r", ["A(?x)"], "B(?x)")], [evidence(fact="A(x, y)")]),
        ([], [evidence(fact="A(x)"), evidence("other", "A(x, y)")]),
    ]:
        managed = reasoning.TemporalTruthMaintenanceAdapter(rules=rules)
        with pytest.raises(ValidationError):
            managed.sync(graph(*records), valid_at=at(1), known_at="2020-01-01")
        assert managed.graph_revision == managed.version == 0


@pytest.mark.parametrize(
    "field,value",
    [
        ("recorded_at", None),
        ("recorded_at", True),
        ("recorded_at", "not-a-date"),
        ("valid_until", at(1)),
        ("valid_until", "2026-08-01"),
        ("superseded_at", at(1)),
        ("valid_from", False),
        ("valid_until", float("nan")),
    ],
)
def test_invalid_time_in_inactive_evidence_does_not_publish(field, value):
    managed = adapter()
    with pytest.raises(ValidationError):
        managed.sync(
            graph(evidence(**{field: value})), valid_at=at(1), known_at="2020-01-01"
        )
    assert managed.version == managed.graph_revision == 0
    assert managed.valid_at is managed.known_at is None


@pytest.mark.parametrize(
    "bad_graph",
    [
        None,
        [],
        {"entities": None},
        {"relationships": "rows"},
        graph(evidence(), evidence()),
        {"entities": [{"id": "a"}, {"id": "a"}]},
        {"entities": [{"id": "missing"}], "relationships": [evidence()]},
        graph({**evidence(), "metadata": {"truth_maintenance": None}}),
        graph(evidence(fact="Employed(?x)")),
        graph(evidence(support_id=" ")),
    ],
)
def test_malformed_graph_is_rejected_without_losing_live_state(bad_graph):
    managed = adapter()
    managed.sync(graph(evidence()), valid_at=at(10), known_at=at(10))
    before = state(managed)
    with pytest.raises(ValidationError):
        managed.sync(bad_graph, valid_at=at(11), known_at=at(11))
    assert state(managed) == before


def test_endpoint_expiry_retracts_support_even_when_edge_is_still_valid():
    managed = adapter()
    source = graph(evidence())
    source["entities"][0]["valid_until"] = at(12)
    managed.sync(source, valid_at=at(11), known_at=at(11))
    assert managed.facts
    managed.advance(valid_at=at(12), known_at=at(12))
    assert not managed.facts
    assert managed.query_at(valid_at=at(11), known_at=at(15)).facts


def test_endpoint_known_time_is_also_required():
    managed = adapter()
    source = graph(evidence())
    source["entities"][1]["recorded_at"] = at(10)
    managed.sync(source, valid_at=at(11), known_at=at(9))
    assert not managed.facts
    managed.advance(valid_at=at(11), known_at=at(10))
    assert managed.facts


def test_full_precision_and_timezone_normalization_at_boundary():
    managed = adapter()
    start = "2026-09-10T08:00:00.000001+08:00"
    end = "2026-09-10T00:00:00.000003Z"
    managed.sync(
        graph(evidence(valid_from=start, valid_until=end)),
        valid_at=start,
        known_at=at(10),
    )
    assert managed.valid_at == at(10).replace(microsecond=1)
    managed.advance(valid_at=at(10).replace(microsecond=2), known_at=at(10))
    assert managed.facts
    managed.advance(valid_at=end, known_at=at(10))
    assert not managed.facts


def test_rules_input_graph_and_historical_results_are_detached():
    rule = Rule("r", "r", ["Employed(?x)"], "Eligible(?x)")
    managed = reasoning.TemporalTruthMaintenanceAdapter(rules=iter([rule]))
    source = graph(evidence())
    managed.sync(source, valid_at=at(10), known_at=at(10))
    snapshot = managed.query_at(valid_at=at(10), known_at=at(10))
    source["relationships"][0]["metadata"]["truth_maintenance"]["fact"] = "Changed(x)"
    rule.conclusion = "Changed(?x)"
    managed.advance(valid_at=at(30), known_at=at(30))
    assert snapshot.facts == frozenset({"Employed(Alice)", "Eligible(Alice)"})
    assert managed.query_at(valid_at=at(10), known_at=at(10)) == snapshot
    with pytest.raises(FrozenInstanceError):
        snapshot.active_supports[0].fact = "Changed(x)"


def test_source_revision_changes_without_live_support_version_change():
    managed = adapter()
    original = evidence()
    managed.sync(graph(original), valid_at=at(10), known_at=at(10))
    before = managed.version
    delta = managed.sync(
        graph(original, evidence("future", recorded_at=at(20))),
        valid_at=at(11),
        known_at=at(11),
    )
    assert managed.version == before
    assert managed.graph_revision == 2
    assert not delta.added_facts and not delta.added_supports
    assert managed.valid_at == managed.known_at == at(11)
    managed.sync(
        graph(original, evidence("future", recorded_at=at(20))),
        valid_at=at(11),
        known_at=at(11),
    )
    assert managed.graph_revision == 2


def test_failed_reasoning_batch_rolls_back_projection_clocks_and_history(monkeypatch):
    managed = adapter()
    source = graph(evidence())
    managed.sync(source, valid_at=at(10), known_at=at(10))
    before = state(managed)

    def fail_match(*args):
        raise RuntimeError("injected matcher failure")

    with monkeypatch.context() as patch:
        patch.setattr(managed._session, "_match_rule", fail_match)
        with pytest.raises(ProcessingError):
            managed.sync(
                graph(evidence(), evidence("bob", "Employed(Bob)")),
                valid_at=at(11),
                known_at=at(11),
            )
    assert state(managed) == before
    managed.sync(
        graph(evidence(), evidence("bob", "Employed(Bob)")),
        valid_at=at(11),
        known_at=at(11),
    )
    assert "Eligible(Bob)" in managed.facts


def test_unannotated_edges_are_not_automatically_promoted_to_facts():
    managed = adapter()
    managed.sync(
        graph({"source": "alice", "target": "acme", "type": "EMPLOYED_BY"}),
        valid_at=at(10),
        known_at=at(10),
    )
    assert not managed.facts


def test_relationship_only_graph_and_canonical_fact_are_supported():
    managed = adapter()
    managed.sync(
        {"relationships": [evidence(fact=" Employed( Alice ) ")]},
        valid_at=at(10),
        known_at=at(10),
    )
    assert managed.explain("Employed(Alice)").explicit_support_ids == ("hr-v1",)


@pytest.mark.parametrize("value", [None, True, "bad-time"])
def test_invalid_query_coordinates_cannot_move_live_state(value):
    managed = adapter()
    managed.sync(graph(evidence()), valid_at=at(10), known_at=at(10))
    before = state(managed)
    with pytest.raises(ValidationError):
        managed.advance(valid_at=value, known_at=at(10))
    with pytest.raises(ValidationError):
        managed.query_at(valid_at=at(10), known_at=value)
    assert state(managed) == before


def test_adding_endpoint_lifetimes_cannot_reinterpret_relationship_only_history():
    managed = adapter()
    managed.sync({"relationships": [evidence()]}, valid_at=at(10), known_at=at(10))
    revised = graph(evidence())
    revised["entities"][0]["valid_until"] = at(5)
    with pytest.raises(ValidationError):
        managed.sync(revised, valid_at=at(10), known_at=at(10))
    assert managed.query_at(valid_at=at(10), known_at=at(10)).facts


@pytest.mark.parametrize("rules", [None, 1, "A(x)"])
def test_invalid_rule_iterable_raises_validation_error(rules):
    with pytest.raises(ValidationError):
        reasoning.TemporalTruthMaintenanceAdapter(rules=rules)


def test_advancing_backward_reactivates_original_source_without_losing_history():
    managed = adapter()
    managed.sync(graph(evidence(valid_until=at(10))), valid_at=at(9), known_at=at(9))
    managed.advance(valid_at=at(10), known_at=at(10))
    delta = managed.advance(valid_at=at(9), known_at=at(9))
    assert delta.added_supports == (FactSupport("hr-v1", "Employed(Alice)"),)
    assert managed.graph_revision == 1


def test_empty_history_has_no_implicit_wall_clock_or_facts():
    managed = adapter()
    snapshot = managed.query_at(valid_at=at(1), known_at=at(1))
    assert not snapshot.facts and not snapshot.active_supports
    assert managed.valid_at is managed.known_at is None
    assert managed.version == managed.graph_revision == 0
