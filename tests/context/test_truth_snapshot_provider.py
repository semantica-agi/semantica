"""Immutable read views captured from real PR1 sessions and PR3 adapters.

These tests pin the capture contract used by grounded context assembly: one
view identifies exactly one committed reading of the truth state, and the
provider can later tell whether that reading is still the current one.
"""

from dataclasses import FrozenInstanceError
from datetime import datetime, timezone

import pytest
from semantica.context import TruthSnapshotProvider
from semantica.reasoning import (
    FactSupport,
    Rule,
    TemporalTruthMaintenanceAdapter,
    TruthMaintenanceSession,
)
from semantica.utils.exceptions import ProcessingError, ValidationError

NAMESPACE = "rag-test"


def at(day):
    return datetime(2026, 9, day, tzinfo=timezone.utc)


def rules():
    return [Rule("eligibility", "Eligibility", ["Employed(?x)"], "Eligible(?x)")]


def supported_session():
    session = TruthMaintenanceSession(rules=[])
    session.apply(assertions=[FactSupport("s1", "A(x)")])
    return session


def temporal_graph(*extra):
    return {
        "entities": [{"id": "alice"}, {"id": "acme"}],
        "relationships": [
            {
                "source": "alice",
                "target": "acme",
                "type": "EMPLOYED_BY",
                "valid_from": at(1),
                "valid_until": at(30),
                "recorded_at": at(1),
                "metadata": {
                    "truth_maintenance": {
                        "support_id": "hr-v1",
                        "fact": "Employed(Alice)",
                    }
                },
            },
            *extra,
        ],
    }


def future_record():
    return {
        "source": "alice",
        "target": "acme",
        "type": "PROMOTED_TO",
        "valid_from": at(25),
        "valid_until": at(30),
        "recorded_at": at(25),
        "metadata": {
            "truth_maintenance": {"support_id": "hr-v2", "fact": "Senior(Alice)"}
        },
    }


def synced_adapter():
    managed = TemporalTruthMaintenanceAdapter(rules=rules())
    managed.sync(temporal_graph(), valid_at=at(15), known_at=at(15))
    return managed


def live_state(managed):
    return (
        managed.facts,
        managed.version,
        managed.graph_revision,
        managed.valid_at,
        managed.known_at,
    )


# -- session views ---------------------------------------------------------


def test_session_view_is_detached_and_detects_later_change():
    session = supported_session()
    provider = TruthSnapshotProvider(session, namespace=NAMESPACE)

    view = provider.capture()
    provider.assert_current(view)
    session.apply(retractions=["s1"])

    assert view.facts == frozenset({"A(x)"})
    assert view.stamp.version == 1
    assert session.facts == frozenset()
    with pytest.raises(ProcessingError):
        provider.assert_current(view)


def test_session_stamp_leaves_temporal_coordinates_unset():
    provider = TruthSnapshotProvider(supported_session(), namespace=NAMESPACE)

    view = provider.capture()

    assert view.stamp.namespace == NAMESPACE
    assert view.stamp.source_kind == "session"
    assert view.stamp.graph_revision is None
    assert view.stamp.valid_at is None
    assert view.stamp.known_at is None
    assert view.read_kind == "live"
    assert view.active_supports == (FactSupport("s1", "A(x)"),)


def test_view_is_frozen():
    provider = TruthSnapshotProvider(supported_session(), namespace=NAMESPACE)

    view = provider.capture()

    with pytest.raises(FrozenInstanceError):
        view.read_kind = "historical"
    with pytest.raises(FrozenInstanceError):
        view.stamp.version = 99


@pytest.mark.parametrize(
    "coordinates",
    [
        {"valid_at": at(15)},
        {"known_at": at(15)},
        {"valid_at": at(15), "known_at": at(15)},
    ],
)
def test_session_capture_rejects_temporal_coordinates(coordinates):
    provider = TruthSnapshotProvider(supported_session(), namespace=NAMESPACE)

    with pytest.raises(ValidationError):
        provider.capture(**coordinates)


@pytest.mark.parametrize("namespace", ["", "  ", " rag", "rag ", 7, None])
def test_namespace_must_be_a_trimmed_nonempty_word(namespace):
    with pytest.raises(ValidationError):
        TruthSnapshotProvider(supported_session(), namespace=namespace)


@pytest.mark.parametrize("source", [object(), None, "session", supported_session])
def test_source_must_be_a_supported_truth_source(source):
    with pytest.raises(ValidationError):
        TruthSnapshotProvider(source, namespace=NAMESPACE)


# -- temporal views --------------------------------------------------------


def test_uninitialized_adapter_cannot_be_captured():
    managed = TemporalTruthMaintenanceAdapter(rules=rules())
    provider = TruthSnapshotProvider(managed, namespace=NAMESPACE)

    with pytest.raises(ValidationError):
        managed.snapshot()
    with pytest.raises(ValidationError):
        provider.capture()


def test_temporal_capture_matches_query_at_without_moving_state():
    managed = synced_adapter()
    provider = TruthSnapshotProvider(managed, namespace=NAMESPACE)
    before = live_state(managed)

    view = provider.capture()
    expected = managed.query_at(valid_at=at(15), known_at=at(15))

    assert view.facts == expected.facts
    assert view.facts == frozenset({"Employed(Alice)", "Eligible(Alice)"})
    assert view.active_supports == expected.active_supports
    assert view.stamp.source_kind == "temporal"
    assert view.stamp.version is None
    assert view.stamp.graph_revision == 1
    assert view.stamp.valid_at == at(15)
    assert view.stamp.known_at == at(15)
    assert view.read_kind == "live"
    assert live_state(managed) == before


def test_capture_reuses_the_live_session_instead_of_reasoning_again(monkeypatch):
    managed = synced_adapter()
    provider = TruthSnapshotProvider(managed, namespace=NAMESPACE)

    def forbidden(*args, **kwargs):
        raise AssertionError("capturing the current view must not re-derive facts")

    monkeypatch.setattr(
        "semantica.reasoning.temporal_truth_maintenance.TruthMaintenanceSession",
        forbidden,
    )

    view = provider.capture()

    assert view.facts == frozenset({"Employed(Alice)", "Eligible(Alice)"})


def test_live_temporal_view_detects_cursor_movement():
    managed = synced_adapter()
    provider = TruthSnapshotProvider(managed, namespace=NAMESPACE)
    live = provider.capture()

    managed.advance(valid_at=at(20), known_at=at(20))

    assert managed.facts == live.facts
    assert live.stamp.version is None
    assert managed.graph_revision == live.stamp.graph_revision
    with pytest.raises(ProcessingError):
        provider.assert_current(live)


def test_historical_view_ignores_live_cursor_movement():
    managed = synced_adapter()
    provider = TruthSnapshotProvider(managed, namespace=NAMESPACE)
    historical = provider.capture(valid_at=at(15), known_at=at(15))

    managed.advance(valid_at=at(20), known_at=at(20))

    provider.assert_current(historical)
    assert historical.read_kind == "historical"
    assert historical.stamp.version is None
    assert historical.stamp.valid_at == at(15)
    assert historical.stamp.known_at == at(15)


def test_future_evidence_moves_graph_revision_without_moving_version():
    managed = synced_adapter()
    provider = TruthSnapshotProvider(managed, namespace=NAMESPACE)
    live = provider.capture()
    historical = provider.capture(valid_at=at(15), known_at=at(15))

    managed.sync(temporal_graph(future_record()), valid_at=at(15), known_at=at(15))

    assert managed.facts == live.facts
    assert managed.version == 1
    assert managed.graph_revision == 2
    assert live.stamp.graph_revision == historical.stamp.graph_revision == 1
    with pytest.raises(ProcessingError):
        provider.assert_current(live)
    with pytest.raises(ProcessingError):
        provider.assert_current(historical)


@pytest.mark.parametrize("coordinates", [{"valid_at": at(15)}, {"known_at": at(15)}])
def test_one_temporal_coordinate_is_never_enough(coordinates):
    provider = TruthSnapshotProvider(synced_adapter(), namespace=NAMESPACE)

    with pytest.raises(ValidationError):
        provider.capture(**coordinates)


@pytest.mark.parametrize("shared_source", [False, True])
@pytest.mark.parametrize("read_kind", ["session", "live", "historical"])
def test_assert_current_rejects_other_provider_with_matching_counters(
    shared_source, read_kind
):
    factory = supported_session if read_kind == "session" else synced_adapter
    source = factory()
    other_source = source if shared_source else factory()
    provider = TruthSnapshotProvider(source, namespace=NAMESPACE)
    other = TruthSnapshotProvider(other_source, namespace=NAMESPACE)
    coordinates = (
        {"valid_at": at(15), "known_at": at(15)}
        if read_kind == "historical"
        else {}
    )
    view = provider.capture(**coordinates)
    foreign = other.capture(**coordinates)
    assert view.facts == foreign.facts
    assert view.stamp.version == foreign.stamp.version
    assert view.stamp.graph_revision == foreign.stamp.graph_revision
    assert view.stamp.valid_at == foreign.stamp.valid_at
    assert view.stamp.known_at == foreign.stamp.known_at
    provider.assert_current(view)
    other.assert_current(foreign)
    with pytest.raises(ValidationError, match="provider"):
        provider.assert_current(foreign)
    with pytest.raises(ValidationError, match="provider"):
        other.assert_current(view)


def test_assert_current_rejects_foreign_views():
    session_provider = TruthSnapshotProvider(supported_session(), namespace=NAMESPACE)
    temporal_provider = TruthSnapshotProvider(synced_adapter(), namespace=NAMESPACE)
    renamed = TruthSnapshotProvider(supported_session(), namespace="other-namespace")
    view = session_provider.capture()

    with pytest.raises(ValidationError):
        temporal_provider.assert_current(view)
    with pytest.raises(ValidationError):
        renamed.assert_current(view)
    with pytest.raises(ValidationError):
        session_provider.assert_current("not-a-read-view")


@pytest.mark.parametrize("fact", ["NOT AN ATOM", "P(?x)", "P(a,,b)", 42])
@pytest.mark.parametrize("target", ["dependencies", "view"])
def test_fact_entry_points_reject_invalid_or_non_ground_atoms(fact, target):
    from semantica.context.grounded_context_types import (
        ContextDependencies,
        ContextReadView,
        SnapshotStamp,
    )

    with pytest.raises(ValidationError):
        if target == "dependencies":
            ContextDependencies(required_facts=[fact])
        else:
            ContextReadView(
                stamp=SnapshotStamp(NAMESPACE, "session", version=0),
                read_kind="live",
                facts=[fact],
                active_supports=(),
            )


def test_fact_entry_points_canonicalize_whitespace_and_deduplicate():
    from semantica.context.grounded_context_types import (
        ContextDependencies,
        ContextReadView,
        SnapshotStamp,
    )

    facts = ["  P( a , b )  ", "P(a,b)"]
    dependencies = ContextDependencies(
        required_facts=facts, required_support_ids=["source:revision-1"]
    )
    view = ContextReadView(
        stamp=SnapshotStamp(NAMESPACE, "session", version=0),
        read_kind="live",
        facts=facts,
        active_supports=(),
    )
    assert dependencies.required_facts == view.facts == frozenset({"P(a, b)"})
    assert dependencies.required_support_ids == frozenset({"source:revision-1"})
    with pytest.raises(FrozenInstanceError):
        view.facts = frozenset()


@pytest.mark.parametrize("offset_hours", [8, -5, 0])
def test_temporal_stamp_normalizes_both_coordinates_to_utc(offset_hours):
    from datetime import timedelta

    from semantica.context.grounded_context_types import SnapshotStamp

    zone = timezone(timedelta(hours=offset_hours))
    valid = datetime(2026, 9, 15, 10, tzinfo=zone)
    known = datetime(2026, 9, 20, 12, tzinfo=zone)
    stamp = SnapshotStamp(
        NAMESPACE, "temporal", graph_revision=1, valid_at=valid, known_at=known
    )
    assert stamp.valid_at.tzinfo is timezone.utc
    assert stamp.known_at.tzinfo is timezone.utc
    assert stamp.valid_at == datetime(2026, 9, 15, 10, tzinfo=timezone.utc) - timedelta(
        hours=offset_hours
    )
    assert stamp.known_at == datetime(2026, 9, 20, 12, tzinfo=timezone.utc) - timedelta(
        hours=offset_hours
    )
    with pytest.raises(FrozenInstanceError):
        stamp.valid_at = valid


@pytest.mark.parametrize("field", ["valid_at", "known_at"])
def test_temporal_stamp_rejects_naive_coordinates(field):
    from semantica.context.grounded_context_types import SnapshotStamp

    coordinates = {"valid_at": at(15), "known_at": at(20)}
    coordinates[field] = datetime(2026, 9, 15)
    with pytest.raises(ValidationError, match="timezone aware"):
        SnapshotStamp(NAMESPACE, "temporal", graph_revision=1, **coordinates)
